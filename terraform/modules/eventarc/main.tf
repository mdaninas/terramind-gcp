variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "image" { type = string }
variable "bucket" { type = string }
variable "database" { type = string }
variable "labels" { type = map(string) }
variable "deletion_protection" { type = bool }

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.name}-evt-index"
  display_name = "Terramind synthetic Eventarc indexer"
}

resource "google_service_account" "trigger" {
  project      = var.project_id
  account_id   = "${var.name}-evt-call"
  display_name = "Terramind Eventarc delivery identity"
}

resource "google_project_iam_custom_role" "data" {
  project = var.project_id
  role_id = "${replace(var.name, "-", "_")}_event_index"
  title   = "Terramind event indexing data"
  permissions = [
    "datastore.databases.get",
    "datastore.entities.get", "datastore.entities.list", "datastore.entities.create",
    "datastore.entities.update", "datastore.entities.delete",
  ]
}

resource "google_project_iam_member" "data" {
  project = var.project_id
  role    = google_project_iam_custom_role.data.name
  member  = "serviceAccount:${google_service_account.runtime.email}"
  condition {
    title      = "terramind_database_only"
    expression = "resource.name == 'projects/${var.project_id}/databases/${var.database}'"
  }
}

resource "google_project_iam_custom_role" "prediction" {
  project     = var.project_id
  role_id     = "${replace(var.name, "-", "_")}_event_prediction"
  title       = "Terramind event embedding requests"
  permissions = ["aiplatform.endpoints.predict", "serviceusage.services.use"]
}

resource "google_project_iam_member" "prediction" {
  project = var.project_id
  role    = google_project_iam_custom_role.prediction.name
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "source_reader" {
  bucket = var.bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.trigger.email}"
}

data "google_storage_project_service_account" "storage" { project = var.project_id }

resource "google_project_iam_member" "storage_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.storage.email_address}"
}

resource "google_firestore_field" "receipt_expiry" {
  project    = var.project_id
  database   = var.database
  collection = "ingestion_receipts"
  field      = "expires_at"
  ttl_config {}
  index_config {}
}

resource "google_cloud_run_v2_service" "indexer" {
  project              = var.project_id
  name                 = "${var.name}-events"
  location             = var.region
  labels               = var.labels
  deletion_protection  = var.deletion_protection
  ingress              = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  invoker_iam_disabled = false
  scaling { max_instance_count = 1 }
  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "240s"
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
          TERRAMIND_SERVICE       = "events"
          TERRAMIND_EVENTARC_MODE = "cloud"
          GCP_PROJECT_ID          = var.project_id
          FIRESTORE_DATABASE      = var.database
          RUNBOOK_BUCKET          = var.bucket
          EMBEDDING_MODEL         = "gemini-embedding-001"
          EMBEDDING_LOCATION      = var.region
        }
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
        timeout_seconds   = 2
        period_seconds    = 3
        failure_threshold = 10
        http_get { path = "/healthz" }
      }
      liveness_probe {
        timeout_seconds = 2
        period_seconds  = 30
        http_get { path = "/healthz" }
      }
    }
  }
  depends_on = [google_project_iam_member.data, google_project_iam_member.prediction]
}

resource "google_cloud_run_v2_service_iam_member" "trigger_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.indexer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.trigger.email}"
}

resource "google_logging_project_exclusion" "request_urls" {
  project = var.project_id
  name    = "${var.name}-event-request-urls"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${google_cloud_run_v2_service.indexer.name}\" AND log_id(\"run.googleapis.com/requests\")"
}

resource "google_eventarc_trigger" "source_finalized" {
  project         = var.project_id
  name            = "${var.name}-source-finalized"
  location        = var.region
  service_account = google_service_account.trigger.email
  labels          = var.labels
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = var.bucket
  }
  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.indexer.name
      region  = var.region
      path    = "/events/storage"
    }
  }
  depends_on = [
    google_cloud_run_v2_service_iam_member.trigger_invoker,
    google_project_iam_member.event_receiver,
    google_project_iam_member.storage_publisher,
  ]
}

output "security_settings" {
  value = {
    min_instances      = google_cloud_run_v2_service.indexer.template[0].scaling[0].min_instance_count
    max_instances      = google_cloud_run_v2_service.indexer.scaling[0].max_instance_count
    concurrency        = google_cloud_run_v2_service.indexer.template[0].max_instance_request_concurrency
    ingress            = google_cloud_run_v2_service.indexer.ingress
    iam_enforced       = !google_cloud_run_v2_service.indexer.invoker_iam_disabled
    data_condition     = google_project_iam_member.data.condition[0].expression
    data_permissions   = google_project_iam_custom_role.data.permissions
    source_access_role = google_storage_bucket_iam_member.source_reader.role
    source_bucket      = var.bucket
    endpoint           = google_eventarc_trigger.source_finalized.destination[0].cloud_run_service[0].path
  }
}
