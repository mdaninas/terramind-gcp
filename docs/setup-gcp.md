# GCP setup and deployment

The Terraform foundation and FastAPI liveness service were deployed in an approved
dedicated project. Real `/health` requests returned anonymous 403 and authenticated
200. The [verification record](cloud-foundation-verification.md) separates those
live results from configuration checks and mock-provider tests.

Provisioning, API enablement, IAM changes, image uploads and paid resource usage
require explicit owner approval. The commands below are operator instructions;
they are not run by the application or the local validation script.

## Local verification

Install Terraform 1.10 or later, below 2.0. The configuration was checked with
Terraform 1.17.1 and Google provider 8.10.0. Provider lockfiles include Windows and
Linux amd64 checksums. Python dependencies are pinned in `uv.lock`.

```sh
uv sync --locked
uv run --locked python scripts/check.py
uv run --locked python scripts/check_infrastructure.py --scan
uv run --locked --extra api python -m terramind.api
```

If Terraform is outside PATH, pass `--terraform /absolute/path/to/terraform`.
The infrastructure checker uses an isolated `TF_DATA_DIR`, initializes with
`-backend=false`, validates all three roots and runs mock-provider plans. It never runs
apply, contacts a remote backend or uses a GCP provider for real resource operations.
Initial package/provider downloads require internet access. The standalone
`terraform test` runs also use mocks. The checker now covers the optional project
root, state bootstrap and dev environment.

The local service binds to `127.0.0.1:8080`; `GET /health` and `GET /healthz` return liveness only.
It does not implement Google authentication locally. The container binds to
`0.0.0.0` and respects Cloud Run's `PORT` environment variable.

