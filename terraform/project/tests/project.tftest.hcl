mock_provider "google" {}
mock_provider "google" { alias = "budget" }
variables {
  project_id         = "terramind-synthetic-project"
  organization_id    = "123456789012"
  billing_account_id = "000000-000000-000000"
  budget_currency    = "IDR"
  budget_units       = 180000
}
run "isolated_project_and_credit_usage_alerts" {
  command = plan
  assert {
    condition     = !google_project.portfolio.auto_create_network && google_project.portfolio.deletion_policy == "PREVENT"
    error_message = "Avoid a default VPC and require deliberate final project deletion."
  }
  assert {
    condition     = google_billing_budget.portfolio[0].budget_filter[0].credit_types_treatment == "EXCLUDE_ALL_CREDITS"
    error_message = "Alerts must track gross usage so promotional credits cannot hide consumption."
  }
  assert {
    condition     = google_billing_budget.portfolio[0].amount[0].specified_amount[0].currency_code == "IDR" && google_billing_budget.portfolio[0].amount[0].specified_amount[0].units == "180000"
    error_message = "The alert amount must use the approved billing currency and amount."
  }
  assert {
    condition     = google_billing_budget.portfolio[0].all_updates_rule[0].enable_project_level_recipients
    error_message = "Project owners must receive the requested budget warnings."
  }
}
run "unbilled_project_import_profile" {
  command = plan
  variables { enable_billing = false }
  assert {
    condition     = google_project.portfolio.billing_account == null && length(google_billing_budget.portfolio) == 0
    error_message = "The import profile must not attach billing or create a budget before its first apply."
  }
}
run "reject_invalid_alert_amount" {
  command = plan
  variables { budget_units = 0 }
  expect_failures = [var.budget_units]
}
