import base64
import copy
import json
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from terramind.cloud.budget import DependencyUnavailable
from terramind.portal.app import create_app
from terramind.portal.firestore import FirestorePortalStore
from terramind.portal.settings import PortalSettings
from terramind.portal.store import HistoryFilters, token_hash
from terramind.reports.render import build_report
from tests.unit.test_portal_store import bundle


class Document:
    def __init__(self, client, path):
        self.client, self.path, self.id = client, path, path.split("/")[-1]

    def get(self, *, transaction=None, timeout, retry=None):
        assert timeout == 5 and (transaction is None or not transaction.writes)
        if self.client.fail:
            raise RuntimeError("synthetic-private-provider-error")
        value = copy.deepcopy(self.client.data.get(self.path))
        return SimpleNamespace(id=self.id, to_dict=lambda: value)


class Query:
    def __init__(self, client, name, filters=(), fields=None, bound=2049):
        self.client, self.name = client, name
        self.filters, self.fields, self.bound = filters, fields, bound

    def document(self, key):
        return Document(self.client, self.name + "/" + key)

    def where(self, *, filter):
        return Query(self.client, self.name, (*self.filters, filter), self.fields, self.bound)

    def limit(self, bound):
        return Query(self.client, self.name, self.filters, self.fields, bound)

    def select(self, fields):
        assert "bundle" not in fields
        return Query(self.client, self.name, self.filters, fields, self.bound)

    def stream(self, *, transaction=None, timeout, retry=None):
        assert timeout == 5 and (transaction is None or not transaction.writes)
        if self.client.fail:
            raise RuntimeError("synthetic-private-provider-error")
        results = []
        for path, value in self.client.data.items():
            if not path.startswith(self.name + "/"):
                continue
            if any(
                not (
                    value[item.field_path] > item.value
                    if item.op_string == ">"
                    else value[item.field_path] == item.value
                )
                for item in self.filters
            ):
                continue
            projected = (
                {key: copy.deepcopy(value[key]) for key in self.fields}
                if self.fields
                else copy.deepcopy(value)
            )
            results.append(
                SimpleNamespace(id=path.split("/")[-1], to_dict=lambda value=projected: value)
            )
        return results[: self.bound]


class Transaction:
    def __init__(self, client):
        self.client, self.writes = client, []

    def create(self, ref, value):
        self.writes.append(("create", ref.path, value))

    def update(self, ref, value):
        self.writes.append(("update", ref.path, value))

    def set(self, ref, value):
        self.writes.append(("set", ref.path, value))

    def delete(self, ref):
        self.writes.append(("delete", ref.path, None))

    def commit(self):
        if self.client.fail:
            raise RuntimeError("synthetic-private-provider-error")
        staged = copy.deepcopy(self.client.data)
        for action, path, value in self.writes:
            if action == "delete":
                staged.pop(path, None)
            elif action == "create" and path in staged:
                raise RuntimeError("Already exists")
            elif action == "update":
                staged[path].update(value)
            else:
                staged[path] = copy.deepcopy(value)
        self.client.data = staged


class Client:
    def __init__(self):
        self.data, self.fail, self.closed = {}, False, False

    def collection(self, name):
        return Query(self, name)

    def transaction(self, *, max_attempts):
        assert max_attempts == 3
        return Transaction(self)

    def close(self):
        self.closed = True


@pytest.fixture
def cloud_store(monkeypatch):
    def transactional(operation):
        def wrapped(transaction):
            result = operation(transaction)
            transaction.commit()
            return result

        return wrapped

    monkeypatch.setattr("google.cloud.firestore.transactional", transactional)
    clock, client = [1800000000.0], Client()
    return (
        FirestorePortalStore(
            "synthetic-project", "synthetic-portal", client=client, clock=lambda: clock[0]
        ),
        clock,
        client,
    )


