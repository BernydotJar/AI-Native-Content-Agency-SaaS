data "google_monitoring_notification_channel" "delivery" {
  for_each = toset(var.notification_channel_display_names)

  project      = var.project_id
  display_name = each.value
  type         = "email"
}

locals {
  notification_channel_ids = sort([
    for channel in data.google_monitoring_notification_channel.delivery : channel.name
  ])
}

resource "terraform_data" "notification_delivery_gate" {
  input = local.notification_channel_ids

  lifecycle {
    precondition {
      condition = alltrue([
        for channel in data.google_monitoring_notification_channel.delivery :
        channel.enabled && channel.verification_status == "VERIFIED"
      ])
      error_message = "Every alert/budget channel must be an enabled and VERIFIED Monitoring email channel."
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
