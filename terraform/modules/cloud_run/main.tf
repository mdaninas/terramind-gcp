variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "image" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9-]+-docker\\.pkg\\.dev/[a-z0-9-]+/[a-z0-9-]+/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Use an Artifact Registry image pinned to a SHA-256 digest."
  }
}
variable "runtime_email" { type = string }
variable "deployer_email" { type = string }
variable "invoker_members" { type = set(string) }
variable "labels" { type = map(string) }
variable "deletion_protection" { type = bool }
variable "environment" {
  type    = map(string)
  default = {}
}
variable "allow_deployer_invoke" {
  type    = bool
  default = false
}
variable "max_instances" {
  type = number
  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 3 && floor(var.max_instances) == var.max_instances
    error_message = "The demo supports an integer instance cap between 1 and 3."
  }
}

resource "google_cloud_run_v2_service" "api" {
  project              = var.project_id
  location             = var.region
  name                 = var.name
  description          = "Private Terramind API for synthetic Terraform analysis."
  labels               = var.labels
  deletion_protection  = var.deletion_protection
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false

  scaling { max_instance_count = var.max_instances }
  template {
    service_account                  = var.runtime_email
    timeout                          = "30s"
    max_instance_request_concurrency = 8
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }
    containers {
      image = var.image
      dynamic "env" {
        for_each = var.environment
        content {
          name  = env.key
          value = env.value
        }
      }
      ports { container_port = 8080 }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = false
      }
      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 2
        period_seconds        = 3
        failure_threshold     = 10
        http_get { path = "/healthz" }
      }
      liveness_probe {
        timeout_seconds   = 2
        period_seconds    = 30
        failure_threshold = 3
        http_get { path = "/healthz" }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = var.invoker_members
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = each.value
  lifecycle {
    precondition {
      condition     = can(regex("^(user|group|serviceAccount):[^ ]+@[^ ]+$", each.value))
      error_message = "Only explicit user, group or service account identities may invoke the API."
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "deployer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${var.deployer_email}"
}

resource "google_cloud_run_v2_service_iam_member" "deployer_invoker" {
  count    = var.allow_deployer_invoke ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.deployer_email}"
}

output "uri" { value = google_cloud_run_v2_service.api.uri }
output "name" { value = google_cloud_run_v2_service.api.name }
output "security_settings" {
  description = "Plan-visible settings for offline infrastructure contract tests."
  value = {
    invoker_iam_disabled = google_cloud_run_v2_service.api.invoker_iam_disabled
    min_instances        = google_cloud_run_v2_service.api.template[0].scaling[0].min_instance_count
    max_instances        = google_cloud_run_v2_service.api.scaling[0].max_instance_count
    cpu_idle             = google_cloud_run_v2_service.api.template[0].containers[0].resources[0].cpu_idle
    deletion_protection  = google_cloud_run_v2_service.api.deletion_protection
    environment          = var.environment
    deployer_invokes     = var.allow_deployer_invoke
  }
}
