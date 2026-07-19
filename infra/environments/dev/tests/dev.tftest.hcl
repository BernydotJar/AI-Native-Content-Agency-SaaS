mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      name       = "agency-dev-test"
      number     = "123456789012"
      project_id = "agency-dev-test"
    }
  }

  mock_data "google_monitoring_notification_channel" {
    defaults = {
      name                = "projects/agency-dev-test/notificationChannels/1234567890"
      enabled             = true
      verification_status = "VERIFIED"
    }
  }

  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/agency-dev-test/serviceAccounts/agency-runtime-dev@agency-dev-test.iam.gserviceaccount.com"
      email = "agency-runtime-dev@agency-dev-test.iam.gserviceaccount.com"
    }
  }
}

run "dev_is_private_passwordless_and_bounded" {
  command = apply

  variables {
    project_id                             = "agency-dev-test"
    create_project                         = false
    billing_account                        = "AAAAAA-BBBBBB-CCCCCC"
    region                                 = "us-central1"
    image_pusher_service_account_email     = "github-image-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    runtime_plan_service_account_email     = "github-plan-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    runtime_deployer_service_account_email = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    notification_channel_display_names     = ["Agency dev operators"]
  }

  assert {
    condition     = output.environment == "dev"
    error_message = "Only the dev environment is executable."
  }

  assert {
    condition     = output.budget_enabled
    error_message = "A real dev plan must include the bounded billing budget."
  }

  assert {
    condition = (
      length(output.notification_channel_ids) == 1
      && output.notification_channel_ids[0] == "projects/agency-dev-test/notificationChannels/1234567890"
    )
    error_message = "5xx and budget alerts must use an explicit dev notification channel."
  }

  assert {
    condition = (
      toset(google_project_iam_custom_role.runtime_deployer.permissions) == local.runtime_deployer_permissions
      && google_artifact_registry_repository_iam_member.runtime_deployer_reader.role == "roles/artifactregistry.reader"
      && !contains(keys(google_project_iam_member.runtime_deployer), "roles/run.admin")
    )
    error_message = "The apply identity must use the exact custom runtime permissions and repository-scoped image reader, never Cloud Run Admin."
  }

}
