import copy
import json

import pytest
from jsonschema import Draft202012Validator

from terramind.cli import main
from terramind.errors import InputError
from terramind.incidents.search import IncidentSearcher
from terramind.llm.service import explain
from terramind.normalizer.io import load_normalized
from terramind.normalizer.plan import normalize
from terramind.policies.engine import evaluate
from terramind.policies.samples import hardening_sample
from terramind.rag.retrieval import RULE_QUERIES
from terramind.reports.render import build_report, markdown
from terramind.schemas.normalized import NormalizedPlan, serialize_plan
from tests.knowledge_helpers import RecordingSynthesizer, local_system

BUCKET = "google_storage_bucket"
SQL = "google_sql_database_instance"
STORAGE = {"uniform_bucket_level_access": False, "public_access_prevention": "inherited"}
SAFE_STORAGE = {"uniform_bucket_level_access": True, "public_access_prevention": "enforced"}


def database(*, public=True, world="0.0.0.0/0", mode="ALLOW_UNENCRYPTED_AND_ENCRYPTED"):
    return {
        "settings": [
            {
                "ip_configuration": [
                    {
                        "ipv4_enabled": public,
                        "ssl_mode": mode,
                        "authorized_networks": [{"name": "synthetic-canary", "value": world}],
                    }
                ]
            }
        ]
    }


def projected(terraform_plan, encode, kind, after, before=None, actions=None, **markers):
    raw = terraform_plan(kind, copy.deepcopy(after), actions=actions or ["create"])
    raw["resource_changes"][0]["change"].update(before=before, **markers)
    pack = "storage-hardening" if kind == BUCKET else "database-hardening"
    return normalize(encode(raw), policy_packs=(pack,))


@pytest.mark.parametrize(
    ("kind", "after", "rules", "risk"),
    [
        (BUCKET, STORAGE, ["TM-GCP-005", "TM-GCP-006"], "MEDIUM"),
        (SQL, database(), ["TM-GCP-007", "TM-GCP-008"], "HIGH"),
    ],
)
def test_new_weak_settings_have_evidence_and_explicit_scope(
    terraform_plan, encode, kind, after, rules, risk
):
    plan = projected(terraform_plan, encode, kind, after)
    report = build_report(plan)
    assert [finding.rule_id for finding in report.findings] == rules
    assert report.overall_risk == risk
    assert report.policy_version == "1.1" and report.policy_packs[0] == "gcp-core"
    assert all(f.evidence and f.remediation for f in report.findings)
    assert "6 specific policies" in report.limitations[0]
    assert report.policy_packs[1] in markdown(report)
    serialized = serialize_plan(plan)
    assert "synthetic-canary" not in serialized
    assert "settings" not in serialized
    assert load_normalized(serialized.encode()) == plan


@pytest.mark.parametrize(("kind", "after"), [(BUCKET, STORAGE), (SQL, database())])
def test_unchanged_weak_settings_do_not_flag_label_updates(terraform_plan, encode, kind, after):
    plan = projected(
        terraform_plan,
        encode,
        kind,
        {**after, "labels": {"team": "new"}},
        before=after,
        actions=["update"],
    )
    assert evaluate(plan) == ()


@pytest.mark.parametrize(
    ("kind", "before", "after"),
    [
        (BUCKET, SAFE_STORAGE, STORAGE),
        (SQL, database(public=False, world="192.0.2.0/24", mode="ENCRYPTED_ONLY"), database()),
    ],
)
def test_weakening_is_detected_and_restoring_controls_is_quiet(
    terraform_plan, encode, kind, before, after
):
    assert len(evaluate(projected(terraform_plan, encode, kind, after, before, ["update"]))) == 2
    assert not evaluate(projected(terraform_plan, encode, kind, before, after, ["update"]))


@pytest.mark.parametrize("actions", [["no-op"], ["read"], ["forget"], ["delete"]])
@pytest.mark.parametrize("kind", [BUCKET, SQL])
def test_only_proposed_changes_trigger_hardening(terraform_plan, encode, actions, kind):
    after = STORAGE if kind == BUCKET else database()
    findings = evaluate(projected(terraform_plan, encode, kind, after, actions=actions))
    assert all(f.rule_id == "TM-GCP-004" for f in findings)


@pytest.mark.parametrize("marker", ["after_unknown", "after_sensitive"])
@pytest.mark.parametrize(
    "mask",
    [
        True,
        {"settings": True},
        {
            "settings": [
                {
                    "ip_configuration": [
                        {
                            "ipv4_enabled": True,
                            "ssl_mode": True,
                            "authorized_networks": [{"value": True}],
                        }
                    ]
                }
            ]
        },
    ],
)
def test_nested_unknown_and_sensitive_sql_facts_are_not_claimed(
    terraform_plan, encode, marker, mask
):
    plan = projected(terraform_plan, encode, SQL, database(), **{marker: mask})
    assert not evaluate(plan)
    assert plan.changes[0].attributes.ssl_mode == "unknown"


@pytest.mark.parametrize("marker", ["after_unknown", "after_sensitive"])
def test_bucket_sensitive_settings_remain_unknown(terraform_plan, encode, marker):
    assert not evaluate(projected(terraform_plan, encode, BUCKET, STORAGE, **{marker: True}))


def test_false_sensitive_markers_do_not_hide_known_nested_values(terraform_plan, encode):
    plan = projected(
        terraform_plan,
        encode,
        SQL,
        database(),
        after_sensitive={
            "settings": [{"ip_configuration": [{"ssl_mode": False, "ipv4_enabled": False}]}]
        },
    )
    assert len(evaluate(plan)) == 2


