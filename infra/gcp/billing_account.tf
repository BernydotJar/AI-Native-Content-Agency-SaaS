data "google_billing_account" "selected" {
  billing_account = var.billing_account_id
  open            = true
  lookup_projects = false
}
