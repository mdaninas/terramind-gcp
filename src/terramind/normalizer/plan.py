"""Convert Terraform show JSON locally; never retain arbitrary values or identities."""

import ipaddress
import json
import re
from typing import Any

from pydantic import ValidationError

from terramind.errors import InputError
from terramind.normalizer.hardening import bucket_attributes, sql_attributes
from terramind.normalizer.io import parse_json
from terramind.policies.catalog import EXTRA_PACKS, ExtraPack
from terramind.schemas.normalized import (
    MAX_CHANGES,
    MAX_PLAN_BYTES,
    MAX_REQUEST_BYTES,
    Attributes,
    Change,
    NormalizedPlan,
    Note,
    ResourceType,
    serialize_plan,
)

ROLES = frozenset(
    {
        "roles/storage.objectViewer",
        "roles/storage.objectAdmin",
        "roles/storage.admin",
        "roles/storage.objectUser",
        "roles/storage.legacyObjectReader",
        "roles/storage.legacyBucketReader",
        "roles/storage.legacyBucketOwner",
        "roles/owner",
        "roles/editor",
    }
)
PUBLIC = frozenset({"allUsers", "allAuthenticatedUsers"})
ACTIONS = {
    ("no-op",),
    ("create",),
    ("read",),
    ("update",),
    ("delete",),
    ("forget",),
    ("delete", "create"),
    ("create", "delete"),
}


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError("Expected an object in Terraform plan")
    return value


def _list(value: Any, limit: int = 100) -> list[Any]:
    if not isinstance(value, list) or len(value) > limit:
        raise InputError("Expected a bounded list in Terraform plan")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 4096:
        raise InputError("Expected a bounded string in Terraform plan")
    return value


def _optional_list(values: dict[str, Any], key: str) -> list[Any]:
    value = values.get(key)
    return _list(value if value is not None else [])


def _marked(mask: Any, key: str) -> bool:
    if mask is True:
        return True
    if isinstance(mask, dict):
        return bool(mask.get(key, False))
    return False


def _grants(values: dict[str, Any], kind: str) -> list[tuple[str, str, str]]:
    """Identity strings stay in this stack frame, only redacted facts leave it."""
    if not values:
        return []
    if kind.endswith("_policy"):
        policy = parse_json(_string(values.get("policy_data")).encode(), MAX_PLAN_BYTES)
        bindings = _list(policy.get("bindings", []))
    elif kind.endswith("_binding"):
        bindings = [values]
    else:
        bindings = [{**values, "members": [values.get("member")]}]
    grants: list[tuple[str, str, str]] = []
    for binding_value in bindings:
        binding = _dict(binding_value)
        role = _string(binding.get("role"))
        members = _list(binding.get("members"))
        condition = (
            json.dumps(binding["condition"], sort_keys=True) if binding.get("condition") else ""
        )
        for member in members:
            identity = _string(member)
            if role in ROLES:
                grants.append((role, identity, condition))
    if len(grants) > 100:
        raise InputError("Too many risk-relevant IAM grants")
    return grants


def _iam_attributes(
    entry: dict[str, Any],
    kind: str,
    after: dict[str, Any],
    notes: set[Note],
    pap: dict[str, str],
) -> dict[str, Any]:
    change = _dict(entry["change"])
    mask = change.get("after_unknown", {})
    sensitive = change.get("after_sensitive", {})
    keys = ("policy_data",) if kind.endswith("_policy") else ("role", "members", "member")
    if any(_marked(mask, key) or _marked(sensitive, key) for key in keys):
        notes.add("unresolved_grants")
        return {}
    after_grants = _grants(after, kind)
    before = _dict(change.get("before") or {})
    before_sensitive = change.get("before_sensitive", {})
    before_known = bool(before) and not any(_marked(before_sensitive, key) for key in keys)
    before_grants = _grants(before, kind) if before_known else []
    old = set(before_grants)
    # Moving a binding to another scope grants access there even if members are identical.
    scope = "bucket" if kind.startswith("google_storage_bucket_") else "project"
    same_scope = before.get(scope) == after.get(scope)
    grants = []
    for role, member, condition in after_grants:
        if condition:
            notes.add("conditional_iam")
        new: bool | None = (role, member, condition) not in old or not same_scope
        if "create" in change["actions"]:
            new = True
        elif not before_known:
            new = None
        grants.append(
            {
                "role": role,
                "principal": member if member in PUBLIC else "redacted",
                "newly_granted": new,
            }
        )
    attributes: dict[str, Any] = {"grants": grants}
    if scope == "bucket":
        bucket = after.get("bucket")
        attributes["public_access_prevention"] = (
            pap.get(bucket, "unknown")
            if isinstance(bucket, str)
            and not _marked(mask, "bucket")
            and not _marked(sensitive, "bucket")
            else "unknown"
        )
    return attributes


