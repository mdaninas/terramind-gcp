variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "ingester_email" { type = string }
variable "labels" { type = map(string) }

resource "google_storage_bucket" "runbooks" {
  # checkov:skip=CKV_GCP_62:Legacy object access-log delivery is deferred for this synthetic demo; administrative audit logs remain enabled. See docs/security-exceptions.md.
  project                     = var.project_id
  name                        = var.name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = var.labels
  versioning { enabled = true }
  soft_delete_policy { retention_duration_seconds = 604800 }
  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}

resource "google_storage_bucket_iam_member" "ingester" {
  bucket = google_storage_bucket.runbooks.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${var.ingester_email}"
}

output "name" { value = google_storage_bucket.runbooks.name }
output "security_settings" {
  value = {
    uniform_access           = google_storage_bucket.runbooks.uniform_bucket_level_access
    public_access_prevention = google_storage_bucket.runbooks.public_access_prevention
    force_destroy            = google_storage_bucket.runbooks.force_destroy
  }
}
