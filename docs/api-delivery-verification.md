# API and delivery verification

The API and private report presentation are implemented. Hosted CI and the
restricted analysis container are verified; the protected deployment environment
is configured. WIF exchange, runtime IAM activation and deployment of the new
analysis image remain unverified. No GCP resource, IAM or API changes were executed
in this feature's delivery checks.

## Files and decisions

| Area | Created or modified |
| --- | --- |
| HTTP boundary | api/app.py, api/service.py, schemas/api.py, analysis-request.v1.schema.json |
| Presentation | api/views.py, packaged CSS/JavaScript and synthetic sample |
| Persistence | reports/store.py, cloud/reports.py |
| Delivery | .github/workflows/ci.yml and deploy.yml, Dockerfile, privacy/environment/runtime check scripts |
| Demonstration | scripts/demo_cloud.py, Makefile, .env.example |
| Infrastructure | Dev configuration/tests, identity, Firestore and Cloud Run modules |
| Verification | Analysis API integration, Firestore storage and workflow security tests |
| Documentation | API operating guide, delivery approval guide, roadmap, architecture, threat model and evaluation |

The implementation reuses policy and synthesis through an injectable service.
Report storage has a protocol and independent memory/Firestore adapters. A small
server-rendered page avoids a frontend framework, login service or dashboard.
Google authentication stays at Cloud Run's existing IAM boundary. All invokers
share one synthetic demo trust boundary; there is no per-user report ownership.

Reports use create-only writes and application-enforced expiry in addition to
Firestore's asynchronous TTL. Process-local admission control limits request
cost and concurrency, without pretending to impose a project-wide spending cap.
Runtime IAM is opt-in. The image deployer stays unable to change infrastructure.

## Commands and observed results

```sh
uv run --locked python scripts/check.py
uv run --locked python scripts/check_public_files.py
uv run --locked pytest tests/integration/test_analysis_api.py tests/unit/test_report_storage.py tests/security/test_delivery.py -q
uv run --locked python scripts/check_infrastructure.py --terraform ./artifacts/tools/terraform/terraform.exe --scan
./artifacts/tools/actionlint/actionlint.exe -shellcheck= .github/workflows/ci.yml .github/workflows/deploy.yml
uv run --locked --extra api python -m terramind.api
uv run --locked python scripts/demo_cloud.py --url http://127.0.0.1:8080 --local
```

Targeted API/storage/delivery tests passed, including all eight fixture expectations,
actual streamed size limits, duplicate/malformed JSON, schema/privacy boundaries,
slow-body timeout, storage failure, expiry before TTL deletion, throttling, model
fallback, escaped rendering, SDK connection cleanup and workflow trust conditions.
The full suite passed: **291 tests**, with **97.58%** normalization/policy branch-aware
coverage. Ruff lint/format, strict mypy (48 source files), generated schema drift and
public-file privacy checks passed. Separate API/report-storage coverage was
**92.11%** across 74 targeted tests. The all-extras dependency audit reported no
known vulnerabilities, with the existing non-fatal Windows cache-write warning.
Source distribution and wheel builds passed. Isolated base-only offline analysis
and API-only asset/sample/route loading passed without Google SDKs installed.

Terraform formatting and all three roots validated using isolated data directories
and mock providers. Twelve mock-plan cases passed (three project, two bootstrap,
seven dev). Checkov reported 17 passed, zero failed and four documented skips.
Actionlint 1.7.12 passed both workflows; the binary was downloaded from the official
release and verified against its published checksum. ShellCheck was not available
in that Windows validation, so that optional actionlint integration was disabled.
Dockerfile Checkov scanning passed 48 checks with zero failures or skips.

The local real-HTTP smoke check preserved four HIGH findings and verified report
round-trip, Markdown and HTML. One observed POST took 0.005 seconds in offline
memory mode. This does not measure Gemini, Firestore or cloud latency. Chrome's
analysis button created a report and navigated to its report page; screenshot proof
is retained under ignored artifacts. This browser check used no Google services.

## Security and live gates

Errors and logs omit rejected input, arbitrary URLs, identifiers, headers, tokens
and provider exception details. HTML uses escaping and a restrictive same-origin
Content Security Policy. No raw Terraform plans, credentials or long-lived keys
were uploaded or committed. The Docker build context excludes operator artifacts.

The local Docker engine did not answer a bounded CLI check after Docker Desktop
was started. The new analysis container was therefore not built or smoke-tested
locally. The new image was subsequently built and executed on a GitHub-hosted
Linux runner, as recorded below.

Initial GitHub inspection found no environments. The development environment was
then configured through authenticated GitHub API calls with an owner reviewer,
self-review permitted, exactly one main branch policy and seven non-secret
deployment variables. Its settings passed the same guard used by the workflow.
No long-lived credential was created or added to GitHub. Google operator access
is still required for runtime activation; no GCP mutations were attempted.

## Hosted CI evidence

Implementation commit `e284f92` passed all 291 Python tests, the dependency audit,
Terraform/Checkov checks and the image build. Its readiness probe encountered a
connection reset during startup. Commit `f891019` added bounded retry handling for
startup errors. The [successful hosted CI run](https://github.com/mdaninas/terramind-gcp/actions/runs/42596169414)
passed both jobs on Ubuntu 24.04 with Python 3.12.16. The restricted container
used a read-only filesystem, dropped all capabilities and disabled privilege gain.
Its real HTTP check preserved all four findings and verified persisted JSON,
Markdown and the report page. One observed offline POST took 0.002 seconds.
This is not a live Firestore/Gemini measurement or a deployed Cloud Run check.

To finish live verification, activate the reviewed
[runtime IAM/index/configuration changes](delivery.md#runtime-change-prepared-for-approval)
through an authenticated Google operator session, then run protected deployment
and the authenticated cloud demo. The workflows and environment protection are
already configured. Existing health and retrieval resources remain active. Cleanup remains
tracked for completion of the portfolio project.
