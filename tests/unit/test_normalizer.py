import copy
import json

import pytest

from terramind.errors import InputError
from terramind.normalizer.io import load_normalized, parse_json, read_bounded
from terramind.normalizer.plan import normalize
from terramind.policies.engine import evaluate
from terramind.reports.render import build_report
from terramind.schemas.normalized import MAX_PLAN_BYTES, MAX_REQUEST_BYTES, serialize_plan


def test_roundtrip_and_privacy(terraform_plan, encode):
    raw = terraform_plan()
    raw["variables"] = {"password": {"value": "synthetic-canary"}}
    raw["outputs"] = {"secret": "synthetic-canary"}
    raw["resource_changes"][0]["change"]["after"]["labels"] = {"team": "synthetic-canary"}
    plan = normalize(encode(raw))
    serialized = serialize_plan(plan)
    assert load_normalized(serialized.encode()) == plan
    assert "private_identifier" not in serialized
    assert "synthetic-canary" not in serialized
    assert "synthetic-bucket" not in serialized
    assert evaluate(plan)[0].rule_id == "TM-GCP-001"


@pytest.mark.parametrize(
    "data",
    [
        b"{",
        b"[]",
        b"null",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b"\xff",
        b'{"a":' + b"[" * 1100 + b"0" + b"]" * 1100 + b"}",
    ],
)
def test_bad_json_is_safe(data):
    with pytest.raises(InputError):
        parse_json(data, MAX_PLAN_BYTES)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(format_version="2.0"),
        lambda p: p.update(format_version=None),
        lambda p: p.pop("resource_changes"),
        lambda p: p.update(values={}),
        lambda p: p.update(resource_changes={}),
        lambda p: p.update(resource_changes=[{}]),
        lambda p: p["resource_changes"][0].update(type="bad-type"),
        lambda p: p["resource_changes"][0].update(mode="invalid"),
        lambda p: p["resource_changes"][0].update(address=""),
        lambda p: p["resource_changes"][0].update(change=[]),
        lambda p: p["resource_changes"][0]["change"].update(actions=["apply"]),
        lambda p: p["resource_changes"][0]["change"].update(actions=[{}]),
        lambda p: p["resource_changes"][0]["change"].update(after=[]),
        lambda p: p["resource_changes"][0]["change"].pop("after"),
        lambda p: p["resource_changes"][0]["change"].update(before=[]),
        lambda p: p["resource_changes"][0]["change"].update(after_unknown="wrong"),
        lambda p: p["resource_changes"][0]["change"]["after"].update(member=3),
        lambda p: p["resource_changes"][0]["change"]["after"].update(role="x" * 5000),
    ],
)
def test_malformed_plan(terraform_plan, encode, mutation):
    raw = terraform_plan()
    mutation(raw)
    with pytest.raises(InputError):
        normalize(encode(raw))


def test_bounds_and_io(tmp_path, terraform_plan, encode):
    with pytest.raises(InputError, match="byte limit"):
        normalize(b" " * (MAX_PLAN_BYTES + 1))
    with pytest.raises(InputError, match="byte limit"):
        load_normalized(b" " * (MAX_REQUEST_BYTES + 1))
    raw = terraform_plan()
    raw["resource_changes"] *= 101
    with pytest.raises(InputError, match="bounded list"):
        normalize(encode(raw))
    path = tmp_path / "oversized.json"
    path.write_bytes(b"abcd")
    assert read_bounded(path, 4) == b"abcd"
    with pytest.raises(InputError, match="byte limit"):
        read_bounded(path, 3)
    with pytest.raises(InputError, match="Unable to read"):
        read_bounded(tmp_path / "missing", 100)


def test_duplicates(terraform_plan, encode):
    raw = terraform_plan()
    raw["resource_changes"] *= 2
    with pytest.raises(InputError, match="unique"):
        normalize(encode(raw))


def test_pap_exact_bucket_correlation(terraform_plan, encode):
    raw = terraform_plan()
    bucket = terraform_plan(
        "google_storage_bucket",
        {
            "name": "synthetic-bucket",
            "public_access_prevention": "enforced",
        },
    )["resource_changes"][0]
    raw["resource_changes"].append(bucket)
    findings = evaluate(normalize(encode(raw)))
    assert findings[0].status == "REVIEW"
    bucket["change"]["after"]["name"] = "unrelated-synthetic-bucket"
    assert evaluate(normalize(encode(raw)))[0].status == "FAIL"
    bucket["change"]["after"]["name"] = "synthetic-bucket"
    bucket["change"]["after_unknown"] = {"public_access_prevention": True}
    assert evaluate(normalize(encode(raw)))[0].status == "FAIL"


@pytest.mark.parametrize("marker", ["after_unknown", "after_sensitive"])
@pytest.mark.parametrize("resource_index,field", [(0, "bucket"), (1, "name")])
def test_pap_link_requires_known_nonsensitive_identity(
    terraform_plan, encode, marker, resource_index, field
):
    raw = terraform_plan()
    raw["resource_changes"].append(
        terraform_plan(
            "google_storage_bucket",
            {
                "name": "synthetic-bucket",
                "public_access_prevention": "enforced",
            },
        )["resource_changes"][0]
    )
    raw["resource_changes"][resource_index]["change"][marker] = {field: True}
    assert evaluate(normalize(encode(raw)))[0].status == "FAIL"


@pytest.mark.parametrize(
    "after",
    [
        {"source_ranges": False},
        {"source_ranges": ""},
        {"allow": {}},
        {"allow": [{"protocol": "tcp", "ports": False}]},
    ],
)
def test_empty_values_still_require_correct_shape(terraform_plan, encode, after):
    with pytest.raises(InputError):
        normalize(encode(terraform_plan("google_compute_firewall", after)))