def test_unknown_before_requires_review(terraform_plan, encode):
    plan = projected(
        terraform_plan,
        encode,
        SQL,
        database(),
        before=database(),
        actions=["update"],
        before_sensitive=True,
    )
    assert {finding.status for finding in evaluate(plan)} == {"REVIEW"}


@pytest.mark.parametrize(
    "after",
    [
        database(public=False),
        database(world="192.0.2.0/24"),
        database(world="::/0"),
        database(public=None),
    ],
)
def test_sql_world_rule_requires_explicit_public_ipv4_and_ipv4_world(terraform_plan, encode, after):
    assert [f.rule_id for f in evaluate(projected(terraform_plan, encode, SQL, after))] == [
        "TM-GCP-008"
    ]


def test_absent_tls_mode_does_not_infer_from_legacy_flag(terraform_plan, encode):
    after = database(public=False)
    ip = after["settings"][0]["ip_configuration"][0]
    ip.pop("ssl_mode")
    ip["require_ssl"] = False
    assert not evaluate(projected(terraform_plan, encode, SQL, after))


def test_expiring_network_is_not_assumed_effective(terraform_plan, encode):
    after = database(mode="ENCRYPTED_ONLY")
    network = after["settings"][0]["ip_configuration"][0]["authorized_networks"][0]
    network["expiration_time"] = "2000-01-01T00:00:00Z"
    plan = projected(terraform_plan, encode, SQL, after)
    assert plan.changes[0].attributes.world_authorized_network is None
    assert not evaluate(plan)


@pytest.mark.parametrize(
    "after", [database(world="bad-cidr"), database(public="yes"), database(mode="unexpected")]
)
def test_malformed_risk_facts_fail_closed(terraform_plan, encode, after):
    with pytest.raises(InputError):
        projected(terraform_plan, encode, SQL, after)


def test_pack_opt_in_and_legacy_output(terraform_plan, encode):
    raw = terraform_plan(BUCKET, STORAGE)
    legacy = normalize(encode(raw))
    assert legacy.schema_version == "1.0" and not legacy.policy_packs
    assert "uniform_bucket_level_access" not in serialize_plan(legacy)
    assert not evaluate(legacy)
    for packs in [("unknown",), ("storage-hardening", "storage-hardening")]:
        with pytest.raises(InputError):
            normalize(encode(raw), policy_packs=packs)


@pytest.mark.parametrize("pack", ["storage-hardening", "database-hardening"])
def test_pack_samples_validate_export_and_have_partial_incident_coverage(pack):
    plan = hardening_sample(pack)
    value = json.loads(serialize_plan(plan))
    validator = Draft202012Validator(NormalizedPlan.model_json_schema())
    validator.validate(value)
    report = build_report(plan)
    memory = IncidentSearcher().search(report)
    assert memory.status == "partial" and not memory.matches
    value["schema_version"] = "1.0"
    assert list(validator.iter_errors(value))
    with pytest.raises(InputError):
        load_normalized(json.dumps(value).encode())
    value["policy_packs"] = []
    assert list(validator.iter_errors(value))
    with pytest.raises(InputError):
        load_normalized(json.dumps(value).encode())


def test_cli_selects_pack_at_normalization(tmp_path, terraform_plan, encode):
    raw, normalized, report = (tmp_path / name for name in ("raw.json", "plan.json", "report.json"))
    raw.write_bytes(encode(terraform_plan(BUCKET, STORAGE)))
    assert (
        main(
            [
                "normalize",
                "--input",
                str(raw),
                "--output",
                str(normalized),
                "--policy-pack",
                "storage-hardening",
            ]
        )
        == 0
    )
    assert main(["analyze", "--input", str(normalized), "--output", str(report)]) == 0
    assert json.loads(report.read_text())["overall_risk"] == "MEDIUM"


@pytest.mark.parametrize("pack", ["storage-hardening", "database-hardening"])
def test_extra_rule_retrieval_and_synthesis_preserve_findings(pack):
    _, _, _, retriever = local_system()
    plan = hardening_sample(pack)
    base = build_report(plan)
    citations = {}
    for finding in base.findings:
        results = retriever.search(RULE_QUERIES[finding.rule_id])
        assert results[0].doc_id == f"rb-{pack}"
        citations[f"{finding.rule_id}:{finding.resource}"] = results[0].citation_id

    def select_runbook(value):
        for item in value["explanations"]:
            item["citation_ids"] = [citations[item["finding_id"]]]
        value["citations"] = list(dict.fromkeys(citations.values()))
        return value

    report = explain(plan, retriever, RecordingSynthesizer(select_runbook))
    assert report.rag_status == "available" and report.advisory is not None
    assert report.findings == base.findings and report.overall_risk == base.overall_risk
    assert report.policy_packs == base.policy_packs and report.policy_version == "1.1"
    assert {source.doc_id for source in report.advisory.sources} == {f"rb-{pack}"}
    fallback = explain(
        plan, retriever, RecordingSynthesizer(lambda value: {**value, "overall_risk": "INFO"})
    )
    assert fallback.advisory is None
    assert fallback.findings == base.findings and fallback.overall_risk == base.overall_risk


def test_core_is_always_evaluated_and_both_packs_are_traceable(terraform_plan, encode):
    raw = terraform_plan(BUCKET, STORAGE, before=SAFE_STORAGE, actions=["delete", "create"])
    plan = normalize(encode(raw), policy_packs=("storage-hardening", "database-hardening"))
    report = build_report(plan)
    assert {f.rule_id for f in report.findings} == {"TM-GCP-004", "TM-GCP-005", "TM-GCP-006"}
    assert "8 specific policies" in report.limitations[0]
