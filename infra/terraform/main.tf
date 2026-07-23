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
    name  = "runtime.storage.backend"
    value = var.storage_backend
  }

  set {
    name  = "runtime.storage.postgresql.existingSecret"
    value = var.postgresql_existing_secret
  }

  set {
    name  = "runtime.storage.postgresql.databaseUrlKey"
    value = var.postgresql_database_url_key
  }

  set {
    name  = "runtime.storage.postgresql.poolMinSize"
    value = tostring(var.postgresql_pool_min_size)
  }

  set {
    name  = "runtime.storage.postgresql.poolMaxSize"
    value = tostring(var.postgresql_pool_max_size)
  }

  set {
    name  = "runtime.storage.postgresql.connectTimeoutSeconds"
    value = tostring(var.postgresql_connect_timeout_seconds)
  }

  set {
    name  = "runtime.storage.postgresql.schemaMode"
    value = lower(trimspace(var.postgresql_schema_mode))
  }

  set {
    name  = "observability.prometheusRule.enabled"
    value = tostring(var.prometheus_rule_enabled)
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

  set {
    name  = "runtime.social.existingSecret"
    value = var.social_existing_secret
  }

  set {
    name  = "runtime.social.x.consumerKeyKey"
    value = var.x_consumer_key_secret_key
  }

  set {
    name  = "runtime.social.x.consumerSecretKey"
    value = var.x_consumer_secret_secret_key
  }

  set {
    name  = "runtime.social.x.redirectUri"
    value = var.x_redirect_uri
  }

  set {
    name  = "runtime.social.instagram.appIdKey"
    value = var.instagram_app_id_secret_key
  }

  set {
    name  = "runtime.social.instagram.appSecretKey"
    value = var.instagram_app_secret_secret_key
  }

  set {
    name  = "runtime.social.instagram.redirectUri"
    value = var.instagram_redirect_uri
  }

  lifecycle {
    precondition {
      condition     = var.login_source_max_failures >= var.login_max_failures
      error_message = "login_source_max_failures must be greater than or equal to login_max_failures."
    }

    precondition {
      condition     = var.storage_backend != "sqlite" || var.replica_count == 1
      error_message = "The SQLite backend requires replica_count=1."
    }

    precondition {
      condition     = var.storage_backend != "postgresql" || length(trimspace(var.postgresql_existing_secret)) > 0
      error_message = "postgresql_existing_secret is required for the PostgreSQL backend."
    }

    precondition {
      condition     = var.postgresql_pool_max_size >= var.postgresql_pool_min_size
      error_message = "postgresql_pool_max_size must be greater than or equal to postgresql_pool_min_size."
    }
  }
}
