# API and delivery verification

The private analysis API is deployed and verified on GCP. On 2026-11-10
(Asia/Jakarta), the protected GitHub workflow exchanged its identity through WIF,
published an immutable image and passed an authenticated end-to-end analysis.
All verification data was synthetic. Resources remain active for development;
final portfolio cleanup has not been executed.

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
| Documentation | API operating guide, delivery guide, roadmap, architecture, threat model and evaluation |

The API reuses policy and synthesis through an injectable service. Report storage
has a protocol and independent memory/Firestore adapters. A server-rendered page
avoids a frontend framework, login service or dashboard. Google authentication
stays at Cloud Run's IAM boundary. All invokers share one synthetic demo trust
boundary; there is no per-user report ownership.

Reports use create-only writes and application-enforced expiry in addition to
Firestore's asynchronous TTL. Process-local admission control limits request
cost and concurrency without imposing a project-wide spending cap. Runtime roles
are opt-in in Terraform and activated in the approved project. The image deployer
can update its existing service, without infrastructure provisioning or IAM
administration grants. The workflow updates only the image.

## Local and hosted checks

```sh
uv run --locked python scripts/check.py
uv run --locked python scripts/check_public_files.py
uv run --locked pytest tests/integration/test_analysis_api.py tests/unit/test_report_storage.py tests/security/test_delivery.py -q
uv run --locked python scripts/check_infrastructure.py --terraform ./artifacts/tools/terraform/terraform.exe --scan
./artifacts/tools/actionlint/actionlint.exe -shellcheck= .github/workflows/ci.yml .github/workflows/deploy.yml
uv run --locked --extra api python -m terramind.api
uv run --locked python scripts/demo_cloud.py --url http://127.0.0.1:8080 --local
```

The full suite passed **297 tests**, including the immutable OIDC identity guard.
All eight fixture expectations, streamed size limits, duplicate/malformed JSON,
timeouts, storage failure, expiry, throttling, model fallback, HTML escaping,
SDK cleanup and workflow trust checks passed. Ruff lint/format, strict mypy
(48 source files), generated schema drift and public-file privacy checks passed.
Normalization/policy branch-aware coverage was **97.58%**. Separate API/storage
coverage was **92.11%** across 74 targeted tests. The all-extras dependency audit
reported no known vulnerabilities, with a non-fatal Windows cache-write warning.
Source and wheel builds passed before the OIDC guard change; isolated base-only
analysis and API-only route/asset loading worked without Google SDKs installed.

Terraform formatting and all three roots validated. Twelve mock-plan cases passed
(three project, two bootstrap, seven dev); the seven dev cases were rerun after
the identity change. Checkov reported 17 passed, zero failed and four documented
skips. Dockerfile scanning passed 48 checks without failures or skips. Actionlint
1.7.12 passed both workflows; ShellCheck integration was disabled on Windows.

