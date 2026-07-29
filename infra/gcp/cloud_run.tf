resource "google_cloud_run_v2_service" "app" {
  count = var.enable_cloud_run ? 1 : 0

  project             = var.project_id
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.environment == "production"
  labels              = local.labels

  template {
    service_account                  = google_service_account.runtime[0].email
    timeout                          = "300s"
    max_instance_request_concurrency = 20

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      name  = "campaignos"
      image = var.container_image

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.container_cpu
          memory = var.container_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = var.runtime_environment
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_environment
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = env.value.version
            }
          }
        }
      }

      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 2
        period_seconds        = 5
        failure_threshold     = 24

        http_get {
          path = "/readyz"
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 10
        timeout_seconds       = 2
        period_seconds        = 30
        failure_threshold     = 3

        http_get {
          path = "/healthz"
          port = 8080
        }
      }
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret.runtime,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.enable_cloud_run && var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_service.app[0].location
  name     = google_cloud_run_v2_service.app[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
