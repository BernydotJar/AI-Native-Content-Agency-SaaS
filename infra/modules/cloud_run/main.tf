locals {
  database_url = format(
    "postgresql+psycopg:///?host=127.0.0.1&port=5432&dbname=%s&user=%s",
    urlencode(var.database_name),
    urlencode(var.database_user),
  )
}

resource "google_cloud_run_v2_service" "application" {
  project              = var.project_id
  name                 = var.service_name
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = var.deletion_protection
  labels               = var.labels

  template {
    service_account                  = var.runtime_service_account_email
    timeout                          = "300s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      name       = "application"
      image      = var.container_image
      depends_on = ["cloud-sql-proxy"]

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "AGENCY_ENVIRONMENT"
        value = "development"
      }

      env {
        name  = "AGENCY_AUTH_MODE"
        value = "development_headers"
      }

      env {
        name  = "AGENCY_AUTO_CREATE_SCHEMA"
        value = "false"
      }

      env {
        name  = "AGENCY_DATABASE_URL"
        value = local.database_url
      }

      env {
        name  = "AGENCY_CORS_ORIGINS"
        value = jsonencode(var.cors_origins)
      }

      env {
        name  = "AGENCY_WEB_DIST"
        value = "/app/static"
      }

      env {
        name  = "AGENCY_RUN_MIGRATIONS_ON_START"
        value = "true"
      }

      env {
        name  = "AGENCY_CLOUD_SQL_CONNECTION_NAME"
        value = var.cloud_sql_connection_name
      }

      env {
        name  = "AGENCY_CLOUD_SQL_DATABASE"
        value = var.database_name
      }

      env {
        name  = "AGENCY_CLOUD_SQL_IAM_USER"
        value = var.database_user
      }

      env {
        name  = "AGENCY_ALEMBIC_INI"
        value = "/app/backend/alembic.ini"
      }

      env {
        name  = "PORT"
        value = "8080"
      }

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 20

        http_get {
          path = "/readyz"
          port = 8080
        }
      }

      liveness_probe {
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 30
        failure_threshold     = 3

        http_get {
          path = "/healthz"
          port = 8080
        }
      }
    }

    containers {
      name  = "cloud-sql-proxy"
      image = var.cloud_sql_proxy_image
      args = [
        "--auto-iam-authn",
        "--structured-logs",
        "--address=127.0.0.1",
        "--port=5432",
        var.cloud_sql_connection_name,
      ]

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 3
        period_seconds        = 3
        failure_threshold     = 20

        tcp_socket {
          port = 5432
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

resource "google_cloud_run_v2_job" "migrations" {
  project             = var.project_id
  name                = "${var.service_name}-migrate"
  location            = var.region
  deletion_protection = var.deletion_protection
  labels              = var.labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = var.runtime_service_account_email
      timeout         = "600s"
      max_retries     = 1

      containers {
        name    = "migration"
        image   = var.container_image
        command = ["python"]
        args    = ["/app/scripts/run_cloud_migrations.py"]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "AGENCY_CLOUD_SQL_CONNECTION_NAME"
          value = var.cloud_sql_connection_name
        }

        env {
          name  = "AGENCY_CLOUD_SQL_DATABASE"
          value = var.database_name
        }

        env {
          name  = "AGENCY_CLOUD_SQL_IAM_USER"
          value = var.database_user
        }

        env {
          name  = "AGENCY_ALEMBIC_INI"
          value = "/app/backend/alembic.ini"
        }
      }
    }
  }
}
