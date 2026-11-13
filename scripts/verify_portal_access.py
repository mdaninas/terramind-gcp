"""Read-only ownership and pagination checks through an authenticated loopback proxy."""

import argparse
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from terramind.portal.store import PortalAnalysis
from terramind.reports.store import valid_id

Fetch = Callable[[str, str], tuple[int, bytes]]
MAX_BYTES = 1024 * 1024
MAX_REQUESTS = 32
MAX_PAGES = 4


class VerificationFailure(RuntimeError):
    def __init__(self, summary: dict[str, object]):
        super().__init__("Portal verification failed")
        self.summary = dict(summary, status="failed")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def transport(url: str) -> Fetch:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use the approved loopback proxy base URL with an explicit port")
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def fetch(path: str, token: str) -> tuple[int, bytes]:
        headers = {"Cookie": f"terramind_session={token}"} if token else {}
        request = Request(url.rstrip("/") + path, headers=headers, method="GET")
        try:
            response = opener.open(request, timeout=8)
        except HTTPError as error:
            response = error
        with response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("Response exceeds its bound")
            return int(response.code), body

    return fetch


def run(
    url: str,
    token_a: str,
    token_b: str,
    report_a: str,
    report_b: str,
    *,
    fetch: Fetch | None = None,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "status": "failed",
        "stage": "configuration",
        "analysis_submissions": 0,
        "http_requests": 0,
        "max_http_requests": MAX_REQUESTS,
    }
    try:
        default_fetch = transport(url)
        if (
            token_a == token_b
            or not all(re.fullmatch(r"[A-Za-z0-9_-]{40,64}", token) for token in (token_a, token_b))
            or report_a == report_b
            or not all(valid_id(report) for report in (report_a, report_b))
        ):
            raise ValueError(
                "Two distinct authenticated sessions and owned report IDs are required"
            )
        perform = fetch or default_fetch
        requests = 0

        def request(path: str, token: str, expected: int) -> bytes:
            nonlocal requests
            if requests >= MAX_REQUESTS:
                raise ValueError("Request bound exhausted")
            requests += 1
            summary["http_requests"] = requests
            status, body = perform(path, token)
            if status != expected or len(body) > MAX_BYTES:
                raise ValueError("Unexpected response")
            return body

        summary["stage"] = "anonymous_access"
        request("/api/history", "", 401)

        def history(token: str, minimum: int) -> tuple[set[str], int]:
            cursor, seen_cursors, ids = "", set(), set()
            total: int | None = None
            for page in range(1, MAX_PAGES + 1):
                query = {"risk": "NO_KNOWN_FINDINGS"}
                if cursor:
                    query["cursor"] = cursor
                data = json.loads(request("/api/history?" + urlencode(query), token, 200))
                if not isinstance(data, dict) or set(data) != {"items", "next_cursor", "totals"}:
                    raise ValueError("Invalid history response")
                count = data["totals"]["reports"]
                if (
                    type(count) is not int
                    or count < minimum
                    or (total is not None and count != total)
                ):
                    raise ValueError("History totals changed or the fixture is incomplete")
                total = count
                items = data["items"]
                if not isinstance(items, list) or not 1 <= len(items) <= 20:
                    raise ValueError("Invalid history page")
                for item in items:
                    key = item["analysis_id"]
                    if not isinstance(key, str) or not valid_id(key) or key in ids:
                        raise ValueError("Duplicate or invalid history identity")
                    if item["risk"] != "NO_KNOWN_FINDINGS" or item["findings"] != 0:
                        raise ValueError("Use the no-change synthetic pagination dataset")
                    ids.add(key)
                cursor = data["next_cursor"]
                if not isinstance(cursor, str) or len(cursor) > 256 or cursor in seen_cursors:
                    raise ValueError("Invalid or repeated pagination cursor")
                if not cursor:
                    if len(ids) != total:
                        raise ValueError("History omitted or added reports")
                    return ids, page
                if len(items) != 20:
                    raise ValueError("A continuing page must contain twenty reports")
                seen_cursors.add(cursor)
            raise ValueError("History exceeds this verification's page bound")

        summary["stage"] = "pagination"
        ids_a, pages_a = history(token_a, 21)
        ids_b, pages_b = history(token_b, 1)
        if ids_a & ids_b or report_a not in ids_a or report_b not in ids_b:
            raise ValueError("History ownership mismatch")
        summary.update(
            owner_a_reports=len(ids_a),
            owner_b_reports=len(ids_b),
            owner_a_pages=pages_a,
            owner_b_pages=pages_b,
        )
        summary["stage"] = "owned_exports"
        for own, other, report in ((token_a, token_b, report_a), (token_b, token_a, report_b)):
            raw = request(f"/reports/{report}/json", own, 200)
            bundle = PortalAnalysis.model_validate_json(raw)
            if bundle.report.analysis_id != report or bundle.report.findings:
                raise ValueError("Owned no-change export mismatch")
            request(f"/reports/{report}", own, 200)
            request(f"/reports/{report}/markdown", own, 200)
            for suffix in ("", "/json", "/markdown"):
                request(f"/reports/{report}{suffix}", other, 404)
        summary["stage"] = "owner_override"
        for token in (token_a, token_b):
            request("/api/history?owner=synthetic-other-owner", token, 400)
        return dict(summary, status="passed", stage="complete", cross_owner_exports_rejected=True)
    except Exception:
        raise VerificationFailure(summary) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--report-a", required=True)
    parser.add_argument("--report-b", required=True)
    args = parser.parse_args()
    try:
        summary = run(
            args.url,
            os.environ.get("TERRAMIND_SESSION_A", ""),
            os.environ.get("TERRAMIND_SESSION_B", ""),
            args.report_a,
            args.report_b,
        )
    except VerificationFailure as error:
        summary = error.summary
    path = Path("artifacts/operational-readiness/portal-summary.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
