"""Offline advisory reporting. Findings remain authoritative."""

import html
import re
from datetime import UTC, datetime
from uuid import uuid4

from terramind.policies.engine import evaluate, overall_risk
from terramind.schemas.normalized import NormalizedPlan
from terramind.schemas.report import Report

NOTE_TEXT = {
    "unknown_values": "Some Terraform values are unknown; related risks may be undetectable.",
    "sensitive_values": "Sensitive attributes were excluded from normalization.",
    "unsupported_resource": "Some resource types are outside the four-rule policy scope.",
    "conditional_iam": "IAM conditions were redacted; grant applicability requires review.",
    "unresolved_grants": "Some IAM grants could not be resolved from known non-sensitive facts.",
    "incomplete_plan": "Terraform reports an incomplete, failed or deferred plan; "
    "review the full change locally.",
}


def build_report(plan: NormalizedPlan) -> Report:
    findings = evaluate(plan)
    notes = set(plan.notes).union(*(set(change.notes) for change in plan.changes))
    return Report.model_validate(
        {
            "analysis_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "overall_risk": overall_risk(findings),
            "findings": findings,
            "changed_resources": tuple(
                change.address
                for change in plan.changes
                if change.actions not in (("no-op",), ("read",))
            ),
            "explanation": "Offline deterministic analysis. "
            "No retrieval or model calls were requested.",
            "limitations": (
                "Terramind checks four specific policies; "
                "no known findings is not a guarantee of safety.",
                "Findings describe proposed changes, "
                "not verified deployed exposure or backup status.",
                "Resource aliases conceal original identifiers; correlate by input order locally.",
                *(NOTE_TEXT[note] for note in sorted(notes)),
            ),
        }
    )


def markdown(report: Report) -> str:
    lines = [
        "# Terramind risk report",
        "",
        f"Analysis: `{report.analysis_id}`",
        f"Generated (UTC): {report.timestamp}",
        f"Overall risk: **{report.overall_risk}**",
        f"Policy version: {report.policy_version}",
        f"RAG status: {report.rag_status}; model: {report.model_id or 'none'}",
        "",
        _plain(report.explanation),
        "",
        "## Changed resources",
        "",
    ]
    lines.extend(f"- `{resource}`" for resource in report.changed_resources)
    if not report.changed_resources:
        lines.append("No proposed resource changes.")
    lines.extend(["", "## Findings", ""])
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.rule_id} - {finding.title}",
                "",
                f"**{finding.severity} / {finding.status}** - `{finding.resource}`",
                "",
                finding.rationale,
                "",
                "Evidence:",
                "",
                *(f"- {evidence}" for evidence in finding.evidence),
                "",
                f"Remediation: {finding.remediation}",
                "",
            ]
        )
    if not report.findings:
        lines.extend(["NO_KNOWN_FINDINGS. Review the limitations below.", ""])
    if report.advisory is not None:
        lines.extend(["## AI advisory", "", "Advisory text does not change policy findings.", ""])
        for item in report.advisory.explanations:
            lines.extend(
                [
                    f"- {_plain(item.finding_id)}: {_plain(item.text)}",
                    f"  Sources: {', '.join(item.citation_ids)}",
                ]
            )
        lines.extend(["", "### Recommendations", ""])
        lines.extend(f"- {_plain(text)}" for text in report.advisory.recommendations)
        lines.extend(["", "### Cited synthetic sources", ""])
        for source in report.advisory.sources:
            lines.append(
                f"- `{source.citation_id}`: {_plain(source.title)} "
                f"({_plain(source.doc_id)}, {_plain(source.section_id)}, "
                f"version {_plain(source.version)}, {_plain(source.source_path)}); "
                f"content SHA-256 `{source.content_hash}`"
            )
        lines.append("")
    lines.extend(["## Limitations", "", *(f"- {_plain(text)}" for text in report.limitations), ""])
    return "\n".join(lines)


def _plain(text: str) -> str:
    """Render untrusted advisory prose as text, without active Markdown or HTML."""
    return html.escape(re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text.replace("\n", " ")))
