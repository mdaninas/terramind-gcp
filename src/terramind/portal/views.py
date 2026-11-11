"""Escaped, server-rendered portal with no external assets or browser token storage."""

from html import escape
from typing import get_args
from urllib.parse import urlencode

from terramind.policies.catalog import RuleId
from terramind.portal.store import HistoryFilters, PortalAnalysis, Session


def page(title: str, body: str, session: Session | None = None) -> str:
    logout = (
        '<form method="post" action="/auth/logout">'
        + csrf(session)
        + '<button class="secondary" type="submit">Sign out</button></form>'
        if session and session.owner
        else ""
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} | Terramind</title>"
        '<link rel="stylesheet" href="/assets/portal.css">'
        '<link rel="icon" href="/assets/terramind-icon.png"></head><body>'
        '<header><a class="brand" href="/dashboard"><img src="/assets/terramind-logo.png" '
        'alt="Terramind" width="216" height="72"></a><nav><a href="/dashboard">Dashboard</a>'
        f"{logout}</nav></header><main>{body}</main><footer>Synthetic data only. "
        "Policy findings remain authoritative. Terramind never approves or applies infrastructure "
        "changes. Reports expire after 24 hours.</footer></body></html>"
    )


def csrf(session: Session) -> str:
    return f'<input type="hidden" name="csrf" value="{escape(session.csrf, quote=True)}">'


def login(session: Session, *, demo: bool) -> str:
    if demo:
        actions = "".join(
            f'<form method="post" action="/auth/demo">{csrf(session)}'
            f'<input type="hidden" name="account" value="{account}">'
            f'<button type="submit">Continue as synthetic {account}</button></form>'
            for account in ("analyst", "reviewer")
        )
        context = "Local demonstration: these disposable accounts are not identity verification."
    else:
        actions = (
            f'<form method="post" action="/auth/google">{csrf(session)}'
            '<button type="submit">Sign in with Google</button></form>'
        )
        context = "Access requires a verified Google account on the configured allowlist."
    return page(
        "Sign in",
        '<div class="eyebrow">Terramind review workspace</div>'
        "<h1>Review changes.<br>Keep the evidence.</h1>"
        '<p class="intro">Analyze synthetic infrastructure changes, inspect related '
        "tabletop incidents and revisit your own reports.</p>"
        f'<section class="panel login"><h2>Sign in</h2><p>{context}</p>'
        f'<div class="actions">{actions}</div></section>',
    )


def google_continue(authorization_url: str) -> str:
    return page(
        "Continue to Google",
        '<section class="panel login"><h1>Continue to Google</h1>'
        "<p>Choose your approved Google account to sign in to Terramind.</p>"
        f'<a class="button" rel="noreferrer" href="{escape(authorization_url, quote=True)}">'
        "Continue with Google</a></section>",
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
        f"<article><span>{label}</span><strong>{totals[key]}</strong></article>"
        for key, label in (
            ("reports", "Matching reports"),
            ("high_risk", "High or critical"),
            ("findings", "Findings"),
        )
    )
    risk_options = "".join(
        f'<option value="{risk}"{" selected" if filters.risk == risk else ""}>{risk}</option>'
        for risk in ("HIGH", "NO_KNOWN_FINDINGS", "CRITICAL", "MEDIUM", "LOW", "INFO")
    )
    rule_options = "".join(
        f'<option value="{rule}"{" selected" if filters.rule == rule else ""}>{rule}</option>'
        for rule in get_args(RuleId)
    )
    items = history["items"]
    assert isinstance(items, list)
    rows = "".join(
        f'<tr><td><a href="/reports/{item["analysis_id"]}">'
        f"<code>{item['analysis_id'][:8]}</code></a></td>"
        f"<td>{escape(item['created_at'][:19].replace('T', ' '))} UTC</td>"
        f'<td><span class="badge">{escape(item["risk"])}</span></td><td>{item["findings"]}</td>'
        f"<td>{escape(', '.join(item['rules'])) or 'None'}</td></tr>"
        for item in items
    )
    next_link = ""
    if history["next_cursor"]:
        query = urlencode({**raw_filters, "cursor": str(history["next_cursor"])})
        next_link = (
            f'<a class="button secondary" href="/dashboard?{escape(query, quote=True)}">'
            "Next page</a>"
        )
    date_fields = "".join(
        f'<label>{label}<input type="date" name="{key}" '
        f'value="{escape(raw_filters[key], quote=True)}"></label>'
        for key, label in (("from", "From (UTC)"), ("to", "Through (UTC)"))
    )
    empty = '<tr><td colspan="5">No matching reports. Create a report or adjust filters.</td></tr>'
    context = (
        "Cloud analysis: admitted samples can request metered retrieval and Gemini advice."
        if mode == "cloud"
        else "Offline analysis: no cloud or model calls."
    )
    return page(
        "Dashboard",
        f'<div class="eyebrow">{escape(session.display)}</div><h1>Your review history</h1>'
        '<p class="intro">Your active synthetic reports, with deterministic findings '
        "and separately labeled incident context.</p>"
        f'<section class="cards" aria-label="Filtered report totals">{cards}</section>'
        '<section class="panel"><h2>Create a report</h2><p>Choose a packaged synthetic '
        f"scenario.</p><p>{context}</p>"
        f'<form class="actions" method="post" action="/analyses">{csrf(session)}'
        '<label>Scenario<select name="scenario">'
        '<option value="risk-demo">Four risk findings</option>'
        '<option value="storage-hardening">Storage hardening</option>'
        '<option value="database-hardening">Database hardening</option>'
        '<option value="benign">No proposed changes</option></select></label>'
        '<button type="submit">Analyze synthetic sample</button></form></section>'
        '<section><h2>Report history</h2><form class="filters" method="get" action="/dashboard">'
        '<label>Risk<select name="risk"><option value="">All risks</option>'
        f"{risk_options}</select></label>"
        '<label>Rule<select name="rule"><option value="">All rules</option>'
        f"{rule_options}</select></label>"
        f'{date_fields}<button type="submit">Filter history</button>'
        '<a href="/dashboard">Reset</a></form>'
        '<div class="table-wrap"><table><thead><tr><th>Report</th><th>Created</th>'
        "<th>Risk</th><th>Findings</th><th>Rules</th></tr></thead>"
        f"<tbody>{rows or empty}</tbody></table></div>{next_link}</section>",
        session,
    )


