mock_provider "google" {
  mock_resource "google_monitoring_notification_channel" {
    defaults = {
      name                = "projects/agency-dev-test/notificationChannels/1234567890"
      enabled             = true
      verification_status = "VERIFIED"
    }
  }
}

variables {
  project_id             = "agency-dev-test"
  project_number         = "123456789012"
  cloud_run_service_name = "agency-control-plane-dev"
  billing_account        = "AAAAAA-BBBBBB-CCCCCC"
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

run "verified_channel_with_reviewed_evidence_enables_delivery" {
  command = plan

  assert {
    condition     = length(output.notification_channel_ids) == 1
    error_message = "The verified Terraform-managed channel must be used for delivery."
  }
}

run "unverified_channel_blocks_alert_and_budget_delivery" {
  command = apply

  override_resource {
    target = google_monitoring_notification_channel.delivery["operators"]
    values = {
      name                = "projects/agency-dev-test/notificationChannels/1234567890"
      enabled             = true
      verification_status = "UNVERIFIED"
    }
  }

  expect_failures = [terraform_data.notification_delivery_gate]
}

run "missing_review_evidence_blocks_alert_and_budget_delivery" {
  command = plan

  variables {
    notification_channels = [{
      schema_version    = "gcp-notification-channel.v1"
      key               = "operators"
      provisioning_mode = "CREATE_NEW"
      project_id        = "agency-dev-test"
      display_name      = "Agency dev operators"
      email_address     = "operators@example.invalid"
      acknowledgement   = "I_ACKNOWLEDGE_TERRAFORM_WILL_CREATE_AND_MANAGE_THIS_EMAIL_CHANNEL"
    }]
  }

  expect_failures = [terraform_data.notification_delivery_gate]
}
