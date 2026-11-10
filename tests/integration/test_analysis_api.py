import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from terramind.api.app import create_app, demo_plan
from terramind.api.service import AnalysisService, ApiSettings, cloud_analysis
from terramind.api.views import report_page
from terramind.cloud.budget import DependencyUnavailable
from terramind.cloud.settings import CloudSettings
from terramind.llm.service import explain
from terramind.reports.render import build_report
from terramind.reports.store import MemoryReportStore, StoredAnalysis
from terramind.schemas.normalized import MAX_REQUEST_BYTES, serialize_plan
from tests.knowledge_helpers import RecordingSynthesizer, local_system


def system(analyze=build_report, store=None, per_minute=6):
    store = store or MemoryReportStore()
    service = AnalysisService(ApiSettings(requests_per_minute=per_minute), store, analyze)
    return service, TestClient(create_app(service))


def post(client, plan=None):
    return client.post(
        "/v1/analyses",
        content=serialize_plan(plan or demo_plan()),
        headers={"Content-Type": "application/json"},
    )


def test_local_api_round_trip_without_network(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network call"))
    service, client = system()
    with client:
        response = post(client)
        assert response.status_code == 201
        report = response.json()
        expected = build_report(demo_plan())
        assert report["findings"] == expected.model_dump(mode="json")["findings"]
        assert report["overall_risk"] == "HIGH"
        assert report["model_id"] is None
        assert report["rag_status"] == "not_requested"
        location = response.headers["location"]
        assert client.get(location).json() == report
        download = client.get(location + "/markdown")
        assert download.status_code == 200
        assert download.headers["content-disposition"].startswith("attachment;")
        assert report["analysis_id"] in download.text
        view = client.get(location + "/view")
        assert view.status_code == 200
        assert "Download Markdown" in view.text
        assert "Offline mode" in view.text
        assert "TM-GCP-004" in view.text
        record = service.store.get(report["analysis_id"])
        assert 23 * 3600 < (record.expires_at - datetime.now(UTC)).total_seconds() <= 24 * 3600
        assert set(record.model_dump()) == {"analysis_id", "report_json", "source", "expires_at"}
        assert '"attributes"' not in record.report_json


@pytest.mark.parametrize("path", sorted(Path("examples/normalized-plans").glob("*.json")))
def test_api_preserves_every_packaged_fixture(path):
    service, client = system()
    with client:
        response = client.post(
            "/v1/analyses", content=path.read_bytes(), headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 201
        from terramind.normalizer.io import load_normalized

        expected = build_report(load_normalized(path.read_bytes())).model_dump(mode="json")
        assert response.json()["findings"] == expected["findings"]
        assert response.json()["overall_risk"] == expected["overall_risk"]


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b"[]",
        b"{}{}",
        b"\xff",
        b'{"x":NaN}',
        b'{"source":1,"source":2}',
        b'{"x":' + b"[" * 70 + b"0" + b"]" * 70 + b"}",
    ],
)
def test_invalid_json_is_400_and_private(body, caplog):
    service, client = system(lambda plan: pytest.fail("Invalid request analyzed"))
    with client:
        response = client.post(
            "/v1/analyses", content=body, headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid JSON object"}


@pytest.mark.parametrize("mutation", ["secret", "raw", "real", "alias", "many"])
def test_schema_and_synthetic_boundary(mutation, caplog):
    payload = json.loads(serialize_plan(demo_plan()))
    if mutation == "secret":
        payload["authorization"] = "synthetic-private-canary"
    elif mutation == "raw":
        payload = {"resource_changes": [], "outputs": {"value": "synthetic-private-canary"}}
    elif mutation == "real":
        payload["source"] = "local-normalizer"
    elif mutation == "alias":
        payload["changes"][0]["address"] = (
            "google_storage_bucket_iam_member.synthetic-private-canary"
        )
    else:
        payload["changes"] *= 26
    service, client = system(lambda plan: pytest.fail("Invalid request analyzed"))
    with client:
        response = client.post("/v1/analyses", json=payload)
    assert response.status_code == 422
    assert "synthetic-private-canary" not in response.text + caplog.text


@pytest.mark.parametrize("chunked", [False, True])
def test_actual_body_size_is_bounded(chunked):
    service, client = system(lambda plan: pytest.fail("Oversized request analyzed"))
    data = b" " * (MAX_REQUEST_BYTES + 1)
    with client:
        response = client.post(
            "/v1/analyses",
            content=iter([data[:100], data[100:]]) if chunked else data,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Content-Type": "text/plain"}, 415),
        ({"Content-Type": "application/json", "Content-Encoding": "gzip"}, 415),
        ({"Content-Type": "application/json", "Content-Length": "invalid"}, 400),
        ({"Content-Type": "application/json", "Content-Length": "99999999999999999"}, 413),
    ],
)
def test_transport_rejections(headers, status):
    service, client = system()
    with client:
        assert client.post("/v1/analyses", content=b"{}", headers=headers).status_code == status


