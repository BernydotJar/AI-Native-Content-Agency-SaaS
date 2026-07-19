variable "project_id" {
  type     = string
  nullable = false
}

variable "location" {
  type     = string
  nullable = false
}

variable "repository_id" {
  type    = string
  default = "agency-images"
}

variable "labels" {
  type    = map(string)
  default = {}
}
