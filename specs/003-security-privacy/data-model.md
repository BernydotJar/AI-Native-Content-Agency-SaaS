# Security and Privacy Data Model

## Public error

```json
{
  "code": "authorization_denied",
  "detail": "request not permitted",
  "request_id": "request-security-0001"
}
```

Validation errors additionally contain:

```json
{
  "errors": [
    {"location": ["body", "objective"], "type": "string_too_long"}
  ]
}
```

No `input`, context object, internal exception string, role, permission, session state or requested resource identifier is included.

## Security denial audit event

- `tenant_id`: authenticated server-side principal tenant
- `request_id`: validated/generate correlation ID
- `action`: `authorization.denied` or `request.verification_denied`
- `resource_type`: `permission` or `request`
- `resource_id`: bounded internal permission name or `mutation`
- `actor`: existing `api-key:<subject>` / `browser-session:<subject>` convention
- `payload`: bounded `{reason, auth_method, role}` for tenant audit only

Never include API key, cookie, CSRF token, request body, campaign content, raw source IP, credential fingerprint or database URL.

## Data classes

- **Restricted:** API keys, session/CSRF tokens, database URLs, backup credentials.
- **Confidential client:** briefs, artifacts, memories, Greenlight notes/reviewer, campaign strategy.
- **Confidential identity:** tenant ID, subject ID, role/key ID, audit actor, session metadata.
- **Operational sensitive:** request IDs, audit events, rate-limit hashes, logs, metrics, backups.
- **Public/product:** runtime version, sandbox capability flags, documented API schema without tenant data.
