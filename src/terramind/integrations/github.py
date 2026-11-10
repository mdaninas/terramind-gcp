"""Analyze synthetic PR blobs as data, then publish bounded summaries from trusted code."""

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Protocol
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field

from terramind.errors import InputError
from terramind.normalizer.io import load_normalized
from terramind.policies.catalog import PackName, RuleId
from terramind.reports.render import build_report
from terramind.schemas.normalized import MAX_REQUEST_BYTES, ClosedModel

MARKER = "<!-- terramind-synthetic-review:v1 -->"
REPOSITORY = r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+"
PLAN_PATH = r"examples/normalized-plans/[a-z0-9_-]{1,64}\.json"
SHA = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]


class PlanSummary(ClosedModel):
    path: Annotated[str, Field(pattern=rf"^{PLAN_PATH}$")]
    blob_sha: SHA
    findings: Annotated[int, Field(ge=0, le=800)]
    rules: tuple[RuleId, ...] = Field(max_length=8)
    policy_packs: tuple[PackName, ...] = Field(default=("gcp-core",), max_length=3)
    risk: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NO_KNOWN_FINDINGS"]


class PullRequestReview(ClosedModel):
    schema_version: Literal["1.0"] = "1.0"
    repository: Annotated[str, Field(pattern=rf"^{REPOSITORY}$", max_length=200)]
    repository_id: Annotated[int, Field(gt=0)]
    pull_number: Annotated[int, Field(gt=0)]
    base_sha: SHA
    head_sha: SHA
    plans: tuple[PlanSummary, ...] = Field(max_length=20)