def test_sessions_persist_rotate_revoke_and_expire(cloud_store):
    store, clock, client = cloud_store
    anon = store.new_session()
    assert "portal_sessions/" + token_hash(anon.token) in client.data
    signed = store.new_session("owner-a", "Google account", previous=anon.token)
    assert store.session(anon.token) is None
    restarted = FirestorePortalStore(
        "synthetic-project", "synthetic-portal", client=client, clock=lambda: clock[0]
    )
    assert restarted.session(signed.token) == signed
    assert restarted.session("invalid") is None
    clock[0] += 1801
    assert restarted.session(signed.token) is None
    active = store.new_session("owner-a")
    store.logout(active.token)
    assert store.session(active.token) is None
    store.close()
    assert client.closed


def test_absolute_expiry_and_single_use_browser_bound_flows(cloud_store):
    store, clock, _ = cloud_store
    first, other = store.new_session(), store.new_session()
    state, nonce, verifier = store.begin_flow(first)
    assert store.consume_flow(other, state) is None
    assert store.consume_flow(first, "wrong-state") is None
    assert store.consume_flow(first, state) == (nonce, verifier)
    assert store.consume_flow(first, state) is None
    old, _, _ = store.begin_flow(first)
    state, _, _ = store.begin_flow(first)
    assert store.consume_flow(first, old) is None
    clock[0] += 301
    assert store.consume_flow(first, state) is None
    for _ in range(15):
        clock[0] += 900
        assert store.session(first.token) is not None
    clock[0] += 901
    assert store.session(first.token) is None


def test_owned_reports_create_only_history_filters_and_expiry(cloud_store):
    store, clock, client = cloud_store
    ids = set()
    for _ in range(25):
        report = bundle()
        store.save("owner-a", report)
        ids.add(report.report.analysis_id)
    store.save("owner-b", bundle())
    assert store.get("owner-a", report.report.analysis_id) == report
    assert store.get("owner-b", report.report.analysis_id) is None
    assert store.get("owner-a", "invalid") is None
    with pytest.raises(DependencyUnavailable):
        store.save("owner-a", report)
    now = int(clock[0] * 1000000)
    filters = HistoryFilters(risk="HIGH", rule="TM-GCP-001", since=now, until=now + 1)
    first = store.history("owner-a", filters)
    second = store.history("owner-a", filters, first["next_cursor"])
    assert len(first["items"]) == 20 and len(second["items"]) == 5
    assert {row["analysis_id"] for row in [*first["items"], *second["items"]]} == ids
    assert first["totals"] == {"reports": 25, "high_risk": 25, "findings": 100}
    assert not store.history("owner-a", HistoryFilters(risk="MEDIUM"))["items"]
    assert not store.history("owner-a", HistoryFilters(rule="TM-GCP-008"))["items"]
    assert not store.history("owner-a", HistoryFilters(since=now + 1))["items"]
    assert not store.history("owner-a", HistoryFilters(until=now))["items"]
    clock[0] += 86401
    assert not store.history("owner-a", HistoryFilters())["items"]
    assert store.get("owner-a", report.report.analysis_id) is None
    assert len(client.data) == 26  # Reads enforce expiry before asynchronous TTL cleanup.


@pytest.mark.parametrize(
    "cursor", ["bad", "x" * 257, {"at": True, "id": str(uuid4())}, {"at": 1, "id": "../private"}]
)
def test_cursor_and_date_validation(cloud_store, cursor):
    store, _, _ = cloud_store
    if isinstance(cursor, dict):
        cursor = base64.urlsafe_b64encode(json.dumps(cursor).encode()).decode()
    with pytest.raises(ValueError):
        store.history("owner-a", HistoryFilters(), cursor)
    with pytest.raises(ValueError):
        store.history("owner-a", HistoryFilters(since=2, until=1))


def test_storage_failures_and_corruption_are_sanitized(cloud_store):
    store, _, client = cloud_store
    report = bundle()
    store.save("owner-a", report)
    path = "portal_reports/" + report.report.analysis_id
    client.data[path]["bundle"] = "{}"
    with pytest.raises(DependencyUnavailable):
        store.get("owner-a", report.report.analysis_id)
    client.fail = True
    for operation in [
        lambda: store.new_session(),
        lambda: store.history("owner-a", HistoryFilters()),
        lambda: store.get("owner-a", report.report.analysis_id),
    ]:
        with pytest.raises(DependencyUnavailable, match="unavailable") as error:
            operation()
        assert "private-provider" not in str(error.value)


