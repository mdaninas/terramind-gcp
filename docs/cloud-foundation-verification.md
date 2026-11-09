# Cloud foundation verification

This record captures the foundation and liveness deployment. The service was deployed
with owner approval in a new,
dedicated portfolio project on 2026-11-09 (Asia/Jakarta). Cloud Run authentication,
private buckets and Firestore index readiness were verified. The existing lab
project was left unchanged. Notification delivery was not tested. Federation
exchange was untested at this stage; it subsequently passed with the protected
analysis deployment recorded in [API delivery verification](api-delivery-verification.md).

## Files

| Area | Created or updated |
| --- | --- |
| API adapter | `src/terramind/api/{__init__,__main__,app}.py`, `apps/api/main.py` |
| Container | `Dockerfile`, `.dockerignore`, `.env.example` |
| Dedicated project | `terraform/project/main.tf`, synthetic variable/backend examples, provider lockfile, `tests/project.tftest.hcl` |
| Bootstrap | `terraform/bootstrap/main.tf`, local variable/backend examples, provider lockfile, `tests/state.tftest.hcl` |
| Dev environment | `terraform/environments/dev/{versions,variables,main,outputs}.tf`, variable/backend examples, provider lockfile, `tests/foundation.tftest.hcl` |
| Modules | `terraform/modules/{artifact_registry,cloud_run,firestore,identity,storage}/main.tf`, `firestore/firestore.rules` |
| Checks and packaging | `scripts/check_infrastructure.py`, `Makefile`, `pyproject.toml`, `uv.lock`, `.gitignore` |
| Tests | `tests/integration/test_health.py`, `tests/unit/test_api_entrypoint.py` |
| Documentation | README, changelog, architecture, roadmap, threat model, evaluation, deployment setup, cost/cleanup, security exceptions and this record |

## Decisions and tradeoffs

- Keep the offline analyzer independent of optional HTTP dependencies. The API
  imports the domain package, while the offline CLI never imports the API.
- Use Cloud Run invoker IAM instead of maintaining application credentials. Local
  loopback liveness does not prove cloud authentication.
