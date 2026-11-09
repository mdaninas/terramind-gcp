"""Small server-rendered report pages with escaped text and no remote assets."""

from html import escape

from terramind.llm.contracts import finding_id
from terramind.reports.store import valid_id
from terramind.schemas.normalized import NormalizedPlan, serialize_plan
from terramind.schemas.report import Report


def _items(items: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def report_page(
    report: Report, *, mode: str, sample: NormalizedPlan | None = None, retention_hours: int = 24
) -> str:
    advisory = report.advisory
    explanations = {item.finding_id: item for item in advisory.explanations} if advisory else {}
    findings = ""
    for finding in report.findings:
        explanation = explanations.get(finding_id(finding))
        narrative = (
            '<div class="advisory"><h4>AI advisory</h4>'
            f"<p>{escape(explanation.text)}</p>"
            f'<p class="muted">Sources: {escape(", ".join(explanation.citation_ids))}</p></div>'
            if explanation
            else ""
        )
        findings += (
            '<article class="finding">'
            f'<div class="eyebrow">{escape(finding.rule_id)} / {escape(finding.status)}</div>'
            f"<h3>{escape(finding.title)}</h3>"
            f'<p><span class="badge">{escape(finding.severity)}</span> '
            f"<code>{escape(finding.resource)}</code></p>"
            f"<p>{escape(finding.rationale)}</p>"
            f"<h4>Observed facts</h4>{_items(finding.evidence)}"
            f"<h4>Remediation</h4><p>{escape(finding.remediation)}</p>{narrative}</article>"
        )
    sources = ""
    if advisory:
        sources = '<section><h2>Supporting runbooks</h2><div class="sources">'
        for source in advisory.sources:
            sources += (
                f"<article><h3>{escape(source.title)}</h3><p><code>"
                f"{escape(source.citation_id)}</code></p><p>Version {escape(source.version)}"
                f" / {escape(source.source_path)}</p><details><summary>Source provenance</summary>"
                f"<p>Content SHA-256: <code>{escape(source.content_hash)}</code></p>"
                f"<p>Chunk: <code>{escape(source.chunk_id)}</code></p></details></article>"
            )
        sources += "</div></section>"
    actions = ""
    if sample:
        actions = (
            '<button id="analyze" type="button">Analyze synthetic sample</button>'
            '<p id="status" role="status" aria-live="polite">'
            "Preview only. Select analyze to create a report.</p>"
            f'<pre id="synthetic-sample" hidden>{escape(serialize_plan(sample))}</pre>'
            '<script src="/assets/demo.js" defer></script>'
        )
    elif valid_id(report.analysis_id):
        prefix = f"/v1/analyses/{report.analysis_id}"
        actions = (
            f'<a class="button" href="{prefix}/markdown">Download Markdown</a> '
            f'<a class="button secondary" href="{prefix}">View JSON</a>'
            f'<p class="muted">Analysis <code>{report.analysis_id}</code></p>'
        )
    context = (
        "Cloud mode: retrieval and AI are requested when findings exist."
        if mode == "cloud"
        else "Offline mode: deterministic analysis, no cloud or model calls."
    )
    recommendations = (
        advisory.recommendations
        if advisory
        else tuple(dict.fromkeys(item.remediation for item in report.findings))
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Terramind | Terraform risk report</title>"
        '<link rel="stylesheet" href="/assets/report.css"></head><body>'
        '<header><a href="/demo" class="brand">Terramind</a>'
        '<span class="muted">Terraform change intelligence</span></header><main>'
        '<div class="eyebrow">Synthetic portfolio demonstration</div>'
        "<h1>Understand the risk<br>before infrastructure changes.</h1>"
        '<p class="intro">Deterministic findings, supporting evidence '
        "and advisory explanations.</p>"
        f'<div class="toolbar">{actions}</div><p class="muted">{escape(context)}</p>'
        '<section class="summary" aria-label="Risk summary">'
        f"<div><span>Overall risk</span><strong>{escape(report.overall_risk)}</strong></div>"
        f"<div><span>Findings</span><strong>{len(report.findings)}</strong></div>"
        f"<div><span>Changed resources</span><strong>{len(report.changed_resources)}</strong></div>"
        '<div><span>Retrieval</span><strong class="small">'
        f"{escape(report.rag_status)}</strong></div>"
        "</section><section><h2>Analysis summary</h2>"
        f'<p>{escape(report.explanation)}</p><p class="muted">Model: '
        f"{escape(report.model_id or 'none')} / Policy "
        f"{escape(report.policy_version)}</p></section>"
        f"<section><h2>Changed resources</h2>{_items(report.changed_resources)}</section>"
        "<section><h2>Findings</h2>"
        f"{findings or '<p>No known findings. Review the limitations.</p>'}"
        f"</section>{sources}<section><h2>Recommendations</h2>{_items(recommendations)}</section>"
        f"<section><h2>Limitations</h2>{_items(report.limitations)}</section>"
        f"<footer>Synthetic data only. Reports expire after at most {retention_hours} hours. "
        "Local reports are discarded on restart. Terramind never approves or applies "
        "infrastructure changes.</footer></main></body></html>"
    )
