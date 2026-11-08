"""Deterministic report contracts; model adapters cannot own policy severity."""

from typing import Literal

from terramind.schemas.normalized import ClosedModel

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


class Finding(ClosedModel):
    rule_id: Literal["TM-GCP-001", "TM-GCP-002", "TM-GCP-003", "TM-GCP-004"]
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
    model_id: None = None
    rag_status: Literal["not_requested"] = "not_requested"
    policy_version: Literal["1.0"] = "1.0"
    limitations: tuple[str, ...]
