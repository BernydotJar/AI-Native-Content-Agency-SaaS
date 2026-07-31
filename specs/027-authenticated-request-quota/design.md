# INC-027 Design — Durable Authenticated Request Quota

## Decision

Use a durable fixed-window counter with one row per opaque bucket. Each authenticated request atomically checks and increments a principal bucket and a tenant bucket. The dependency executes inside `require_principal`, after successful authentication/session resolution and before CSRF or permission checks.

## Bucket derivation

- principal bucket: SHA-256 of a domain-separated canonical tuple containing tenant ID and subject ID;
- tenant bucket: SHA-256 of a domain-separated canonical tuple containing tenant ID.

Authentication method, key ID and session ID are intentionally excluded so switching between bearer and browser session cannot bypass the principal quota. Only the digest is persisted.

## Storage

SQLite adds `authenticated_request_rate_limits(bucket_hash PRIMARY KEY, window_started_at, request_count)`.

PostgreSQL adds the same table in schema v8. The transaction obtains advisory locks in sorted bucket order, reads rows `FOR UPDATE`, rejects without increment if any active bucket is at its cap, and otherwise inserts/resets/increments every bucket. This prevents partial consumption and cross-replica races.

## API behavior

`require_principal` resolves the principal, stores bounded identity metadata in request state, then consumes both quota buckets. A rejection raises a safe `request_rate_limited` 429 with `Retry-After`. It does not call the security-denial audit path. Successful consumption increments a low-cardinality metric.

## Configuration

- `AGENCY_AUTHENTICATED_REQUEST_MAX_PER_PRINCIPAL` default 600;
- `AGENCY_AUTHENTICATED_REQUEST_MAX_PER_TENANT` default 6000;
- `AGENCY_AUTHENTICATED_REQUEST_WINDOW_SECONDS` default 60.

Bounds: principal 10–100000, tenant 10–1000000, window 1–3600 seconds, tenant >= principal.

## Alternatives rejected

- In-memory limiter: bypassed by restart and replicas.
- Per-denial limiter: still permits unbounded successful/read traffic and duplicates authorization policy.
- Append-only request rows: recreates the storage-amplification problem.
- Token bucket: finer smoothing but more state/math and no current product need; fixed windows are deterministic and auditable.

## Risks and mitigations

- Legitimate bursts: high defaults, tenant headroom and `Retry-After`.
- Identity bypass: principal bucket ignores auth method/session/key ID.
- Tenant noisy neighbor: aggregate tenant bucket.
- Storage growth: one row per active bucket and expired-row cleanup.
- Audit ambiguity: quota rejections are metric/HTTP evidence, not durable denial events, explicitly preventing recursive amplification.
