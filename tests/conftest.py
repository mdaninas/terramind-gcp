"""Terraform-shaped synthetic objects are built in memory, never saved as raw fixtures."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir():
    return Path(__file__).resolve().parents[1] / "examples" / "normalized-plans"


@pytest.fixture
def terraform_plan():
    def build(
        kind="google_storage_bucket_iam_member",
        after=None,
        before=None,
        actions=None,
        **change_fields,
    ):
        return {
            "format_version": "1.2",
            "resource_changes": [
                {
                    "address": f"module.synthetic.{kind}.private_identifier",
                    "type": kind,
                    "mode": "managed",
                    "change": {
                        "actions": actions or ["create"],
                        "before": before,
                        "after": after
                        if after is not None
                        else {
                            "role": "roles/storage.objectViewer",
                            "member": "allUsers",
                            "bucket": "synthetic-bucket",
                        },
                        **change_fields,
                    },
                }
            ],
        }

    return build


@pytest.fixture
def encode():
    return lambda value: json.dumps(value).encode("utf-8")
