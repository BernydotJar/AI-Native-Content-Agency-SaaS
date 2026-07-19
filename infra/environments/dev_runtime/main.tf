locals {
  foundation_state_prefix = "environments/dev"
  required_labels = {
    application = "ai-native-content-agency"
    environment = "dev"
    managed_by  = "terraform"
  }
  effective_labels = merge(var.additional_labels, local.required_labels)
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
      condition = (
        var.project_id != var.bootstrap_project_id
        && data.terraform_remote_state.foundation.outputs.bootstrap_project_id == var.bootstrap_project_id
      )
      error_message = "The runtime must bind one distinct reviewed bootstrap project."
    }

    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.project_id == var.project_id
      error_message = "The dev runtime project must exactly match the reviewed dev foundation state."
    }

    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.region == var.region
      error_message = "The dev runtime region must exactly match the reviewed dev foundation region."
    }

    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.project_provenance_sha256 == var.foundation_project_provenance_sha256
      error_message = "The runtime project provenance digest must match the reviewed dev foundation output."
    }

    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.notification_channel_provenance_sha256 == var.foundation_notification_channel_provenance_sha256
      error_message = "The notification-channel provenance digest must match the reviewed dev foundation output."
    }

    precondition {
      condition     = data.terraform_remote_state.foundation.outputs.runtime_deployer_service_account_email == var.runtime_deployer_service_account_email
      error_message = "The apply identity must exactly match the reviewed dev foundation output."
    }

    precondition {
      condition = (
        data.terraform_remote_state.foundation.outputs.github_repository_owner_id == var.github_repository_owner_id
        && data.terraform_remote_state.foundation.outputs.github_repository_id == var.github_repository_id
      )
      error_message = "The runtime must bind the immutable GitHub owner and repository IDs reviewed by foundation."
    }

    precondition {
      condition = try(
        split("@", var.container_image)[0] == "${data.terraform_remote_state.foundation.outputs.artifact_repository}/app"
        && can(regex("^sha256:[0-9a-f]{64}$", split("@", var.container_image)[1])),
        false,
      )
      error_message = "The application image must be the app digest from the exact foundation Artifact Registry repository."
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
  labels                        = local.effective_labels

  depends_on = [terraform_data.foundation_gate]
}
