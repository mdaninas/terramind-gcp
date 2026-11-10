# Controlled delivery

Hosted CI and private analysis deployment passed. The development environment has
a required owner reviewer and exactly one allowed deployment branch, main. A real
OIDC exchange through WIF, immutable image promotion and live Firestore/Gemini
analysis were verified on 2026-11-10 (Asia/Jakarta). See the
[deployment record](api-delivery-verification.md). Project billing was subsequently
disabled with owner approval. See the [current operating status](cost-and-cleanup.md).

The separate manual [synthetic PR review](pr-integration.md) workflow is implemented
and locally tested. Its comment/check publishing has not been run on GitHub.
The optional [Eventarc receiver](eventarc-indexing.md) also remains undeployed.

## Pull request CI

`ci.yml` runs on pull requests, main pushes and manual dispatch. It checks Python
lint/types/schemas/tests, public-file privacy, locked dependencies, offline demos,
the container and a local HTTP round-trip. A separate job runs Terraform formatting,
validation, mock-provider plans and Checkov. No real provider plan or Terraform
apply runs in these jobs.

All CI jobs have read-only repository contents permission, no OIDC permission, no
environment secrets and no Google authentication action. Fork pull requests run
on ephemeral hosted runners. Checkout does not retain Git credentials. The Docker
context is an allowlist of source, package metadata and lockfiles.

The public-file scanner is defense in depth. It rejects credential markers,
private Terraform files, raw-plan JSON shapes and local credential-file paths
without printing matched values. Tests separately check request/log/model privacy.
Neither scanning nor a `synthetic-demo` label proves arbitrary data is non-sensitive.

## Manual image deployment

`deploy.yml` accepts only workflow_dispatch from main. Before building, its
credential-free job reads environment metadata using a read-only GitHub token.
The guard requires at least one reviewer and exactly one selected branch policy,
`main` of type branch. Missing settings, wildcards, tag policies or inaccessible
metadata block the run. Configure the environment before dispatching; do not rely
on GitHub automatically creating an unprotected environment.

The trusted main source is checked, built without cloud credentials and saved as
a one-day artifact belonging to that same workflow run. The protected deployment
job verifies the archive checksum, loads the image, and then authenticates using
WIF. Only this job receives id-token write permission. It never consumes a pull
request artifact or invokes Terraform apply.

The deployment job checks the existing service for cloud-mode configuration,
private invoker enforcement, zero minimum instances, an instance cap of one,
request-based CPU and the configured retention/admission limits. It publishes a
unique tag, resolves its SHA-256 digest, and updates only the existing service's
image. It does not create a service, modify IAM or repair configuration. A final
short-lived identity token drives an authenticated synthetic end-to-end check and
anonymous rejection checks. A failed smoke check fails the workflow; it does not
claim a release or automatically re-run a paid analysis.

Record the deployed digest from the workflow summary in the private Terraform
`container_image` variable before any later infrastructure apply. Terraform
continues to own the service configuration. Roll back by deploying the previous
verified digest, then reconcile the private variable in the same way.

