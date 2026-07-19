mock_provider "google" {}

override_data {
  target = data.terraform_remote_state.foundation
  values = {
    outputs = {
      project_id                             = "agency-dev-test"
      bootstrap_project_id                   = "agency-bootstrap-test"
      region                                 = "us-central1"
      project_provenance_sha256              = "3333333333333333333333333333333333333333333333333333333333333333"
      runtime_service_account_email          = "agency-runtime-dev@agency-dev-test.iam.gserviceaccount.com"
      runtime_deployer_service_account_email = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
      cloud_sql_connection_name              = "agency-dev-test:us-central1:agency-postgres-dev"
      database_name                          = "agency"
      database_user                          = "agency-runtime-dev@agency-dev-test.iam"
      artifact_repository                    = "us-central1-docker.pkg.dev/agency-dev-test/agency-images"
      budget_enabled                         = true
      notification_channel_ids               = ["projects/agency-dev-test/notificationChannels/1234567890"]
      notification_channel_provenance_sha256 = "4444444444444444444444444444444444444444444444444444444444444444"
      github_repository_owner_id             = "12345678"
      github_repository_id                   = "87654321"
    }
  }
}

run "runtime_is_private_immutable_and_foundation_bound" {
  command = plan

  variables {
    project_id                                        = "agency-dev-test"
    bootstrap_project_id                              = "agency-bootstrap-test"
    region                                            = "us-central1"
    state_bucket_name                                 = "agency-bootstrap-test-tfstate"
    foundation_project_provenance_sha256              = "3333333333333333333333333333333333333333333333333333333333333333"
    foundation_notification_channel_provenance_sha256 = "4444444444444444444444444444444444444444444444444444444444444444"
    runtime_deployer_service_account_email            = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    github_repository_owner_id                        = "12345678"
    github_repository_id                              = "87654321"
    container_image                                   = "us-central1-docker.pkg.dev/agency-dev-test/agency-images/app@sha256:1111111111111111111111111111111111111111111111111111111111111111"
    cloud_sql_proxy_image                             = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.2@sha256:fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"
  }

  assert {
    condition     = output.environment == "dev"
    error_message = "Only the dev runtime environment is executable."
  }

  assert {
    condition     = output.cloud_run_invoker_iam_disabled == false
    error_message = "Cloud Run IAM invoker enforcement must remain enabled."
  }

  assert {
    condition = (
      output.bootstrap_project_id == "agency-bootstrap-test"
      && output.region == "us-central1"
      && output.foundation_project_provenance_sha256 == "3333333333333333333333333333333333333333333333333333333333333333"
      && output.foundation_notification_channel_provenance_sha256 == "4444444444444444444444444444444444444444444444444444444444444444"
      && output.github_repository_owner_id == "12345678"
      && output.github_repository_id == "87654321"
      && output.foundation_artifact_repository == "us-central1-docker.pkg.dev/agency-dev-test/agency-images"
      && local.effective_labels.application == "ai-native-content-agency"
      && local.effective_labels.environment == "dev"
      && local.effective_labels.managed_by == "terraform"
    )
    error_message = "Runtime must bind the exact bootstrap project, foundation region, provenance and protected labels."
  }
}

run "application_image_is_exactly_foundation_repository_app" {
  command = plan

  variables {
    project_id                                        = "agency-dev-test"
    bootstrap_project_id                              = "agency-bootstrap-test"
    region                                            = "us-central1"
    state_bucket_name                                 = "agency-bootstrap-test-tfstate"
    foundation_project_provenance_sha256              = "3333333333333333333333333333333333333333333333333333333333333333"
    foundation_notification_channel_provenance_sha256 = "4444444444444444444444444444444444444444444444444444444444444444"
    runtime_deployer_service_account_email            = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    github_repository_owner_id                        = "12345678"
    github_repository_id                              = "87654321"
    container_image                                   = "evil.invalid/agency-images/app@sha256:1111111111111111111111111111111111111111111111111111111111111111"
  }

  expect_failures = [terraform_data.foundation_gate]
}

run "proxy_image_is_exactly_source_reviewed" {
  command = plan

  variables {
    project_id                                        = "agency-dev-test"
    bootstrap_project_id                              = "agency-bootstrap-test"
    region                                            = "us-central1"
    state_bucket_name                                 = "agency-bootstrap-test-tfstate"
    foundation_project_provenance_sha256              = "3333333333333333333333333333333333333333333333333333333333333333"
    foundation_notification_channel_provenance_sha256 = "4444444444444444444444444444444444444444444444444444444444444444"
    runtime_deployer_service_account_email            = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    github_repository_owner_id                        = "12345678"
    github_repository_id                              = "87654321"
    container_image                                   = "us-central1-docker.pkg.dev/agency-dev-test/agency-images/app@sha256:1111111111111111111111111111111111111111111111111111111111111111"
    cloud_sql_proxy_image                             = "evil.invalid/cloud-sql-proxy:2.18.2@sha256:fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"
  }

  expect_failures = [var.cloud_sql_proxy_image]
}
