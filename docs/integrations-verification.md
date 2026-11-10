# PR review and Eventarc verification

The synthetic PR review and Eventarc indexing implementations passed local
verification on 2026-11-10 (Asia/Jakarta). Changes were tested in the existing
Windows checkout based on `899b73760eaad852332af16fb9a01b4ea620d991`, before
committing the integration changes. This is not a fresh-clone verification or
evidence of hosted activation. See the [machine-readable results](evaluations/integrations-2026-11-10.json).

## Implemented behavior

- The [manual PR workflow](pr-integration.md) installs only trusted main code,
  analyzes bounded synthetic Git blobs with a read-only token, and passes a typed
  same-run artifact to a separate publisher. Publishing revalidates the PR head,
  updates only its own bot comment and creates a neutral check.
- The [Eventarc receiver](eventarc-indexing.md) validates the exact source and
  generation against the packaged synthetic corpus. A durable receipt deduplicates
  deliveries. A fenced Firestore transaction commits index changes and receipt
  together, preventing an expired worker from committing a staged result.
- Optional Terraform adds a separate private receiver and trigger only when
  explicitly enabled. It defaults to disabled and has no effect on the existing
  analysis runtime's identity or deployment workflow.

## Observed checks

| Check | Result |
| --- | --- |
| Full application suite | 366 passed in 9.57 seconds |
| Normalization/policy branch-aware coverage | 97.58%, unchanged |
| Targeted integration/entry-point suite | 74 passed |
| New event/integration module branch-aware coverage | 92.23%, measured separately |
| Ruff lint/format, strict mypy and schemas | Passed; mypy checked 56 source files |
| Packaged synthetic corpus drift | Passed; ten documents match reviewed Markdown |
| Terraform formatting and validation | Passed in project, bootstrap and dev roots |
| Terraform mock-provider cases | 15 passed; no cloud credentials or apply |
| Terraform Checkov | 38 passed, zero failed, four previously documented exceptions |
| Dockerfile Checkov | 48 passed, zero failed, zero skipped |
| Actionlint | All three workflows passed; ShellCheck integration disabled on Windows |
| Source archive and wheel | Built successfully |
| Isolated wheel installation | Packaged corpus and PR review contracts loaded without cloud extras |
| Real local event entry point | Health 200, disabled ingestion 503; no provider calls |
| Public-file privacy and whitespace checks | Passed |

The tests cover fork input, pinned comparisons and blob integrity, unknown/raw
fields, malformed/oversized fixtures, stale PR heads, spoofed bot markers, manual
workflow trust and publishing permissions. Event tests cover duplicate deliveries
across worker instances, changed generations with reused vectors, unknown/old
objects, source mismatch, busy/lost/expired leases, failed commits, concurrent
index changes, generation preconditions and SDK client cleanup.

The local HTTP check started the real Python entry point with
`TERRAMIND_SERVICE=events` and ingestion disabled. It confirmed separation from the
analysis app and shut down its temporary process after verification. It does not
exercise Cloud Run IAM or Eventarc transport. The isolated wheel check imported
the packaged ten-document manifest and versioned review model from an installed
wheel with base dependencies only. SDK transaction tests use local doubles, not a
Firestore emulator or live database.

Reproduce the checks with:

```sh
uv run --locked python scripts/check.py
uv run --locked pytest tests/integration/test_pr_review.py tests/integration/test_eventarc.py tests/unit/test_eventarc_adapters.py tests/security/test_pr_integration.py tests/unit/test_api_entrypoint.py --cov=terramind.events --cov=terramind.integrations --cov-report=term-missing --cov-fail-under=80 -q
uv run --locked python scripts/check_infrastructure.py --terraform ./artifacts/tools/terraform/terraform.exe --scan
uv run --locked python scripts/check_public_files.py
uv build
```

Use a platform-appropriate Terraform path. `artifacts/tools/actionlint/actionlint.exe
-shellcheck= .github/workflows/ci.yml .github/workflows/deploy.yml
.github/workflows/pr-review.yml` was the local syntax command. Raw verification
logs and local artifacts remain ignored.

## Hosted verification still required

No workflow was dispatched, no PR comment/check was published, no event trigger
or receiver was deployed, and no IAM, billing or cloud resources were changed
during integration implementation. No embedding or Gemini calls were made.
Project billing remains disabled from the earlier owner-approved shutdown.

A future deliberate maintainer run must verify GitHub publishing with a synthetic
PR, stale-head rejection and repeat comment updates. A separate approved cloud
activation must verify Eventarc transport, private receiver IAM, storage-generation
reads, Firestore transactions and receipts, retry behavior and cost. Local
SDK/mock-plan results do not substitute for those checks.

Historical incident similarity, user login/dashboard/history and additional
policies remain the next requested development work. They are not implemented
by this change.
