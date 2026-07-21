provider "kubernetes" {
  config_path = pathexpand(var.kubeconfig_path)
}

provider "helm" {
  kubernetes {
    config_path = pathexpand(var.kubeconfig_path)
  }
}

resource "kubernetes_namespace_v1" "app" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = var.namespace
  }
}

resource "helm_release" "app" {
  name      = "ai-native-content-agency"
  namespace = var.namespace
  chart     = "${path.module}/../helm/ai-native-content-agency"
  wait      = var.helm_wait
  timeout   = var.helm_timeout_seconds

  depends_on = [kubernetes_namespace_v1.app]

  set {
    name  = "image.repository"
    value = var.image_repository
  }

  set {
    name  = "image.tag"
    value = var.image_tag
  }

  set {
    name  = "replicaCount"
    value = tostring(var.replica_count)
  }

  set {
    name  = "persistence.enabled"
    value = tostring(var.persistence_enabled)
  }

  set {
    name  = "runtime.auth.existingSecret"
    value = var.runtime_auth_existing_secret
  }

  set {
    name  = "runtime.auth.tenantApiKeysKey"
    value = var.runtime_auth_tenant_api_keys_key
  }

  set {
    name  = "runtime.session.cookieSecure"
    value = tostring(var.session_cookie_secure)
  }
}
