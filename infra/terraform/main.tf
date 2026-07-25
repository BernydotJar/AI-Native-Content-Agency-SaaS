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
    name  = "runtime.model.executionEnabled"
    value = tostring(var.model_execution_enabled)
  }

  set {
    name  = "runtime.model.effectAuthorityEnabled"
    value = tostring(var.model_effect_authority_enabled)
  }

  set {
    name  = "runtime.model.selectedProvider"
    value = lower(trimspace(var.model_provider))
  }

  set {
    name  = "runtime.model.egressAllowedHosts"
    value = var.model_egress_allowed_hosts
  }

  set {
    name  = "runtime.model.maxOutputTokens"
    value = tostring(var.model_max_output_tokens)
  }

  set {
    name  = "runtime.model.existingSecret"
    value = var.model_existing_secret
  }

  set {
    name  = "runtime.model.apiKeyKeys.openai"
    value = var.model_api_key_secret_keys.openai
  }

  set {
    name  = "runtime.model.apiKeyKeys.anthropic"
    value = var.model_api_key_secret_keys.anthropic
  }

  set {
    name  = "runtime.model.apiKeyKeys.deepseek"
    value = var.model_api_key_secret_keys.deepseek
  }

  set {
    name  = "runtime.model.apiKeyKeys.moonshot"
    value = var.model_api_key_secret_keys.moonshot
  }

  set {
    name  = "runtime.model.apiKeyKeys.llama"
    value = var.model_api_key_secret_keys.llama
  }

  set {
    name  = "runtime.model.models.openai"
    value = var.model_names.openai
  }

  set {
    name  = "runtime.model.models.anthropic"
    value = var.model_names.anthropic
  }

  set {
    name  = "runtime.model.models.deepseek"
    value = var.model_names.deepseek
  }

  set {
    name  = "runtime.model.models.moonshot"
    value = var.model_names.moonshot
  }

  set {
    name  = "runtime.model.models.llama"
    value = var.model_names.llama
  }

  set {
    name  = "runtime.social.politicalContentEnabled"
    value = tostring(var.political_content_enabled)
  }

  set {
    name  = "runtime.social.publicationEnabled"
    value = tostring(var.social_publication_enabled)
  }

  set {
    name  = "runtime.social.politicalPublicationEnabled"
    value = tostring(var.political_publication_enabled)
  }

  set {
    name  = "runtime.social.politicalPaidMediaEnabled"
    value = tostring(var.political_paid_media_enabled)
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

  set {
    name  = "runtime.social.encryptionKeysJsonKey"
    value = var.social_oauth_secret_keys.encryption_keys_json
  }

  set {
    name  = "runtime.social.activeEncryptionKeyIdKey"
    value = var.social_oauth_secret_keys.active_encryption_key_id
  }

  set {
    name  = "runtime.social.x.userAccessTokenKey"
    value = var.social_oauth_secret_keys.x_user_access_token
  }

  set {
    name  = "runtime.social.x.userAccessTokenSecretKey"
    value = var.social_oauth_secret_keys.x_user_access_token_secret
  }

  set {
    name  = "runtime.social.x.accountIdKey"
    value = var.social_oauth_secret_keys.x_account_id
  }

  set {
    name  = "runtime.social.x.accountUsernameKey"
    value = var.social_oauth_secret_keys.x_account_username
  }

  set {
    name  = "runtime.social.instagram.accessTokenKey"
    value = var.social_oauth_secret_keys.instagram_access_token
  }

  set {
    name  = "runtime.social.instagram.accountIdKey"
    value = var.social_oauth_secret_keys.instagram_account_id
  }

  set {
    name  = "runtime.social.instagram.accountUsernameKey"
    value = var.social_oauth_secret_keys.instagram_account_username
  }

  set {
    name  = "runtime.social.instagram.tokenExpiresAtKey"
    value = var.social_oauth_secret_keys.instagram_token_expires_at
  }

  set {
    name  = "runtime.social.bootstrapTenantId"
    value = var.social_bootstrap_tenant_id
  }

  lifecycle {
    precondition {
      condition     = var.login_source_max_failures >= var.login_max_failures
      error_message = "login_source_max_failures must be greater than or equal to login_max_failures."
    }

    precondition {
      condition     = !var.model_effect_authority_enabled || var.model_execution_enabled
      error_message = "model_effect_authority_enabled requires model_execution_enabled."
    }

    precondition {
      condition = !var.model_execution_enabled || (
        length(trimspace(var.model_existing_secret)) > 0 &&
        length(trimspace(var.model_provider)) > 0 &&
        length(trimspace(var.model_egress_allowed_hosts)) > 0
      )
      error_message = "enabled model execution requires model_existing_secret, model_provider and model_egress_allowed_hosts."
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
