from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from terramind.api.app import demo_plan
from terramind.api.service import ApiSettings
from terramind.cloud.budget import DependencyUnavailable
from terramind.cloud.reports import FirestoreReportStore
from terramind.cloud.settings import CloudSettings
from terramind.reports.render import build_report
from terramind.reports.store import StoredAnalysis


def record():
    report = build_report(demo_plan())
    return StoredAnalysis(
        analysis_id=report.analysis_id,
        report_json=report.model_dump_json(),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )


def system():
    client = Mock()
    store = FirestoreReportStore(CloudSettings(project_id="terramind-demo"), client)
    return client, store


def test_firestore_create_only_datetime_ttl_and_fixed_collection():
    client, store = system()
    item = record()
    store.save(item)
    client.collection.assert_called_once_with("analyses")
    doc = client.collection.return_value.document
    doc.assert_called_once_with(item.analysis_id)
    args, kwargs = doc.return_value.create.call_args
    assert args[0] == item.model_dump()
    assert isinstance(args[0]["expires_at"], datetime)
    assert kwargs["retry"] is None and 0 < kwargs["timeout"] <= 3


def test_firestore_ambiguous_write_is_not_retried():
    client, store = system()
    client.collection.return_value.document.return_value.create.side_effect = RuntimeError(
        "private-canary"
    )
    with pytest.raises(DependencyUnavailable, match="External dependency unavailable"):
        store.save(record())
    assert client.collection.return_value.document.return_value.create.call_count == 1


@pytest.mark.parametrize("state", ["valid", "expired", "missing", "mismatch", "invalid"])
def test_firestore_read_validation_and_application_expiry(state):
    client, store = system()
    item = record()
    data = item.model_dump()
    if state == "expired":
        data["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    elif state == "mismatch":
        data["analysis_id"] = str(uuid4())
    elif state == "invalid":
        data["source"] = "real-plan"
    snapshot = SimpleNamespace(exists=state != "missing", to_dict=lambda: data)
    client.collection.return_value.document.return_value.get.return_value = snapshot
    if state in {"mismatch", "invalid"}:
        with pytest.raises(DependencyUnavailable):
            store.get(item.analysis_id)
    else:
        result = store.get(item.analysis_id)
        assert result == (item if state == "valid" else None)
    assert store.get("analyses/../../other") is None
    assert client.collection.return_value.document.call_count == 1


@pytest.mark.parametrize(
    "values",
    [
        {"mode": "other"},
        {"retention_hours": 25},
        {"requests_per_minute": 31},
        {"requests_per_minute": 0},
    ],
)
def test_api_settings_reject_unbounded_configuration(values):
    with pytest.raises(ValueError):
        ApiSettings(**values)
