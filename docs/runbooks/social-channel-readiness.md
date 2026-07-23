# X and Instagram channel readiness

This runbook configures **application readiness only**. It does not issue an OAuth redirect,
persist an access token, or publish content. Those mutation paths remain absent until the
encrypted tenant token store and durable publication intent/receipt are implemented.

## Local readiness

Export values in the shell that starts the integrated product. Do not place real values in
Git, `.env` files, screenshots, issue comments, or browser storage.

```bash
export AGENCY_X_CONSUMER_KEY='<from X developer console>'
export AGENCY_X_CONSUMER_SECRET='<from X developer console>'
export AGENCY_X_REDIRECT_URI='http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback'

export AGENCY_INSTAGRAM_APP_ID='<from Meta app dashboard>'
export AGENCY_INSTAGRAM_APP_SECRET='<from Meta app dashboard>'
export AGENCY_INSTAGRAM_REDIRECT_URI='http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback'

npm run start:local
```

The local runner inherits these variables. It does not print their values. After connecting
the workspace, open **Configuración → Canales de publicación**. Each configured channel
must show **Lista para autenticar**. The API response contains only variable names and
boolean readiness state.

The callback paths above are reserved configuration values; the current readiness slice
intentionally exposes no OAuth callback route. Registering them in provider consoles is
useful only after the OAuth implementation lands.

## Kubernetes and Terraform

Create one Secret outside Terraform. Example key names:

```text
x-consumer-key
x-consumer-secret
instagram-app-id
instagram-app-secret
```

Set these non-secret Terraform variables:

```hcl
social_existing_secret  = "ai-native-content-agency-social"
x_redirect_uri          = "https://app.example.com/api/v1/social-channels/x/oauth/callback"
instagram_redirect_uri  = "https://app.example.com/api/v1/social-channels/instagram/oauth/callback"
```

Terraform passes only the Secret name, Secret data-key names, and callback URIs to Helm.
It does not create the Secret or receive its values.

## Expected product behavior

- X shows a text post preview and treats media as optional.
- Instagram shows a caption preview and requires image, reel, or carousel media.
- Both show Copy → Asset → Greenlight → Account → Publication.
- `Publicar` remains disabled while the account is not connected or the durable publisher
  boundary is unavailable.
- Setting app credentials does not authorize a customer account.

## External test gate

A real test later requires:

1. registered callback URLs in X and Meta developer consoles;
2. an X account used for sandbox authorization;
3. an Instagram Professional account (Business or Creator);
4. explicit approval to use the credentials and create external posts;
5. implemented encrypted token storage and publication intent/receipt reconciliation.