def _firewall_attributes(
    change: dict[str, Any],
    after: dict[str, Any],
    notes: set[Note],
) -> dict[str, Any]:
    unknown = change.get("after_unknown", {})
    sensitive = change.get("after_sensitive", {})

    def known(key: str) -> bool:
        return not (_marked(unknown, key) or _marked(sensitive, key))

    result: dict[str, Any] = {}
    if known("direction"):
        direction = after.get("direction", "INGRESS")
        if direction not in ("INGRESS", "EGRESS", None):
            raise InputError("Invalid firewall direction")
        result["direction"] = direction or "unknown"
    if known("disabled"):
        disabled = after.get("disabled", False)
        if disabled is not None and type(disabled) is not bool:
            raise InputError("Invalid firewall disabled flag")
        result["disabled"] = disabled
    if known("source_ranges"):
        worlds: set[str] = set()
        # Omitted source range facts are not enough to claim public exposure.
        for cidr in _optional_list(after, "source_ranges"):
            try:
                network = ipaddress.ip_network(_string(cidr), strict=False)
            except ValueError:
                raise InputError("Invalid firewall source CIDR") from None
            if network.prefixlen == 0:
                worlds.add(str(network))
        result["source_ranges"] = sorted(worlds)
    if known("allow"):
        rules = []
        for raw_rule in _optional_list(after, "allow"):
            rule = _dict(raw_rule)
            protocol = _string(rule.get("protocol")).lower()
            protocol = {"6": "tcp", "17": "udp", "-1": "all"}.get(protocol, protocol)
            if protocol not in ("tcp", "udp", "all"):
                protocol = "other"
            ports = [_string(port) for port in _optional_list(rule, "ports")]
            rules.append({"protocol": protocol, "ports": ports})
        result["allow"] = rules
    else:
        notes.add("unknown_values")
    return result


