"""Fixed fabricated examples shared by the portal and contract tests."""

import json

from terramind.schemas.normalized import NormalizedPlan


def hardening_sample(pack: str) -> NormalizedPlan:
    if pack == "storage-hardening":
        kind = "google_storage_bucket"
        attributes: dict[str, object] = {
            "public_access_prevention": "inherited",
            "uniform_bucket_level_access": False,
            "newly_disabled_uniform_access": True,
            "newly_inherited_prevention": True,
        }
    elif pack == "database-hardening":
        kind = "google_sql_database_instance"
        attributes = {
            "ipv4_enabled": True,
            "world_authorized_network": True,
            "newly_world_accessible": True,
            "ssl_mode": "ALLOW_UNENCRYPTED_AND_ENCRYPTED",
            "newly_unencrypted": True,
        }
    else:
        raise ValueError("Unknown hardening sample")
    return NormalizedPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.1",
                "source": "synthetic-demo",
                "policy_packs": [pack],
                "changes": [
                    {
                        "address": f"{kind}.resource_0001",
                        "type": kind,
                        "actions": ["create"],
                        "attributes": attributes,
                    }
                ],
            }
        )
    )
