resource "google_sql_database_instance" "app" {
  count = var.enable_cloud_sql ? 1 : 0

  project             = var.project_id
  name                = var.cloud_sql_instance_name
  region              = var.region
  database_version    = "POSTGRES_15"
  deletion_protection = var.cloud_sql_deletion_protection

  settings {
    tier                  = var.cloud_sql_tier
    edition               = "ENTERPRISE"
    availability_type     = "ZONAL"
    activation_policy     = "ALWAYS"
    connector_enforcement = "REQUIRED"

    disk_type             = "PD_SSD"
    disk_size             = var.cloud_sql_disk_size_gb
    disk_autoresize       = true
    disk_autoresize_limit = var.cloud_sql_disk_autoresize_limit_gb

    retain_backups_on_delete = false
    user_labels              = local.labels

    backup_configuration {
      enabled                        = true
      start_time                     = var.cloud_sql_backup_start_time
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = var.cloud_sql_backup_retention_count
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled                                  = true
      enable_private_path_for_google_cloud_services = false
      ssl_mode                                      = "ENCRYPTED_ONLY"
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "app" {
  count = var.enable_cloud_sql ? 1 : 0

  project   = var.project_id
  name      = var.cloud_sql_database_name
  instance  = google_sql_database_instance.app[0].name
  charset   = "UTF8"
  collation = "en_US.UTF8"
}
