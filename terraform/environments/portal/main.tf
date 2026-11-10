terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = "= 8.10.0" }
  }
  backend "gcs" {}
}

provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}

variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,61}[a-z0-9]$", var.project_id))
    error_message = "Use the approved project ID."
  }
}
variable "project_number" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{6,20}$", var.project_number))
    error_message = "Use the approved numeric project identity."
  }
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "name" {
  type    = string
  default = "terramind-portal"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.name))
    error_message = "Use a simple service and service-account name."
  }
}
variable "image" {
  type = string
  validation {
    condition     = can(regex("^${var.region}-docker\\.pkg\\.dev/${var.project_id}/terramind-dev/terramind@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Use an approved immutable Terramind image digest."
  }
}
variable "oauth_client_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]+-[A-Za-z0-9_-]+\\.apps\\.googleusercontent\\.com$", var.oauth_client_id))
    error_message = "Supply the reviewed Google OAuth web client ID."
  }
}
variable "oauth_secret_name" {
  type        = string
  description = "Existing Secret Manager secret containing the OAuth client secret; secret data never enters Terraform."
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,255}$", var.oauth_secret_name))
    error_message = "Use an existing secret ID in this project, not a resource URL."
  }
}
variable "oauth_secret_version" {
  type = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.oauth_secret_version))
    error_message = "Pin an existing numeric secret version, not latest."
  }
}
variable "allowed_emails" {
  type      = list(string)
  sensitive = true
  validation {
    condition     = length(var.allowed_emails) >= 1 && length(var.allowed_emails) <= 10 && alltrue([for email in var.allowed_emails : can(regex("^[^ ,]+@[^ ,]+$", email))])
    error_message = "Use one to ten explicit reviewed Google accounts."
  }
}
variable "invoker_members" {
  type      = set(string)
  sensitive = true
  validation {
    condition     = length(var.invoker_members) >= 1 && alltrue([for member in var.invoker_members : can(regex("^(user|group):[^ ]+@[^ ]+$", member))])
    error_message = "Allow explicit operator identities only; public invocation is forbidden."
  }
}
variable "knowledge_database" {
  type    = string
  default = "terramind-dev"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,61}[a-z0-9]$", var.knowledge_database))
    error_message = "Use the reviewed named knowledge database."
  }
}
variable "gemini_model" {
  type    = string
  default = "gemini-3.5-flash"
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{0,79}$", var.gemini_model))
    error_message = "Use a supported publisher model ID."
  }
}
variable "transport_host" {
  type        = string
  default     = null
  description = "Exact hostname returned by Cloud Run and used by its authenticated proxy."
  validation {
    condition     = var.transport_host == null || can(regex("^${var.name}-[a-z0-9.-]+\\.run\\.app$", var.transport_host))
    error_message = "Use this service's exact Cloud Run hostname, without scheme, port or path."
  }
}

locals {
  labels         = { application = "terramind", environment = "dev", data = "synthetic" }
  transport_host = coalesce(var.transport_host, "${var.name}-${var.project_number}.${var.region}.run.app")
}

resource "google_project_service" "secrets" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "portal" {
  project      = var.project_id
  account_id   = var.name
  display_name = "Terramind private portal"
}

resource "google_firestore_database" "portal" {
  project                     = var.project_id
  name                        = var.name
  location_id                 = var.region
  type                        = "FIRESTORE_NATIVE"
  concurrency_mode            = "PESSIMISTIC"
  app_engine_integration_mode = "DISABLED"
  delete_protection_state     = "DELETE_PROTECTION_ENABLED"
  deletion_policy             = "ABANDON"
}

resource "google_firestore_field" "expiry" {
  for_each   = toset(["portal_sessions", "portal_flows", "portal_reports"])
  project    = var.project_id
  database   = google_firestore_database.portal.name
  collection = each.key
  field      = "expires_at"
  ttl_config {}
}

resource "google_firestore_field" "report_payload" {
  project    = var.project_id
  database   = google_firestore_database.portal.name
  collection = "portal_reports"
  field      = "bundle"
  index_config {}
}

resource "google_firestore_field" "session_csrf" {
  project    = var.project_id
  database   = google_firestore_database.portal.name
  collection = "portal_sessions"
  field      = "csrf"
  index_config {}
}

resource "google_firestore_field" "flow_secrets" {
  for_each   = toset(["state", "nonce", "verifier"])
  project    = var.project_id
  database   = google_firestore_database.portal.name
  collection = "portal_flows"
  field      = each.key
  index_config {}
}

resource "google_firestore_index" "owned_active_reports" {
  project     = var.project_id
  database    = google_firestore_database.portal.name
  collection  = "portal_reports"
  query_scope = "COLLECTION"
  fields {
    field_path = "owner"
    order      = "ASCENDING"
  }
  fields {
    field_path = "expires_at"
    order      = "ASCENDING"
  }
}

resource "google_firebaserules_ruleset" "deny_clients" {
  project = var.project_id
  source {
    files {
      name    = "firestore.rules"
      content = file("../../modules/firestore/firestore.rules")
    }
  }
  lifecycle { create_before_destroy = true }
}

resource "google_firebaserules_release" "deny_clients" {
  project      = var.project_id
  name         = "cloud.firestore/${google_firestore_database.portal.name}"
  ruleset_name = "projects/${var.project_id}/rulesets/${google_firebaserules_ruleset.deny_clients.name}"
}

