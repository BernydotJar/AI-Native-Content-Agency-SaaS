# Research

## Observed runtime behavior

- `TenantAuthenticator` binds tenant, subject, role and key ID server-side and uses constant-time digest comparison.
- SQLite and PostgreSQL query runs and audit events with tenant-leading predicates and composite keys.
- Session and CSRF tokens are hashed at rest; browser cookie is HttpOnly/SameSite Strict and Secure by default in production configuration.
- HTTP logs use route templates and omit query/body/credentials. Prometheus metrics have no tenant or identity labels.
- API exceptions currently return raw `AuthenticationError`, `AuthorizationError`, `SessionAuthenticationError`, `SessionCsrfError`, `KeyError`, `ValueError` and `GreenlightError` text.
- Raw responses reveal permission names, role names, session deactivation/revocation state and requested run IDs.
- Pydantic/FastAPI validation responses can contain the submitted `input` value unless sanitized.
- Mutations and session lifecycle are audited; authenticated RBAC/CSRF denials are not.
- Authentication failures cannot safely be assigned to a tenant before proof of credential and are instead represented by durable hashed rate-limit buckets and sanitized metrics/logs.

## Design decision

Keep FastAPI's HTTP status semantics but return a stable application body with safe `code`, `detail` and `request_id`. Validation returns only bounded field locations and error types. Internal causes remain chained for server diagnosis but are not serialized.

Security-denial events are written to the authenticated principal's tenant ledger before returning 403. They contain actor, request ID, bounded action/resource and minimal payload. Failure to persist never permits the requested action.

## Residual risk

A valid low-privilege principal can generate denial events and consume audit storage because the runtime does not yet have a general authenticated request quota. This is bounded operationally only by deployment edge controls and credential revocation and remains a risk for the SLO/rate-limit increment. The ledger is append-only through application interfaces but not cryptographically signed or exported immutably.
