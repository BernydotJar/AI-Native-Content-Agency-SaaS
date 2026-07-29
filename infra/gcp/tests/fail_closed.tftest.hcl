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
    condition     = length(google_cloud_run_v2_service.app) == 0
    error_message = "Default plan must not create Cloud Run."
  }

  assert {
    condition     = output.resource_creation_enabled == false
    error_message = "Bootstrap must be disabled by default."
  }
}

run "bootstrap_has_keyless_identity" {
  command = plan

  variables {
    project_id       = "campaignos-test-12345"
    enable_bootstrap = true
  }

  assert {
    condition     = length(google_service_account.runtime) == 1 && length(google_service_account.deployer) == 1
    error_message = "Bootstrap must create distinct runtime and deployer service accounts."
  }

  assert {
    condition     = length(google_iam_workload_identity_pool_provider.github) == 1
    error_message = "Bootstrap must use GitHub Workload Identity Federation."
  }
}

run "cloud_run_requires_immutable_image" {
  command = plan

  variables {
    project_id       = "campaignos-test-12345"
    enable_bootstrap = true
    enable_cloud_run = true
    container_image  = "us-central1-docker.pkg.dev/campaignos-test-12345/campaignos/app:latest"
  }

  expect_failures = [var.container_image, var.secret_environment]
}
