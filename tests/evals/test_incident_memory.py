import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from terramind.cli import main
from terramind.incidents.search import LABEL, IncidentSearcher
from terramind.normalizer.io import load_normalized
from terramind.reports.render import build_report


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("public_bucket", "inc-public-exposure"),
        ("ssh_open_world", "inc-admin-ingress"),
        ("project_owner_grant", "inc-basic-role-expansion"),
        ("bucket_delete", "inc-destructive-replacement"),
    ],
)
def test_frozen_synthetic_incident_queries_rank_expected_context_first(fixture, expected):
    report = build_report(
        load_normalized(Path(f"examples/normalized-plans/{fixture}.json").read_bytes())
    )
    original = copy.deepcopy(report.model_dump())
    result = IncidentSearcher().search(report)
    assert result.matches[0].doc_id == expected
    assert result.matches[0].evidence_label == LABEL
    assert 0 < result.matches[0].similarity <= 1
    assert all(match.source_path.startswith("incidents/") for match in result.matches)
    assert report.model_dump() == original
    schema = json.loads(Path("schemas/incident-memory.v1.schema.json").read_text())
    Draft202012Validator(schema).validate(result.model_dump(mode="json"))


def test_benign_plan_does_not_fabricate_incident_context():
    report = build_report(
        load_normalized(Path("examples/normalized-plans/no_changes.json").read_bytes())
    )
    result = IncidentSearcher().search(report)
    assert result.status == "not_requested" and result.matches == ()


def test_source_integrity_and_duplicate_ids_are_rejected():
    search = IncidentSearcher()
    with pytest.raises(ValueError, match="integrity"):
        IncidentSearcher((search.documents[0], search.documents[0]))
    with pytest.raises(ValueError, match="integrity"):
        IncidentSearcher((search.documents[0].model_copy(update={"body": "modified"}),))
    with pytest.raises(ValueError):
        IncidentSearcher(())


def test_incident_cli_runs_without_network_and_emits_explicit_evidence_label(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No external connection is allowed")

    monkeypatch.setattr("socket.create_connection", forbidden)
    destination = tmp_path / "incidents.json"
    assert (
        main(
            [
                "incidents",
                "--input",
                "examples/normalized-plans/public_bucket.json",
                "--output",
                str(destination),
            ]
        )
        == 0
    )
    data = json.loads(destination.read_text())
    assert data["method"] == "local-tfidf-cosine"
    assert data["matches"][0]["evidence_label"] == LABEL