def test_admission_limit_and_release_after_failure():
    service, client = system(per_minute=1)
    with client:
        assert post(client).status_code == 201
        rejected = post(client)
        assert rejected.status_code == 429
        assert rejected.headers["retry-after"] == "60"
    assert service.gate.busy is False
    service, client = system()
    with client, service.gate.enter():
        assert post(client).status_code == 429


def test_store_failure_never_claims_a_saved_report(caplog):
    class BrokenStore:
        def save(self, record):
            raise DependencyUnavailable("synthetic-private-canary")

        def get(self, analysis_id):
            raise DependencyUnavailable("synthetic-private-canary")

    service, client = system(store=BrokenStore())
    with client:
        response = post(client)
        assert response.status_code == 503
        assert client.get(f"/v1/analyses/{uuid4()}").status_code == 503
        assert client.get("/v1/analyses/not-an-id").status_code == 404
    assert service.gate.busy is False
    assert "synthetic-private-canary" not in response.text + caplog.text


def test_expired_reports_are_404_before_background_ttl_deletion():
    service, client = system()
    with client:
        response = post(client)
        key = response.json()["analysis_id"]
        record = service.store.records[key]
        service.store.records[key] = record.model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
        )
        for suffix in ("", "/view", "/markdown"):
            assert client.get(f"/v1/analyses/{key}{suffix}").status_code == 404


def test_rag_api_and_html_escape_untrusted_text():
    _, _, _, retriever = local_system()

    def analyze(plan):
        return explain(plan, retriever, RecordingSynthesizer())

    service, client = system(analyze)
    with client:
        response = post(client)
        report = response.json()
        assert report["overall_risk"] == "HIGH"
        assert len(report["findings"]) == 4
        assert report["rag_status"] == "available"
        assert report["advisory"]["sources"]
        view = client.get(response.headers["location"] + "/view")
        assert "Supporting runbooks" in view.text
        assert "Content SHA-256" in view.text
    report = build_report(demo_plan()).model_copy(
        update={"explanation": '<script>alert("synthetic")</script>'}
    )
    page = report_page(report, mode="offline")
    assert '<script>alert("synthetic")</script>' not in page
    assert "&lt;script&gt;" in page


def test_provider_initialization_failure_returns_policy_fallback(monkeypatch):
    from terramind.cloud import google

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic-private-canary")

    monkeypatch.setattr(google, "GoogleEmbedder", fail)
    settings = CloudSettings(project_id="terramind-demo")
    service, client = system(lambda plan: cloud_analysis(plan, settings))
    with client:
        response = post(client)
        assert response.status_code == 201
        assert response.json()["rag_status"] == "unavailable"
        assert len(response.json()["findings"]) == 4
        assert "synthetic-private-canary" not in response.text


