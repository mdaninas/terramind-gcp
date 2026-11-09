"""Read-only guard: manual deployments require reviewers and the exact main branch."""

import json
import os
import sys
from typing import Any
from urllib.request import Request, urlopen


def protected(environment: dict[str, Any], branches: dict[str, Any]) -> bool:
    rules = environment.get("protection_rules", [])
    reviewers = any(
        rule.get("type") == "required_reviewers" and bool(rule.get("reviewers")) for rule in rules
    )
    policy = environment.get("deployment_branch_policy") or {}
    allowed = branches.get("branch_policies", [])
    return bool(
        reviewers
        and policy.get("custom_branch_policies") is True
        and policy.get("protected_branches") is False
        and branches.get("total_count") == 1
        and len(allowed) == 1
        and allowed[0].get("name") == "main"
        and allowed[0].get("type") == "branch"
    )


def main() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    import re

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
        print("Deployment environment check requires repository metadata and a read token.")
        return 1

    def get(suffix: str) -> dict[str, Any]:
        request = Request(
            f"https://api.github.com/repos/{repository}/environments/development{suffix}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(request, timeout=10) as response:
            value: dict[str, Any] = json.loads(response.read(256 * 1024))
            return value

    try:
        ready = protected(get(""), get("/deployment-branch-policies?per_page=100"))
    except Exception:
        ready = False
    print(
        "Deployment environment protection verified."
        if ready
        else "Deployment blocked: configure required reviewers and an exact main branch policy."
    )
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
