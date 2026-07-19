mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      name       = "agency-dev-test"
      number     = "123456789012"
      project_id = "agency-dev-test"
    }
  }

  mock_resource "google_monitoring_notification_channel" {
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

variables {
  project_id                             = "agency-dev-test"
  bootstrap_project_id                   = "agency-bootstrap-test"
  project_provisioning_mode              = "CREATE_NEW"
  billing_account                        = "AAAAAA-BBBBBB-CCCCCC"
  region                                 = "us-central1"
  image_pusher_service_account_email     = "github-image-dev@agency-bootstrap-test.iam.gserviceaccount.com"
  runtime_plan_service_account_email     = "github-plan-dev@agency-bootstrap-test.iam.gserviceaccount.com"
  runtime_deployer_service_account_email = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
  github_repository_owner_id             = "12345678"
  github_repository_id                   = "87654321"
  notification_channels = [{
    schema_version     = "gcp-notification-channel.v1"
    key                = "operators"
    provisioning_mode  = "CREATE_NEW"
    project_id         = "agency-dev-test"
    display_name       = "Agency dev operators"
    email_address      = "operators@example.invalid"
    evidence_sha256    = "1111111111111111111111111111111111111111111111111111111111111111"
    decision_reference = "https://example.invalid/review/1"
    acknowledgement    = "I_ACKNOWLEDGE_TERRAFORM_WILL_CREATE_AND_MANAGE_THIS_EMAIL_CHANNEL"
  }]
}

run "bootstrap_and_dev_projects_must_differ" {
  command = plan

  variables {
    bootstrap_project_id = "agency-dev-test"
  }

  expect_failures = [terraform_data.authorization_gate]
}

run "notification_configuration_must_match_the_dev_project" {
  command = plan

  variables {
    notification_channels = [{
      schema_version     = "gcp-notification-channel.v1"
      key                = "operators"
      provisioning_mode  = "CREATE_NEW"
      project_id         = "different-dev-project"
      display_name       = "Agency dev operators"
      email_address      = "operators@example.invalid"
      evidence_sha256    = "1111111111111111111111111111111111111111111111111111111111111111"
      decision_reference = "https://example.invalid/review/1"
      acknowledgement    = "I_ACKNOWLEDGE_TERRAFORM_WILL_CREATE_AND_MANAGE_THIS_EMAIL_CHANNEL"
    }]
  }

  expect_failures = [var.notification_channels]
}

run "reserved_dev_labels_are_rejected" {
  command = plan

  variables {
    additional_labels = {
      managed_by = "manual"
    }
  }

  expect_failures = [var.additional_labels]
}

run "phase_identities_must_come_from_the_exact_bootstrap_project" {
  command = plan

  variables {
    runtime_deployer_service_account_email = "github-deploy-dev@different-bootstrap.iam.gserviceaccount.com"
  }

  expect_failures = [terraform_data.authorization_gate]
}
