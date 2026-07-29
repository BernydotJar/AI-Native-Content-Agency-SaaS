resource "google_billing_budget" "project" {
  count = var.enable_bootstrap ? 1 : 0

  billing_account = data.google_billing_account.selected.id
  display_name    = "CampaignOS ${var.environment} monthly guardrail"

  amount {
    specified_amount {
      currency_code = data.google_billing_account.selected.currency_code
      units         = tostring(var.monthly_budget_units)
    }
  }

  budget_filter {
    calendar_period = "MONTH"
    projects        = ["projects/${var.project_number}"]
  }

  dynamic "threshold_rules" {
    for_each = local.budget_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  depends_on = [google_project_service.required]
}
