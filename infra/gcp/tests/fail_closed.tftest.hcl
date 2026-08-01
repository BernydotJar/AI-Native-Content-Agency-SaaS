mock_provider "google" {}

run "defaults_plan_zero_resources" {
  command = plan

  variables {
    project_id = "campaignos-test-12345"
  }

  assert {
    condition     = length(google_project_service.required) == 0
    error_message = "Default plan must not enable project services."
  }

  assert {
    condition     = length(google_billing_budget.project) == 0
    error_message = "Default plan must not create a billing budget."
  }

  assert {
    condition     = length(google_cloud_run_v2_service.app) == 0
    error_message = "Default plan must not create Cloud Run."
  }

  assert {
    condition     = length(google_sql_database_instance.app) == 0 && length(google_sql_database.app) == 0
    error_message = "Default plan must not create Cloud SQL resources."
  }

  assert {
    condition     = length(google_project_iam_member.runtime_cloud_sql_client) == 0 && length(google_project_iam_member.deployer_cloud_sql_admin) == 0
    error_message = "Default plan must not grant Cloud SQL authority."
  }

  assert {
    condition     = output.resource_creation_enabled == false
    error_message = "Bootstrap must be disabled by default."
  }
}

run "bootstrap_has_keyless_identity_and_budget" {
  command = plan

  variables {
    project_id           = "campaignos-test-12345"
    project_number       = "970393454298"
    billing_account_id   = "01CF41-85C4FF-734D97"
    enable_bootstrap     = true
    monthly_budget_units = 20
  }

  assert {
    condition     = length(google_service_account.runtime) == 1 && length(google_service_account.deployer) == 1
    error_message = "Bootstrap must create distinct runtime and deployer service accounts."
  }

  assert {
    condition     = length(google_iam_workload_identity_pool_provider.github) == 1
    error_message = "Bootstrap must use GitHub Workload Identity Federation."
  }

  assert {
    condition     = length(google_billing_budget.project) == 1
    error_message = "Bootstrap must create a project-scoped budget before runtime resources."
  }

  assert {
    condition     = length(google_artifact_registry_repository.app[0].cleanup_policies) == 2
    error_message = "Artifact Registry must keep bounded cleanup policies."
  }
}

run "cloud_run_requires_immutable_image" {
  command = plan

  variables {
    project_id                           = "campaignos-test-12345"
    project_number                       = "970393454298"
    billing_account_id                   = "01CF41-85C4FF-734D97"
    enable_bootstrap                     = true
    enable_cloud_sql                     = true
    cost_review_receipt_sha256           = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    enable_cloud_run                     = true
    authorized_monthly_cost_cap_units    = 30000
    reviewed_monthly_cost_estimate_units = 28000
    monthly_budget_units                 = 30000
    schema_initialization_receipt_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    container_image                      = "us-central1-docker.pkg.dev/campaignos-test-12345/campaignos/app:latest"
  }

  expect_failures = [var.container_image, var.secret_environment]
}


run "cloud_sql_rejects_estimate_above_hard_cap" {
  command = plan

  variables {
    project_id                           = "campaignos-test-12345"
    project_number                       = "970393454298"
    billing_account_id                   = "01CF41-85C4FF-734D97"
    enable_bootstrap                     = true
    enable_cloud_sql                     = true
    cost_review_receipt_sha256           = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    authorized_monthly_cost_cap_units    = 4000
    reviewed_monthly_cost_estimate_units = 24609
    monthly_budget_units                 = 4000
  }

  expect_failures = [var.enable_cloud_sql]
}

run "cloud_sql_plan_is_bounded" {
  command = plan

  variables {
    project_id                           = "campaignos-test-12345"
    project_number                       = "970393454298"
    billing_account_id                   = "01CF41-85C4FF-734D97"
    enable_bootstrap                     = true
    enable_cloud_sql                     = true
    cost_review_receipt_sha256           = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    authorized_monthly_cost_cap_units    = 30000
    reviewed_monthly_cost_estimate_units = 28000
    monthly_budget_units                 = 30000
  }

  assert {
    condition     = length(google_sql_database_instance.app) == 1 && length(google_sql_database.app) == 1
    error_message = "Approved Cloud SQL planning must create exactly one instance and one application database."
  }

  assert {
    condition     = google_sql_database_instance.app[0].database_version == "POSTGRES_15"
    error_message = "The pilot database must stay on PostgreSQL 15."
  }

  assert {
    condition = (
      google_sql_database_instance.app[0].settings[0].availability_type == "ZONAL" &&
      google_sql_database_instance.app[0].settings[0].connector_enforcement == "REQUIRED" &&
      google_sql_database_instance.app[0].settings[0].disk_type == "PD_SSD" &&
      google_sql_database_instance.app[0].settings[0].disk_size == 10 &&
      google_sql_database_instance.app[0].settings[0].disk_autoresize_limit == 20
    )
    error_message = "The pilot database must use the bounded zonal storage profile."
  }

  assert {
    condition = (
      google_sql_database_instance.app[0].settings[0].backup_configuration[0].enabled &&
      google_sql_database_instance.app[0].settings[0].backup_configuration[0].point_in_time_recovery_enabled &&
      google_sql_database_instance.app[0].settings[0].backup_configuration[0].transaction_log_retention_days == 7
    )
    error_message = "Cloud SQL backups and point-in-time recovery must remain enabled."
  }

  assert {
    condition = (
      google_sql_database_instance.app[0].settings[0].ip_configuration[0].ipv4_enabled &&
      length(google_sql_database_instance.app[0].settings[0].ip_configuration[0].authorized_networks) == 0
    )
    error_message = "Cloud SQL may expose its connector endpoint but must not authorize direct client networks."
  }

  assert {
    condition     = length(google_project_iam_member.runtime_cloud_sql_client) == 1 && length(google_project_iam_member.deployer_cloud_sql_admin) == 1
    error_message = "Cloud SQL planning must separate runtime client and deployer administration authority."
  }
}

