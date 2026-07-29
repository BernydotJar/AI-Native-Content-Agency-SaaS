resource "google_secret_manager_secret" "runtime" {
  for_each = var.enable_bootstrap ? var.managed_secret_ids : toset([])

  project   = var.project_id
  secret_id = each.value
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}
