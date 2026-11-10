locals {
  labels = { application = "terramind", environment = "dev", data = "synthetic" }
  apis = toset(concat([
    "run.googleapis.com", "artifactregistry.googleapis.com", "iam.googleapis.com",
    "iamcredentials.googleapis.com", "sts.googleapis.com", "aiplatform.googleapis.com",
    "firestore.googleapis.com", "firebaserules.googleapis.com",
    "logging.googleapis.com", "monitoring.googleapis.com",
  ], var.enable_eventarc_indexing ? ["eventarc.googleapis.com", "pubsub.googleapis.com", "storage.googleapis.com"] : []))
}

resource "google_project_service" "required" {
  for_each           = local.apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "identity" {
  source               = "../../modules/identity"
  project_id           = var.project_id
  project_number       = var.project_number
  name                 = var.name_prefix
  github_repository    = var.github_repository
  github_repository_id = var.github_repository_id
  github_owner_id      = var.github_owner_id
  github_environment   = var.github_environment
  enable_analysis_api  = var.enable_analysis_api
  depends_on           = [google_project_service.required]
}

module "artifact_registry" {
  source         = "../../modules/artifact_registry"
  project_id     = var.project_id
  region         = var.region
  name           = var.name_prefix
  deployer_email = module.identity.deployer_email
  labels         = local.labels
  depends_on     = [google_project_service.required]
}

module "storage" {
  source         = "../../modules/storage"
  project_id     = var.project_id
  region         = var.region
  name           = "${var.project_id}-${var.name_prefix}-runbooks"
  ingester_email = module.identity.ingester_email
  labels         = local.labels
  depends_on     = [google_project_service.required]
}

module "firestore" {
  source              = "../../modules/firestore"
  project_id          = var.project_id
  region              = var.region
  name                = var.name_prefix
  ingester_email      = module.identity.ingester_email
  runtime_email       = module.identity.runtime_email
  enable_analysis_api = var.enable_analysis_api
  deletion_protection = var.deletion_protection
  depends_on          = [google_project_service.required]
}

module "cloud_run" {
  count                 = var.container_image == null ? 0 : 1
  source                = "../../modules/cloud_run"
  project_id            = var.project_id
  region                = var.region
  name                  = var.name_prefix
  image                 = var.container_image
  runtime_email         = module.identity.runtime_email
  deployer_email        = module.identity.deployer_email
  invoker_members       = var.invoker_members
  max_instances         = var.max_instances
  deletion_protection   = var.deletion_protection
  labels                = local.labels
  allow_deployer_invoke = var.enable_analysis_api
  environment = var.enable_analysis_api ? {
    TERRAMIND_API_MODE     = "cloud"
    GCP_PROJECT_ID         = var.project_id
    FIRESTORE_DATABASE     = module.firestore.name
    GEMINI_MODEL           = var.gemini_model
    GEMINI_LOCATION        = var.gemini_location
    EMBEDDING_MODEL        = "gemini-embedding-001"
    EMBEDDING_LOCATION     = var.region
    EXPLANATION_LANGUAGE   = var.explanation_language
    REPORT_RETENTION_HOURS = "24"
    ANALYSES_PER_MINUTE    = "6"
  } : {}
  depends_on = [google_project_service.required]
}

resource "google_logging_project_exclusion" "raw_request_urls" {
  count       = var.container_image == null ? 0 : 1
  project     = var.project_id
  name        = "${var.name_prefix}-raw-request-urls"
  description = "Avoid retaining automatic request URLs; structured application telemetry excludes user content."
  filter      = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.name_prefix}\" AND log_id(\"run.googleapis.com/requests\")"
  depends_on  = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "server_errors" {
  count                 = var.container_image == null ? 0 : 1
  project               = var.project_id
  display_name          = "Terramind repeated server errors"
  combiner              = "OR"
  enabled               = true
  notification_channels = var.notification_channels
  user_labels           = local.labels
  documentation {
    content   = "Review content-free Terramind application logs. Do not paste plans, prompts or credentials into incidents."
    mime_type = "text/markdown"
  }
  conditions {
    display_name = "More than four server errors in an aligned minute"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.name_prefix}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 4
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger { count = 1 }
    }
  }
  alert_strategy { auto_close = "1800s" }
  depends_on = [module.cloud_run]
}

module "eventarc" {
  count               = var.enable_eventarc_indexing ? 1 : 0
  source              = "../../modules/eventarc"
  project_id          = var.project_id
  region              = var.region
  name                = var.name_prefix
  image               = var.container_image
  bucket              = module.storage.name
  database            = module.firestore.name
  labels              = local.labels
  deletion_protection = var.deletion_protection
  depends_on          = [google_project_service.required]
}
