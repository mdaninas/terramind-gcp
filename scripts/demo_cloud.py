"""One synthetic end-to-end analysis, with optional strict live-advisory verification."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from terramind.api.app import demo_plan
from terramind.llm.contracts import SourceCitation, finding_id
from terramind.llm.diagnostics import LIMITATIONS
from terramind.policies.samples import hardening_sample
from terramind.rag.corpus import corpus_chunks, load_corpus
from terramind.reports.render import build_report
from terramind.schemas.normalized import serialize_plan
from terramind.schemas.report import Report


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None  # Never forward an identity token to a redirected host.


SCENARIOS = ("risk-demo", "storage-hardening", "database-hardening")


class VerificationFailure(RuntimeError):
    def __init__(self, summary: dict[str, object]):
        super().__init__("Synthetic verification failed")
        self.summary = dict(summary, status="failed")


def run(
    url: str, *, local: bool, require_advisory: bool, scenario: str = "risk-demo"
) -> dict[str, object]:
    summary: dict[str, object] = {
        "mode": "local" if local else "cloud",
        "scenario": scenario if scenario in SCENARIOS else "invalid",
        "status": "failed",
        "stage": "configuration",
        "analysis_submitted": False,
    }
    started = perf_counter()
    try:
        result = verify(
            url, local=local, require_advisory=require_advisory, scenario=scenario, summary=summary
        )
        return dict(result, status="passed", stage="complete")
    except Exception:
        summary["verification_seconds"] = round(perf_counter() - started, 3)
        raise VerificationFailure(summary) from None


def verify(
    url: str,
    *,
    local: bool,
    require_advisory: bool,
    scenario: str,
    summary: dict[str, object],
) -> dict[str, object]:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown synthetic scenario")
    parsed = urlsplit(url)
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("Use the service base URL")
    if local:
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Local mode requires a loopback HTTP URL")
        token = ""
    else:
        if parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9-]+\.a\.run\.app", parsed.netloc):
            raise ValueError("Use the approved HTTPS Cloud Run URL")
        token = os.environ.get("TERRAMIND_ID_TOKEN", "")
        if not token:
            raise ValueError("TERRAMIND_ID_TOKEN must contain a short-lived identity token")
    base = url.rstrip("/")
    opener = build_opener(NoRedirect())

    def request(
        path: str, data: bytes | None = None, *, authenticated: bool = True
    ) -> tuple[int, bytes]:
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if token and authenticated:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(base + path, data=data, headers=headers)
        try:
            with opener.open(req, timeout=35) as response:
                body = response.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise ValueError("Response exceeded verification limit")
                return response.status, body
        except HTTPError as error:
            status = error.code
            error.close()
            return status, b""

    if not local:
        summary["stage"] = "anonymous_access"
        for path, data in (("/health", None), ("/demo", None), ("/v1/analyses", b"{}")):
            if request(path, data, authenticated=False)[0] not in {401, 403}:
                raise ValueError("Anonymous requests were not rejected")
    summary["anonymous_rejection_verified"] = not local
    summary["stage"] = "health"
    if request("/health")[0] != 200 or request("/demo")[0] != 200:
        raise ValueError("Health or demo check failed")
    summary["stage"] = "invalid_input"
    if request("/v1/analyses", b"{")[0] != 400:
        raise ValueError("Invalid JSON was not rejected")
    plan = demo_plan() if scenario == "risk-demo" else hardening_sample(scenario)
    summary["stage"] = "analysis"
    summary["analysis_submitted"] = True
    started = perf_counter()
    status, body = request("/v1/analyses", serialize_plan(plan).encode())
    elapsed = perf_counter() - started
    summary["analysis_request_seconds"] = round(elapsed, 3)
    summary["analysis_http_status"] = status
    if status != 201:
        raise ValueError("Analysis request failed")
    summary["stage"] = "report_contract"
    report = Report.model_validate_json(body)
    expected = build_report(plan)
    summary["stage"] = "policy_findings"
    if (
        report.findings != expected.findings
        or report.overall_risk != expected.overall_risk
        or report.policy_packs != expected.policy_packs
        or report.policy_version != expected.policy_version
        or report.changed_resources != expected.changed_resources
    ):
        raise ValueError("Deterministic findings changed")
    summary.update(
        findings_preserved=True,
        finding_count=len(report.findings),
        rag_status=report.rag_status,
        model_id=report.model_id,
        advisory_present=report.advisory is not None,
    )
    summary["stage"] = "stored_report"
    prefix = f"/v1/analyses/{report.analysis_id}"
    status, stored = request(prefix)
    if status != 200 or Report.model_validate_json(stored) != report:
        raise ValueError("Stored report did not round-trip")
    summary["report_round_trip_verified"] = True
    summary["stage"] = "markdown_export"
    status, text = request(prefix + "/markdown")
    if status != 200 or not all(item.rule_id.encode() in text for item in report.findings):
        raise ValueError("Markdown export failed")
    summary["stage"] = "report_page"
    status, page = request(prefix + "/view")
    if status != 200 or b"Download Markdown" not in page or b"Limitations" not in page:
        raise ValueError("Report page failed")
    summary["markdown_and_page_verified"] = True
    if require_advisory:
        summary["stage"] = "advisory"
        if report.advisory is None or report.rag_status != "available":
            summary["advisory_failure"] = next(
                (
                    reason.value
                    for reason, text in LIMITATIONS.items()
                    if text in report.limitations
                ),
                "unspecified",
            )
            raise ValueError("A grounded live advisory was not returned")
        summary["stage"] = "source_provenance"
        chunks = {
            chunk.citation_id: SourceCitation.from_chunk(chunk)
            for chunk in corpus_chunks(load_corpus(Path("knowledge-base")))
        }
        if any(chunks.get(source.citation_id) != source for source in report.advisory.sources):
            raise ValueError("Source provenance differs from the reviewed synthetic corpus")
        summary["stage"] = "advisory_coverage"
        explanations = report.advisory.explanations
        expected_ids = {finding_id(finding) for finding in report.findings}
        used = {citation for item in explanations for citation in item.citation_ids}
        source_ids = [source.citation_id for source in report.advisory.sources]
        if (
            len(explanations) != len(expected_ids)
            or {item.finding_id for item in explanations} != expected_ids
            or used != set(report.advisory.citations)
            or used != set(report.citations)
            or used != set(source_ids)
            or len(source_ids) != len(set(source_ids))
            or report.model_id != report.advisory.model_id
            or report.advisory.rag_status != "available"
        ):
            raise ValueError("Advisory coverage differs from the verified findings and sources")
    summary["source_count"] = len(report.advisory.sources) if report.advisory else 0
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("CLOUD_RUN_URL"))
    parser.add_argument(
        "--local", action="store_true", help="Loopback only; does not test cloud IAM"
    )
    parser.add_argument("--require-advisory", action="store_true")
    scenarios = parser.add_mutually_exclusive_group()
    scenarios.add_argument("--scenario", choices=SCENARIOS, default="risk-demo")
    scenarios.add_argument(
        "--all-scenarios", action="store_true", help="At most three submissions, without retries"
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/api-demo-summary.json"))
    args = parser.parse_args()
    if not args.url:
        parser.error("Provide --url or CLOUD_RUN_URL")
    if args.all_scenarios and not args.require_advisory:
        parser.error("--all-scenarios requires --require-advisory")
    results = []
    for scenario in SCENARIOS if args.all_scenarios else (args.scenario,):
        try:
            result = run(
                args.url,
                local=args.local,
                require_advisory=args.require_advisory,
                scenario=scenario,
            )
        except VerificationFailure as error:
            result = error.summary
        results.append(result)
    passed = all(result["status"] == "passed" for result in results)
    summary = (
        {
            "status": "passed" if passed else "failed",
            "scenario_limit": 3,
            "analysis_submission_limit": 3,
            "analysis_submissions": sum(bool(result["analysis_submitted"]) for result in results),
            "results": results,
        }
        if args.all_scenarios
        else results[0]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