The [hosted CI run for the deployed source](https://github.com/mdaninas/terramind-gcp/actions/runs/42660198226)
passed both jobs. Its Linux container ran with a read-only filesystem, all
capabilities dropped and privilege gain disabled. Real HTTP checks verified all
four findings, saved JSON, Markdown and HTML in offline mode. The local Chrome
report interaction was also verified; its ignored screenshot is local UI evidence,
not proof of a cloud browser session.

## Approved cloud activation and deployment

Operator commands used an authenticated local Google Cloud CLI and ADC stored
outside the repository. Actual backend, variable and saved-plan paths were kept
under ignored artifacts. These are the executed command forms; placeholders
protect private operator paths:

```sh
gcloud projects describe terramind-gcp-mdaninas --format=json
terraform -chdir=terraform/environments/dev init -backend-config=PRIVATE_BACKEND
terraform -chdir=terraform/environments/dev plan -var-file=PRIVATE_VARS -out=PRIVATE_PLAN
terraform -chdir=terraform/environments/dev apply PRIVATE_PLAN
gcloud run services describe terramind-dev --project=terramind-gcp-mdaninas --region=us-central1 --format=json
gcloud run services get-iam-policy terramind-dev --project=terramind-gcp-mdaninas --region=us-central1 --format=json
gcloud firestore indexes fields list --collection-group=analyses --database=terramind-dev --project=terramind-gcp-mdaninas --format=json
gcloud firestore indexes composite list --collection-group=knowledge_chunks --database=terramind-dev --project=terramind-gcp-mdaninas --format=json
```

Runtime activation applied six additions and two in-place changes, with no deletion
or replacement: two custom roles and bindings, deployer invoker access, report
indexing, service configuration and the runtime identity description. Data
permissions are get/list/create, conditioned on the named database; prediction
permissions are predict and quota use at project scope. Live role and policy reads
verified these grants and no public principals. The report expiry policy is ACTIVE,
report-body and expiry-field indexes are excluded, and the 768-dimensional knowledge
index is READY.

The first workflow failed closed during federation because GitHub issued an
immutable subject containing owner/repository IDs. The provider was corrected
through a separately reviewed one-resource in-place plan. Only the exact subject
format changed; repository and owner IDs, repository name, main ref, manual event
and exact workflow restrictions remained enforced. The deployment guard now checks
OIDC metadata before building. No wildcard or long-lived key was introduced.

The [successful protected deployment](https://github.com/mdaninas/terramind-gcp/actions/runs/42660304648)
used source `a9ca913877b51e624b961230ca116dba769bff04`. It built without cloud
credentials, verified the same run's archive, exchanged OIDC through WIF, checked
the runtime and deployed this image digest:

```text
sha256:6f63da0382f4b70e13ba469ee8f2f5866b558729e8333aca53543a459a20eeb1
```

Cloud Run revision `terramind-dev-00004-9zq` became Ready. The workflow executed:

```sh
uv run --locked python scripts/demo_cloud.py --url "$CLOUD_RUN_URL" --require-advisory
```

| Live check | Observed result |
| --- | --- |
| Anonymous health, demo and analysis submission | Rejected |
| Authenticated health and demo | 200 |
| Malformed JSON | 400 |
| Synthetic analysis | 201; four original HIGH findings preserved |
| Retrieval and model | available; gemini-3.5-flash; ten sources matched the reviewed corpus |
| Saved report, Markdown and HTML | Passed |
| Analysis request latency | 10.898 seconds, one observation including retrieval, synthesis and storage |
| Independent operator check | Existing Firestore report validated; three authenticated reads 200; anonymous report 403; zero new model calls |
| Retention and scaling | 24-hour expiry; minimum zero and maximum one instance; request-based CPU |

The [machine-readable record](evaluations/api-delivery-2026-11-10.json) contains
content-free evidence. Model prose remains advisory; provenance validation does
not establish semantic correctness. Terraform's private image variable was
reconciled to the promoted digest. A reviewed in-place update removed only the
CLI client/client-version metadata added during image promotion; the image and
service specification stayed unchanged. The final live dev plan returned exit
**0**, with no resource changes.

## Security and remaining work

Errors and application logs omit rejected input, arbitrary URLs, report IDs,
headers, tokens and provider exception details. HTML uses escaping and a
restrictive same-origin Content Security Policy. No raw Terraform plans, state or
credentials were committed, published as CI artifacts or sent to the model.

The development environment retains its required owner reviewer and exact main
branch policy. Cloud Run remains private, with minimum zero and maximum one
instance, a 30-second timeout and six admitted analyses per minute per process.
The monthly alert remains IDR 180,000 before credits, with 50/90/100% thresholds;
it does not stop spending. No automatic shutdown or background generation is
configured. Storage, reads and model use remain metered.

Portfolio walkthrough/screenshots and fresh-clone reproduction were subsequently
completed in the [release verification record](release-verification.md). Release
tagging and final resource cleanup remain owner actions. Budget notification
delivery, a Monitoring notification channel and organization-inherited policies
are not verified by these checks. Resources were last documented as active;
cleanup has not been executed.
