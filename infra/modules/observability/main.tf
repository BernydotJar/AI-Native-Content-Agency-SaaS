locals {
  notification_channels_by_key = {
    for channel in var.notification_channels : nonsensitive(channel.key) => channel
  }
  notification_channel_keys = toset(nonsensitive([
    for channel in var.notification_channels : channel.key
  ]))
  notification_channel_ids = sort([
    for channel in google_monitoring_notification_channel.delivery : channel.name
  ])
  notification_channel_provenance_sha256 = nonsensitive(sha256(jsonencode(sort([
    for channel in var.notification_channels : jsonencode({
      schema_version        = channel.schema_version
      key                   = channel.key
      provisioning_mode     = channel.provisioning_mode
      project_id            = channel.project_id
      display_name          = channel.display_name
      email_address         = channel.email_address
      existing_channel_name = channel.existing_channel_name
      evidence_sha256       = channel.evidence_sha256
      decision_reference    = channel.decision_reference
      acknowledgement       = channel.acknowledgement
    })
  ]))))
}

resource "google_monitoring_notification_channel" "delivery" {
  for_each = local.notification_channel_keys

  project      = var.project_id
  display_name = local.notification_channels_by_key[each.key].display_name
  type         = "email"
  enabled      = true
  force_delete = false
  labels = {
    email_address = local.notification_channels_by_key[each.key].email_address
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "terraform_data" "notification_delivery_gate" {
  input = local.notification_channel_ids

  lifecycle {
    precondition {
      condition = alltrue([
        for key, channel in google_monitoring_notification_channel.delivery :
        channel.enabled
        && channel.verification_status == "VERIFIED"
        && startswith(channel.name, "projects/${var.project_id}/notificationChannels/")
        && channel.type == "email"
        && channel.labels["email_address"] == local.notification_channels_by_key[key].email_address
        && can(regex("^[0-9a-f]{64}$", local.notification_channels_by_key[key].evidence_sha256))
        && can(regex("^https://[^[:space:]]+$", local.notification_channels_by_key[key].decision_reference))
        && (
          local.notification_channels_by_key[key].provisioning_mode == "CREATE_NEW"
          || channel.name == local.notification_channels_by_key[key].existing_channel_name
        )
      ])
      error_message = "Every Terraform-managed channel must resolve inside the dev project as an enabled and VERIFIED email channel with reviewed evidence before alerts or budget are created."
    }
  }
}

resource "google_monitoring_alert_policy" "cloud_run_server_errors" {
  count = var.enable_cloud_run_alert ? 1 : 0

  project               = var.project_id
  display_name          = "Agency dev Cloud Run 5xx"
  combiner              = "OR"
  enabled               = true
  notification_channels = local.notification_channel_ids

  documentation {
    content   = "Investigate structured application logs and the latest Cloud Run revision. No automatic rollback is performed."
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "Cloud Run 5xx responses"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_revision\"",
        "resource.label.service_name = \"${var.cloud_run_service_name}\"",
        "metric.type = \"run.googleapis.com/request_count\"",
        "metric.label.response_code_class = \"5xx\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  user_labels = var.labels

  depends_on = [terraform_data.notification_delivery_gate]
}

resource "google_billing_budget" "dev" {
  billing_account = var.billing_account
  display_name    = "AI Native Agency dev monthly guard"

  budget_filter {
    projects = ["projects/${var.project_number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }

  threshold_rules {
    threshold_percent = 0.9
  }

  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = local.notification_channel_ids
    disable_default_iam_recipients   = true
  }

  depends_on = [terraform_data.notification_delivery_gate]
}
