mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      name       = "agency-dev-adopt"
      number     = "123456789012"
      project_id = "agency-dev-adopt"
    }
  }

  mock_resource "google_monitoring_notification_channel" {
    defaults = {
      name                = "projects/agency-dev-adopt/notificationChannels/1234567890"
      enabled             = true
      verification_status = "VERIFIED"
    }
  }

  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/agency-dev-adopt/serviceAccounts/agency-runtime-dev@agency-dev-adopt.iam.gserviceaccount.com"
      email = "agency-runtime-dev@agency-dev-adopt.iam.gserviceaccount.com"
    }
  }
}

override_resource {
  target = google_project.dev
  values = {
    project_id = "agency-dev-adopt"
  }
}

override_resource {
  target = module.observability.google_monitoring_notification_channel.delivery["operators"]
  values = {
    name                = "projects/agency-dev-adopt/notificationChannels/1234567890"
    enabled             = true
    verification_status = "VERIFIED"
  }
}

variables {
  project_id                = "agency-dev-adopt"
  bootstrap_project_id      = "agency-bootstrap-test"
  project_provisioning_mode = "ADOPT_EXISTING"
  existing_project_adoption = {
    schema_version     = "gcp-project-adoption.v1"
    project_id         = "agency-dev-adopt"
    evidence_sha256    = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    decision_reference = "https://example.invalid/review/adopt"
    acknowledgement    = "I_ACKNOWLEDGE_TERRAFORM_WILL_MANAGE_THIS_EXISTING_PROJECT"
  }
  billing_account                        = "AAAAAA-BBBBBB-CCCCCC"
  region                                 = "us-central1"
  image_pusher_service_account_email     = "github-image-dev@agency-bootstrap-test.iam.gserviceaccount.com"
  runtime_plan_service_account_email     = "github-plan-dev@agency-bootstrap-test.iam.gserviceaccount.com"
  runtime_deployer_service_account_email = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
  github_repository_owner_id             = "12345678"
  github_repository_id                   = "87654321"
  notification_channels = [{
    schema_version        = "gcp-notification-channel.v1"
    key                   = "operators"
    provisioning_mode     = "ADOPT_EXISTING"
    project_id            = "agency-dev-adopt"
    display_name          = "Agency dev operators"
    email_address         = "operators@example.invalid"
    existing_channel_name = "projects/agency-dev-adopt/notificationChannels/1234567890"
    evidence_sha256       = "1111111111111111111111111111111111111111111111111111111111111111"
    decision_reference    = "https://example.invalid/review/1"
    acknowledgement       = "I_ACKNOWLEDGE_TERRAFORM_WILL_IMPORT_AND_MANAGE_THIS_VERIFIED_EMAIL_CHANNEL"
  }]
}

run "existing_dev_project_is_imported_and_provenanced" {
  command = plan

  assert {
    condition = (
      output.project_provisioning_mode == "ADOPT_EXISTING"
      && can(regex("^[0-9a-f]{64}$", output.project_provenance_sha256))
    )
    error_message = "An adopted dev project must expose versioned provenance."
  }
}

run "dev_adoption_cannot_target_a_different_project" {
  command = plan

  variables {
    existing_project_adoption = {
      schema_version     = "gcp-project-adoption.v1"
      project_id         = "different-dev-project"
      evidence_sha256    = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      decision_reference = "https://example.invalid/review/adopt"
      acknowledgement    = "I_ACKNOWLEDGE_TERRAFORM_WILL_MANAGE_THIS_EXISTING_PROJECT"
    }
  }

  expect_failures = [terraform_data.authorization_gate]
}
