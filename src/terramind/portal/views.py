"""Escaped, server-rendered portal with no external assets or browser token storage."""

from html import escape
from typing import get_args
from urllib.parse import urlencode

from terramind.policies.catalog import RuleId
from terramind.portal.store import HistoryFilters, PortalAnalysis, Session


def _icon(name: str) -> str:
    shapes = {
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/>'
        '<rect x="14" y="3" width="7" height="7" rx="1.5"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1.5"/>'
        '<rect x="14" y="14" width="7" height="7" rx="1.5"/>',
        "report": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
        '<path d="M14 3v6h6M8 13h8M8 17h5"/>',
        "arrow": '<path d="M5 12h14m-5-5 5 5-5 5"/>',
        "plus": '<path d="M12 5v14M5 12h14"/>',
        "shield": '<path d="m12 3 8 4v5c0 5-8 9-8 9s-8-4-8-9V7z"/>'
        '<path d="m8.5 12 2.5 2.5 4.5-5"/>',
        "filter": '<path d="M4 6h16M7 12h10M10 18h4"/>',
        "chevron": '<path d="m8 10 4 4 4-4"/>',
        "download": '<path d="M12 3v12m-4-4 4 4 4-4M5 16v4h14v-4"/>',
        "layers": '<path d="m12 3 10 5-10 5L2 8zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
    }
    return (
        '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{shapes[name]}</svg>'
    )


def _tone(value: str) -> str:
    return {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
        "INFO": "neutral",
        "NO_KNOWN_FINDINGS": "neutral",
    }.get(value, "neutral")


def _risk_label(value: str) -> str:
    return "No known findings" if value == "NO_KNOWN_FINDINGS" else value


def _badge(value: str) -> str:
    return f'<span class="badge badge-{_tone(value)}">{escape(_risk_label(value))}</span>'


def _metric(label: str, value: str | int, note: str, *, tone: str = "neutral") -> str:
    return (
        f'<article class="metric metric-{tone}"><span>{escape(label)}</span>'
        f"<strong>{escape(str(value))}</strong><p>{escape(note)}</p></article>"
    )


def page(title: str, body: str, session: Session | None = None) -> str:
    signed_in = bool(session and session.owner)
    current = ' aria-current="page"' if title == "Dashboard" else ""
    navigation = (
        '<nav class="workspace-nav" aria-label="Workspace">'
        f'<a href="/dashboard"{current}>{_icon("grid")}Dashboard</a>'
        f'<a href="/dashboard#report-history">{_icon("report")}Reports</a></nav>'
        if signed_in
        else '<span class="workspace-label">Terraform change intelligence</span>'
    )
    account = (
        f'<span class="account-name">{escape(session.display)}</span>'
        '<form method="post" action="/auth/logout">'
        + csrf(session)
        + '<button class="secondary compact" type="submit">Sign out</button></form>'
        if session and session.owner
        else '<span class="environment-label">Review workspace</span>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} | Terramind</title>"
        '<link rel="stylesheet" href="/assets/portal.css">'
        '<link rel="icon" href="/assets/terramind-icon.png"></head><body>'
        '<a class="skip-link" href="#main-content">Skip to content</a>'
        '<header class="app-header"><div class="header-inner">'
        '<a class="brand" href="/dashboard" aria-label="Terramind dashboard">'
        '<img src="/assets/terramind-logo.png" alt="Terramind" width="216" height="72"></a>'
        f'{navigation}<div class="header-account">{account}</div></div></header>'
        f'<main id="main-content" class="{"workspace" if signed_in else "public-page"}" '
        f'tabindex="-1">{body}</main>'
        '<footer class="app-footer"><span>Synthetic data only. '
        "Reports expire after 24 hours.</span>"
        "<span>Policy findings remain authoritative. Terramind never approves or applies "
        "infrastructure changes.</span></footer></body></html>"
    )