@pytest.mark.parametrize("marker", ["after_unknown", "after_sensitive"])
def test_unknown_and_sensitive_grants_excluded(terraform_plan, encode, marker):
    plan = normalize(encode(terraform_plan(**{marker: {"member": True}})))
    assert not plan.changes[0].attributes.grants
    assert "unresolved_grants" in plan.changes[0].notes
    assert "could not be resolved" in " ".join(build_report(plan).limitations)


def test_existing_grant_not_new(terraform_plan, encode):
    values = {
        "bucket": "synthetic-bucket",
        "role": "roles/storage.objectViewer",
        "member": "allUsers",
    }
    plan = normalize(encode(terraform_plan(after=values, before=values, actions=["update"])))
    assert plan.changes[0].attributes.grants[0].newly_granted is False
    assert not evaluate(plan)
    moved = dict(values, bucket="another-synthetic-bucket")
    assert evaluate(
        normalize(encode(terraform_plan(after=moved, before=values, actions=["update"])))
    )


def test_sensitive_prior_grant_is_review(terraform_plan, encode):
    raw = terraform_plan(actions=["update"], before_sensitive={"member": True})
    finding = evaluate(normalize(encode(raw)))[0]
    assert finding.status == "REVIEW"


@pytest.mark.parametrize("kind", ["google_project_iam_binding", "google_project_iam_policy"])
def test_bindings_policy_and_membership_diff(terraform_plan, encode, kind):
    binding = {"role": "roles/editor", "members": ["user:synthetic-one@example.invalid"]}
    after_binding = dict(
        binding, members=[*binding["members"], "user:synthetic-two@example.invalid"]
    )
    before = (
        binding
        if kind.endswith("_binding")
        else {"policy_data": json.dumps({"bindings": [binding]})}
    )
    after = (
        after_binding
        if kind.endswith("_binding")
        else {"policy_data": json.dumps({"bindings": [after_binding]})}
    )
    plan = normalize(encode(terraform_plan(kind, after, before, ["update"])))
    grants = plan.changes[0].attributes.grants
    assert [grant.newly_granted for grant in grants] == [False, True]
    assert all(grant.principal == "redacted" for grant in grants)
    assert evaluate(plan)[0].rule_id == "TM-GCP-003"


def test_conditional_iam(terraform_plan, encode):
    after = {
        "role": "roles/owner",
        "member": "user:synthetic@example.invalid",
        "condition": [{"expression": "synthetic-condition"}],
    }
    plan = normalize(encode(terraform_plan("google_project_iam_member", after)))
    assert evaluate(plan)[0].status == "REVIEW"
    assert "synthetic-condition" not in serialize_plan(plan)


def test_unsupported_data_and_incomplete(terraform_plan, encode):
    raw = terraform_plan("synthetic_unrecognized_resource", {"labels": {"a": "b"}})
    raw["complete"] = False
    plan = normalize(encode(raw))
    assert plan.changes[0].type == "unsupported_resource"
    assert "incomplete_plan" in plan.notes
    assert "unsupported_resource" in plan.changes[0].notes
    raw["resource_changes"][0]["mode"] = "data"
    assert not normalize(encode(raw)).changes


def test_firewall_normalization(terraform_plan, encode):
    after = {
        "source_ranges": ["10.0.0.0/8", "192.0.2.8/0", "::/0"],
        "allow": [{"protocol": "6", "ports": ["20-25"]}],
    }
    plan = normalize(encode(terraform_plan("google_compute_firewall", after)))
    attrs = plan.changes[0].attributes
    assert attrs.source_ranges == ("0.0.0.0/0", "::/0")
    assert attrs.allow[0].protocol == "tcp"
    assert evaluate(plan)[0].rule_id == "TM-GCP-002"
    assert "10.0.0.0" not in serialize_plan(plan)


@pytest.mark.parametrize(
    "after",
    [
        {"direction": "wrong"},
        {"disabled": "false"},
        {"source_ranges": ["invalid"]},
        {"allow": [{"protocol": "tcp", "ports": ["25-20"]}]},
        {"allow": [{"protocol": "tcp", "ports": ["65536"]}]},
        {"allow": [{"protocol": "tcp", "ports": ["password=synthetic"]}]},
    ],
)
def test_invalid_firewall(terraform_plan, encode, after):
    with pytest.raises(InputError):
        normalize(encode(terraform_plan("google_compute_firewall", after)))


def test_unknown_firewall_allow_does_not_infer_ports(terraform_plan, encode):
    raw = terraform_plan(
        "google_compute_firewall", {"source_ranges": ["0.0.0.0/0"]}, after_unknown={"allow": True}
    )
    plan = normalize(encode(raw))
    assert not evaluate(plan)
    assert "unknown_values" in plan.changes[0].notes


def test_no_change_and_delete(terraform_plan, encode):
    assert not normalize(encode({"format_version": "1.0", "resource_changes": []})).changes
    raw = terraform_plan("google_storage_bucket", {}, actions=["delete"])
    raw["resource_changes"][0]["change"]["after"] = None
    assert evaluate(normalize(encode(raw)))[0].rule_id == "TM-GCP-004"


def test_normalized_schema_rejects_arbitrary_fields(fixture_dir, encode):
    original = json.loads((fixture_dir / "public_bucket.json").read_bytes())
    for location in ("root", "change", "attributes", "grant"):
        value = copy.deepcopy(original)
        targets = {
            "root": value,
            "change": value["changes"][0],
            "attributes": value["changes"][0]["attributes"],
            "grant": value["changes"][0]["attributes"]["grants"][0],
        }
        targets[location]["password"] = "synthetic-canary"
        with pytest.raises(InputError, match="schema validation"):
            load_normalized(encode(value))
