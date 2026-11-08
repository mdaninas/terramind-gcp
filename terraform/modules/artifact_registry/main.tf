variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "deployer_email" { type = string }
variable "labels" { type = map(string) }

resource "google_artifact_registry_repository" "images" {
  # checkov:skip=CKV_GCP_84:Google-managed encryption is used for synthetic demo images; CMEK adds key costs and operational overhead. See docs/security-exceptions.md.
  project       = var.project_id
  location      = var.region
  repository_id = var.name
  description   = "Terramind API container images."
  format        = "DOCKER"
  labels        = var.labels
  docker_config { immutable_tags = true }
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "remove-old-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "1209600s"
    }
  }
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions { keep_count = 10 }
  }
}

resource "google_artifact_registry_repository_iam_member" "publisher" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${var.deployer_email}"
}

output "image_prefix" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