def csrf(session: Session) -> str:
    return f'<input type="hidden" name="csrf" value="{escape(session.csrf, quote=True)}">'


def login(session: Session, *, demo: bool) -> str:
    if demo:
        actions = "".join(
            f'<form method="post" action="/auth/demo">{csrf(session)}'
            f'<input type="hidden" name="account" value="{account}">'
            f'<button class="{"secondary" if account == "reviewer" else ""}" type="submit">'
            f"Continue as synthetic {account}{_icon('arrow')}</button></form>"
            for account in ("analyst", "reviewer")
        )
        context = "Local demonstration: these disposable accounts are not identity verification."
    else:
        actions = (
            f'<form method="post" action="/auth/google">{csrf(session)}'
            f'<button type="submit">Sign in with Google{_icon("arrow")}</button></form>'
        )
        context = "Access requires a verified Google account on the configured allowlist."
    steps = "".join(
        f'<li><span class="step-icon">{_icon(icon)}</span><div><h3>{label}</h3>'
        f"<p>{description}</p></div></li>"
        for icon, label, description in (
            (
                "shield",
                "Deterministic risk checks",
                "Review policy findings before a change is applied.",
            ),
            (
                "layers",
                "Evidence in context",
                "Inspect observed facts and labeled incident context.",
            ),
            ("report", "A traceable review", "Keep your history and export JSON or Markdown."),
        )
    )
    return page(
        "Sign in",
        '<div class="login-layout"><section class="login-copy">'
        '<div class="eyebrow">Infrastructure review, with evidence</div>'
        "<h1>Understand the change.<br>Keep the evidence.</h1>"
        '<p class="intro">Review synthetic Terraform changes with clear risk findings, '
        "practical remediation and the context behind each decision.</p>"
        f'<ul class="workflow-list">{steps}</ul></section>'
        '<section class="surface login" aria-labelledby="sign-in-heading">'
        f'<span class="auth-symbol">{_icon("shield")}</span>'
        '<div class="eyebrow">Your review workspace</div>'
        '<h2 id="sign-in-heading">Start your review</h2>'
        f'<p class="muted">{context}</p><div class="auth-actions">{actions}</div>'
        '<div class="auth-note">Synthetic inputs. Human decisions.<br>'
        "Terramind never approves or applies a change.</div></section></div>",
    )


def google_continue(authorization_url: str) -> str:
    return page(
        "Continue to Google",
        '<section class="surface login google-continue">'
        f'<span class="auth-symbol">{_icon("shield")}</span>'
        '<div class="eyebrow">Account verification</div><h1>Continue to Google</h1>'
        '<p class="intro">Choose your approved Google account to sign in to Terramind.</p>'
        f'<a class="button" rel="noreferrer" href="{escape(authorization_url, quote=True)}">'
        f"Continue with Google{_icon('arrow')}</a></section>",
    )


