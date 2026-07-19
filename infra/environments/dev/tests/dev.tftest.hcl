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

run "dev_is_private_passwordless_and_bounded" {
  command = apply

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

  assert {
    condition     = output.environment == "dev"
    error_message = "Only the dev environment is executable."
  }

  assert {
    condition = (
      output.bootstrap_project_id == "agency-bootstrap-test"
      && output.region == "us-central1"
      && output.github_repository_owner_id == "12345678"
      && output.github_repository_id == "87654321"
      && can(regex("^[0-9a-f]{64}$", output.project_provenance_sha256))
      && can(regex("^[0-9a-f]{64}$", output.notification_channel_provenance_sha256))
      && local.effective_labels.application == "ai-native-content-agency"
      && local.effective_labels.environment == "dev"
      && local.effective_labels.managed_by == "terraform"
    )
    error_message = "Foundation outputs must bind project separation, region, provenance and protected labels."
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
      && length(local.runtime_deployer_permissions) == 16
      && local.runtime_deployer_permissions == toset([
        "resourcemanager.projects.get",
        "run.executions.get",
        "run.jobs.create",
        "run.jobs.get",
        "run.jobs.getIamPolicy",
        "run.jobs.list",
        "run.jobs.run",
        "run.jobs.update",
        "run.locations.get",
        "run.locations.list",
        "run.operations.get",
        "run.services.create",
        "run.services.get",
        "run.services.getIamPolicy",
        "run.services.list",
        "run.services.update",
      ])
      && google_artifact_registry_repository_iam_member.runtime_deployer_reader.role == "roles/artifactregistry.reader"
      && google_artifact_registry_repository_iam_member.runtime_deployer_rollback_tag.role == google_project_iam_custom_role.rollback_tag_operator.name
      && toset(google_project_iam_custom_role.rollback_tag_operator.permissions) == toset([
        "artifactregistry.tags.create",
        "artifactregistry.tags.update",
      ])
      && length(google_project_iam_custom_role.rollback_tag_operator.permissions) == 2
      && google_artifact_registry_repository_iam_member.runtime_plan_reader.role == "roles/artifactregistry.reader"
      && google_project_iam_member.image_pusher_runtime_reader["roles/run.viewer"].role == "roles/run.viewer"
      && !contains(keys(google_project_iam_member.runtime_deployer), "roles/run.admin")
    )
    error_message = "Build, plan and apply identities must have only their reviewed runtime-read, rollback-tag and repository-scoped permissions."
  }


  assert {
    condition = (
      google_project_iam_member.runtime_deployer["roles/run.servicesInvoker"].role == "roles/run.servicesInvoker"
      && !contains(local.runtime_deployer_permissions, "run.services.delete")
      && !contains(local.runtime_deployer_permissions, "run.jobs.delete")
      && !contains(local.runtime_deployer_permissions, "run.services.setIamPolicy")
    )
    error_message = "Foundation must grant private invocation while routine deployment fails closed on IAM mutation and deletion."
  }

  assert {
    condition = (
      module.artifact_registry.repository_id == "agency-images"
      && module.artifact_registry.docker_repository == "us-central1-docker.pkg.dev/agency-dev-test/agency-images"
    )
    error_message = "The foundation must expose the dedicated regional image repository."
  }

}
