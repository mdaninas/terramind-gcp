"""Closed identifiers for the mandatory core and optional hardening packs."""

from typing import Literal

RuleId = Literal[
    "TM-GCP-001",
    "TM-GCP-002",
    "TM-GCP-003",
    "TM-GCP-004",
    "TM-GCP-005",
    "TM-GCP-006",
    "TM-GCP-007",
    "TM-GCP-008",
]
ExtraPack = Literal["storage-hardening", "database-hardening"]
PackName = Literal["gcp-core", "storage-hardening", "database-hardening"]
CORE_RULES = ("TM-GCP-001", "TM-GCP-002", "TM-GCP-003", "TM-GCP-004")
EXTRA_PACKS: tuple[ExtraPack, ...] = ("storage-hardening", "database-hardening")
PACK_RULES = {
    "gcp-core": CORE_RULES,
    "storage-hardening": ("TM-GCP-005", "TM-GCP-006"),
    "database-hardening": ("TM-GCP-007", "TM-GCP-008"),
}