- Keep `/healthz` for internal container probes and add `/health` for external
  liveness. Google's frontend returned 404 for the reserved external path ending
  in `z`; both paths use the same handler. This platform compatibility adjustment
  preserves the PRD probe while allowing real invoker-IAM verification. See
  [Cloud Run reserved URL paths](https://docs.cloud.google.com/run/docs/known-issues).
- Separate state bootstrap and application state. A null image allows the
  repository to exist before the first container build/push, avoiding a deployment
  cycle or an unreviewed placeholder image.
- Use separate runtime, image-deployment and ingestion identities. The health
  runtime has no data privileges. Federation is configured for immutable repository
  IDs, main, an exact workflow, manual event and protected environment subject.
- Isolate project/billing controls, state storage and application resources in
  three state prefixes. Each API has one owning root. The project budget uses
  billing-account currency and excludes credits so trial consumption is visible;
  it provides alerts rather than a spending cap.
- Use a named Firestore database, native Terraform vector index and expiry-field
  policy. Database-conditioned IAM does not enforce collections; client rules
  deny direct access, and later application adapters must enforce collection names.
- Default to Google-managed encryption for synthetic images and omit legacy bucket
  access-log sinks. The [resource-level exceptions](security-exceptions.md) describe
  these decisions and the scanner's unresolved module-subject limitation.

## Commands executed locally

Terraform was downloaded from HashiCorp's official 1.17.1 release and its archive
SHA-256 matched the published checksum. The executable remains under ignored
`artifacts/tools/terraform/`, rather than being committed. Google provider 8.10.0
was verified as signed by HashiCorp and locked for Windows/Linux amd64.

```sh
uv sync --locked
uv run --locked python scripts/check.py
uv run --locked python scripts/demo_offline.py
uv run --locked pytest tests/integration/test_health.py tests/unit/test_api_entrypoint.py --cov=terramind.api --cov-report=term-missing
uv run --locked python scripts/check_infrastructure.py --terraform artifacts/tools/terraform/terraform.exe --scan
uvx --from checkov==3.4.3 checkov -f Dockerfile --framework dockerfile --skip-download --compact --quiet
uv export --locked --all-extras --no-emit-project --format requirements-txt --output-file artifacts/audit-requirements.txt --quiet
uv run --locked pip-audit --no-deps --disable-pip --requirement artifacts/audit-requirements.txt
uv build
git diff --check
```

The checker executes formatting, backend-free initialization with readonly
lockfiles, validation and mock-provider tests for each root. Provider checksums
were also populated using `terraform providers lock -platform=windows_amd64
-platform=linux_amd64` in each root. A separate local subprocess smoke check
started Uvicorn on a temporary loopback port, received the expected HTTP 200 JSON
and shut down the subprocess. It did not invoke GCP.

## Results

- Python suite: **168 passed**, Ruff and strict mypy passed, schema checks passed.
- Existing normalization/policy coverage: **97.58%**. Separately measured API
  adapter branch-aware coverage: **94.92%** across 14 API tests.
- Terraform formatting and validation: **passed** for project, bootstrap and dev.
- Terraform mock plans: **ten passed**, including negative budget/access/image/scale tests.
- Checkov Terraform: **17 passed, zero failed, four documented resource-level skips**.
- Checkov Dockerfile: **48 passed, zero failed, zero skipped**.
- Offline demo still produces four findings. Wheel and source distribution build.
- Pinned Python dependency audit: **no known vulnerabilities reported**, exit 0.
  pip-audit emitted a Windows cache-write warning; the audit completed.
- Real local HTTP liveness: **200**, expected service/version response.
- Local Windows Docker daemon did not answer the bounded availability probe.
  A real Linux amd64 build subsequently passed in Cloud Shell. Running that image
  with a read-only filesystem, dropped capabilities and no-new-privileges returned
  the expected HTTP 200 liveness JSON.

## Live cloud verification

- Created the dedicated project with `gcloud projects create`, enabled management
  APIs only there and imported the project into Terraform. Linked the approved
  existing billing account; no billing account or payment method was created.
- Applied reviewed project, bootstrap, foundation and service plans. Migrated
  project/bootstrap state to separate GCS prefixes; dev uses its own prefix.
- Verified the project-filtered budget with `gcloud billing budgets describe`:
  IDR 180,000 monthly, credits excluded, 50/90/100% thresholds, default billing and
  project-owner recipients enabled. Alerts are not a hard spending cap.
- Built with `docker build --platform linux/amd64`, ran the hardened container and
  published its image. Registry connection errors affected `docker push`; the
  compatibility image was successfully published with `docker buildx build --push`.
  Terraform deploys the resulting immutable SHA-256 digest.
- `curl "$SERVICE_URL/health"` returned **403** anonymously. A request with a
  short-lived Google identity token returned **200** and exactly
  `{"status":"ok","service":"terramind","version":"0.1.0"}`.
- `gcloud storage buckets describe` verified enforced public access prevention,
  uniform access and versioning on both state and synthetic-runbook buckets.
- `gcloud firestore indexes composite list` reported **READY**. The report expiry
  field policy reported **ACTIVE**. The Firebase Rules API returned the named
  database's deny-all client rule release.
- Project and service IAM policies contain no public principals. The runtime has
  no explicit project-role grants. Separate deployment and ingestion identities
  are configured; this does not establish collection-level Firestore enforcement.
- The configured demo limits are zero minimum instances, one maximum instance,
  request-based CPU and a 30-second request timeout. No model calls were made
  during these foundation checks; later CLI verification is recorded separately.
- Final live `terraform plan -detailed-exitcode` checks returned **0** for all
  three roots: project, bootstrap and dev. No configuration drift was reported.

One long initial apply outlived its short-lived credential while saving state.
The failed process had exited; its recovery state and backend were backed up
privately. After verifying lock ownership, the stale GCS lock was released using
its generation and the recovery state was pushed without force. A fresh live
foundation plan reported no changes. No resources were recreated to recover state.
Private plans, logs, backend settings and inventory remain outside version control.

## Remaining work and operational limits

The deployment is active for development. Cleanup has not been executed; follow
the [cleanup procedure](cost-and-cleanup.md) when the portfolio work is finished.
No automatic shutdown is configured. Budget email delivery, server-error alert
delivery, federation exchange, protected GitHub environments and organization-level
IAM/log-sink inheritance have not been verified. The server-error policy currently
has no notification channel. The subsequent retrieval and Gemini CLI checks are
recorded in [retrieval verification](retrieval-verification.md). Analysis endpoints
and deployment workflows remain subsequent work.
