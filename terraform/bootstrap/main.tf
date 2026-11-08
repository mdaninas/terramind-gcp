terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = "= 8.10.0" }
  }
  # Bootstrap starts with LOCAL state. The application environment uses this bucket
  # only after it exists. Keep the bootstrap state private and backed up separately.
}

provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}

variable "project_id" {
  type        = string
  description = "Approved demo project ID."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Provide a valid GCP project ID."
  }
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "state_bucket_name" {
  type        = string
  description = "Globally unique private state bucket name."
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.state_bucket_name))
    error_message = "Use a valid bucket name with 3-63 lowercase letters, numbers or hyphens."
  }
}
variable "state_operator_members" {
  type        = set(string)
  description = "Explicit trusted operators allowed to read and write Terraform state."
  default     = []
  validation {
    condition     = alltrue([for member in var.state_operator_members : can(regex("^(user|group|serviceAccount):[^ ]+@[^ ]+$", member))])
    error_message = "State access requires explicit user, group or service account identities."
  }
}

resource "google_project_service" "storage" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "state" {
  # checkov:skip=CKV_GCP_62:Legacy object access-log delivery is deferred; state is private and versioned, and administrative audit logs remain enabled. See docs/security-exceptions.md.
  project                     = var.project_id
  name                        = var.state_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = { application = "terramind", purpose = "terraform-state" }
  versioning { enabled = true }
  soft_delete_policy { retention_duration_seconds = 604800 }
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 90
      num_newer_versions         = 5
      with_state                 = "ARCHIVED"
    }
    action { type = "Delete" }
  }
  depends_on = [google_project_service.storage]
}

resource "google_storage_bucket_iam_member" "state_operator" {
  for_each = var.state_operator_members
  bucket   = google_storage_bucket.state.name
  role     = "roles/storage.objectAdmin"
  member   = each.value
}

output "state_bucket_name" { value = google_storage_bucket.state.name }
