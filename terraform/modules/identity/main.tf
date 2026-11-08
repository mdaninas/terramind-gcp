variable "project_id" { type = string }
variable "project_number" { type = string }
variable "name" { type = string }
variable "github_repository" { type = string }
variable "github_repository_id" { type = string }
variable "github_owner_id" { type = string }
variable "github_environment" { type = string }

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.name}-runtime"
  display_name = "Terramind API runtime"
  description  = "Health service identity. No data or cloud administrator roles."
}
resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "${var.name}-deployer"
  display_name = "Terramind image deployer"
}
resource "google_service_account" "ingester" {
  project      = var.project_id
  account_id   = "${var.name}-ingest"
  display_name = "Terramind synthetic knowledge ingester"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "${var.name}-github"
  display_name              = "Terramind GitHub deployments"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  # checkov:skip=CKV_GCP_125:Checkov 3.4.3 cannot resolve the parameterized module subject; Terraform mock-plan tests assert the full evaluated allowlist. See docs/security-exceptions.md.
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "Trusted manual deployments"
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
    "attribute.repository"          = "assertion.repository"
    "attribute.ref"                 = "assertion.ref"
  }
  attribute_condition = <<-CEL
    assertion.repository_id == '${var.github_repository_id}' &&
    assertion.repository_owner_id == '${var.github_owner_id}' &&
    assertion.repository == '${var.github_repository}' &&
    assertion.ref == 'refs/heads/main' &&
    assertion.sub == 'repo:${var.github_repository}:environment:${var.github_environment}' &&
    assertion.workflow_ref == '${var.github_repository}/.github/workflows/deploy.yml@refs/heads/main' &&
    assertion.event_name == 'workflow_dispatch'
  CEL
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "github_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/attribute.repository_id/${var.github_repository_id}"
}

resource "google_service_account_iam_member" "runtime_act_as" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

output "runtime_email" { value = google_service_account.runtime.email }
output "deployer_email" { value = google_service_account.deployer.email }
output "ingester_email" { value = google_service_account.ingester.email }
output "workload_identity_provider" { value = google_iam_workload_identity_pool_provider.github.name }
output "federation_condition" { value = google_iam_workload_identity_pool_provider.github.attribute_condition }
