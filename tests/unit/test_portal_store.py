import base64
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from terramind.api.app import demo_plan
from terramind.cloud.budget import DependencyUnavailable
from terramind.incidents.search import IncidentSearcher
from terramind.portal.store import (
    HistoryFilters,
    PortalAnalysis,
    PortalStore,
    owner_key,
    token_hash,
)
from terramind.reports.render import build_report


def bundle():
    report = build_report(demo_plan())
    return PortalAnalysis(report=report, incident_memory=IncidentSearcher().search(report))


@pytest.fixture
def store():
    clock = [1800000000.0]
    database = PortalStore(Path(":memory:"), clock=lambda: clock[0])
    yield database, clock
    database.close()


def test_session_tokens_are_hashed_rotated_revoked_and_idle_expired(store):
    database, clock = store
    anon = database.new_session()
    assert database.db.execute("SELECT digest FROM sessions").fetchone()[0] == token_hash(
        anon.token
    )
    signed = database.new_session(
        owner_key("demo", "analyst"), "Synthetic analyst", previous=anon.token
    )
    assert database.session(anon.token) is None
    assert signed.token != anon.token and signed.csrf != anon.csrf
    assert database.session(signed.token).owner == signed.owner
    clock[0] += 1801
    assert database.session(signed.token) is None
    active = database.new_session(signed.owner)
    database.logout(active.token)
    assert database.session(active.token) is None


def test_absolute_expiry_applies_even_when_session_keeps_being_used(store):
    database, clock = store
    active = database.new_session("owner")
    for _ in range(15):
        clock[0] += 900
        assert database.session(active.token) is not None
    clock[0] += 901
    assert database.session(active.token) is None


def test_oauth_flows_bind_to_browser_expire_and_are_single_use(store):
    database, clock = store
    first, second = database.new_session(), database.new_session()
    state, nonce, verifier = database.begin_flow(first)
    assert len(verifier) >= 43
    assert database.consume_flow(second, state) is None
    assert database.consume_flow(first, state) == (nonce, verifier)
    assert database.consume_flow(first, state) is None
    state, _, _ = database.begin_flow(first)
    clock[0] += 301
    assert database.consume_flow(first, state) is None


def test_owned_reports_persist_across_restart_and_cannot_cross_users(tmp_path):
    path = tmp_path / "private.sqlite3"
    first, second = owner_key("demo", "analyst"), owner_key("demo", "reviewer")
    report = bundle()
    database = PortalStore(path)
    database.save(first, report)
    database.close()
    restarted = PortalStore(path)
    assert restarted.get(first, report.report.analysis_id) == report
    assert restarted.get(second, report.report.analysis_id) is None
    assert restarted.history(second, HistoryFilters())["totals"]["reports"] == 0
    restarted.close()


def test_history_pages_are_stable_for_tied_timestamps_and_never_include_other_owner(store):
    database, _ = store
    ids = set()
    for _ in range(25):
        report = bundle()
        database.save("owner-a", report)
        ids.add(report.report.analysis_id)
    database.save("owner-b", bundle())
    first = database.history("owner-a", HistoryFilters())
    second = database.history("owner-a", HistoryFilters(), first["next_cursor"])
    assert len(first["items"]) == 20 and len(second["items"]) == 5
    assert {item["analysis_id"] for item in [*first["items"], *second["items"]]} == ids
    assert first["totals"]["reports"] == second["totals"]["reports"] == 25


def test_risk_rule_date_filters_and_expiry_are_owner_scoped(store):
    database, clock = store
    database.save("owner-a", bundle())
    now = int(clock[0] * 1000000)
    assert (
        database.history(
            "owner-a", HistoryFilters(risk="HIGH", rule="TM-GCP-001", since=now, until=now + 1)
        )["totals"]["reports"]
        == 1
    )
    assert (
        database.history("owner-a", HistoryFilters(risk="NO_KNOWN_FINDINGS"))["totals"]["reports"]
        == 0
    )
    clock[0] += 86401
    assert database.history("owner-a", HistoryFilters())["totals"]["reports"] == 0


def test_create_only_report_writes_and_corruption_checks(store):
    database, _ = store
    report = bundle()
    database.save("owner", report)
    with pytest.raises(sqlite3.IntegrityError):
        database.save("owner", report)
    assert database.get("owner", report.report.analysis_id) == report
    database.db.execute("UPDATE reports SET bundle=?", ("{}",))
    with pytest.raises(DependencyUnavailable):
        database.get("owner", report.report.analysis_id)


def test_dashboard_high_risk_total_includes_critical_reports(store):
    database, _ = store
    first = bundle()
    second = bundle()
    critical = second.report.model_copy(update={"overall_risk": "CRITICAL"})
    database.save("owner", first)
    database.save("owner", second.model_copy(update={"report": critical}))
    assert database.history("owner", HistoryFilters())["totals"]["high_risk"] == 2


@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        "x" * 257,
        {"at": 10**50, "id": str(uuid4())},
        {"at": True, "id": str(uuid4())},
        {"at": 1, "id": "../private"},
    ],
)
def test_cursor_validation_cannot_inject_queries_or_overflow_sqlite(store, value):
    database, _ = store
    cursor = (
        value
        if isinstance(value, str)
        else base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
    )
    with pytest.raises(ValueError):
        database.history("owner", HistoryFilters(), cursor)
