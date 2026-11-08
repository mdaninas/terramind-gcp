"""Stable evaluation order and maximum deterministic severity."""

from terramind.policies.rules import (
    open_admin_ports,
    persistent_deletion,
    project_basic_roles,
    public_bucket,
)
from terramind.schemas.normalized import NormalizedPlan
from terramind.schemas.report import Finding, Severity

RULES = (public_bucket, open_admin_ports, project_basic_roles, persistent_deletion)
SEVERITY_ORDER: dict[Severity, int] = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def evaluate(plan: NormalizedPlan) -> tuple[Finding, ...]:
    return tuple(
        finding
        for change in sorted(plan.changes, key=lambda item: item.address)
        for rule in RULES
        for finding in rule(change)
    )


def overall_risk(findings: tuple[Finding, ...]) -> Severity | str:
    return max(
        (finding.severity for finding in findings),
        key=SEVERITY_ORDER.__getitem__,
        default="NO_KNOWN_FINDINGS",
    )
