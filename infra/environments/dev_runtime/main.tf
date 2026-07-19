locals {
  foundation_state_prefix = "environments/dev"
}

data "terraform_remote_state" "foundation" {
  backend = "gcs"

  config = {
    bucket = var.state_bucket_name
    prefix = local.foundation_state_prefix
  }
}

resource "terraform_data" "foundation_gate" {
  input = data.terraform_remote_state.foundation.outputs.project_id

  lifecycle {
    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.project_id == var.project_id
      error_message = "The dev runtime project must exactly match the reviewed dev foundation state."
    }

    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.runtime_deployer_service_account_email == var.runtime_deployer_service_account_email
      error_message = "The apply identity must exactly match the reviewed dev foundation output."
    }
  }
}

module "cloud_run" {
  source = "../../modules/cloud_run"

  project_id                    = var.project_id
  region                        = var.region
  container_image               = var.container_image
  cloud_sql_proxy_image         = var.cloud_sql_proxy_image
  runtime_service_account_email = data.terraform_remote_state.foundation.outputs.runtime_service_account_email
  cloud_sql_connection_name     = data.terraform_remote_state.foundation.outputs.cloud_sql_connection_name
  database_name                 = data.terraform_remote_state.foundation.outputs.database_name
  database_user                 = data.terraform_remote_state.foundation.outputs.database_user
  cors_origins                  = var.cors_origins
  invoker_members               = ["serviceAccount:${var.runtime_deployer_service_account_email}"]
  labels                        = var.labels

  depends_on = [terraform_data.foundation_gate]
}
