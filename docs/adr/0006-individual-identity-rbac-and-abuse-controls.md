# ADR 0006: Individual identity, RBAC, key rotation, and durable abuse controls

- Status: accepted
- Date: 2026-07-21
- Amends: ADR 0001 and ADR 0003

## Context

The first production-readiness slice authenticated a tenant-level API key and issued a tenant-scoped browser session. That boundary prevented caller-selected tenant IDs and protected browser credentials, but every credential effectively had administrator access. Audit actors were credential fingerprints rather than individual subjects, key deactivation did not invalidate derived sessions, and failed authentication attempts had no durable control.

A public or multi-operator pilot requires least privilege, accountable actors, controlled key rotation, and abuse resistance. The current single-node SQLite architecture can enforce these controls locally without claiming SSO, MFA, or an external identity provider.

## Decision

1. Configure individual credentials through `AGENCY_IDENTITY_CREDENTIALS_JSON` with `tenant_id`, `subject_id`, `role`, `key_id`, `api_key`, `active`, and an optional exact-allowlisted `entitlements` array.
2. Support four fixed roles:
   - `viewer`: identity, run, and audit read;
   - `operator`: viewer plus run creation;
   - `approver`: viewer plus Greenlight decisions;
   - `admin`: all current permissions.
3. Derive tenant, subject, role, key ID, and permissions only from server-side credential configuration or a server-issued session.
4. Persist subject, role, key ID, and credential fingerprint with each browser session. Re-resolve the active credential on every session-authenticated request. Accept the historical 16-character fingerprint only for migrated sessions; issue full SHA-256 fingerprints for new sessions.
5. Permit multiple active key IDs for one subject during rotation. Deactivating/removing a key invalidates its bearer credential and every session derived from it after redeploy/restart.
6. Retain `AGENCY_TENANT_API_KEYS_JSON` only as a migration path that maps each legacy tenant key to an administrator identity. The Helm production chart requires individual identity and can omit the legacy Secret key.
7. Store only SHA-256-derived credential, session, CSRF, source, and rate-limit bucket values. Never persist raw authentication material.
8. Enforce durable rolling-window limits separately:
   - a strict threshold per credential fingerprint;
   - a higher threshold per network source to detect password spray without allowing a few invalid keys to block a valid credential behind the same ingress.
9. Return `429` with `Retry-After` when a bucket is limited, and expose only aggregate authentication outcomes in Prometheus.
10. Trust forwarded source addresses only from `FORWARDED_ALLOW_IPS`, passed explicitly to Uvicorn. The production chart defaults to loopback and requires operators to list known proxies.
11. Record audit actors as `api-key:<subject_id>` or `browser-session:<subject_id>` instead of exposing a credential fingerprint.
12. Fail Helm rendering when individual identity is absent or when rate-limit bounds are invalid. Mirror the same settings and ordering precondition in Terraform.
13. Treat `theme:premium` as the only current product entitlement. It is server-owned, consistent across simultaneously active keys for one subject, returned by identity/session responses, revalidated on session-authenticated requests, absent from persisted session rows and audit payloads, and independent from RBAC permissions.

## Consequences

### Positive

- Run creation and Greenlight decisions are separated by role.
- Audit events identify an accountable configured subject without exposing raw keys.
- Key rotation supports overlap and deterministic revocation of old bearer/session access.
- Failed attempts survive process restart and do not store credential or source plaintext.
- Password-spray control is distinct from credential lockout, reducing shared-ingress denial-of-service risk.
- Browser and machine clients use the same permission model.
- Product entitlements can be revoked through the same active-identity revalidation without granting operational permissions.
- Helm and Terraform encode the production identity and proxy-trust contract.

### Trade-offs

- Identity remains application-managed static configuration. SSO, MFA, SCIM/lifecycle provisioning, recovery, device posture, IdP token validation, checkout and billing are not implemented.
- `theme:premium` controls the supported UI path but is not DRM; frontend assets and CSS remain inspectable.
- Configuration changes require a Secret update and workload restart/redeploy.
- SQLite rate limiting is correct only for the current single-writer deployment. Horizontal replicas require a shared atomic limiter.
- `subject_id` appears in tenant-scoped audit events. Deployments with stricter privacy requirements should use opaque pseudonymous subjects and maintain the directory mapping elsewhere.
- All four roles currently receive `audit:read`; deployments may need a narrower policy.
- Source-based controls depend on correct trusted-proxy configuration and complement rather than replace ingress/WAF controls.

## Rejected alternatives

- Continue tenant-wide administrator keys: rejected because it prevents least privilege and accountable audit actors.
- Use client-provided roles or subject headers: rejected because callers could escalate privileges.
- Apply the same low threshold to both credential and source buckets: rejected because a few invalid credentials could block valid users sharing one proxy.
- Trust all forwarded headers: rejected because clients could spoof source addresses unless a trusted edge strips them.
- Claim external identity readiness without an IdP: rejected because the repository has no verified SSO, MFA, recovery, or lifecycle integration.