resource "google_project_iam_custom_role" "portal" {
  project = var.project_id
  role_id = "terramind_portal_data"
  title   = "Terramind portal private state"
  permissions = [
    "datastore.databases.get", "datastore.entities.get", "datastore.entities.list",
    "datastore.entities.create", "datastore.entities.update", "datastore.entities.delete",
  ]
}

resource "google_project_iam_member" "portal_data" {
  project = var.project_id
  role    = google_project_iam_custom_role.portal.name
  member  = "serviceAccount:${google_service_account.portal.email}"
  condition {
    title      = "portal_database_only"
    expression = "resource.name == 'projects/${var.project_id}/databases/${google_firestore_database.portal.name}'"
  }
}

resource "google_project_iam_custom_role" "knowledge" {
  project     = var.project_id
  role_id     = "terramind_portal_knowledge"
  title       = "Terramind portal read-only knowledge"
  permissions = ["datastore.entities.get", "datastore.entities.list"]
}

resource "google_project_iam_member" "knowledge" {
  project = var.project_id
  role    = google_project_iam_custom_role.knowledge.name
  member  = "serviceAccount:${google_service_account.portal.email}"
  condition {
    title      = "knowledge_database_only"
    expression = "resource.name == 'projects/${var.project_id}/databases/${var.knowledge_database}'"
  }
}

resource "google_project_iam_custom_role" "prediction" {
  project     = var.project_id
  role_id     = "terramind_portal_prediction"
  title       = "Terramind portal bounded model calls"
  permissions = ["aiplatform.endpoints.predict", "serviceusage.services.use"]
}

resource "google_project_iam_member" "prediction" {
  project = var.project_id
  role    = google_project_iam_custom_role.prediction.name
  member  = "serviceAccount:${google_service_account.portal.email}"
}

resource "google_secret_manager_secret_iam_member" "oauth" {
  project    = var.project_id
  secret_id  = var.oauth_secret_name
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.portal.email}"
  depends_on = [google_project_service.secrets]
}

resource "google_cloud_run_v2_service" "portal" {
  project              = var.project_id
  name                 = var.name
  location             = var.region
  labels               = local.labels
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  scaling { max_instance_count = 1 }
  template {
    service_account                  = google_service_account.portal.email
    timeout                          = "60s"
    max_instance_request_concurrency = 1
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.image
      dynamic "env" {
        for_each = {
          TERRAMIND_SERVICE         = "portal"
          PORTAL_AUTH_MODE          = "google"
          PORTAL_ANALYSIS_MODE      = "cloud"
          PORTAL_STORAGE_BACKEND    = "firestore"
          PORTAL_FIRESTORE_DATABASE = google_firestore_database.portal.name
          PORTAL_ORIGIN             = "http://127.0.0.1:8091"
          PORTAL_TRANSPORT_HOST     = local.transport_host
          GOOGLE_OAUTH_CLIENT_ID    = var.oauth_client_id
          GCP_PROJECT_ID            = var.project_id
          FIRESTORE_DATABASE        = var.knowledge_database
          GEMINI_MODEL              = var.gemini_model
          GEMINI_LOCATION           = "global"
          EMBEDDING_MODEL           = "gemini-embedding-001"
          EMBEDDING_LOCATION        = var.region
        }
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name  = "PORTAL_ALLOWED_EMAILS"
        value = join(",", var.allowed_emails)
      }
      env {
        name = "GOOGLE_OAUTH_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.oauth_secret_name
            version = var.oauth_secret_version
          }
        }
      }
      ports { container_port = 8080 }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = false
      }
      startup_probe {
        timeout_seconds   = 2
        period_seconds    = 3
        failure_threshold = 15
        http_get {
          path = "/healthz"
          http_headers {
            name  = "Host"
            value = local.transport_host
          }
        }
      }
      liveness_probe {
        timeout_seconds = 2
        period_seconds  = 30
        http_get {
          path = "/healthz"
          http_headers {
            name  = "Host"
            value = local.transport_host
          }
        }
      }
    }
  }
  depends_on = [google_project_iam_member.portal_data, google_project_iam_member.knowledge,
    google_project_iam_member.prediction, google_secret_manager_secret_iam_member.oauth,
  google_logging_project_exclusion.request_urls]
}

resource "google_cloud_run_v2_service_iam_member" "operators" {
  for_each = nonsensitive(var.invoker_members)
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.portal.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_logging_project_exclusion" "request_urls" {
  project = var.project_id
  name    = "${var.name}-request-urls"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.name}\" AND log_id(\"run.googleapis.com/requests\")"
}

output "service_url" { value = google_cloud_run_v2_service.portal.uri }
output "runtime_identity" { value = google_service_account.portal.email }
output "security_settings" {
  value = {
    iam_enforced    = !google_cloud_run_v2_service.portal.invoker_iam_disabled
    min_instances   = google_cloud_run_v2_service.portal.template[0].scaling[0].min_instance_count
    max_instances   = google_cloud_run_v2_service.portal.scaling[0].max_instance_count
    origin          = "http://127.0.0.1:8091"
    storage_backend = "firestore"
    data_condition  = google_project_iam_member.portal_data.condition[0].expression
    secret_version  = var.oauth_secret_version
  }
}