def test_cloud_capacity_checks_are_bounded_and_atomic(cloud_store):
    store, _, client = cloud_store
    now = datetime.fromtimestamp(1800000000 + 3600, UTC)
    client.data = {f"portal_sessions/{i}": {"seen": now, "expires_at": now} for i in range(512)}
    before = copy.deepcopy(client.data)
    with pytest.raises(DependencyUnavailable, match="capacity"):
        store.new_session()
    assert client.data == before
    client.data = {
        f"portal_reports/{i}": {"owner": "owner-a", "expires_at": now} for i in range(512)
    }
    with pytest.raises(DependencyUnavailable, match="capacity"):
        store.save("owner-a", bundle())
    client.data = {
        f"portal_reports/{i}": {"owner": f"owner-{i}", "expires_at": now} for i in range(2048)
    }
    with pytest.raises(DependencyUnavailable, match="capacity"):
        store.save("new-owner", bundle())


def test_private_proxy_keeps_fixed_origin_and_durable_owned_reports(cloud_store):
    store, _, _ = cloud_store
    origin, host = "http://127.0.0.1:8091", "synthetic-portal-123456789012.us-central1.run.app"
    settings = PortalSettings(
        origin=origin,
        auth_mode="google",
        storage_backend="firestore",
        project="synthetic-project",
        firestore_database="synthetic-portal",
        transport_host=host,
        client_id="123-synthetic.apps.googleusercontent.com",
        client_secret="synthetic-client-secret",
        allowed_emails=("analyst@example.invalid",),
    )

    class Provider:
        def authorize(self, state, nonce, verifier):
            self.nonce, self.verifier = nonce, verifier
            return "https://accounts.google.com/o/oauth2/v2/auth?state=" + state

        def exchange(self, code, nonce, verifier):
            assert (code, nonce, verifier) == ("synthetic", self.nonce, self.verifier)
            return "owner-a"

    application = create_app(settings, store, Provider(), build_report)
    client = TestClient(
        application, base_url=origin, headers={"Host": host}, follow_redirects=False
    )
    login = client.get("/login")
    token = re.search(r'name="csrf" value="([^"]+)"', login.text).group(1)
    auth = client.post("/auth/google", data={"csrf": token}, headers={"Origin": origin})
    state = parse_qs(urlsplit(auth.headers["location"]).query)["state"][0]
    assert client.get("/auth/callback?state=" + state + "&code=synthetic").status_code == 303
    dashboard = client.get("/dashboard")
    token = re.search(r'name="csrf" value="([^"]+)"', dashboard.text).group(1)
    result = client.post(
        "/analyses",
        data={"csrf": token, "scenario": "storage-hardening"},
        headers={"Origin": origin},
    )
    assert result.status_code == 303
    assert "storage-hardening" in client.get(result.headers["location"]).text
    assert client.get("/api/history").json()["totals"]["reports"] == 1
    assert client.get("/healthz").status_code == 200
    assert client.get("/login", headers={"Host": "attacker.invalid"}).status_code == 400
    assert (
        client.post(
            "/analyses",
            data={"csrf": token, "scenario": "risk-demo"},
            headers={"Origin": "https://attacker.invalid"},
        ).status_code
        == 403
    )
    assert store.history("owner-b", HistoryFilters())["items"] == []


def test_cloud_settings_reject_ephemeral_state_and_untrusted_transport(monkeypatch):
    google = dict(
        auth_mode="google",
        client_id="123-synthetic.apps.googleusercontent.com",
        client_secret="synthetic-client-secret",
        allowed_emails=("analyst@example.invalid",),
    )
    with pytest.raises(ValueError):
        PortalSettings(storage_backend="other", **google)
    with pytest.raises(ValueError):
        PortalSettings(storage_backend="firestore", **google)
    with pytest.raises(ValueError):
        PortalSettings(transport_host="attacker.invalid", **google)
    monkeypatch.setenv("K_SERVICE", "synthetic-portal")
    with pytest.raises(ValueError, match="durable"):
        PortalSettings(**google)
