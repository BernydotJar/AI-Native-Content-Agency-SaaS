output "provider_names" {
  description = "Phase-specific WIF provider resource names consumed by google-github-actions/auth."
  value       = { for phase, provider in google_iam_workload_identity_pool_provider.phase : phase => provider.name }
}

output "service_account_emails" {
  description = "Phase-specific keyless service-account emails."
  value       = { for phase, account in google_service_account.phase : phase => account.email }
}

output "attribute_condition" {
  description = "Auditable exact repository/ref/environment/workflow provider condition."
  value       = { for phase, provider in google_iam_workload_identity_pool_provider.phase : phase => provider.attribute_condition }
}

output "workflow_ref" {
  value = local.workflow_ref
}
