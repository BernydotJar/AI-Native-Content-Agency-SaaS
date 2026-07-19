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

run "runtime_region_must_match_foundation" {
  command = plan

  variables {
    region = "us-east1"
  }

  expect_failures = [terraform_data.foundation_gate]
}

run "runtime_project_must_differ_from_bootstrap" {
  command = plan

  variables {
    bootstrap_project_id = "agency-dev-test"
  }

  expect_failures = [terraform_data.foundation_gate]
}

run "runtime_project_provenance_must_match" {
  command = plan

  variables {
    foundation_project_provenance_sha256 = "5555555555555555555555555555555555555555555555555555555555555555"
  }

  expect_failures = [terraform_data.foundation_gate]
}

run "runtime_notification_provenance_must_match" {
  command = plan

  variables {
    foundation_notification_channel_provenance_sha256 = "6666666666666666666666666666666666666666666666666666666666666666"
  }

  expect_failures = [terraform_data.foundation_gate]
}

run "runtime_immutable_repository_identity_must_match" {
  command = plan

  variables {
    github_repository_id = "99999999"
  }

  expect_failures = [terraform_data.foundation_gate]
}

run "reserved_runtime_labels_are_rejected" {
  command = plan

  variables {
    additional_labels = {
      application = "different-application"
    }
  }

  expect_failures = [var.additional_labels]
}