def dashboard(
    session: Session,
    history: dict[str, object],
    filters: HistoryFilters,
    raw_filters: dict[str, str],
    mode: str = "offline",
) -> str:
    totals = history["totals"]
    assert isinstance(totals, dict)
    cards = "".join(
        _metric(label, totals[key], note, tone=tone)
        for key, label, note, tone in (
            ("reports", "Matching reports", "Active in your history", "neutral"),
            ("high_risk", "High or critical", "Prioritize for review", "high"),
            ("findings", "Findings", "Deterministic policy results", "violet"),
        )
    )
    risk_options = "".join(
        f'<option value="{risk}"{" selected" if filters.risk == risk else ""}>'
        f"{_risk_label(risk)}</option>"
        for risk in ("HIGH", "NO_KNOWN_FINDINGS", "CRITICAL", "MEDIUM", "LOW", "INFO")
    )
    rule_options = "".join(
        f'<option value="{rule}"{" selected" if filters.rule == rule else ""}>{rule}</option>'
        for rule in get_args(RuleId)
    )
    items = history["items"]
    assert isinstance(items, list)
    rows = "".join(
        '<tr><td><a class="report-link" '
        f'href="/reports/{item["analysis_id"]}">{_icon("report")}'
        f"<code>{item['analysis_id'][:8]}</code></a></td>"
        f"<td><time>{escape(item['created_at'][:10])}</time>"
        f'<span class="cell-note">{escape(item["created_at"][11:19])} UTC</span></td>'
        f'<td>{_badge(item["risk"])}</td><td><span class="count">{item["findings"]}</span></td>'
        '<td><div class="rule-list">'
        + (
            "".join(f"<code>{escape(rule)}</code>" for rule in item["rules"])
            or '<span class="muted">None</span>'
        )
        + "</div></td></tr>"
        for item in items
    )
    next_link = ""
    if history["next_cursor"]:
        query = urlencode({**raw_filters, "cursor": str(history["next_cursor"])})
        next_link = (
            f'<a class="button secondary compact" href="/dashboard?{escape(query, quote=True)}">'
            f"Next page{_icon('arrow')}</a>"
        )
    date_fields = "".join(
        f'<label>{label}<input type="date" name="{key}" '
        f'value="{escape(raw_filters[key], quote=True)}"></label>'
        for key, label in (("from", "From (UTC)"), ("to", "Through (UTC)"))
    )
    empty = (
        '<tr><td colspan="5"><div class="empty-state">'
        f"{_icon('report')}<h3>Your next review starts here</h3>"
        "<p>No matching reports. Create a report or adjust filters.</p>"
        '<a href="#create-report">Create a report</a></div></td></tr>'
    )
    context = (
        "Cloud analysis: retrieval and Gemini may incur usage charges."
        if mode == "cloud"
        else "Offline analysis: no cloud or model calls."
    )
    filter_count = sum(bool(value) for value in raw_filters.values())
    filter_label = f"{filter_count} active" if filter_count else "Risk, rule and date"
    return page(
        "Dashboard",
        '<div class="page-heading"><div><div class="eyebrow">Review workspace</div>'
        '<h1>Infrastructure reviews</h1><p class="intro">Your reports, findings and '
        "supporting evidence in one place.</p></div>"
        f'<a class="button" href="#create-report">{_icon("plus")}New analysis</a></div>'
        f'<section class="cards" aria-label="Filtered report totals">{cards}</section>'
        '<div class="workspace-grid"><section id="report-history" class="surface history">'
        '<div class="section-heading"><div><h2>Report history</h2>'
        '<p class="muted">Review your active synthetic analyses.</p></div>'
        f'<span class="label-pill">{totals["reports"]} reports</span></div>'
        f'<details class="filter-panel"{" open" if filter_count else ""}>'
        f'<summary>{_icon("filter")}Filter reports<span class="filter-hint">{filter_label}</span>'
        f'{_icon("chevron")}</summary><form class="filters" method="get" action="/dashboard">'
        '<label>Risk<select name="risk"><option value="">All risks</option>'
        f"{risk_options}</select></label>"
        '<label>Rule<select name="rule"><option value="">All rules</option>'
        f"{rule_options}</select></label>{date_fields}"
        '<div class="filter-actions"><button type="submit">Filter history</button>'
        '<a href="/dashboard#report-history">Reset</a></div></form></details>'
        '<div class="table-wrap" tabindex="0" role="region" aria-label="Report history table">'
        f'<table class="{"history-table" if items else "empty-history"}">'
        '<caption class="visually-hidden">Your filtered reports. '
        "Creation times are UTC.</caption>"
        '<thead><tr><th scope="col">Report</th><th scope="col">Created</th>'
        '<th scope="col">Risk</th><th scope="col">Findings</th>'
        '<th scope="col">Rules</th></tr></thead>'
        f"<tbody>{rows or empty}</tbody></table></div>"
        f'<div class="history-footer"><span>Showing {len(items)} of {totals["reports"]} '
        f"matching reports</span>{next_link}</div></section>"
        '<aside id="create-report" class="surface create-panel" aria-labelledby="create-heading">'
        f'<span class="section-icon">{_icon("plus")}</span>'
        '<h2 id="create-heading">Create a report</h2>'
        '<p class="muted">Start with a packaged synthetic Terraform scenario.</p>'
        f'<form class="create-form" method="post" action="/analyses">{csrf(session)}'
        '<label>Scenario<select name="scenario">'
        '<option value="risk-demo">Four risk findings</option>'
        '<option value="storage-hardening">Storage hardening</option>'
        '<option value="database-hardening">Database hardening</option>'
        '<option value="benign">No proposed changes</option></select></label>'
        f'<button type="submit">Analyze synthetic sample{_icon("arrow")}</button></form>'
        f'<p class="analysis-mode">{_icon("shield")}{context}</p>'
        '<p class="create-note">Every finding includes observed facts and remediation. '
        "Export your review as JSON or Markdown.</p></aside></div>",
        session,
    )


