# ADR 0003: Browser session boundary with HttpOnly cookies and CSRF rotation

- Status: accepted
- Date: 2026-07-21

## Context

The React application needed to invoke the authenticated runtime. Embedding a tenant API key in the bundle, local storage, session storage, or long-lived JavaScript state would expose a durable credential to browser extensions, accidental logging, and cross-site scripting. Bearer-only APIs were appropriate for machine clients but not for a production browser surface.

## Decision

1. Exchange the tenant API key once through `POST /api/v1/sessions` over the same origin.
2. Store only SHA-256 hashes of the session token and CSRF token in SQLite.
3. Return the session token exclusively in an `HttpOnly`, `SameSite=Strict`, path-scoped cookie; default `Secure=true`.
4. Return the CSRF token in the JSON response and keep it only in React memory.
5. Require `X-CSRF-Token` for every state-changing request authenticated by cookie.
6. Allow bearer machine clients to continue without CSRF.
7. Restore a valid browser session after reload through `GET /api/v1/sessions/current`, rotating the CSRF token each time.
8. Revoke the session transactionally and append `session.created` / `session.revoked` audit events.
9. Never place the API key, session token, or CSRF token in application logs, metrics, URLs, audit payloads, or browser storage.
10. Serve frontend and API from the same process/origin; no permissive CORS policy is introduced.

## Consequences

### Positive

- The production console uses the real durable runtime without persisting tenant API keys in browser storage.
- Reloads can recover the HttpOnly session and receive a rotated CSRF token.
- Session revocation survives process restart.
- Existing machine-to-machine bearer clients remain compatible.

### Trade-offs

- The one-time key exchange still requires TLS and should later be replaced by a managed user identity flow.
- Tenant API keys represent a tenant, not an individual person; reviewer identity remains supplied by the operator.
- There is no login rate limiter, account lockout, MFA, or external identity provider yet.
- `SameSite=Strict` assumes the SPA and API remain same-origin.