def test_demo_preview_and_assets_never_run_analysis():
    service, client = system(lambda plan: pytest.fail("Preview invoked model"))
    with client:
        for path in (
            "/demo",
            "/assets/report.css",
            "/assets/demo.js",
            "/assets/terramind-logo.png",
            "/assets/terramind-icon.png",
            "/assets/apple-touch-icon.png",
            "/favicon.ico",
            "/health",
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-frame-options"] == "DENY"
            assert "default-src 'none'" in response.headers["content-security-policy"]
            assert "img-src 'self'" in response.headers["content-security-policy"]
            if path.endswith(".png"):
                assert response.headers["content-type"] == "image/png"
                assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
            elif path.endswith(".ico"):
                assert response.headers["content-type"] == "image/vnd.microsoft.icon"
                assert response.content.startswith(b"\x00\x00\x01\x00")
        assert (
            client.options(
                "/v1/analyses",
                headers={
                    "Origin": "https://example.invalid",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            ).headers.get("access-control-allow-origin")
            is None
        )
    assert not service.store.records


def test_logs_use_route_template_and_exclude_ids(caplog):
    service, client = system()
    with client:
        response = post(client)
        key = response.json()["analysis_id"]
        client.get(response.headers["location"] + "?token=synthetic-private-canary")
    assert key not in caplog.text
    assert "synthetic-private-canary" not in caplog.text
    entries = [json.loads(r.message) for r in caplog.records if r.name == "terramind.api"]
    assert entries[-1]["route"] == "/v1/analyses/{analysis_id}"


def test_memory_capacity_is_bounded_and_expired_entries_are_pruned():
    store = MemoryReportStore(capacity=1)
    report = build_report(demo_plan())
    record = StoredAnalysis(
        analysis_id=report.analysis_id,
        report_json=report.model_dump_json(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    store.save(record)
    with pytest.raises(DependencyUnavailable):
        store.save(record)
    store.records[record.analysis_id] = record.model_copy(
        update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
    )
    store.save(record)
    assert len(store.records) == 1


def test_falsely_small_content_length_does_not_bypass_limit():
    service, client = system()
    with client:
        response = client.post(
            "/v1/analyses",
            content=b" " * (MAX_REQUEST_BYTES + 1),
            headers={"Content-Type": "application/json", "Content-Length": "1"},
        )
    assert response.status_code == 413


def test_api_body_read_deadline(monkeypatch):
    import asyncio

    from fastapi import HTTPException, Request

    from terramind.api import app as api_module

    original = asyncio.timeout
    monkeypatch.setattr(api_module.asyncio, "timeout", lambda _: original(0.001))

    async def receive():
        await asyncio.sleep(0.1)
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {"type": "http", "headers": [(b"content-type", b"application/json")]}, receive
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_module.read_plan(request))
    assert error.value.status_code == 408


def test_analysis_slot_is_released_after_unexpected_failure():
    def fail(plan):
        raise RuntimeError("synthetic-private-canary")

    service, client = system(fail)
    with client:
        response = post(client)
        assert response.status_code == 500
        assert "synthetic-private-canary" not in response.text
    assert service.gate.busy is False


def test_cloud_composition_and_client_cleanup_with_explicit_test_doubles(monkeypatch):
    from unittest.mock import Mock

    from terramind.cloud import google

    _, embedder, store, _ = local_system()
    synth = RecordingSynthesizer()
    for adapter in (embedder, store, synth):
        adapter.client = Mock()
    monkeypatch.setattr(google, "GoogleEmbedder", lambda *args: embedder)
    monkeypatch.setattr(google, "FirestoreKnowledgeStore", lambda *args: store)
    monkeypatch.setattr(google, "GeminiSynthesizer", lambda *args: synth)
    report = cloud_analysis(demo_plan(), CloudSettings(project_id="terramind-demo"))
    assert report.rag_status == "available"
    assert len(report.findings) == 4
    for adapter in (embedder, store, synth):
        adapter.client.close.assert_called_once()


def test_cloud_report_connection_lifecycle_with_local_store(monkeypatch):
    from unittest.mock import Mock

    from terramind.api import service as service_module
    from terramind.cloud import reports

    store = MemoryReportStore()
    store.client = Mock()
    monkeypatch.setenv("GCP_PROJECT_ID", "terramind-demo")
    monkeypatch.setattr(reports, "FirestoreReportStore", lambda settings: store)
    monkeypatch.setattr(service_module, "cloud_analysis", lambda plan, settings: build_report(plan))
    service = service_module.default_service(ApiSettings(mode="cloud"))
    with TestClient(create_app(service)) as client:
        response = post(client)
        assert response.status_code == 201
        assert client.get(response.headers["location"]).status_code == 200
    assert store.client.close.call_count == 2
