resource "google_project_service" "required" {
  for_each = var.enable_bootstrap ? local.required_services : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
