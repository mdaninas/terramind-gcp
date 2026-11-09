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
from terramind.llm.contracts import SourceCitation
from terramind.rag.corpus import corpus_chunks, load_corpus
from terramind.reports.render import build_report
from terramind.schemas.normalized import serialize_plan
from terramind.schemas.report import Report


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None  # Never forward an identity token to a redirected host.


def run(url: str, *, local: bool, require_advisory: bool) -> dict[str, object]:
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
        for path, data in (("/health", None), ("/demo", None), ("/v1/analyses", b"{}")):
            if request(path, data, authenticated=False)[0] not in {401, 403}:
                raise ValueError("Anonymous requests were not rejected")
    if request("/health")[0] != 200 or request("/demo")[0] != 200:
        raise ValueError("Health or demo check failed")
    if request("/v1/analyses", b"{")[0] != 400:
        raise ValueError("Invalid JSON was not rejected")
    plan = demo_plan()
    started = perf_counter()
    status, body = request("/v1/analyses", serialize_plan(plan).encode())
    elapsed = perf_counter() - started
    if status != 201:
        raise ValueError("Analysis request failed")
    report = Report.model_validate_json(body)
    expected = build_report(plan)
    if report.findings != expected.findings or report.overall_risk != expected.overall_risk:
        raise ValueError("Deterministic findings changed")
    prefix = f"/v1/analyses/{report.analysis_id}"
    status, stored = request(prefix)
    if status != 200 or Report.model_validate_json(stored) != report:
        raise ValueError("Stored report did not round-trip")
    status, text = request(prefix + "/markdown")
    if status != 200 or not all(item.rule_id.encode() in text for item in report.findings):
        raise ValueError("Markdown export failed")
    status, page = request(prefix + "/view")
    if status != 200 or b"Download Markdown" not in page or b"Limitations" not in page:
        raise ValueError("Report page failed")
    if require_advisory:
        if report.advisory is None or report.rag_status != "available":
            raise ValueError("A grounded live advisory was not returned")
        chunks = {
            chunk.citation_id: SourceCitation.from_chunk(chunk)
            for chunk in corpus_chunks(load_corpus(Path("knowledge-base")))
        }
        if any(chunks.get(source.citation_id) != source for source in report.advisory.sources):
            raise ValueError("Source provenance differs from the reviewed synthetic corpus")
    return {
        "mode": "local" if local else "cloud",
        "anonymous_rejection_verified": not local,
        "report_round_trip_verified": True,
        "markdown_and_page_verified": True,
        "findings_preserved": True,
        "finding_count": len(report.findings),
        "source_count": len(report.advisory.sources) if report.advisory else 0,
        "model_id": report.model_id,
        "rag_status": report.rag_status,
        "analysis_request_seconds": round(elapsed, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("CLOUD_RUN_URL"))
    parser.add_argument(
        "--local", action="store_true", help="Loopback only; does not test cloud IAM"
    )
    parser.add_argument("--require-advisory", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/api-demo-summary.json"))
    args = parser.parse_args()
    if not args.url:
        parser.error("Provide --url or CLOUD_RUN_URL")
    try:
        summary = run(args.url, local=args.local, require_advisory=args.require_advisory)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    except Exception:
        print("API verification failed. Check configuration and content-free service logs.")
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
