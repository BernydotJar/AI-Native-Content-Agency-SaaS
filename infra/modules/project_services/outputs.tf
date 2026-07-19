output "enabled_services" {
  description = "Service names managed by this module."
  value       = sort(tolist(var.services))
}
