terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = "= 8.10.0" }
  }
}

provider "google" {
  project               = var.project_id
  billing_project       = coalesce(var.management_quota_project_id, var.project_id)
  user_project_override = true
}
provider "google" {
  alias                 = "budget"
  project               = var.project_id
  billing_project       = var.project_id
  user_project_override = true
}

variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Provide a valid, globally unique GCP project ID."
  }
}
variable "organization_id" {
  type        = string
  default     = null
  description = "Approved organization parent, or null for an account without an organization."
}
variable "management_quota_project_id" {
  type        = string
  default     = null
  description = "Existing API-enabled management project for initial creation, or null after CLI bootstrap of the target project."
}
variable "billing_account_id" {
  type        = string
  description = "Existing approved billing account. No payment account or payment method is created."
}
variable "enable_billing" {
  type        = bool
  default     = true
  description = "Use false only while importing an unbilled CLI-created project; enable before its first apply."
}
variable "budget_currency" {
  type        = string
  description = "Must match the existing billing account's currency."
  validation {
    condition     = can(regex("^[A-Z]{3}$", var.budget_currency))
    error_message = "Use the billing account's three-letter currency code."
  }
}
variable "budget_units" {
  type        = number
  description = "Monthly alert amount in billing currency; this is not a hard spending cap."
  validation {
    condition     = var.budget_units > 0 && floor(var.budget_units) == var.budget_units
    error_message = "Use a positive whole amount in the billing account's currency."
  }
}
variable "deletion_policy" {
  type    = string
  default = "PREVENT"
  validation {
    condition     = contains(["PREVENT", "DELETE"], var.deletion_policy)
    error_message = "Use PREVENT normally; DELETE only for approved final project cleanup."
  }
}

resource "google_project" "portfolio" {
  name                = "Terramind"
  project_id          = var.project_id
  org_id              = var.organization_id
  billing_account     = var.enable_billing ? var.billing_account_id : null
  auto_create_network = false
  deletion_policy     = var.deletion_policy
  labels              = { application = "terramind", purpose = "portfolio", data = "synthetic" }
}

resource "google_project_service" "management" {
  for_each           = toset(["cloudbilling.googleapis.com", "cloudresourcemanager.googleapis.com", "serviceusage.googleapis.com"])
  project            = google_project.portfolio.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_service" "budgets" {
  count              = var.enable_billing ? 1 : 0
  project            = google_project.portfolio.project_id
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_iam_audit_config" "portfolio" {
  project = google_project.portfolio.project_id
  service = "allServices"
  audit_log_config { log_type = "ADMIN_READ" }
  audit_log_config { log_type = "DATA_READ" }
  audit_log_config { log_type = "DATA_WRITE" }
}

resource "google_billing_budget" "portfolio" {
  count           = var.enable_billing ? 1 : 0
  provider        = google.budget
  billing_account = var.billing_account_id
  display_name    = "Terramind portfolio monthly alert"
  budget_filter {
    projects               = ["projects/${google_project.portfolio.number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }
  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_units)
    }
  }
  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }
  all_updates_rule {
    monitoring_notification_channels = []
    disable_default_iam_recipients   = false
    enable_project_level_recipients  = true
  }
  depends_on = [google_project_service.budgets]
}

output "project_id" { value = google_project.portfolio.project_id }
output "project_number" { value = google_project.portfolio.number }
output "budget_name" { value = var.enable_billing ? google_billing_budget.portfolio[0].name : null }
