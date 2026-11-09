variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "deletion_protection" { type = bool }
variable "ingester_email" { type = string }
variable "runtime_email" { type = string }
variable "enable_analysis_api" {
  type    = bool
  default = false
}

resource "google_firestore_database" "data" {
  project                     = var.project_id
  name                        = var.name
  location_id                 = var.region
  type                        = "FIRESTORE_NATIVE"
  concurrency_mode            = "PESSIMISTIC"
  app_engine_integration_mode = "DISABLED"
  delete_protection_state     = var.deletion_protection ? "DELETE_PROTECTION_ENABLED" : "DELETE_PROTECTION_DISABLED"
  deletion_policy             = "DELETE"
}

resource "google_firestore_index" "embeddings" {
  project     = var.project_id
  database    = google_firestore_database.data.name
  collection  = "knowledge_chunks"
  query_scope = "COLLECTION"
  fields {
    field_path = "__name__"
    order      = "ASCENDING"
  }
  fields {
    field_path = "embedding"
    vector_config {
      dimension = 768
      flat {}
    }
  }
}

resource "google_firestore_field" "report_expiry" {
  project    = var.project_id
  database   = google_firestore_database.data.name
  collection = "analyses"
  field      = "expires_at"
  ttl_config {}
  index_config {}
}

resource "google_firestore_field" "report_body" {
  count      = var.enable_analysis_api ? 1 : 0
  project    = var.project_id
  database   = google_firestore_database.data.name
  collection = "analyses"
  field      = "report_json"
  index_config {}
}

resource "google_project_iam_custom_role" "runtime" {
  count       = var.enable_analysis_api ? 1 : 0
  project     = var.project_id
  role_id     = "${replace(var.name, "-", "_")}_reports"
  title       = "Terramind synthetic analysis data"
  description = "Read synthetic knowledge and create/read reports; no update, delete or index administration."
  permissions = ["datastore.entities.get", "datastore.entities.list", "datastore.entities.create"]
}

resource "google_project_iam_member" "runtime" {
  count   = var.enable_analysis_api ? 1 : 0
  project = var.project_id
  role    = google_project_iam_custom_role.runtime[0].name
  member  = "serviceAccount:${var.runtime_email}"
  condition {
    title       = "terramind_database_only"
    description = "Server SDK access is restricted to the dedicated named database."
    expression  = "resource.name == 'projects/${var.project_id}/databases/${google_firestore_database.data.name}'"
  }
}

resource "google_firebaserules_ruleset" "deny_clients" {
  project = var.project_id
  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/firestore.rules")
    }
  }
  lifecycle { create_before_destroy = true }
}

resource "google_firebaserules_release" "deny_clients" {
  project      = var.project_id
  name         = "cloud.firestore/${google_firestore_database.data.name}"
  ruleset_name = "projects/${var.project_id}/rulesets/${google_firebaserules_ruleset.deny_clients.name}"
}

resource "google_project_iam_custom_role" "ingestion" {
  project     = var.project_id
  role_id     = "${replace(var.name, "-", "_")}_ingestion"
  title       = "Terramind synthetic knowledge ingestion"
  description = "Read and update synthetic knowledge documents; no index or IAM administration."
  permissions = [
    "datastore.entities.get", "datastore.entities.list",
    "datastore.entities.create", "datastore.entities.update", "datastore.entities.delete",
  ]
}

resource "google_project_iam_member" "ingestion" {
  project = var.project_id
  role    = google_project_iam_custom_role.ingestion.name
  member  = "serviceAccount:${var.ingester_email}"
  condition {
    title       = "terramind_database_only"
    description = "Firestore enforces database scope for server SDK calls."
    expression  = "resource.name == 'projects/${var.project_id}/databases/${google_firestore_database.data.name}'"
  }
}

output "name" { value = google_firestore_database.data.name }
output "security_settings" {
  value = {
    dimensions              = google_firestore_index.embeddings.fields[1].vector_config[0].dimension
    delete_protection_state = google_firestore_database.data.delete_protection_state
    client_rules_deny_all   = strcontains(google_firebaserules_ruleset.deny_clients.source[0].files[0].content, "allow read, write: if false;")
    runtime_permissions     = var.enable_analysis_api ? google_project_iam_custom_role.runtime[0].permissions : []
    runtime_condition       = var.enable_analysis_api ? google_project_iam_member.runtime[0].condition[0].expression : null
  }
}
