"""Reject Terraform promotions that change anything beyond reviewed runtime images."""

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

SERVICES = {
    "dev": {
        "module.cloud_run[0].google_cloud_run_v2_service.api": "terramind-dev",
        "module.eventarc[0].google_cloud_run_v2_service.indexer": "terramind-dev-events",
    },
    "portal": {"google_cloud_run_v2_service.portal": "terramind-portal"},
}
COMPUTED = {
    "conditions",
    "create_time",
    "creator",
    "delete_time",
    "effective_annotations",
    "effective_labels",
    "etag",
    "expire_time",
    "generation",
    "last_modifier",
    "latest_created_revision",
    "latest_ready_revision",
    "observed_generation",
    "reconciling",
    "terminal_condition",
    "traffic_statuses",
    "uid",
    "update_time",
    "uri",
    "urls",
}


def unknown(value: object) -> bool:
    if isinstance(value, dict):
        return any(unknown(item) for item in value.values())
    if isinstance(value, list):
        return any(unknown(item) for item in value)
    return value is True


def check(plan: dict[str, Any], root: str, project: str, image: str) -> int:
    if root not in SERVICES or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project):
        raise ValueError("Invalid promotion target")
    if not re.fullmatch(
        rf"us-central1-docker\.pkg\.dev/{re.escape(project)}/terramind-dev/terramind@sha256:[a-f0-9]{{64}}",
        image,
    ):
        raise ValueError("Use the reviewed immutable image in the existing repository")
    if plan.get("errored") or plan.get("complete") is False or plan.get("deferred_changes"):
        raise ValueError("An incomplete plan cannot be approved")
    seen: set[str] = set()
    changes = 0
    for row in plan["resource_changes"]:
        change = row["change"]
        actions = change["actions"]
        if row.get("mode") == "data" and actions in (["read"], ["no-op"]):
            continue
        address = row["address"]
        if address not in SERVICES[root]:
            if actions != ["no-op"]:
                raise ValueError("An unrelated resource would change")
            continue
        if address in seen or row["type"] != "google_cloud_run_v2_service":
            raise ValueError("Unexpected runtime resource")
        seen.add(address)
        if actions not in (["update"], ["no-op"]):
            raise ValueError("Creation, deletion and replacement are forbidden")
        before, after = copy.deepcopy(change["before"]), copy.deepcopy(change["after"])
        for value in (before, after):
            if value["project"] != project or value["name"] != SERVICES[root][address]:
                raise ValueError("Runtime identity mismatch")
            if value["location"] != "us-central1":
                raise ValueError("Runtime location mismatch")
            containers = value["template"][0]["containers"]
            if len(containers) != 1:
                raise ValueError("Unexpected container count")
        if after["template"][0]["containers"][0]["image"] != image:
            raise ValueError("Image differs from the reviewed digest")
        unresolved = {
            k: v
            for k, v in change.get("after_unknown", {}).items()
            if k not in COMPUTED | {"client", "client_version"}
        }
        if unknown(unresolved):
            raise ValueError("Configuration contains unresolved changes")
        for value in (before, after):
            value["template"][0]["containers"][0].pop("image")
            for key in COMPUTED | {"client", "client_version"}:
                value.pop(key, None)
        if before != after:
            raise ValueError("Runtime configuration would change beyond the image")
        changes += actions == ["update"]
    if seen != set(SERVICES[root]):
        raise ValueError("The full expected runtime plan is required")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root", choices=tuple(SERVICES), required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    try:
        count = check(json.loads(args.plan.read_bytes()), args.root, args.project, args.image)
    except Exception:
        print("Promotion blocked: review the private plan; it is not an image-only update.")
        return 1
    print(f"Image-only promotion plan passed: {count} runtime updates, no creation or deletion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
