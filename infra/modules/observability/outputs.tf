output "alert_policy_name" {
  value = try(google_monitoring_alert_policy.cloud_run_server_errors[0].name, null)
}

output "budget_enabled" {
  value = true
}

output "notification_channel_ids" {
  value = local.notification_channel_ids
}
