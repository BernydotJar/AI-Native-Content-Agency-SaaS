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
    name  = "runtime.auth.identityCredentialsKey"
    value = var.runtime_auth_identity_credentials_key
  }

  set {
    name  = "runtime.auth.loginMaxFailures"
    value = tostring(var.login_max_failures)
  }

  set {
    name  = "runtime.auth.loginSourceMaxFailures"
    value = tostring(var.login_source_max_failures)
  }

  set {
    name  = "runtime.auth.loginWindowSeconds"
    value = tostring(var.login_window_seconds)
  }

  set {
    name  = "runtime.proxy.forwardedAllowIps"
    value = var.forwarded_allow_ips
  }

  set {
    name  = "runtime.session.cookieSecure"
    value = tostring(var.session_cookie_secure)
  }

  lifecycle {
    precondition {
      condition     = var.login_source_max_failures >= var.login_max_failures
      error_message = "login_source_max_failures must be greater than or equal to login_max_failures."
    }
  }
}
