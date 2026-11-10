from pathlib import Path

import pytest
import yaml

from scripts.review_pull_request import main


def test_pr_review_uses_only_trusted_manual_code_and_separates_write_token():
    path = Path(".github/workflows/pr-review.yml")
    text = path.read_text()
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    analyze, publish = workflow["jobs"]["analyze"], workflow["jobs"]["publish"]
    assert analyze["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert publish["permissions"] == {
        "contents": "read",
        "actions": "read",
        "pull-requests": "write",
        "checks": "write",
    }
    assert publish["needs"] == "analyze"
    assert "id-token" not in text and "secrets." not in text
    assert "google-github-actions/" not in text and "pull_request_target" not in text
    assert "workflow_run" not in text and "github.event.pull_request.head" not in text
    assert "${{ inputs.pull_number }}" not in "\n".join(
        step.get("run", "") for job in (analyze, publish) for step in job["steps"]
    )
    for job in (analyze, publish):
        assert "refs/heads/main" in job["if"] and "workflow_dispatch" in job["if"]
        checkout = job["steps"][0]
        assert checkout["with"]["ref"] == "${{ github.sha }}"
        assert checkout["with"]["persist-credentials"] == "false"


@pytest.mark.parametrize(
    "event,ref",
    [("pull_request", "refs/heads/main"), ("workflow_dispatch", "refs/heads/untrusted")],
)
def test_cli_rejects_untrusted_context_without_discovering_a_token(monkeypatch, capsys, event, ref):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["review_pull_request.py", "prepare", "--pull-number", "7"])
    assert main() == 1
    assert "failed" in capsys.readouterr().out
