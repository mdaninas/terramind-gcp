mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      email = "synthetic@terramind-demo.iam.gserviceaccount.com"
      name  = "projects/terramind-demo/serviceAccounts/synthetic@terramind-demo.iam.gserviceaccount.com"
    }
  }
}

variables {
  project_id           = "terramind-demo"
  project_number       = "123456789012"
  github_repository    = "synthetic/terramind"
  github_repository_id = "123456789"
  github_owner_id      = "987654321"
  container_image      = "us-central1-docker.pkg.dev/terramind-demo/terramind-dev/terramind@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  invoker_members      = ["user:operator@example.invalid"]
}

run "private_service_and_cost_defaults" {
  command = plan
  assert {
    condition     = module.cloud_run[0].name == "terramind-dev"
    error_message = "Cloud Run must use the configured service name."
  }
  assert {
    condition     = module.cloud_run[0].security_settings.invoker_iam_disabled == false
    error_message = "Cloud Run must enforce invoker IAM."
  }
  assert {
    condition     = module.cloud_run[0].security_settings.min_instances == 0 && module.cloud_run[0].security_settings.max_instances == 2
    error_message = "Cloud Run must scale to zero and cap instances."
  }
  assert {
    condition     = module.cloud_run[0].security_settings.cpu_idle && module.cloud_run[0].security_settings.deletion_protection
    error_message = "Request-based CPU billing and deletion protection must remain enabled."
  }
  assert {
    condition     = module.storage.security_settings.uniform_access && module.storage.security_settings.public_access_prevention == "enforced" && !module.storage.security_settings.force_destroy
    error_message = "Synthetic runbooks must remain private and protected from forced deletion."
  }
  assert {
    condition     = module.firestore.security_settings.dimensions == 768 && module.firestore.security_settings.delete_protection_state == "DELETE_PROTECTION_ENABLED"
    error_message = "Firestore vector dimensions and deletion protection must match the contract."
  }
  assert {
    condition     = module.firestore.security_settings.client_rules_deny_all
    error_message = "Direct client access must be denied."
  }
  assert {
    condition = alltrue([
      for clause in [
        "assertion.repository_id == '123456789'",
        "assertion.repository_owner_id == '987654321'",
        "assertion.repository == 'synthetic/terramind'",
        "assertion.ref == 'refs/heads/main'",
        "assertion.sub == 'repo:synthetic/terramind:environment:development'",
        "assertion.workflow_ref == 'synthetic/terramind/.github/workflows/deploy.yml@refs/heads/main'",
        "assertion.event_name == 'workflow_dispatch'",
      ] : strcontains(module.identity.federation_condition, clause)
    ]) && !strcontains(module.identity.federation_condition, "||")
    error_message = "WIF must constrain exact identity, repository, branch, environment, workflow and event."
  }
  assert {
    condition     = alltrue([for api in google_project_service.required : !api.disable_on_destroy])
    error_message = "Cleanup must not disable project APIs used by other resources."
  }
}

run "foundation_without_image" {
  command = plan
  variables { container_image = null }
  assert {
    condition     = length(module.cloud_run) == 0 && length(google_monitoring_alert_policy.server_errors) == 0
    error_message = "The image repository must be bootstrappable without a Cloud Run image."
  }
}

run "reject_public_invoker" {
  command = plan
  variables { invoker_members = ["allUsers"] }
  expect_failures = [var.invoker_members]
}

run "reject_mutable_image" {
  command = plan
  variables { container_image = "us-central1-docker.pkg.dev/terramind-demo/terramind-dev/terramind:latest" }
  expect_failures = [var.container_image]
}

run "reject_instance_sprawl" {
  command = plan
  variables { max_instances = 50 }
  expect_failures = [var.max_instances]
}
