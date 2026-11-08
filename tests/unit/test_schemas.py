import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from terramind.errors import InputError
from terramind.normalizer.io import load_normalized
from terramind.normalizer.plan import normalize
from terramind.reports.render import build_report
from terramind.schemas.normalized import serialize_plan


def test_committed_schemas_are_valid_and_cover_samples(fixture_dir):
    root = Path(__file__).resolve().parents[2]
    plan_schema = json.loads((root / "schemas/normalized-plan.v1.schema.json").read_text())
    report_schema = json.loads((root / "schemas/report.v1.schema.json").read_text())
    Draft202012Validator.check_schema(plan_schema)
    Draft202012Validator.check_schema(report_schema)
    for fixture in fixture_dir.glob("*.json"):
        data = fixture.read_bytes()
        Draft202012Validator(plan_schema).validate(json.loads(data))
        report = build_report(load_normalized(data))
        Draft202012Validator(report_schema).validate(report.model_dump(mode="json"))


@pytest.mark.parametrize("field", ["schema_version", "source"])
def test_version_and_source_are_explicit(fixture_dir, encode, field):
    raw = json.loads((fixture_dir / "no_changes.json").read_bytes())
    raw.pop(field)
    with pytest.raises(InputError):
        load_normalized(encode(raw))


def test_normalizer_emits_explicit_contract(terraform_plan, encode):
    output = json.loads(serialize_plan(normalize(encode(terraform_plan()))))
    assert output["schema_version"] == "1.0"
    assert output["source"] == "local-normalizer"


def test_schema_rejects_wrong_type_and_actions(fixture_dir):
    schema = json.loads(Path("schemas/normalized-plan.v1.schema.json").read_text())
    validator = Draft202012Validator(schema)
    original = json.loads((fixture_dir / "bucket_delete.json").read_bytes())
    value = copy.deepcopy(original)
    value["changes"][0]["attributes"]["allow"] = []
    assert list(validator.iter_errors(value))
    value = copy.deepcopy(original)
    value["changes"][0]["actions"] = ["update", "delete"]
    assert list(validator.iter_errors(value))
    value = copy.deepcopy(original)
    value["changes"][0]["address"] = "google_compute_disk.resource_0001"
    assert list(validator.iter_errors(value))


def test_normalized_size_is_bounded_after_expansion(terraform_plan, encode):
    after = {
        "role": "roles/editor",
        "members": [f"user:synthetic-{i}@example.invalid" for i in range(50)],
    }
    raw = terraform_plan("google_project_iam_binding", after)
    template = raw["resource_changes"][0]
    raw["resource_changes"] = [
        dict(template, address=f"synthetic.resource_{i}") for i in range(100)
    ]
    with pytest.raises(InputError, match="Normalized payload exceeds"):
        normalize(encode(raw))


def test_condition_removed_is_newly_granted(terraform_plan, encode):
    after = {"role": "roles/editor", "member": "user:synthetic@example.invalid"}
    before = dict(after, condition=[{"expression": "synthetic-time-limit"}])
    plan = normalize(encode(terraform_plan("google_project_iam_member", after, before, ["update"])))
    assert plan.changes[0].attributes.grants[0].newly_granted is True
    assert build_report(plan).findings[0].rule_id == "TM-GCP-003"