class GitHubAPI(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any: ...


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


@dataclass
class GitHubClient:
    token: str = field(repr=False)

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/repos/") or not re.fullmatch(r"[/A-Za-z0-9_.:?=&-]+", path):
            raise InputError("Invalid GitHub API path")
        request = Request(
            "https://api.github.com" + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "terramind-synthetic-review",
            },
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise InputError("GitHub response exceeds its limit")
            return json.loads(raw)
        except Exception:
            raise InputError("GitHub request unavailable; no response content logged") from None


def _pull(client: GitHubAPI, repository: str, repository_id: int, number: int) -> Any:
    if not re.fullmatch(REPOSITORY, repository) or number < 1 or repository_id < 1:
        raise InputError("Invalid review target")
    pr = client.request("GET", f"/repos/{repository}/pulls/{number}")
    try:
        if (
            pr["number"] != number
            or pr["state"] != "open"
            or pr["base"]["ref"] != "main"
            or pr["base"]["repo"]["id"] != repository_id
            or pr["base"]["repo"]["full_name"] != repository
            or not re.fullmatch(REPOSITORY, pr["head"]["repo"]["full_name"])
            or not re.fullmatch(r"[a-f0-9]{40}", pr["head"]["sha"])
            or not re.fullmatch(r"[a-f0-9]{40}", pr["base"]["sha"])
            or type(pr["changed_files"]) is not int
            or not 0 <= pr["changed_files"] <= 100
        ):
            raise InputError("Pull request is outside the supported review scope")
    except (KeyError, TypeError):
        raise InputError("Invalid pull request metadata") from None
    return pr


def prepare_review(
    client: GitHubAPI, repository: str, repository_id: int, number: int
) -> PullRequestReview:
    pr = _pull(client, repository, repository_id, number)
    head_owner = pr["head"]["repo"]["full_name"].split("/", 1)[0]
    comparison = client.request(
        "GET",
        f"/repos/{repository}/compare/{pr['base']['sha']}...{head_owner}:{pr['head']['sha']}",
    )
    rows = comparison.get("files") if isinstance(comparison, dict) else None
    if not isinstance(rows, list) or len(rows) != pr["changed_files"]:
        raise InputError("Incomplete pull request file list")
    summaries: list[PlanSummary] = []
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise InputError("Invalid pull request file metadata")
        if not re.fullmatch(PLAN_PATH, item["filename"]) or item.get("status") == "removed":
            continue
        if item.get("status") not in {"added", "modified", "renamed", "copied", "changed"}:
            raise InputError("Unsupported synthetic fixture change")
        if len(summaries) >= 20 or not re.fullmatch(r"[a-f0-9]{40}", item.get("sha", "")):
            raise InputError("Synthetic review exceeds its bounds")
        head_repository = pr["head"]["repo"]["full_name"]
        blob = client.request("GET", f"/repos/{head_repository}/git/blobs/{item['sha']}")
        try:
            if (
                blob["encoding"] != "base64"
                or type(blob["size"]) is not int
                or not 0 <= blob["size"] <= MAX_REQUEST_BYTES
                or len(blob["content"]) > 2 * MAX_REQUEST_BYTES
            ):
                raise InputError("Synthetic blob exceeds its bounds")
            raw = base64.b64decode("".join(blob["content"].split()), validate=True)
            digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if len(raw) != blob["size"] or digest != item["sha"] or blob["sha"] != digest:
                raise InputError("Synthetic blob integrity mismatch")
        except (KeyError, ValueError, TypeError):
            raise InputError("Invalid synthetic blob") from None
        plan = load_normalized(raw)
        if plan.source != "synthetic-demo":
            raise InputError("Only synthetic normalized fixtures can be reviewed")
        report = build_report(plan)
        summaries.append(
            PlanSummary(
                path=item["filename"],
                blob_sha=digest,
                findings=len(report.findings),
                rules=tuple(sorted({finding.rule_id for finding in report.findings})),
                risk=report.overall_risk,
                policy_packs=report.policy_packs,
            )
        )
    review = PullRequestReview(
        repository=repository,
        repository_id=repository_id,
        pull_number=number,
        base_sha=pr["base"]["sha"],
        head_sha=pr["head"]["sha"],
        plans=tuple(summaries),
    )
    current = _pull(client, repository, repository_id, number)
    if (current["head"]["sha"], current["base"]["sha"]) != (review.head_sha, review.base_sha):
        raise InputError("Pull request changed during analysis; rerun the review")
    return review


def review_markdown(review: PullRequestReview) -> str:
    lines = [
        MARKER,
        "## Terramind synthetic fixture review",
        "",
        f"Reviewed head: `{review.head_sha}`",
        "",
        "Offline deterministic analysis of changed synthetic fixtures only. "
        "Terraform source, real plans, deployment state and AI advice were not evaluated.",
        "",
    ]
    if review.plans:
        lines += [
            "| Synthetic fixture | Risk | Findings | Rules | Policy packs |",
            "| --- | --- | --- | --- | --- |",
        ]
        lines += [
            f"| `{plan.path}` | {plan.risk} | {plan.findings} | "
            f"{', '.join(plan.rules) or 'None'} | {', '.join(plan.policy_packs)} |"
            for plan in review.plans
        ]
    else:
        lines.append(
            "No eligible changed synthetic fixtures were found; no analysis was performed."
        )
    lines += [
        "",
        "Advisory review only. This check never approves or applies infrastructure changes.",
    ]
    return "\n".join(lines) + "\n"


def publish_review(
    client: GitHubAPI,
    review: PullRequestReview,
    *,
    repository: str,
    repository_id: int,
    run_id: str,
) -> None:
    if (review.repository, review.repository_id) != (repository, repository_id):
        raise InputError("Review artifact targets another repository")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise InputError("Invalid trusted workflow run")
    pr = _pull(client, repository, repository_id, review.pull_number)
    if (pr["head"]["sha"], pr["base"]["sha"]) != (review.head_sha, review.base_sha):
        raise InputError("Stale review cannot be published; rerun the workflow")
    prefix = f"/repos/{repository}"
    managed = []
    for page in range(1, 11):
        rows = client.request(
            "GET", f"{prefix}/issues/{review.pull_number}/comments?per_page=100&page={page}"
        )
        if not isinstance(rows, list):
            raise InputError("Invalid comment list")
        for comment in rows:
            if (
                isinstance(comment, dict)
                and isinstance(comment.get("body"), str)
                and comment["body"].startswith(MARKER + "\n")
                and comment.get("user", {}).get("login") == "github-actions[bot]"
                and comment.get("user", {}).get("type") == "Bot"
                and type(comment.get("id")) is int
                and comment["id"] > 0
            ):
                managed.append(comment["id"])
        if len(rows) < 100:
            break
    else:
        raise InputError("Comment pagination exceeds the review limit")
    if len(managed) > 1:
        raise InputError("Multiple managed comments require operator review")
    text = review_markdown(review)
    if managed:
        client.request("PATCH", f"{prefix}/issues/comments/{managed[0]}", {"body": text})
    else:
        client.request("POST", f"{prefix}/issues/{review.pull_number}/comments", {"body": text})
    # The check stays neutral: fixture findings are not a deployment approval gate.
    client.request(
        "POST",
        f"{prefix}/check-runs",
        {
            "name": "Terramind synthetic fixture review",
            "head_sha": review.head_sha,
            "status": "completed",
            "conclusion": "neutral",
            "details_url": f"https://github.com/{repository}/actions/runs/{run_id}",
            "output": {"title": "Synthetic fixtures only", "summary": text},
        },
    )