def analysis_page(session: Session, analysis: PortalAnalysis) -> str:
    report, memory = analysis.report, analysis.incident_memory
    findings = "".join(
        f'<article class="surface finding finding-{_tone(finding.severity)}">'
        f'<div class="finding-meta">{_badge(finding.severity)}'
        f'<span class="finding-status">{escape(finding.status)}</span>'
        f"<code>{escape(finding.rule_id)}</code></div>"
        f"<h3>{escape(finding.title)}</h3>"
        f'<code class="resource-label">{escape(finding.resource)}</code>'
        f'<p>{escape(finding.rationale)}</p><div class="finding-details">'
        '<div class="observed-facts"><h4>Observed facts</h4><ul>'
        + "".join(f"<li><code>{escape(evidence)}</code></li>" for evidence in finding.evidence)
        + '</ul></div><div class="remediation"><h4>Remediation</h4>'
        f"<p>{escape(finding.remediation)}</p></div></div></article>"
        for finding in report.findings
    )
    matches = "".join(
        '<article class="surface incident-card">'
        '<div class="eyebrow">Synthetic incident context</div>'
        f'<h3><a href="/incidents/{match.doc_id}">{escape(match.title)}</a></h3>'
        f'<p class="muted">{escape(match.evidence_label)}</p>'
        "<details><summary>Read incident context</summary>"
        f"<p>{escape(match.excerpt)}</p></details>"
        f'<p class="incident-score">Lexical cosine: {match.similarity:.3f}. '
        f"Related rules: {escape(', '.join(match.related_rules))}.</p>"
        "<details><summary>Source provenance</summary>"
        f"<p>{escape(match.source_path)} / version {escape(match.version)}</p>"
        f"<code>SHA-256: {match.content_hash}</code></details></article>"
        for match in memory.matches
    )
    advisory = ""
    if report.advisory is not None:
        advisory = (
            '<section class="surface advisory-panel" aria-labelledby="advisory-heading">'
            '<div class="eyebrow">Retrieved context</div><h2 id="advisory-heading">AI advisory</h2>'
            '<p class="muted">Advisory text does not change policy findings.</p>'
            f"<p>{escape(report.advisory.summary)}</p><ul>"
            + "".join(f"<li>{escape(item.text)}</li>" for item in report.advisory.explanations)
            + "</ul><h3>Recommendations</h3><ul>"
            + "".join(f"<li>{escape(item)}</li>" for item in report.advisory.recommendations)
            + '</ul><h3>Validated advisory sources</h3><div class="advisory-sources">'
            + "".join(
                "<details><summary>"
                f"{escape(item.title)}</summary><p><code>{escape(item.citation_id)}</code></p>"
                f"<p>Version {escape(item.version)}</p>"
                f"<code>SHA-256: {item.content_hash}</code></details>"
                for item in report.advisory.sources
            )
            + "</div></section>"
        )
    metrics = (
        _metric(
            "Overall risk",
            _risk_label(report.overall_risk),
            "Policy assessment",
            tone=_tone(report.overall_risk),
        )
        + _metric("Findings", len(report.findings), "Deterministic results")
        + _metric("Changed resources", len(report.changed_resources), "Included in this review")
        + _metric("Related incidents", len(memory.matches), "Synthetic context", tone="violet")
    )
    no_findings = (
        '<div class="surface empty-state">'
        f"{_icon('shield')}<h3>No known findings</h3>"
        "<p>No known findings. This does not establish safety.</p></div>"
    )
    return page(
        "Risk report",
        '<div class="breadcrumbs"><a href="/dashboard">Dashboard</a><span>/</span>'
        '<span>Risk report</span></div><div class="page-heading"><div>'
        '<div class="eyebrow">Owned synthetic analysis</div><h1>Terraform change review</h1>'
        '<p class="intro">Inspect the findings. Understand the evidence. '
        "Decide what comes next.</p>"
        '</div></div><div class="report-toolbar"><div class="actions">'
        f'<a class="button" href="/reports/{report.analysis_id}/markdown">'
        f"{_icon('download')}Download Markdown</a>"
        f'<a class="button secondary" href="/reports/{report.analysis_id}/json">View JSON</a>'
        '<a class="text-link" href="/dashboard">Back to history</a></div>'
        f'<span class="report-reference">Report <code>{report.analysis_id[:8]}</code></span></div>'
        f'<section class="cards report-cards" aria-label="Risk summary">{metrics}</section>'
        '<nav class="report-nav" aria-label="Report sections"><a href="#policy-findings">'
        f"Policy findings<span>{len(report.findings)}</span></a>"
        '<a href="#analysis-context">Analysis context</a>'
        '<a href="#incident-memory">Incident Memory</a><a href="#limitations">Limitations</a></nav>'
        '<div class="report-layout"><section id="policy-findings" class="findings-section">'
        '<div class="section-heading"><div><h2>Policy findings</h2>'
        '<p class="muted">Severity comes from deterministic rules.</p></div></div>'
        f"{findings or no_findings}</section>"
        '<aside id="analysis-context" class="surface context-panel">'
        "<h2>Analysis context</h2>"
        f"<p>{escape(report.explanation)}</p><dl><div><dt>Created (UTC)</dt>"
        f"<dd>{escape(report.timestamp[:19].replace('T', ' '))}</dd></div>"
        f"<div><dt>Policy version</dt><dd>{escape(report.policy_version)}</dd></div>"
        f"<div><dt>Policy packs</dt><dd>{escape(', '.join(report.policy_packs))}</dd></div>"
        f"<div><dt>Retrieval</dt><dd>{escape(report.rag_status)}</dd></div>"
        f"<div><dt>Model</dt><dd>{escape(report.model_id or 'none')}</dd></div></dl>"
        '<p class="context-note">Findings describe proposed changes. They do not establish '
        "deployed exposure or recovery readiness.</p></aside></div>"
        f'{advisory}<section id="incident-memory" class="incident-section">'
        '<div class="section-heading"><div><h2>Incident Memory</h2>'
        '<p class="muted">Fabricated tabletop exercises selected by local lexical similarity. '
        "These are not real incident evidence or predictions.</p></div>"
        f'<span class="label-pill">Search status: {escape(memory.status)}</span></div>'
        f'<div class="incident-grid">{matches}</div>'
        + (
            ""
            if matches
            else '<div class="surface empty-context">'
            "No related incident context was selected.</div>"
        )
        + '</section><section id="limitations" class="surface limitations">'
        "<h2>Limitations</h2><ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in (*report.limitations, *memory.limitations))
        + "</ul></section>",
        session,
    )