def normalize(data: bytes, *, policy_packs: tuple[ExtraPack, ...] = ()) -> NormalizedPlan:
    """Normalize a local plan. Unsupported resource types are retained as opaque aliases."""
    if len(set(policy_packs)) != len(policy_packs) or any(
        pack not in EXTRA_PACKS for pack in policy_packs
    ):
        raise InputError("Invalid or duplicate policy pack selection")
    raw = parse_json(data, MAX_PLAN_BYTES)
    version = raw.get("format_version")
    if not isinstance(version, str) or not re.fullmatch(r"1\.[0-9]+", version):
        raise InputError("Only Terraform JSON format major version 1 is supported")
    if "values" in raw or "resource_changes" not in raw:
        raise InputError("Expected Terraform plan resource_changes; state JSON is not accepted")
    entries = _list(raw["resource_changes"], MAX_CHANGES)
    addresses: set[str] = set()
    pap: dict[str, str] = {}
    prepared: list[dict[str, Any]] = []
    for item in entries:
        entry = _dict(item)
        address = _string(entry.get("address"))
        if not address or address in addresses:
            raise InputError("Resource addresses must be nonempty and unique")
        addresses.add(address)
        kind = _string(entry.get("type"))
        if not re.fullmatch(r"[a-z][a-z0-9_]*", kind):
            raise InputError("Invalid Terraform resource type")
        if entry.get("mode", "managed") not in ("managed", "data"):
            raise InputError("Unsupported Terraform resource mode")
        change = _dict(entry.get("change"))
        actions = _list(change.get("actions"), 2)
        if not all(isinstance(action, str) for action in actions) or tuple(actions) not in ACTIONS:
            raise InputError("Unsupported Terraform action sequence")
        if "after" not in change:
            raise InputError("Terraform change.after is required")
        after = _dict(change.get("after") or {})
        if change.get("after") is not None and not isinstance(change["after"], dict):
            raise InputError("Terraform change.after must be an object or null")
        if change.get("before") is not None:
            _dict(change["before"])
        for key in ("after_unknown", "after_sensitive", "before_sensitive"):
            if key in change and not isinstance(change[key], (dict, bool)):
                raise InputError("Invalid Terraform attribute marker")
        if kind == ResourceType.BUCKET and "delete" not in actions:
            name = after.get("name")
            setting = after.get("public_access_prevention", "unknown")
            if (
                isinstance(name, str)
                and setting in ("enforced", "inherited")
                and not _marked(change.get("after_unknown"), "public_access_prevention")
                and not _marked(change.get("after_sensitive"), "public_access_prevention")
                and not _marked(change.get("after_unknown"), "name")
                and not _marked(change.get("after_sensitive"), "name")
            ):
                pap[name] = setting
        if entry.get("mode", "managed") == "managed":
            prepared.append(entry)
    changes: list[Change] = []
    for index, entry in enumerate(prepared, 1):
        kind = entry["type"]
        resource_type = ResourceType(kind) if kind in ResourceType else ResourceType.UNSUPPORTED
        change = entry["change"]
        after = _dict(change.get("after") or {})
        notes: set[Note] = set()
        if change.get("after_unknown"):
            notes.add("unknown_values")
        if change.get("after_sensitive"):
            notes.add("sensitive_values")
        attributes: dict[str, Any] = {}
        if resource_type == ResourceType.UNSUPPORTED:
            notes.add("unsupported_resource")
        elif "_iam_" in kind and change["actions"] not in (["delete"], ["forget"]):
            attributes = _iam_attributes(entry, kind, after, notes, pap)
        elif resource_type == ResourceType.BUCKET:
            name = after.get("name")
            attributes = {
                "public_access_prevention": pap.get(name, "unknown")
                if isinstance(name, str)
                else "unknown"
            }
        elif resource_type == ResourceType.FIREWALL:
            attributes = _firewall_attributes(change, after, notes)
        if resource_type == ResourceType.BUCKET and "storage-hardening" in policy_packs:
            attributes.update(bucket_attributes(change))
        elif resource_type == ResourceType.SQL and "database-hardening" in policy_packs:
            attributes.update(sql_attributes(change))
        try:
            # JSON validation admits JSON arrays while keeping strict primitive types.
            attrs = Attributes.model_validate_json(json.dumps(attributes))
            changes.append(
                Change(
                    address=f"{resource_type.value}.resource_{index:04d}",
                    type=resource_type,
                    actions=tuple(change["actions"]),
                    attributes=attrs,
                    notes=tuple(sorted(notes)),
                )
            )
        except ValidationError:
            raise InputError("Risk-relevant Terraform attributes are invalid") from None
    plan_notes: tuple[Note, ...] = ()
    if raw.get("complete") is False or raw.get("deferred_changes") or raw.get("errored") is True:
        plan_notes = ("incomplete_plan",)
    plan = NormalizedPlan(
        schema_version="1.1" if policy_packs else "1.0",
        source="local-normalizer",
        **({"policy_packs": policy_packs} if policy_packs else {}),
        changes=tuple(changes),
        notes=plan_notes,
    )
    if len(serialize_plan(plan).encode()) + 1 > MAX_REQUEST_BYTES:
        raise InputError("Normalized payload exceeds 256 KiB; split the plan locally")
    return plan
