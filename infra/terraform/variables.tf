variable "kubeconfig_path" {
  description = "Path to the kubeconfig used for the target cluster."
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace for the application."
  type        = string
  default     = "ai-native-content-agency"
}

variable "image_repository" {
  description = "Container image repository."
  type        = string
  default     = "ai-native-content-agency"
}

variable "image_tag" {
  description = "Immutable image tag."
  type        = string
  default     = "local"
}
