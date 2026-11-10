"""Trusted manual-workflow entry point; never checks out or executes a PR head."""

import argparse
import os
from pathlib import Path

from terramind.integrations.github import (
    GitHubClient,
    PullRequestReview,
    prepare_review,
    publish_review,
)
from terramind.normalizer.io import parse_json, read_bounded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "publish"))
    parser.add_argument("--pull-number", type=int)
    parser.add_argument("--artifact", type=Path, default=Path("artifacts/pr-review.json"))
    args = parser.parse_args()
    try:
        if (
            os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
        ):
            raise ValueError("Trusted manual main context is required")
        repository = os.environ["GITHUB_REPOSITORY"]
        repository_id = int(os.environ["GITHUB_REPOSITORY_ID"])
        client = GitHubClient(os.environ["GITHUB_TOKEN"])
        if args.command == "prepare":
            if args.pull_number is None:
                raise ValueError("A pull request number is required")
            review = prepare_review(client, repository, repository_id, args.pull_number)
            args.artifact.parent.mkdir(parents=True, exist_ok=True)
            args.artifact.write_text(review.model_dump_json(indent=2) + "\n", encoding="utf-8")
        else:
            raw = read_bounded(args.artifact, 64 * 1024)
            parse_json(raw, 64 * 1024)
            review = PullRequestReview.model_validate_json(raw)
            publish_review(
                client,
                review,
                repository=repository,
                repository_id=repository_id,
                run_id=os.environ["GITHUB_RUN_ID"],
            )
        print(f"Synthetic PR review {args.command} completed.")
        return 0
    except Exception:
        print("Synthetic PR review failed; check trusted context, scope and current PR head.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
