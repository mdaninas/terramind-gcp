"""Deterministic report contracts; model adapters cannot own policy severity."""

from typing import Annotated, Literal

from pydantic import Field

from terramind.llm.contracts import Advisory
from terramind.policies.catalog import PackName, RuleId
from terramind.schemas.normalized import ClosedModel

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


class Finding(ClosedModel):
    rule_id: RuleId
    resource: str
    severity: Severity = "HIGH"
    title: str
    rationale: str
    evidence: tuple[str, ...]
    remediation: str
    status: Literal["FAIL", "REVIEW"]


class Report(ClosedModel):
    analysis_id: str
    timestamp: str
    overall_risk: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NO_KNOWN_FINDINGS"]
    findings: tuple[Finding, ...]
    changed_resources: tuple[str, ...]
    explanation: str
    citations: tuple[str, ...] = ()
    model_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,79}$")] | None = None
    rag_status: Literal["not_requested", "available", "partial", "unavailable"] = "not_requested"
    advisory: Advisory | None = None
    policy_version: Literal["1.0", "1.1"] = "1.0"
    policy_packs: tuple[PackName, ...] = ("gcp-core",)
    limitations: tuple[str, ...]
