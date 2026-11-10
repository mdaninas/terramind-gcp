import re
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from terramind.portal.app import create_app
from terramind.portal.settings import PortalSettings
from terramind.portal.store import PortalStore, owner_key

ORIGIN = "http://127.0.0.1:8080"


def csrf(client, path="/dashboard"):
    text = client.get(path).text
    return re.search(r'name="csrf" value="([^"]+)"', text).group(1)


def login(client, account="analyst"):
    token = csrf(client, "/login")
    return client.post(
        "/auth/demo", data={"csrf": token, "account": account}, headers={"Origin": ORIGIN}
    )


def analyze(client, scenario="risk-demo"):
    return client.post(
        "/analyses", data={"csrf": csrf(client), "scenario": scenario}, headers={"Origin": ORIGIN}
    )


@pytest.fixture
def portal():
    database = PortalStore(Path(":memory:"))
    settings = PortalSettings(database=Path(":memory:"))
    application = create_app(settings, database)
    first = TestClient(
        application, base_url=ORIGIN, client=("127.0.0.1", 51000), follow_redirects=False
    )
    second = TestClient(
        application, base_url=ORIGIN, client=("127.0.0.1", 51001), follow_redirects=False
    )
    yield first, second, database
    first.close()
    second.close()
    database.close()


@pytest.mark.parametrize(
    ("scenario", "risk", "rule"),
    [
        ("storage-hardening", "MEDIUM", "TM-GCP-005"),
        ("database-hardening", "HIGH", "TM-GCP-008"),
    ],
)
def test_optional_packs_keep_owned_history_and_explain_incident_gap(portal, scenario, risk, rule):
    client, other, _ = portal
    login(client)
    login(other, "reviewer")
    result = analyze(client, scenario)
    assert result.status_code == 303
    path = result.headers["location"]
    bundle = client.get(path + "/json").json()
    assert bundle["report"]["policy_packs"] == ["gcp-core", scenario]
    assert bundle["report"]["overall_risk"] == risk
    assert bundle["incident_memory"]["status"] == "partial"
    assert not bundle["incident_memory"]["matches"]
    assert "Search status: partial" in client.get(path).text
    history = client.get(f"/api/history?rule={rule}&risk={risk}").json()
    assert len(history["items"]) == 1
    assert client.get(path + "/markdown").status_code == 200
    assert scenario in client.get(path + "/markdown").text
    assert other.get(path + "/json").status_code == 404
    assert not other.get(f"/api/history?rule={rule}").json()["items"]


def test_portal_login_report_incidents_history_exports_and_logout(portal):
    client, _, _ = portal
    assert client.get("/dashboard").headers["location"] == "/login"
    pre = client.get("/login")
    old = client.cookies["terramind_session"]
    assert "HttpOnly" in pre.headers["set-cookie"] and "SameSite=lax" in pre.headers["set-cookie"]
    assert login(client).status_code == 303
    assert client.cookies["terramind_session"] != old
    result = analyze(client)
    assert result.status_code == 303
    path = result.headers["location"]
    report = client.get(path + "/json").json()
    assert len(report["report"]["findings"]) == 4
    assert report["incident_memory"]["matches"]
    assert "Synthetic tabletop" in report["incident_memory"]["matches"][0]["evidence_label"]
    page = client.get(path)
    assert page.status_code == 200 and "Incident Memory" in page.text
    assert client.get(path + "/markdown").headers["content-disposition"].startswith("attachment")
    assert client.get("/api/history").json()["totals"]["reports"] == 1
    source = report["incident_memory"]["matches"][0]["doc_id"]
    assert client.get("/incidents/" + source).status_code == 200
    assert client.get("/assets/portal.css").status_code == 200
    assert client.get("/assets/terramind-logo.png").status_code == 200
    assert (
        client.post(
            "/auth/logout", data={"csrf": csrf(client)}, headers={"Origin": ORIGIN}
        ).status_code
        == 303
    )
    assert client.get(path + "/json").status_code == 401


@pytest.mark.parametrize("suffix", ["", "/json", "/markdown"])
def test_other_users_cannot_read_reports_even_with_id_or_owner_header(portal, suffix):
    first, second, _ = portal
    login(first)
    path = analyze(first).headers["location"]
    login(second, "reviewer")
    response = second.get(path + suffix, headers={"X-User-ID": owner_key("demo", "analyst")})
    assert response.status_code == 404
    assert second.get("/api/history").json()["items"] == []
    assert second.get("/v1/analyses/" + path.split("/")[-1]).status_code == 404


@pytest.mark.parametrize(
    "route", ["/api/history", "/reports/unknown/json", "/incidents/inc-public-exposure"]
)
def test_private_portal_routes_require_a_server_session(portal, route):
    assert portal[0].get(route).status_code == 401


