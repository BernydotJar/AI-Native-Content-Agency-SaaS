output "connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "database_name" {
  value = google_sql_database.application.name
}

output "iam_database_user" {
  value = google_sql_user.runtime.name
}

output "instance_name" {
  value = google_sql_database_instance.postgres.name
}
