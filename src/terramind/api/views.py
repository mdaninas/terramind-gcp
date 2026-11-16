"""Server-rendered report workspace with escaped text and no remote assets."""

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
    for index, finding in enumerate(report.findings, 1):
        explanation = explanations.get(finding_id(finding))
        narrative = (
            '<div class="advisory"><h4>AI advisory</h4>'
            f"<p>{escape(explanation.text)}</p>"
            f'<p class="muted">Sources: {escape(", ".join(explanation.citation_ids))}</p></div>'
            if explanation
            else ""
        )
        severity_class = escape(finding.severity.lower(), quote=True)
        findings += (
            f'<article class="finding severity-{severity_class}">'
            '<div class="finding-header"><div class="finding-reference">'
            f'<span class="finding-number">{index:02}</span>'
            f'<span class="eyebrow">{escape(finding.rule_id)}</span></div>'
            '<div class="finding-status">'
            f'<span class="status-pill">{escape(finding.status)}</span>'
            f'<span class="badge severity-{severity_class}">'
            f"{escape(finding.severity)}</span></div></div>"
            f"<h3>{escape(finding.title)}</h3>"
            f'<p class="resource-reference"><code>{escape(finding.resource)}</code></p>'
            f'<p class="finding-rationale">{escape(finding.rationale)}</p>'
            '<div class="finding-detail"><div class="evidence"><h4>Observed facts</h4>'
            f'{_items(finding.evidence)}</div><div class="remediation"><h4>Remediation</h4>'
            f"<p>{escape(finding.remediation)}</p></div></div>{narrative}</article>"
        )
    sources = ""
    if advisory:
        sources = (
            '<section id="sources"><div class="section-heading"><div>'
            '<div class="eyebrow">Grounded context</div><h2>Supporting runbooks</h2></div>'
            f'<span class="count">{len(advisory.sources)} sources</span></div>'
            '<div class="sources">'
        )
        for source in advisory.sources:
            sources += (
                '<article><span class="eyebrow">Runbook evidence</span>'
                f'<h3>{escape(source.title)}</h3><p><code class="source-id">'
                f'{escape(source.citation_id)}</code></p><p class="muted">'
                f"Version {escape(source.version)}"
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
            f'<p class="analysis-id">Analysis <code>{report.analysis_id}</code></p>'
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
    recommendation_items = (
        _items(recommendations) if recommendations else "<p>No policy remediation selected.</p>"
    )
    severity_class = escape(report.overall_risk.lower(), quote=True)
    risk_label = (
        "No known findings"
        if report.overall_risk == "NO_KNOWN_FINDINGS"
        else escape(report.overall_risk)
    )
    retrieval_label = escape(report.rag_status.replace("_", " ").capitalize())
    report_label = "Report preview" if sample else "Risk report"
    source_navigation = '<a href="#sources">Sources</a>' if advisory else ""
    no_findings = (
        '<div class="empty-state"><span class="eyebrow">Policy results</span>'
        "<h3>No known findings</h3><p>No supported policy matched this change set. "
        "Review the limitations before deciding how to proceed.</p></div>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Terramind | Terraform risk report</title>"
        '<link rel="icon" href="/favicon.ico" type="image/vnd.microsoft.icon">'
        '<link rel="icon" href="/assets/terramind-icon.png" type="image/png" sizes="512x512">'
        '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png" sizes="180x180">'
        '<link rel="stylesheet" href="/assets/report.css"></head><body>'
        '<a class="skip-link" href="#main-content">Skip to report</a>'
        '<header><a href="/demo" class="brand" aria-label="Terramind analysis preview">'
        '<img src="/assets/terramind-logo.png" alt="Terramind" width="216" height="72"></a>'
        '<div class="header-context"><span>Terraform change intelligence</span>'
        '<span class="workspace-label">Analysis workspace</span></div></header>'
        '<main id="main-content" tabindex="-1">'
        '<nav class="breadcrumb" aria-label="Breadcrumb">'
        '<a href="/demo">Analysis</a><span aria-hidden="true">/</span>'
        f'<span aria-current="page">{report_label}</span></nav>'
        '<div class="report-heading"><div><div class="eyebrow">'
        "Synthetic infrastructure analysis</div><h1>Terraform change report</h1>"
        '<p class="intro">Review proposed changes, findings and supporting evidence.</p>'
        f'</div><div class="toolbar">{actions}</div></div>'
        '<p class="mode-note"><span class="mode-dot" aria-hidden="true"></span>'
        f'{escape(context)}</p><section class="summary" aria-label="Risk summary">'
        f'<div class="risk-metric severity-{severity_class}"><span>Overall risk</span>'
        f'<strong class="risk-value">{risk_label}</strong>'
        "<small>Determined by policy rules</small></div>"
        f"<div><span>Findings</span><strong>{len(report.findings)}</strong>"
        "<small>Deterministic policy results</small></div>"
        f"<div><span>Changed resources</span><strong>{len(report.changed_resources)}</strong>"
        "<small>In the proposed change set</small></div>"
        f'<div><span>Retrieval</span><strong class="small">{retrieval_label}</strong>'
        "<small>Supporting runbook context</small></div></section>"
        '<nav class="section-nav" aria-label="Report sections">'
        '<a href="#overview">Overview</a><a href="#resources">Resources</a>'
        f'<a href="#findings">Findings <span>{len(report.findings)}</span></a>'
        f'{source_navigation}<a href="#recommendations">Recommendations</a>'
        '<a href="#limitations">Limitations</a></nav>'
        '<div class="overview-grid"><section id="overview" class="surface">'
        '<div class="section-heading"><div><div class="eyebrow">Review context</div>'
        "<h2>Analysis summary</h2></div></div>"
        f'<p>{escape(report.explanation)}</p><dl class="metadata">'
        f"<div><dt>Model</dt><dd>{escape(report.model_id or 'none')}</dd></div>"
        f"<div><dt>Policy version</dt><dd>{escape(report.policy_version)}</dd></div>"
        f"<div><dt>Policy packs</dt><dd>{escape(', '.join(report.policy_packs))}</dd></div>"
        f"<div><dt>Retrieval status</dt><dd>{escape(report.rag_status)}</dd></div></dl></section>"
        '<section id="resources" class="surface"><div class="section-heading"><div>'
        '<div class="eyebrow">Change scope</div><h2>Changed resources</h2></div></div>'
        '<div class="resource-list">'
        f"{_items(report.changed_resources) if report.changed_resources else '<p>No changes.</p>'}"
        "</div></section></div>"
        '<section id="findings"><div class="section-heading"><div>'
        '<div class="eyebrow">Deterministic policies</div><h2>Findings</h2></div>'
        f'<span class="count">{len(report.findings)} findings</span></div>'
        f"{findings or no_findings}</section>{sources}"
        '<div class="closing-grid"><section id="recommendations" class="surface">'
        '<div class="eyebrow">Next steps</div><h2>Recommendations</h2>'
        f"{recommendation_items}"
        '</section><section id="limitations" class="surface limitations">'
        '<div class="eyebrow">Analysis boundaries</div><h2>Limitations</h2>'
        f"{_items(report.limitations)}</section></div>"
        f"<footer><strong>Synthetic data only.</strong> Reports expire after at most "
        f"{retention_hours} hours. "
        "Local reports are discarded on restart. Terramind never approves or applies "
        "infrastructure changes.</footer></main></body></html>"
    )
