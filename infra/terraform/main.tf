provider "kubernetes" {
  config_path = pathexpand(var.kubeconfig_path)
}

provider "helm" {
  kubernetes {
    config_path = pathexpand(var.kubeconfig_path)
  }
}

resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = var.namespace
  }
}

resource "helm_release" "app" {
  name      = "ai-native-content-agency"
  namespace = kubernetes_namespace_v1.app.metadata[0].name
  chart     = "${path.module}/../helm/ai-native-content-agency"

  set {
    name  = "image.repository"
    value = var.image_repository
  }

  set {
    name  = "image.tag"
    value = var.image_tag
  }
}