Actions are pinned to full commit SHAs resolved from official upstream release
tags. Review updates rather than replacing pins with floating tags. Local
actionlint validation does not establish that a hosted run succeeds. See
[GitHub workflow security](https://docs.github.com/en/actions/reference/security/secure-use)
and [deployment environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments).

## Required environment configuration

Create `development` with a required reviewer and selected deployment branch
`main`, type branch. For this personal project the owner may review their own
manual dispatch; leave self-review prevention off unless another reviewer is
available. Keep environment approvals enabled. Set these non-secret environment
variables using reviewed Terraform outputs:

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | Approved dedicated project ID |
| `GCP_REGION` | `us-central1` |
| `CLOUD_RUN_SERVICE` | `terramind-dev` |
| `CLOUD_RUN_URL` | Existing Terraform service URL, without a trailing slash |
| `ARTIFACT_REPOSITORY` | `terramind-dev` |
| `WORKLOAD_IDENTITY_PROVIDER` | Terraform workload_identity_provider output |
| `DEPLOYER_SERVICE_ACCOUNT` | Terraform deployer_service_account output |

No API keys or service-account JSON files are required. GitHub's environment and
branch policies control when WIF can be used; the GCP provider additionally binds
the immutable repository/owner IDs, exact repository, main ref, environment subject,
manual event and exact deploy workflow. Protect changes to main and these files.
The provider requires GitHub's default immutable subject format:
`repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID:environment:development`.
Before deployment, the guard checks the repository's OIDC customization metadata
and rejects legacy/custom subject formats or a different identity prefix. GitHub
uses this default for new repositories created after July 15, 2026; verify it for
an existing repository. Do not add a broad subject wildcard to resolve a mismatch.
See the [GitHub OIDC subject reference](https://docs.github.com/en/actions/reference/security/oidc).
See [GitHub environment REST permissions](https://docs.github.com/en/rest/deployments/environments)
and [Google federation guidance](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

## Runtime activation and approval

The default `enable_analysis_api = false` retains health-only permissions. Setting
it to true enables these changes. They were explicitly approved, applied and
verified in the dedicated project; new deployments still require approval:

| Scope | Change |
| --- | --- |
| Runtime model role | Custom role with aiplatform.endpoints.predict and serviceusage.services.use; bind to runtime only |
| Runtime data role | Custom role with datastore.entities.get/list/create, conditioned on the named Terramind database |
| Deployer invocation | run.invoker on the existing service, enabling authenticated smoke checks |
| Report indexing | Exclude analyses.report_json from indexes; retain the existing expires_at TTL policy |
| Service configuration | Cloud mode, explicit project/database/model/location/language, 24-hour retention, six analyses per minute |
| Image | Approved new API image, pinned by digest; min zero and max one instance |

The runtime receives no bucket, update/delete, index-administration, IAM or service
deployment permissions. Publisher-model invocation is project-scoped; model IDs
are constrained in application configuration, not by an asserted model-level IAM
condition. Firestore IAM isolates the database, not individual collections. The
application adapters enforce knowledge_chunks reads and analyses create/read.
These are explicit limitations. See [Firestore IAM](https://firebase.google.com/docs/firestore/security/iam)
and [model access control](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/access-control).

After owner approval and verification of the target project, current model
availability, quotas and initialized private backend, update the ignored dev
variable file with `enable_analysis_api = true` and `max_instances = 1`. Keep the
existing image digest while preparing permissions/configuration. Plan privately:

```sh
umask 077
export PRIVATE_PLAN_DIR="$(mktemp -d)"
terraform -chdir=terraform/environments/dev plan -out="$PRIVATE_PLAN_DIR/analysis.plan"
terraform -chdir=terraform/environments/dev show -no-color "$PRIVATE_PLAN_DIR/analysis.plan"
```

Review for only the listed IAM, index and service changes. Stop if unrelated
resources change. Do not publish the plan as a CI artifact. Apply the reviewed
plan only with explicit approval:

```sh
terraform -chdir=terraform/environments/dev apply "$PRIVATE_PLAN_DIR/analysis.plan"
```

For a new activation, the old health image does not expose analysis routes until
image promotion. Publish reviewed source/workflows, configure the protected
environment and manually dispatch deployment. Record hosted CI, WIF, image digest,
authentication, retained report and source-validation results. These checks passed
for the current dedicated deployment. Resources stay active until final cleanup is
performed and verified.

## Cloud demonstration

After an approved deployment, in Bash or Cloud Shell:

```sh
export CLOUD_RUN_URL="$(terraform -chdir=terraform/environments/dev output -raw service_url)"
export TERRAMIND_ID_TOKEN="$(gcloud auth print-identity-token)"
make demo-cloud
unset TERRAMIND_ID_TOKEN
```

The identity must already have invoker access. Do not enable shell tracing or print
the token. The client refuses redirects, sends only the packaged synthetic sample,
compares deterministic findings, checks stored JSON and both exports, and validates
citations against the reviewed local corpus. It writes a content-free verification
summary under ignored artifacts. One invocation requests one analysis and can incur
model/retrieval, report-storage and read costs. No automatic schedule is installed.
