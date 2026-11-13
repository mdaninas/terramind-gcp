"""Prepared operator checks exercise real application boundaries with local storage only."""

import copy
import json
import sys
from pathlib import Path
from threading import RLock

import pytest
from fastapi.testclient import TestClient

from scripts import check_promotion_plan, verify_ingestion_fence, verify_portal_access
from terramind.cloud.settings import CloudSettings
from terramind.incidents.search import IncidentSearcher
from terramind.portal.app import create_app
from terramind.portal.settings import PortalSettings
from terramind.portal.store import PortalAnalysis, PortalStore, owner_key
from terramind.reports.render import build_report
from terramind.schemas.normalized import NormalizedPlan
from tests.unit.test_eventarc_adapters import FakeCollection, FakeDocument, FakeFirestore


@pytest.fixture
def portal_probe():
    store = PortalStore(Path(":memory:"))
    sessions = [
        store.new_session(owner_key("demo", name), name) for name in ("analyst", "reviewer")
    ]
    reports = []
    for session, count in zip(sessions, (21, 1), strict=True):
        for _ in range(count):
            report = build_report(
                NormalizedPlan(schema_version="1.0", source="synthetic-demo", changes=())
            )
            store.save(
                session.owner,
                PortalAnalysis(report=report, incident_memory=IncidentSearcher().search(report)),
            )
        reports.append(report.analysis_id)
    app = create_app(PortalSettings(database=Path(":memory:")), store)
    with TestClient(app, base_url="http://127.0.0.1:8080", client=("127.0.0.1", 51001)) as client:

        def fetch(path, token):
            response = client.get(
                path,
                headers={"Cookie": f"terramind_session={token}"} if token else {},
                follow_redirects=False,
            )
            return response.status_code, response.content

        yield sessions, reports, fetch
    store.close()


def run_portal(fixture, fetch=None):
    sessions, reports, default = fixture
    return verify_portal_access.run(
        "http://127.0.0.1:8091",
        sessions[0].token,
        sessions[1].token,
        reports[0],
        reports[1],
        fetch=fetch or default,
    )


def test_prepared_portal_probe_paginates_and_checks_both_owners(portal_probe):
    result = run_portal(portal_probe)
    assert result["status"] == "passed"
    assert result["owner_a_pages"] == 2 and result["owner_b_pages"] == 1
    assert result["owner_a_reports"] == 21 and result["owner_b_reports"] == 1
    assert result["cross_owner_exports_rejected"]
    assert result["analysis_submissions"] == 0
    assert result["http_requests"] <= verify_portal_access.MAX_REQUESTS


@pytest.mark.parametrize("failure", ["cross-owner", "duplicate-page", "wrong-total", "exception"])
def test_portal_probe_fails_closed_without_exposing_sessions(portal_probe, failure):
    sessions, _, fetch = portal_probe

    def broken(path, token):
        if failure == "exception":
            raise RuntimeError("synthetic-private-error:" + sessions[0].token)
        status, body = fetch(path, token)
        if failure == "cross-owner" and status == 404:
            return 200, b"synthetic-private-body"
        if "/api/history?risk=" in path and token == sessions[0].token:
            data = json.loads(body)
            if failure == "wrong-total":
                data["totals"]["reports"] += 1
            elif failure == "duplicate-page" and "cursor=" in path:
                return fetch("/api/history?risk=NO_KNOWN_FINDINGS", token)
            body = json.dumps(data).encode()
        return status, body

    with pytest.raises(verify_portal_access.VerificationFailure) as error:
        run_portal(portal_probe, broken)
    public = json.dumps(error.value.summary)
    assert "synthetic-private" not in public
    assert not any(session.token in public for session in sessions)
    assert error.value.summary["analysis_submissions"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid",
        "http://127.0.0.1:8091@evil.invalid",
        "http://127.0.0.1:8091/path",
        "http://127.0.0.1:8091?token=private",
    ],
)
def test_session_tokens_cannot_be_sent_to_non_proxy_urls(portal_probe, url):
    sessions, reports, _ = portal_probe

    def forbidden(*_):
        raise AssertionError("Invalid configuration must not send a request")

    with pytest.raises(verify_portal_access.VerificationFailure) as error:
        verify_portal_access.run(
            url,
            sessions[0].token,
            sessions[1].token,
            *reports,
            fetch=forbidden,
        )
    assert error.value.summary["http_requests"] == 0


def plan():
    before = {
        "name": "terramind-portal",
        "project": "terramind-demo",
        "location": "us-central1",
        "ingress": "INGRESS_TRAFFIC_ALL",
        "invoker_iam_disabled": False,
        "template": [
            {
                "scaling": [{"min_instance_count": 0, "max_instance_count": 1}],
                "containers": [
                    {"image": "old-image", "env": [{"name": "AUTH", "value": "google"}]}
                ],
            }
        ],
    }
    after = copy.deepcopy(before)
    after["template"][0]["containers"][0]["image"] = IMAGE
    return {
        "resource_changes": [
            {
                "address": "google_cloud_run_v2_service.portal",
                "type": "google_cloud_run_v2_service",
                "mode": "managed",
                "change": {"actions": ["update"], "before": before, "after": after},
            }
        ]
    }