Use `/health` for external Cloud Run checks. `/healthz` remains the PRD-compatible
container probe, but Google's frontend reserves some paths ending in `z` and
returned 404 for that external path during verification. The alias serves the
same handler and remains protected by Cloud Run invoker IAM. See
[reserved URL paths](https://docs.cloud.google.com/run/docs/known-issues).

```sh
docker build -t terramind:local .
docker run --rm -p 127.0.0.1:8080:8080 --read-only --cap-drop=ALL --security-opt=no-new-privileges terramind:local
```

## Project and operator prerequisites

Use an isolated, approved demo project with billing configured. Confirm the project
ID, numeric project number, allowed region, existing Firestore databases and any
organization policies. Inspect existing resources before changing a shared lab.

For a new portfolio project, `terraform/project` manages project creation, billing
linkage, audit configuration and a project-filtered monthly alert budget. Set its
local variable file from the synthetic example, using an approved organization,
existing billing account and that account's currency. Its state starts locally;
after the state bucket exists, the optional backend examples allow migration to
the separate `terramind/project` prefix. Project deletion is protected by default.

The budget excludes credits from spend calculations so promotional credit usage
remains visible. Notifications use the configured billing and project recipients
at 50%, 90% and 100%. This is an alert, not a hard cap. Project creation with
`auto_create_network=false` temporarily uses the Compute API to remove the default
network; it creates no VM.

The operator needs permission to enable the services listed in
`terraform/environments/dev/main.tf`, create the configured resources and manage
their IAM. WIF creation additionally needs Workload Identity Pool administration.
These setup permissions are not granted to the runtime or image deployer. Use
short-lived user credentials or approved impersonation, never service-account keys.

The following examples use Bash, suitable for Cloud Shell. Terraform and uv commands
also work directly in PowerShell; use that shell's environment-variable syntax.

```sh
export GCP_PROJECT_ID="YOUR_APPROVED_PROJECT_ID"
export GCP_REGION="us-central1"
gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)'
gcloud billing projects describe "$GCP_PROJECT_ID"
```

For local Terraform, authenticate with the Google Cloud CLI and configure Application
Default Credentials using the approved identity. Cloud Shell already supplies an
authenticated environment. Verify the active account and project before planning.

Cloud Shell can retain a project environment override after a CLI configuration
change. Set `CLOUDSDK_CORE_PROJECT`, `GOOGLE_CLOUD_PROJECT` and
`GOOGLE_CLOUD_QUOTA_PROJECT` to the approved project and verify them before use.
The providers explicitly select that project's quota context.

If project creation is blocked by missing management APIs in an unrelated quota
project, leave that project unchanged. Create only the approved project with
`gcloud projects create`, enable its management APIs and import it into
`terraform/project` with `enable_billing=false`. Review the imported plan, enable
billing in the variables, then apply the approved billing and budget configuration.
Do not use the import profile for the final deployed configuration. Management
APIs belong to the project root, Storage API to bootstrap, and application APIs to
dev, so separate states never manage the same API resource.

Prefer refreshable Application Default Credentials for long operations. If a
short-lived `GOOGLE_OAUTH_ACCESS_TOKEN` is used, renew it immediately before each
operation without printing it or enabling shell tracing. If expiry prevents a
state save, preserve the private `errored.tfstate` and backend backup. Confirm the
original process has exited and the exact lock belongs to that process before
unlocking, then push the recovery state without `-force` and reconcile a fresh
plan. GCS lock identifiers use the lock object's generation. Never reapply the
old plan before recovering state.

## Create the state bucket first

Copy `terraform/bootstrap/terraform.tfvars.example` to `terraform.tfvars` in the
same directory. Replace all synthetic values with approved parameters. State
operators receive object administration on this bucket only; do not grant public
members. Actual `.tfvars`, state and backend configuration are ignored by Git.

```sh
umask 077
export PRIVATE_PLAN_DIR="$(mktemp -d)"
terraform -chdir=terraform/bootstrap init
terraform -chdir=terraform/bootstrap plan -out="$PRIVATE_PLAN_DIR/bootstrap.plan"
```

Review the plan privately. After explicit approval of the reviewed plan only:

```sh
terraform -chdir=terraform/bootstrap apply "$PRIVATE_PLAN_DIR/bootstrap.plan"
```

Bootstrap initially uses local state because its bucket does not yet exist. Back
that state up privately. After the bucket exists, optionally copy
`backend.tf.example` to `backend.tf` and `backend.hcl.example` to `backend.hcl` in
the bootstrap directory. Set the actual bucket name and retain the distinct
`terramind/bootstrap` prefix, then migrate the state:

```sh
terraform -chdir=terraform/bootstrap init -migrate-state -backend-config=backend.hcl
```

Do not set a bucket retention policy that prevents deleting Terraform lock objects.
Versioning and noncurrent-version lifecycle rules retain state history instead.

## Prepare the foundation

Copy the dev environment's `terraform.tfvars.example` and `backend.hcl.example` to
their local counterparts. Use the existing state bucket and `terramind/dev` prefix.
Verify the numeric GCP project number matches the selected project. Verify the
GitHub repository and immutable numeric IDs before enabling federation.

Leave `container_image = null` initially. This creates the image repository and
supporting resources before an image is available, without a targeted apply or a
placeholder public container. It does not create Cloud Run or its alert yet.

```sh
terraform -chdir=terraform/environments/dev init -backend-config=backend.hcl
terraform -chdir=terraform/environments/dev plan -out="$PRIVATE_PLAN_DIR/foundation.plan"
```

After explicit approval of that reviewed plan only:

```sh
terraform -chdir=terraform/environments/dev apply "$PRIVATE_PLAN_DIR/foundation.plan"
```

The configured services include Cloud Run, Artifact Registry, IAM, IAM Credentials,
STS, Resource Manager, Service Usage, Firestore, Firebase Rules, Vertex AI, Storage,
Logging and Monitoring. No Compute Engine instance, GKE cluster, queue or worker is
required. API resources retain `disable_on_destroy=false` to avoid disrupting
other project resources during cleanup.

## Build and publish the service image

After the repository exists and uploads are approved, build a Linux amd64 image
with a unique immutable tag. Authenticate Docker using the approved identity.

```sh
export IMAGE_PREFIX="$(terraform -chdir=terraform/environments/dev output -raw artifact_image_prefix)"
export IMAGE_TAG="$(git rev-parse HEAD)"
gcloud auth configure-docker "$GCP_REGION-docker.pkg.dev"
docker build --platform linux/amd64 -t "$IMAGE_PREFIX/terramind:$IMAGE_TAG" .
docker push "$IMAGE_PREFIX/terramind:$IMAGE_TAG"
gcloud artifacts docker images describe "$IMAGE_PREFIX/terramind:$IMAGE_TAG" --format='value(image_summary.digest)'
```

Set `container_image` to the full `IMAGE_PREFIX/terramind@sha256:...` reference,
using the returned digest. Mutable tags and images outside the managed project,
region and repository are rejected. Set explicit `invoker_members` and any existing
Monitoring notification-channel resource names. Review and approve a new plan
before applying it. A policy with no notification channels creates incidents but
does not deliver notifications.

The runtime has no data permissions for the health service. The image deployer can
update the named service, publish to its repository and act as its runtime only.
It cannot run the infrastructure configuration with these permissions. Terraform
continues to own service configuration, including the desired image digest;
reconcile the variable with any later image promotion to avoid deployment drift.

## Verify real authentication

Cloud Run permits authenticated callers over HTTPS and enforces invoker IAM.
`INGRESS_TRAFFIC_ALL` permits external HTTPS routing; it does not grant anonymous
invocation. The configuration sets `invoker_iam_disabled=false` and never grants
`allUsers` or `allAuthenticatedUsers`.

Once an approved service is deployed:

```sh
export SERVICE_URL="$(terraform -chdir=terraform/environments/dev output -raw service_url)"
curl --silent --output /dev/null --write-out '%{http_code}\n' "$SERVICE_URL/health"
curl --fail --silent --show-error --header "Authorization: Bearer $(gcloud auth print-identity-token)" "$SERVICE_URL/health"
gcloud run services get-iam-policy terramind-dev --region="$GCP_REGION" --project="$GCP_PROJECT_ID"
gcloud storage buckets describe "gs://$GCP_PROJECT_ID-terramind-dev-runbooks"
```

Record an unauthenticated 401/403, an authenticated 200, private bucket settings and
the deployed image digest. Do not enable shell tracing around token commands or
copy tokens into logs. Review inherited project-level IAM too; service-level
Terraform cannot revoke unrelated grants. Inspect Firestore index readiness and
the named database's deny-all client rule release before adding data adapters.

## GitHub federation preparation

The trust condition requires the exact repository, numeric repository and owner
IDs, main branch, `development` environment subject, manual `workflow_dispatch`
event and `.github/workflows/deploy.yml` from main. Configure protected environment
reviewers and main-branch rules before creating the later deployment workflow.
There is no deployment workflow in this change and no successful token exchange
is claimed. Only the job that needs federation should receive `id-token: write`.

See [security exceptions](security-exceptions.md) and [cost and cleanup](cost-and-cleanup.md).

## References

- [Cloud Run authentication](https://docs.cloud.google.com/run/docs/authenticating/overview)
- [Terraform GCS backend](https://developer.hashicorp.com/terraform/language/backend/gcs)
- [GCP deployment-pipeline federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
- [Firestore vector search](https://firebase.google.com/docs/firestore/vector-search)
