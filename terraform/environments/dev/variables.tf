variable "project_id" {
  type        = string
  description = "Approved isolated demo project ID."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Provide a valid GCP project ID."
  }
}
variable "project_number" {
  type        = string
  description = "Numeric project ID for the WIF principal set. Verify it before deployment."
  validation {
    condition     = can(regex("^[0-9]{6,20}$", var.project_number))
    error_message = "Provide the numeric GCP project number."
  }
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "name_prefix" {
  type    = string
  default = "terramind-dev"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,17}[a-z0-9]$", var.name_prefix))
    error_message = "Use a 4-19 character lowercase resource prefix."
  }
}
variable "github_repository" {
  type        = string
  description = "Exact GitHub owner/repository allowed to deploy."
  default     = "mdaninas/terramind-gcp"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use an exact owner/repository name."
  }
}
variable "github_repository_id" {
  type    = string
  default = "1450398693"
  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "Use the immutable numeric GitHub repository ID."
  }
}
variable "github_owner_id" {
  type    = string
  default = "156415805"
  validation {
    condition     = can(regex("^[0-9]+$", var.github_owner_id))
    error_message = "Use the immutable numeric GitHub owner ID."
  }
}
variable "github_environment" {
  type    = string
  default = "development"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,40}$", var.github_environment))
    error_message = "Use a simple protected GitHub environment name."
  }
}
variable "container_image" {
  type        = string
  default     = null
  description = "Null prepares foundation only. Later supply the API image's Artifact Registry digest."
  validation {
    condition = var.container_image == null || can(regex(
      "^${var.region}-docker\\.pkg\\.dev/${var.project_id}/${var.name_prefix}/terramind@sha256:[a-f0-9]{64}$", var.container_image
    ))
    error_message = "Use the terramind image in this project's managed repository, pinned to sha256."
  }
}
variable "invoker_members" {
  type    = set(string)
  default = []
  validation {
    condition     = alltrue([for member in var.invoker_members : can(regex("^(user|group|serviceAccount):[^ ]+@[^ ]+$", member))])
    error_message = "Invocation requires explicit user, group or service account identities."
  }
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "max_instances" {
  type    = number
  default = 2
  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 3 && floor(var.max_instances) == var.max_instances
    error_message = "The demo supports an integer instance cap between 1 and 3."
  }
}
variable "notification_channels" {
  type        = list(string)
  default     = []
  description = "Existing Monitoring channel resource names. Empty means incidents have no notification delivery."
}
