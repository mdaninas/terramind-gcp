import json
import socket

import pytest
from fastapi.testclient import TestClient

from terramind.api.app import create_app


@pytest.mark.parametrize("path", ["/health", "/healthz"])
def test_health_without_network(monkeypatch, path):
    def denied(*args, **kwargs):
        raise AssertionError("Liveness attempted an external connection")

    monkeypatch.setattr(socket, "create_connection", denied)
    with TestClient(create_app()) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "terramind", "version": "0.1.0"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/v1/analyses", "/demo"])
def test_unimplemented_routes_are_not_exposed(path):
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


def test_logs_exclude_untrusted_content(caplog):
    with TestClient(create_app()) as client:
        client.post(
            "/synthetic-canary?token=synthetic-canary",
            content="synthetic-canary",
            headers={
                "Authorization": "Bearer synthetic-canary",
                "X-Request-ID": "synthetic-canary",
            },
        )
    entries = [record.message for record in caplog.records if record.name == "terramind.api"]
    assert len(entries) == 1
    assert "synthetic-canary" not in entries[0]
    entry = json.loads(entries[0])
    assert entry["route"] == "unmatched"
    assert entry["status"] == 404
    assert entry["duration_ms"] >= 0


def test_error_details_are_not_returned_or_logged(caplog):
    app = create_app()

    @app.get("/fail")
    def fail():
        raise RuntimeError("synthetic-private-canary")

    with TestClient(app) as client:
        response = client.get("/fail")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    entries = [record.message for record in caplog.records if record.name == "terramind.api"]
    assert "synthetic-private-canary" not in " ".join(entries)
    assert json.loads(entries[0])["severity"] == "ERROR"
