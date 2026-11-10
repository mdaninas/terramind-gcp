import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest

from terramind.errors import InputError
from terramind.integrations.github import (
    MARKER,
    GitHubClient,
    NoRedirect,
    PullRequestReview,
    prepare_review,
    publish_review,
    review_markdown,
)

REPOSITORY = "synthetic/terramind"


class FakeGitHub:
    def __init__(self, raw=None):
        raw = raw or Path("examples/normalized-plans/public_bucket.json").read_bytes()
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        self.pr = {
            "number": 7,
            "state": "open",
            "changed_files": 1,
            "base": {"ref": "main", "sha": "a" * 40, "repo": {"id": 123, "full_name": REPOSITORY}},
            "head": {"sha": "b" * 40, "repo": {"full_name": "contributor/fork"}},
        }
        self.files = [
            {
                "filename": "examples/normalized-plans/public_bucket.json",
                "status": "modified",
                "sha": sha,
            }
        ]
        self.blob = {
            "encoding": "base64",
            "size": len(raw),
            "sha": sha,
            "content": base64.b64encode(raw).decode(),
        }
        self.comments = []
        self.calls = []
        self.change_on_second_read = False
        self.reads = 0

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method != "GET":
            return {"id": 10}
        if path.endswith("/pulls/7"):
            self.reads += 1
            if self.change_on_second_read and self.reads == 2:
                self.pr["head"]["sha"] = "c" * 40
            return copy.deepcopy(self.pr)
        if "/compare/" in path:
            assert path.endswith("a" * 40 + "...contributor:" + "b" * 40)
            return {"files": self.files}
        if "/git/blobs/" in path:
            assert path.startswith("/repos/contributor/fork/git/blobs/")
            return self.blob
        if "/comments?" in path:
            return self.comments
        raise AssertionError(path)


def prepare(client):
    return prepare_review(client, REPOSITORY, 123, 7)


def publish(client, review):
    publish_review(client, review, repository=REPOSITORY, repository_id=123, run_id="12345")


def test_fork_fixture_is_read_as_blob_without_execution_or_cloud():
    client = FakeGitHub()
    result = prepare(client)
    assert result.plans[0].findings == 1
    assert result.plans[0].rules == ("TM-GCP-001",)
    assert all(method == "GET" for method, _, _ in client.calls)
    text = review_markdown(result)
    assert "synthetic" in text and "not evaluated" in text
    assert "roles/storage.objectViewer" not in text
    assert "allUsers" not in text
    assert PullRequestReview.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("change", ["closed", "other-base", "other-repo", "many-files", "bad-sha"])
def test_review_rejects_wrong_target_or_unbounded_metadata(change):
    client = FakeGitHub()
    if change == "closed":
        client.pr["state"] = "closed"
    elif change == "other-base":
        client.pr["base"]["ref"] = "untrusted"
    elif change == "other-repo":
        client.pr["base"]["repo"]["id"] = 999
    elif change == "many-files":
        client.pr["changed_files"] = 101
    else:
        client.pr["head"]["sha"] = "$(echo invalid)"
    with pytest.raises(InputError):
        prepare(client)
    assert not any("/git/blobs/" in path for _, path, _ in client.calls)


@pytest.mark.parametrize("change", ["hash", "size", "encoding", "base64", "incomplete-files"])
def test_untrusted_blob_integrity_is_checked(change):
    client = FakeGitHub()
    if change == "hash":
        client.blob["sha"] = "c" * 40
    elif change == "size":
        client.blob["size"] = 300000
    elif change == "encoding":
        client.blob["encoding"] = "raw"
    elif change == "base64":
        client.blob["content"] = "invalid!"
    else:
        client.files = []
    with pytest.raises(InputError):
        prepare(client)


@pytest.mark.parametrize("change", ["raw-plan", "local-source", "extra-field", "duplicate-key"])
def test_privacy_boundary_rejects_unsupported_fixture_data(change):
    payload = json.loads(Path("examples/normalized-plans/public_bucket.json").read_text())
    if change == "raw-plan":
        payload = {"resource_changes": []}
    elif change == "local-source":
        payload["source"] = "local-normalizer"
    elif change == "extra-field":
        payload["credentials"] = "synthetic-private-content"
    raw = json.dumps(payload).encode()
    if change == "duplicate-key":
        raw = b'{"source":"synthetic-demo","source":"local-normalizer"}'
    with pytest.raises(InputError):
        prepare(FakeGitHub(raw))


@pytest.mark.parametrize(
    "path",
    [
        "terraform/main.tf",
        "examples/normalized-plans/../secrets.json",
        "examples/normalized-plans/mention@everyone.json",
    ],
)
def test_noneligible_paths_are_not_fetched_and_do_not_imply_a_clean_plan(path):
    client = FakeGitHub()
    client.files[0]["filename"] = path
    result = prepare(client)
    assert not result.plans
    assert "no analysis was performed" in review_markdown(result)
    assert not any("/git/blobs/" in path for _, path, _ in client.calls)


def test_changed_pr_during_analysis_is_rejected():
    client = FakeGitHub()
    client.change_on_second_read = True
    with pytest.raises(InputError, match="changed during"):
        prepare(client)


def test_stale_review_is_never_published():
    client = FakeGitHub()
    review = prepare(client)
    client.pr["head"]["sha"] = "d" * 40
    with pytest.raises(InputError, match="Stale"):
        publish(client, review)
    assert all(method == "GET" for method, _, _ in client.calls)


@pytest.mark.parametrize("bot", [True, False])
def test_only_owned_bot_comment_is_updated_and_check_is_neutral(bot):
    client = FakeGitHub()
    review = prepare(client)
    client.comments = [
        {
            "id": 81,
            "body": MARKER + "\nprevious",
            "user": {
                "login": "github-actions[bot]" if bot else "contributor",
                "type": "Bot" if bot else "User",
            },
        }
    ]
    publish(client, review)
    writes = [(method, path, body) for method, path, body in client.calls if method != "GET"]
    assert writes[0][0] == ("PATCH" if bot else "POST")
    assert writes[1][1].endswith("/check-runs")
    assert writes[1][2]["head_sha"] == review.head_sha
    assert writes[1][2]["conclusion"] == "neutral"


def test_wrong_repository_artifact_cannot_write():
    client = FakeGitHub()
    review = prepare(client).model_copy(update={"repository_id": 999})
    with pytest.raises(InputError, match="another repository"):
        publish(client, review)
    assert all(method == "GET" for method, _, _ in client.calls)


def test_api_client_never_follows_redirects_or_prints_provider_content(monkeypatch):
    class FailedOpener:
        def open(self, request, timeout):
            assert request.full_url == "https://api.github.com/repos/synthetic/terramind/pulls/7"
            assert timeout == 20
            raise RuntimeError("synthetic-private-provider-response")

    monkeypatch.setattr(
        "terramind.integrations.github.build_opener", lambda handler: FailedOpener()
    )
    client = GitHubClient("synthetic-token")
    with pytest.raises(InputError) as error:
        client.request("GET", "/repos/synthetic/terramind/pulls/7")
    assert "synthetic-private" not in str(error.value)
    assert "synthetic-token" not in repr(client)
    assert NoRedirect().redirect_request(None, None, 302, "", None, "https://other.invalid") is None
    with pytest.raises(InputError, match="API path"):
        client.request("GET", "https://other.invalid")
