output "artifact_image_prefix" { value = module.artifact_registry.image_prefix }
output "runbook_bucket" { value = module.storage.name }
output "firestore_database" { value = module.firestore.name }
output "runtime_service_account" { value = module.identity.runtime_email }
output "deployer_service_account" { value = module.identity.deployer_email }
output "ingester_service_account" { value = module.identity.ingester_email }
output "workload_identity_provider" { value = module.identity.workload_identity_provider }
output "service_url" {
  value = var.container_image == null ? null : module.cloud_run[0].uri
}
