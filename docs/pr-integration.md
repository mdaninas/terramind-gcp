# Synthetic pull request review

The manual `Review synthetic PR fixtures` workflow prepares a deterministic review
of an open pull request targeting `main`, then publishes one managed bot comment
and a neutral check on the reviewed head commit. Implementation, fake-API tests
and workflow syntax are verified locally. Subsequent hosted verification on PR #1
published the exact-head review and neutral checks. Two successful attempts
retained one managed comment. See the [hosted record](live-integrations-verification.md).

## Supported input

Only changed `examples/normalized-plans/[a-z0-9_-]+.json` files are eligible.
They must fit the existing 256 KiB/100-change schema and declare
`source: synthetic-demo`. A label does not prove that caller data is synthetic;
contributors must use handcrafted synthetic facts only. Unknown fields, raw plans,
private identifiers and `local-normalizer` payloads are rejected by the schema.
Removed fixtures and other files are not analyzed. At most 20 eligible fixtures
and 100 changed PR files are supported; larger reviews fail explicitly.

The review never executes Terraform, checks out a contributor branch, installs PR
dependencies or calls Google services. It does not analyze `.tf` source changes,
create a real plan or establish deployment safety. The comment explicitly names
this scope; an empty review means no eligible fixture was analyzed.

## Security design

1. A repository maintainer manually dispatches the workflow from `main`, supplying
   only a PR number. Other events and branches are rejected by both YAML and CLI.
2. The read-only analysis job installs the locked package from the trusted workflow
   commit. It validates the immutable base repository ID, open PR, target branch,
   full base/head SHAs and bounded changed-file count.
3. The GitHub compare request pins both commits, including the fork owner for a
   fork PR. Git blobs are read as bounded base64 data and verified against their
   Git object IDs. No `raw_url`, artifact URL or executable supplied by the PR is used.
4. The artifact contains only typed fixture paths, commit/object IDs, counts, rule
   IDs and risk enums. It carries no raw plan, report body, arbitrary narrative,
   credentials or model output. Retention is one day.
5. A separate publishing job downloads only that workflow run and attempt's named
   artifact. It installs the same trusted base package, validates the artifact and
   rechecks the current open PR and base/head SHAs before any write. A stale review
   fails and must be rerun.
6. The job updates only a comment with the exact Terramind marker authored by
   `github-actions[bot]`; human marker lookalikes are ignored. Multiple managed
   comments or more than 1,000 existing comments require operator review.

Only the publisher receives `pull-requests: write` and `checks: write`.
Neither job receives cloud OIDC permissions or uses repository secrets.
`pull_request_target` and `workflow_run` are not used. Inputs enter the shell
through quoted environment variables, not interpolated expressions. Actions are
pinned to full commit SHAs and checkout credentials are not persisted.

Checks remain neutral even when fixtures contain findings. Each comment/check
includes the exact reviewed head and an explicit advisory limitation. A PR can
change immediately after the last metadata read; the displayed SHA is the review
target, not a promise that a comment always represents the latest commit.
Partial publish failures can leave a comment without a check. Rerunning updates
the managed comment and publishes a new check for the validated head.

## Run and verify

Run the credential-free tests and syntax check:

```sh
uv run --locked pytest tests/integration/test_pr_review.py tests/security/test_pr_integration.py -q
```

After the reviewed workflow is merged, open GitHub Actions, select **Review
synthetic PR fixtures**, choose `main` and supply an open PR number containing an
eligible fixture. This publishes to that PR and needs a deliberate maintainer
dispatch. Rerun after the PR head or base changes. No GCP activation is required.

References: [GitHub workflow security](https://docs.github.com/en/actions/reference/security/secure-use),
[commit comparisons](https://docs.github.com/en/rest/commits/commits#compare-two-commits),
[issue comments](https://docs.github.com/en/rest/issues/comments), and
[checks](https://docs.github.com/en/rest/checks/runs#create-a-check-run).
