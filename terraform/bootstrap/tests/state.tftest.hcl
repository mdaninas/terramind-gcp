mock_provider "google" {}
variables {
  project_id             = "terramind-demo"
  state_bucket_name      = "terramind-synthetic-state"
  state_operator_members = ["user:operator@example.invalid"]
}
run "private_versioned_state" {
  command = plan
  assert {
    condition     = google_storage_bucket.state.public_access_prevention == "enforced" && google_storage_bucket.state.uniform_bucket_level_access
    error_message = "Terraform state must never be public."
  }
  assert {
    condition     = google_storage_bucket.state.versioning[0].enabled && !google_storage_bucket.state.force_destroy
    error_message = "Keep state history and refuse destructive bucket emptying."
  }
  assert {
    condition     = !google_project_service.storage.disable_on_destroy
    error_message = "Destroying state bootstrap must not disable the project's Storage API."
  }
}
run "reject_public_state" {
  command = plan
  variables { state_operator_members = ["allAuthenticatedUsers"] }
  expect_failures = [var.state_operator_members]
}
