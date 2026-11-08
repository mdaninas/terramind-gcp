import pytest

from terramind.normalizer.io import load_normalized
from terramind.policies.engine import evaluate, overall_risk
from terramind.reports.render import build_report, markdown


@pytest.mark.parametrize(
    ("name", "rule_id", "status"),
    [
        ("public_bucket", "TM-GCP-001", "FAIL"),
        ("public_bucket_pap_enforced", "TM-GCP-001", "REVIEW"),
        ("ssh_open_world", "TM-GCP-002", "FAIL"),
        ("ssh_internal_only", None, None),
        ("project_owner_grant", "TM-GCP-003", "FAIL"),
        ("bucket_delete", "TM-GCP-004", "REVIEW"),
        ("benign_labels", None, None),
        ("no_changes", None, None),
    ],
)
def test_eight_golden_fixtures(fixture_dir, name, rule_id, status):
    plan = load_normalized((fixture_dir / f"{name}.json").read_bytes())
    findings = evaluate(plan)
    assert findings == evaluate(plan)
    assert [finding.rule_id for finding in findings] == ([rule_id] if rule_id else [])
    assert overall_risk(findings) == ("HIGH" if rule_id else "NO_KNOWN_FINDINGS")
    if findings:
        assert findings[0].status == status
        assert findings[0].evidence and findings[0].rationale and findings[0].remediation
    report = build_report(plan)
    assert report.model_id is None
    assert report.rag_status == "not_requested"
    assert report.citations == ()
    assert report.overall_risk == overall_risk(findings)
    assert "SAFE" not in markdown(report)


def test_pap_does_not_claim_exposure(fixture_dir):
    report = build_report(
        load_normalized((fixture_dir / "public_bucket_pap_enforced.json").read_bytes())
    )
    assert report.findings[0].status == "REVIEW"
    assert "blocks this public grant" in report.findings[0].rationale
    assert report.overall_risk == "HIGH"