@pytest.mark.parametrize("change", ["origin", "csrf", "missing", "unicode"])
def test_csrf_and_origin_failures_cannot_create_reports(portal, change):
    client, _, _ = portal
    login(client)
    values = {"csrf": csrf(client), "scenario": "risk-demo"}
    headers = {"Origin": ORIGIN}
    if change == "origin":
        headers["Origin"] = "https://attacker.invalid"
    elif change == "missing":
        headers = {}
    else:
        values["csrf"] = "wrong" if change == "csrf" else "\u00e9"
    assert client.post("/analyses", data=values, headers=headers).status_code == 403
    assert client.get("/api/history").json()["totals"]["reports"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "risk=invalid",
        "rule=TM-GCP-999",
        "risk=HIGH&risk=LOW",
        "from=2026-02-30",
        "from=2026-11-11&to=2026-11-09",
        "cursor=invalid",
        "owner=other-user",
        "from=9999-01-01",
    ],
)
def test_history_rejects_invalid_or_injected_filters_without_echoing_input(portal, query):
    client, _, _ = portal
    login(client)
    response = client.get("/api/history?" + query)
    assert response.status_code == 400
    assert "Invalid history" in response.text


def test_history_filters_apply_to_reports_and_totals(portal):
    client, _, _ = portal
    login(client)
    analyze(client)
    analyze(client, "benign")
    assert client.get("/api/history?risk=HIGH&rule=TM-GCP-002").json()["totals"]["reports"] == 1
    assert client.get("/api/history?risk=NO_KNOWN_FINDINGS").json()["totals"]["findings"] == 0
    assert "HIGH" in client.get("/dashboard?risk=HIGH").text


def test_raw_plan_fields_duplicate_forms_and_large_bodies_are_rejected(portal):
    client, _, _ = portal
    login(client)
    token = csrf(client)
    response = client.post(
        "/analyses",
        data={"csrf": token, "scenario": "risk-demo", "resource_changes": "private"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 400 and "private" not in response.text
    duplicate = urlencode({"csrf": token, "scenario": "risk-demo"}) + "&scenario=benign"
    headers = {"Origin": ORIGIN, "Content-Type": "application/x-www-form-urlencoded"}
    assert client.post("/analyses", content=duplicate, headers=headers).status_code == 400
    assert client.post("/analyses", content=b"x" * 4097, headers=headers).status_code == 413
    assert (
        client.post("/analyses", json={"csrf": token}, headers={"Origin": ORIGIN}).status_code
        == 415
    )


def test_host_and_remote_demo_boundaries_are_enforced(portal):
    client, _, _ = portal
    assert client.get("/login", headers={"Host": "attacker.invalid"}).status_code == 400
    remote = TestClient(client.app, base_url=ORIGIN, client=("198.51.100.1", 50000))
    assert remote.get("/login").status_code == 403
    remote.close()


def test_security_headers_and_logout_revoke_the_old_session(portal):
    client, _, _ = portal
    login(client)
    token = client.cookies["terramind_session"]
    response = client.get("/dashboard")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "strict-origin"
    assert "form-action 'self'" in response.headers["content-security-policy"]
    client.post("/auth/logout", data={"csrf": csrf(client)}, headers={"Origin": ORIGIN})
    client.cookies.set("terramind_session", token)
    assert client.get("/api/history").status_code == 401


class FakeGoogle:
    def __init__(self):
        self.flows = []
        self.exchanges = []

    def authorize(self, state, nonce, verifier):
        self.flows.append((state, nonce, verifier))
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({"state": state})

    def exchange(self, code, nonce, verifier):
        self.exchanges.append((code, nonce, verifier))
        assert (nonce, verifier) == self.flows[-1][1:]
        if code != "synthetic-code":
            raise ValueError("synthetic-provider-private-details")
        return owner_key("google", "synthetic-subject")


def test_google_callback_binds_state_rotates_session_and_prevents_replay(tmp_path):
    settings = PortalSettings(
        auth_mode="google",
        database=tmp_path / "private.sqlite3",
        client_id="123-synthetic.apps.googleusercontent.com",
        client_secret="synthetic-client-secret",
        allowed_emails=("analyst@example.invalid",),
    )
    provider = FakeGoogle()
    database = PortalStore(settings.database)
    application = create_app(settings, database, provider)
    client = TestClient(
        application, base_url=ORIGIN, client=("127.0.0.1", 50000), follow_redirects=False
    )
    token = csrf(client, "/login")
    old = client.cookies[settings.cookie_name]
    assert client.post("/auth/demo", data={}).status_code == 404
    start = client.post("/auth/google", data={"csrf": token}, headers={"Origin": ORIGIN})
    assert start.status_code == 303 and start.headers["location"].startswith(
        "https://accounts.google.com/"
    )
    state = provider.flows[-1][0]
    assert (
        client.get(
            "/auth/callback?" + urlencode({"state": "invalid", "code": "synthetic-code"})
        ).status_code
        == 400
    )
    assert provider.exchanges == []
    callback = "/auth/callback?" + urlencode({"state": state, "code": "synthetic-code"})
    assert client.get(callback).status_code == 303
    assert client.cookies[settings.cookie_name] != old
    assert client.get("/api/history").status_code == 200
    assert client.get(callback).status_code == 400
    assert len(provider.exchanges) == 1
    stored = settings.database.read_bytes()
    assert b"synthetic-code" not in stored and b"synthetic-client-secret" not in stored
    client.close()
    database.close()