IMAGE = "us-central1-docker.pkg.dev/terramind-demo/terramind-dev/terramind@sha256:" + "a" * 64


def test_image_plan_guard_accepts_only_image_and_client_metadata_changes():
    value = plan()
    value["resource_changes"][0]["change"]["after"].update(client="terraform", etag="new")
    assert check_promotion_plan.check(value, "portal", "terramind-demo", IMAGE) == 1


@pytest.mark.parametrize(
    "failure", ["iam", "replace", "caps", "env", "unknown", "missing", "digest"]
)
def test_image_plan_guard_rejects_scope_expansion(failure):
    value = plan()
    row = value["resource_changes"][0]
    if failure == "iam":
        value["resource_changes"].append({"address": "iam", "change": {"actions": ["update"]}})
    elif failure == "replace":
        row["change"]["actions"] = ["delete", "create"]
    elif failure == "caps":
        row["change"]["after"]["template"][0]["scaling"][0]["max_instance_count"] = 10
    elif failure == "env":
        row["change"]["after"]["template"][0]["containers"][0]["env"] = []
    elif failure == "unknown":
        row["change"]["after_unknown"] = {"template": [{"scaling": True}]}
    elif failure == "missing":
        value["resource_changes"] = []
    else:
        row["change"]["after"]["template"][0]["containers"][0]["image"] = IMAGE[:-1] + "b"
    with pytest.raises(ValueError):
        check_promotion_plan.check(value, "portal", "terramind-demo", IMAGE)


class ProbeDocument(FakeDocument):
    def update(self, changes, **kwargs):
        self.client.data[self.path].update(changes)

    def delete(self, **kwargs):
        if self.client.fail_cleanup:
            raise RuntimeError("synthetic-private-cleanup-error")
        self.client.data.pop(self.path, None)


class ProbeCollection(FakeCollection):
    def document(self, key):
        return ProbeDocument(self.client, self.name, key)


class ProbeFirestore(FakeFirestore):
    def __init__(self):
        super().__init__()
        self.fail_cleanup = False
        self.guard = RLock()

    def collection(self, name):
        return ProbeCollection(self, name)


def probe_client(monkeypatch):
    def transactional(operation):
        def wrapped(transaction, **kwargs):
            with transaction.client.guard:
                result = operation(transaction, **kwargs)
                transaction.commit()
                return result

        return wrapped

    monkeypatch.setattr("terramind.events.google.firestore.transactional", transactional)
    return ProbeFirestore()


def test_fence_probe_uses_fresh_collections_and_preserves_runtime_data(monkeypatch):
    client = probe_client(monkeypatch)
    client.data["ingestion_control/corpus"] = {"owner": "runtime-owner"}
    client.data["knowledge_chunks/existing"] = {"synthetic": True}
    before = copy.deepcopy(client.data)
    result = verify_ingestion_fence.probe(client, CloudSettings(project_id="terramind-demo"))
    assert result["status"] == "passed" and result["stale_commit_fenced"]
    assert result["sandbox_cleanup_verified"] and client.data == before
    assert result["model_calls"] == 0 and result["staged_chunks"] == 0


def test_fence_probe_does_not_claim_success_if_cleanup_fails(monkeypatch):
    client = probe_client(monkeypatch)
    client.fail_cleanup = True
    result = verify_ingestion_fence.probe(client, CloudSettings(project_id="terramind-demo"))
    assert result["status"] == "failed" and result["stage"] == "cleanup"
    assert not result["sandbox_cleanup_verified"]


def test_default_fence_command_is_only_preparation(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_ingestion_fence.py",
            "--project",
            "terramind-demo",
            "--database",
            "terramind-dev",
        ],
    )

    def forbidden(*_, **__):
        raise AssertionError("Preparation must not create a cloud client")

    monkeypatch.setattr("google.cloud.firestore.Client", forbidden)
    assert verify_ingestion_fence.main() == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "prepared" and summary["mode"] == "no_cloud_calls"


def test_fence_probe_retains_only_its_owned_cleanup_manifest(monkeypatch, tmp_path):
    client = probe_client(monkeypatch)
    result = verify_ingestion_fence.probe(
        client,
        CloudSettings(project_id="terramind-demo"),
        manifest_directory=tmp_path,
    )
    assert result["status"] == "passed"
    manifests = list(tmp_path.glob("verification_*.json"))
    assert len(manifests) == 1
    refs = json.loads(manifests[0].read_text())["documents"]
    assert len(refs) == 3 and all(ref.startswith(manifests[0].stem) for ref in refs)
    assert not any(ref.startswith(("ingestion_", "knowledge_")) for ref in refs)
