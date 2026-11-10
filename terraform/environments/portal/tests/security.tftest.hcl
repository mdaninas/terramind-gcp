mock_provider "google" {}

variables {
  project_id           = "synthetic-project"
  project_number       = "123456789012"
  image                = "us-central1-docker.pkg.dev/synthetic-project/terramind-dev/terramind@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  oauth_client_id      = "123-synthetic.apps.googleusercontent.com"
  oauth_secret_name    = "synthetic-oauth-client"
  oauth_secret_version = "1"
  allowed_emails       = ["analyst@example.invalid"]
  invoker_members      = ["user:analyst@example.invalid"]
}

run "private_durable_portal" {
  command = plan
  assert {
    condition     = output.security_settings.iam_enforced && output.security_settings.min_instances == 0 && output.security_settings.max_instances == 1
    error_message = "Portal must retain invoker IAM and scale between zero and one instance."
  }
  assert {
    condition     = output.security_settings.storage_backend == "firestore" && output.security_settings.secret_version == "1"
    error_message = "Cloud state must be durable and OAuth secrets must use a pinned version."
  }
  assert {
    condition     = output.security_settings.data_condition == "resource.name == 'projects/synthetic-project/databases/terramind-portal'"
    error_message = "Portal writes must be limited to its separate database."
  }
  assert {
    condition     = google_project_iam_member.knowledge.condition[0].expression == "resource.name == 'projects/synthetic-project/databases/terramind-dev'" && !contains(google_project_iam_custom_role.knowledge.permissions, "datastore.entities.update")
    error_message = "Knowledge access must be read-only and database-conditioned."
  }
  assert {
    condition     = length(google_firestore_field.expiry) == 3 && length(google_firestore_field.report_payload.index_config) == 1
    error_message = "Session/flow/report expiry and unindexed report payloads are required."
  }
}

run "reject_public_invoker" {
  command = plan
  variables { invoker_members = ["allUsers"] }
  expect_failures = [var.invoker_members]
}

run "reject_unpinned_secret" {
  command = plan
  variables { oauth_secret_version = "latest" }
  expect_failures = [var.oauth_secret_version]
}

run "reject_mutable_image" {
  command = plan
  variables { image = "us-central1-docker.pkg.dev/synthetic-project/terramind-dev/terramind:latest" }
  expect_failures = [var.image]
}
