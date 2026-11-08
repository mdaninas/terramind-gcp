"""Schema v1.0: only bounded, risk-relevant facts may cross the trust boundary."""

import re
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_PLAN_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = 256 * 1024
MAX_CHANGES = 100


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ResourceType(StrEnum):
    BUCKET = "google_storage_bucket"
    BUCKET_MEMBER = "google_storage_bucket_iam_member"
    BUCKET_BINDING = "google_storage_bucket_iam_binding"
    BUCKET_POLICY = "google_storage_bucket_iam_policy"
    PROJECT_MEMBER = "google_project_iam_member"
    PROJECT_BINDING = "google_project_iam_binding"
    PROJECT_POLICY = "google_project_iam_policy"
    FIREWALL = "google_compute_firewall"
    SQL = "google_sql_database_instance"
    SQL_DATABASE = "google_sql_database"
    DISK = "google_compute_disk"
    REGION_DISK = "google_compute_region_disk"
    FIRESTORE = "google_firestore_database"
    BIGTABLE = "google_bigtable_instance"
    SPANNER = "google_spanner_instance"
    SPANNER_DATABASE = "google_spanner_database"
    FILESTORE = "google_filestore_instance"
    UNSUPPORTED = "unsupported_resource"


Role = Literal[
    "roles/storage.objectViewer",
    "roles/storage.objectAdmin",
    "roles/storage.admin",
    "roles/storage.objectUser",
    "roles/storage.legacyObjectReader",
    "roles/storage.legacyBucketReader",
    "roles/storage.legacyBucketOwner",
    "roles/owner",
    "roles/editor",
]
Principal = Literal["allUsers", "allAuthenticatedUsers", "redacted"]
Action = Literal["no-op", "create", "read", "update", "delete", "forget"]
Note = Literal[
    "unknown_values",
    "sensitive_values",
    "unsupported_resource",
    "conditional_iam",
    "unresolved_grants",
    "incomplete_plan",
]


class Grant(ClosedModel):
    role: Role
    principal: Principal
    newly_granted: bool | None


class Allow(ClosedModel):
    protocol: Literal["tcp", "udp", "all", "other", "unknown"]
    ports: tuple[
        Annotated[str, Field(pattern=r"^[0-9]{1,5}(?:-[0-9]{1,5})?$", max_length=11)], ...
    ] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def valid_ports(self) -> Self:
        for port in self.ports:
            if not re.fullmatch(r"[0-9]{1,5}(?:-[0-9]{1,5})?", port):
                raise ValueError("Invalid port specification")
            parts = [int(value) for value in port.split("-")]
            if not all(0 <= value <= 65535 for value in parts) or parts[0] > parts[-1]:
                raise ValueError("Invalid port range")
        return self


class Attributes(ClosedModel):
    grants: tuple[Grant, ...] = Field(default=(), max_length=100)
    public_access_prevention: Literal["enforced", "inherited", "unknown"] = "unknown"
    direction: Literal["INGRESS", "EGRESS", "unknown"] = "unknown"
    disabled: bool | None = None
    source_ranges: tuple[Literal["0.0.0.0/0", "::/0"], ...] = Field(default=(), max_length=2)
    allow: tuple[Allow, ...] = Field(default=(), max_length=100)


def _change_schema(schema: dict[str, Any]) -> None:
    """Mirror resource-specific structural validators in the exported JSON Schema."""
    conditions: list[dict[str, Any]] = []
    for kind in ResourceType:
        allowed = _attribute_fields(kind)
        conditions.append(
            {
                "if": {"properties": {"type": {"const": kind.value}}},
                "then": {
                    "properties": {
                        "address": {"pattern": rf"^{kind.value}\.resource_[0-9]{{4}}$"},
                        "attributes": {
                            "propertyNames": {"enum": sorted(allowed)} if allowed else False
                        },
                    }
                },
            }
        )
    schema["allOf"] = conditions
    schema["properties"]["actions"]["enum"] = [
        ["no-op"],
        ["create"],
        ["read"],
        ["update"],
        ["delete"],
        ["forget"],
        ["delete", "create"],
        ["create", "delete"],
    ]


def _attribute_fields(kind: ResourceType) -> set[str]:
    if "_iam_" in kind:
        return (
            {"grants", "public_access_prevention"}
            if kind.startswith("google_storage_bucket_")
            else {"grants"}
        )
    if kind == ResourceType.BUCKET:
        return {"public_access_prevention"}
    if kind == ResourceType.FIREWALL:
        return {"direction", "disabled", "source_ranges", "allow"}
    return set()


class Change(ClosedModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        json_schema_extra=_change_schema,
    )
    address: str = Field(pattern=r"^[a-z_]+\.resource_[0-9]{4}$", max_length=100)
    type: ResourceType
    actions: tuple[Action, ...] = Field(min_length=1, max_length=2)
    attributes: Attributes
    notes: tuple[Note, ...] = Field(default=(), max_length=6)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        valid = {
            ("no-op",),
            ("create",),
            ("read",),
            ("update",),
            ("delete",),
            ("forget",),
            ("delete", "create"),
            ("create", "delete"),
        }
        if self.actions not in valid:
            raise ValueError("Unsupported action sequence")
        if not self.address.startswith(f"{self.type.value}."):
            raise ValueError("Address alias must match resource type")
        if self.attributes.model_fields_set - _attribute_fields(self.type):
            raise ValueError("Attributes do not match resource type")
        return self


class NormalizedPlan(ClosedModel):
    schema_version: Literal["1.0"]
    source: Literal["synthetic-demo", "local-normalizer"]
    changes: tuple[Change, ...] = Field(max_length=MAX_CHANGES)
    notes: tuple[Note, ...] = Field(default=(), max_length=6)

    @model_validator(mode="after")
    def unique_addresses(self) -> Self:
        addresses = [change.address for change in self.changes]
        if len(addresses) != len(set(addresses)):
            raise ValueError("Duplicate resource aliases")
        return self


def serialize_plan(plan: NormalizedPlan) -> str:
    # Exclude unset attributes so type-specific allowlists remain round-trippable.
    return plan.model_dump_json(indent=2, exclude_unset=True)
