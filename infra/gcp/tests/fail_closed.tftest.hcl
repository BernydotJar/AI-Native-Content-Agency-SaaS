mock_provider "google" {}

run "defaults_plan_zero_resources" {
  command = plan

  variables {
    project_id = "campaignos-test-12345"
  }

  assert {
    condition     = length(google_project_service.required) == 0
    error_message = "Default plan must not enable project services."
  }

  assert {
    condition     = length(google_billing_budget.project) == 0
    error_message = "Default plan must not create a billing budget."
  }

  assert {
    condition     = length(google_cloud_run_v2_service.app) == 0
    error_message = "Default plan must not create Cloud Run."
  }

  assert {
    condition     = output.resource_creation_enabled == false
    error_message = "Bootstrap must be disabled by default."
  }
}

run "bootstrap_has_keyless_identity_and_budget" {
  command = plan

  variables {
    project_id           = "campaignos-test-12345"
    project_number       = "970393454298"
    billing_account_id   = "01CF41-85C4FF-734D97"
    enable_bootstrap     = true
    monthly_budget_units = 20
  }

  assert {
    condition     = length(google_service_account.runtime) == 1 && length(google_service_account.deployer) == 1
    error_message = "Bootstrap must create distinct runtime and deployer service accounts."
  }

  assert {
    condition     = length(google_iam_workload_identity_pool_provider.github) == 1
    error_message = "Bootstrap must use GitHub Workload Identity Federation."
  }

  assert {
    condition     = length(google_billing_budget.project) == 1
    error_message = "Bootstrap must create a project-scoped budget before runtime resources."
  }

  assert {
    condition     = length(google_artifact_registry_repository.app[0].cleanup_policies) == 2
    error_message = "Artifact Registry must keep bounded cleanup policies."
  }
}

run "cloud_run_requires_immutable_image" {
  command = plan

  variables {
    project_id           = "campaignos-test-12345"
    project_number       = "970393454298"
    billing_account_id   = "01CF41-85C4FF-734D97"
    enable_bootstrap     = true
    enable_cloud_run     = true
    monthly_budget_units = 20
    container_image      = "us-central1-docker.pkg.dev/campaignos-test-12345/campaignos/app:latest"
  }

  expect_failures = [var.container_image, var.secret_environment]
}