def analysis_page(session: Session, analysis: PortalAnalysis) -> str:
    report, memory = analysis.report, analysis.incident_memory
    findings = "".join(
        f'<article class="panel finding"><span class="badge">{escape(finding.severity)}</span>'
        f"<h3>{escape(finding.rule_id)}: {escape(finding.title)}</h3>"
        f"<p>{escape(finding.rationale)}</p>"
        "<ul>"
        + "".join(f"<li>{escape(evidence)}</li>" for evidence in finding.evidence)
        + f"</ul><p><strong>Remediation:</strong> {escape(finding.remediation)}</p></article>"
        for finding in report.findings
    )
    matches = "".join(
        f'<article class="panel"><span class="eyebrow">Synthetic incident context</span>'
        f'<h3><a href="/incidents/{match.doc_id}">{escape(match.title)}</a></h3>'
        f"<p>{escape(match.evidence_label)}</p><p>{escape(match.excerpt)}</p>"
        f'<p class="muted">Lexical cosine: {match.similarity:.3f}. '
        f"Related rules: {escape(', '.join(match.related_rules))}.</p>"
        "<details><summary>Source provenance</summary>"
        f"<p>{escape(match.source_path)} / version {escape(match.version)}</p>"
        f"<code>SHA-256: {match.content_hash}</code></details></article>"
        for match in memory.matches
    )
    no_findings = "<p>No known findings. This does not establish safety.</p>"
    no_matches = "<p>No related incident context was selected.</p>"
    context = (
        "<section><h2>Analysis context</h2>"
        f'<p>{escape(report.explanation)}</p><p class="muted">'
        f"Retrieval: {escape(report.rag_status)}. Model: {escape(report.model_id or 'none')}.</p>"
    )
    if report.advisory is not None:
        context += "<h3>AI advisory</h3><p>Advisory text does not change policy findings.</p>"
        context += f"<p>{escape(report.advisory.summary)}</p><ul>"
        context += "".join(f"<li>{escape(item.text)}</li>" for item in report.advisory.explanations)
        context += "</ul><h3>Recommendations</h3><ul>"
        context += "".join(f"<li>{escape(item)}</li>" for item in report.advisory.recommendations)
        context += "</ul><h3>Validated advisory sources</h3><ul>"
        context += "".join(
            f"<li>{escape(item.title)} ({escape(item.citation_id)}), "
            f"version {escape(item.version)}<br><code>SHA-256: {item.content_hash}</code></li>"
            for item in report.advisory.sources
        )
        context += "</ul>"
    context += "</section>"
    return page(
        "Risk report",
        '<div class="eyebrow">Owned synthetic analysis</div><h1>Evidence before action.</h1>'
        f'<div class="actions"><a class="button secondary" '
        f'href="/reports/{report.analysis_id}/json">View JSON</a>'
        f'<a class="button secondary" href="/reports/{report.analysis_id}/markdown">'
        'Download Markdown</a><a href="/dashboard">Back to history</a></div>'
        '<section class="cards"><article><span>Overall risk</span>'
        f"<strong>{escape(report.overall_risk)}</strong></article>"
        f"<article><span>Findings</span><strong>{len(report.findings)}</strong></article>"
        f"<article><span>Related incidents</span><strong>{len(memory.matches)}</strong>"
        "</article></section>"
        f"<p>Policy version: {escape(report.policy_version)}. "
        f"Packs: {escape(', '.join(report.policy_packs))}.</p>"
        f"{context}"
        f"<section><h2>Policy findings</h2>{findings or no_findings}</section>"
        "<section><h2>Incident Memory</h2><p>Fabricated tabletop exercises selected by "
        "local lexical similarity. These are not real incident evidence or predictions.</p>"
        f"<p>Search status: {escape(memory.status)}.</p>"
        f"{matches or no_matches}</section>"
        "<section><h2>Limitations</h2><ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in (*report.limitations, *memory.limitations))
        + "</ul></section>",
        session,
    )
