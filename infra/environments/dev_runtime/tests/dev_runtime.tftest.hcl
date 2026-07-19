mock_provider "google" {}

override_data {
  target = data.terraform_remote_state.foundation
  values = {
    outputs = {
      project_id                             = "agency-dev-test"
      runtime_service_account_email          = "agency-runtime-dev@agency-dev-test.iam.gserviceaccount.com"
      runtime_deployer_service_account_email = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
      cloud_sql_connection_name              = "agency-dev-test:us-central1:agency-postgres-dev"
      database_name                          = "agency"
      database_user                          = "agency-runtime-dev@agency-dev-test.iam"
      budget_enabled                         = true
      notification_channel_ids               = ["projects/agency-dev-test/notificationChannels/1234567890"]
    }
  }
}

run "runtime_is_private_immutable_and_foundation_bound" {
  command = plan

  variables {
    project_id                             = "agency-dev-test"
    region                                 = "us-central1"
    state_bucket_name                      = "agency-bootstrap-test-tfstate"
    runtime_deployer_service_account_email = "github-deploy-dev@agency-bootstrap-test.iam.gserviceaccount.com"
    container_image                        = "us-central1-docker.pkg.dev/agency-dev-test/agency-images/app@sha256:1111111111111111111111111111111111111111111111111111111111111111"
    cloud_sql_proxy_image                  = "gcr.io/cloud-sql-connectors/cloud-sql-proxy@sha256:2222222222222222222222222222222222222222222222222222222222222222"
  }

  assert {
    condition     = output.environment == "dev"
    error_message = "Only the dev runtime environment is executable."
  }

  assert {
    condition     = output.cloud_run_invoker_iam_disabled == false
    error_message = "Cloud Run IAM invoker enforcement must remain enabled."
  }
}
