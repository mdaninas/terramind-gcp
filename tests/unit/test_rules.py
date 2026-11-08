import json

import pytest

from terramind.normalizer.io import load_normalized
from terramind.policies.engine import evaluate


def changed(fixture_dir, name, **updates):
    raw = json.loads((fixture_dir / f"{name}.json").read_bytes())
    change = raw["changes"][0]
    change.update(updates)
    return raw, change


@pytest.mark.parametrize(
    ("protocol", "ports", "matches"),
    [
        ("tcp", ["22"], True),
        ("tcp", ["21-23"], True),
        ("tcp", [], True),
        ("tcp", ["3389"], True),
        ("udp", ["3389"], True),
        ("udp", ["22"], False),
        ("all", [], True),
        ("tcp", ["80", "443"], False),
        ("other", [], False),
        ("unknown", [], False),
    ],
)
def test_firewall_ports(fixture_dir, encode, protocol, ports, matches):
    raw, change = changed(fixture_dir, "ssh_open_world")
    change["attributes"]["allow"] = [{"protocol": protocol, "ports": ports}]
    assert bool(evaluate(load_normalized(encode(raw)))) is matches


@pytest.mark.parametrize(
    "update",
    [
        {"direction": "EGRESS"},
        {"direction": "unknown"},
        {"disabled": True},
        {"disabled": None},
        {"source_ranges": []},
        {"allow": []},
    ],
)
def test_firewall_negative(fixture_dir, encode, update):
    raw, change = changed(fixture_dir, "ssh_open_world")
    change["attributes"].update(update)
    assert not evaluate(load_normalized(encode(raw)))


@pytest.mark.parametrize("actions", [["no-op"], ["delete"], ["read"], ["forget"]])
@pytest.mark.parametrize("name", ["public_bucket", "ssh_open_world", "project_owner_grant"])
def test_no_new_exposure_on_non_proposed_change(fixture_dir, encode, actions, name):
    raw, _ = changed(fixture_dir, name, actions=actions)
    assert not evaluate(load_normalized(encode(raw)))


@pytest.mark.parametrize("principal", ["allUsers", "allAuthenticatedUsers", "redacted"])
def test_public_principals(fixture_dir, encode, principal):
    raw, change = changed(fixture_dir, "public_bucket")
    change["attributes"]["grants"][0]["principal"] = principal
    assert bool(evaluate(load_normalized(encode(raw)))) is (principal != "redacted")


@pytest.mark.parametrize("name", ["public_bucket", "project_owner_grant"])
def test_existing_and_unknown_grants(fixture_dir, encode, name):
    raw, change = changed(fixture_dir, name)
    grant = change["attributes"]["grants"][0]
    grant["newly_granted"] = False
    assert not evaluate(load_normalized(encode(raw)))
    grant["newly_granted"] = None
    assert evaluate(load_normalized(encode(raw)))[0].status == "REVIEW"


@pytest.mark.parametrize("role", ["roles/editor", "roles/owner"])
def test_project_basic_roles(fixture_dir, encode, role):
    raw, change = changed(fixture_dir, "project_owner_grant")
    change["attributes"]["grants"][0]["role"] = role
    assert evaluate(load_normalized(encode(raw)))[0].severity == "HIGH"
    change["attributes"]["grants"][0]["role"] = "roles/storage.objectViewer"
    assert not evaluate(load_normalized(encode(raw)))


@pytest.mark.parametrize(
    "kind",
    [
        "google_storage_bucket",
        "google_sql_database_instance",
        "google_sql_database",
        "google_compute_disk",
        "google_compute_region_disk",
        "google_firestore_database",
        "google_bigtable_instance",
        "google_spanner_instance",
        "google_spanner_database",
        "google_filestore_instance",
    ],
)
@pytest.mark.parametrize("actions", [["delete"], ["delete", "create"], ["create", "delete"]])
def test_persistent_delete_and_replace(fixture_dir, encode, kind, actions):
    raw, _ = changed(
        fixture_dir, "bucket_delete", type=kind, address=f"{kind}.resource_0004", actions=actions
    )
    finding = evaluate(load_normalized(encode(raw)))[0]
    assert finding.rule_id == "TM-GCP-004"
    assert finding.status == "REVIEW"
    assert "not established" in finding.rationale


def test_no_delete_on_update_or_unsupported(fixture_dir, encode):
    raw, change = changed(fixture_dir, "bucket_delete", actions=["update"])
    assert not evaluate(load_normalized(encode(raw)))
    change.update(
        actions=["delete"],
        type="unsupported_resource",
        address="unsupported_resource.resource_0004",
    )
    assert not evaluate(load_normalized(encode(raw)))