run "cloud_run_requires_schema_receipt_and_minimal_secrets" {
  command = plan

  variables {
    project_id                           = "campaignos-test-12345"
    project_number                       = "970393454298"
    billing_account_id                   = "01CF41-85C4FF-734D97"
    enable_bootstrap                     = true
    enable_cloud_sql                     = true
    cost_review_receipt_sha256           = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    enable_cloud_run                     = true
    authorized_monthly_cost_cap_units    = 30000
    reviewed_monthly_cost_estimate_units = 28000
    monthly_budget_units                 = 30000
    container_image                      = "us-central1-docker.pkg.dev/campaignos-test-12345/campaignos/app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  expect_failures = [var.schema_initialization_receipt_sha256, var.secret_environment]
}

run "effects_off_cloud_run_uses_minimal_pinned_secrets" {
  command = plan

  variables {
    project_id                           = "campaignos-test-12345"
    project_number                       = "970393454298"
    billing_account_id                   = "01CF41-85C4FF-734D97"
    enable_bootstrap                     = true
    enable_cloud_sql                     = true
    cost_review_receipt_sha256           = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    enable_cloud_run                     = true
    allow_unauthenticated                = true
    authorized_monthly_cost_cap_units    = 30000
    reviewed_monthly_cost_estimate_units = 28000
    monthly_budget_units                 = 30000
    schema_initialization_receipt_sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    container_image                      = "us-central1-docker.pkg.dev/campaignos-test-12345/campaignos/app@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    secret_environment = {
      AGENCY_DATABASE_URL = {
        secret  = "campaignos-database-url"
        version = "1"
      }
      AGENCY_IDENTITY_CREDENTIALS_JSON = {
        secret  = "campaignos-identity-credentials"
        version = "2"
      }
      AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON = {
        secret  = "campaignos-audit-checkpoint-signing-keys"
        version = "3"
      }
      AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID = {
        secret  = "campaignos-audit-checkpoint-active-key-id"
        version = "4"
      }
    }
  }

  assert {
    condition     = length(google_cloud_run_v2_service.app) == 1
    error_message = "The fully reviewed pilot profile must include one Cloud Run service."
  }

  assert {
    condition = (
      google_cloud_run_v2_service.app[0].template[0].scaling[0].min_instance_count == 0 &&
      google_cloud_run_v2_service.app[0].template[0].scaling[0].max_instance_count == 2
    )
    error_message = "The pilot must preserve scale-to-zero and the two-instance ceiling."
  }

  assert {
    condition = (
      google_cloud_run_v2_service.app[0].template[0].volumes[0].name == "cloudsql" &&
      google_cloud_run_v2_service.app[0].template[0].containers[0].volume_mounts[0].mount_path == "/cloudsql"
    )
    error_message = "Cloud Run must use the managed Cloud SQL Unix-socket mount."
  }

  assert {
    condition = (
      google_cloud_run_v2_service.app[0].template[0].annotations["agency.dev/cost-review-receipt"] == "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" &&
      google_cloud_run_v2_service.app[0].template[0].annotations["agency.dev/schema-initialization-receipt"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    error_message = "Cloud Run revisions must retain the cost and schema evidence receipts."
  }

  assert {
    condition     = length(google_secret_manager_secret_iam_member.runtime_secret_accessor) == 4
    error_message = "The effects-off runtime must access only the four injected minimum secrets."
  }

  assert {
    condition = (
      var.runtime_environment["AGENCY_SOCIAL_PUBLICATION_ENABLED"] == "false" &&
      var.runtime_environment["AGENCY_POLITICAL_CONTENT_ENABLED"] == "false" &&
      var.runtime_environment["AGENCY_POLITICAL_PUBLICATION_ENABLED"] == "false" &&
      var.runtime_environment["AGENCY_POLITICAL_PAID_MEDIA_ENABLED"] == "false" &&
      var.runtime_environment["AGENCY_MODEL_EXECUTION_ENABLED"] == "false" &&
      var.runtime_environment["AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED"] == "false"
    )
    error_message = "All model, social, political and paid effects must remain disabled."
  }
}
