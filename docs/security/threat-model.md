# Threat Model — Selected `agency_runtime` Architecture

Status: authoritative for PR #3 selected runtime
Model date: 2026-07-21
Runtime version: `0.7.0`
Review scope: React production console, FastAPI, individual identity/RBAC, SQLite/PostgreSQL persistence, deterministic eight-agent orchestration, Greenlight, audit, metrics, backup/restore and OCI/Helm/Terraform packaging
Release disposition: `DENY_RELEASE` until the open HIGH items in this document and the global program are closed or externally blocked with exact evidence

## 1. Security objective

Protect tenant campaign data and operational authority while allowing a small content-agency team to create, review and approve a deterministic campaign package. The product must never infer authority to publish, navigate external sites, generate real media, create infrastructure or spend money from a Greenlight or a successful technical gate.

The selected runtime is `backend/agency_runtime`. The separate `control_plane` implementation on PR #2 is not part of this model unless a control is explicitly ported and reverified on this branch.

## 2. Scope and non-scope

### In scope

- same-origin React/FastAPI console;
- bearer credentials and browser sessions;
- roles `viewer`, `operator`, `approver`, `admin`;
- server-derived tenant binding;
- SQLite and PostgreSQL stores;
- runs, artifact evidence, Greenlight, sessions, rate limits, memories and audit events;
- structured HTTP logs and Prometheus metrics;
- local backup/restore tooling;
- image, Helm and Terraform artifacts;
- deterministic sandbox tool adapters.

### Explicitly out of scope and disabled

- real platform publication;
- browser automation, including `browser-use` or `video-use`;
- external research/provider calls;
- real image/video generation;
- advertising, billing or spend;
- external infrastructure creation;
- managed identity, SSO, MFA and account recovery;
- production cloud/staging runtime.

Any future effectful adapter creates a new trust boundary and requires its own versioned threat-model increment before activation.

## 3. Assets

| Asset | Security property | Consequence of compromise |
|---|---|---|
| API keys, session and CSRF tokens | confidentiality, integrity, revocability | account/tenant impersonation |
| Tenant and subject binding | integrity | cross-tenant access or privilege escalation |
| Campaign briefs, artifacts and memories | confidentiality, integrity, provenance | political/client disclosure, manipulated strategy or unsupported claims |
| Greenlight decision, fencing token and exact artifact hashes | integrity, freshness, non-replay | unreviewed or revoked package treated as approved |
| Audit ledger and request correlation | integrity, availability, tenant isolation | repudiation, false evidence or incident blindness |
| Rate-limit state | integrity, availability | brute-force bypass or credential denial of service |
| SQLite/PostgreSQL data and backups | confidentiality, integrity, recoverability | broad tenant disclosure or unrecoverable loss |
| Runtime/configuration/secrets | confidentiality, integrity | service takeover or unsafe effects |
| OCI image, dependencies and manifests | integrity, provenance | supply-chain execution compromise |
| Human release/deployment authority | explicitness, separation | unauthorized merge, deployment, spend or publication |

## 4. Actors and assumed capabilities

- **Anonymous network attacker:** can submit malformed, oversized and repeated requests and guess credentials/resources.
- **Authenticated low-privilege tenant user:** can exercise permitted reads and intentionally trigger denied mutations at high frequency.
- **Malicious or compromised tenant administrator:** has broad authority inside one tenant but must not cross tenant boundaries or alter platform controls.
- **Operator/reviewer:** can configure credentials and deployment; mistakes or compromised access can affect multiple tenants.
- **Dependency/build attacker:** attempts to alter packages, actions, base images or generated evidence.
- **Future external provider:** may return malicious content, prompt injection, inconsistent receipts or replayed callbacks.
- **Infrastructure/database attacker:** may observe traffic/storage or exploit an overprivileged runtime role.

No trust is assigned merely because traffic originates from the browser, a private network, a proxy header, an agent output or a successful CI job.

## 5. Trust boundaries

```text
[Browser or machine client]
        |
        | TLS required outside local development
        | bearer OR HttpOnly session + CSRF for mutation
        v
[FastAPI boundary]
  request-size limit -> authentication -> server tenant/role binding
  -> authorization -> validation -> RuntimeService
        |
        +--> [structured logs / bounded metrics]
        |
        +--> [SQLite single-replica OR PostgreSQL shared state]
        |       runs, sessions, rate limits, audit, memories
        |
        +--> [deterministic orchestrator + sandbox adapters]
        |
        +--> [checksummed local backup artifacts]

[Repository/build boundary]
  lockfiles -> tests -> OCI -> Helm/Terraform -> supply-chain evidence

[Human authority boundary]
  merge / release / persistent restore / external infrastructure /
  credentials / publication / spend / legal decisions
```

### Boundary rules

1. Client-supplied tenant, subject, role or key ID is never authoritative.
2. Forwarded source addresses are trusted only from configured proxy networks.
3. PostgreSQL/SQLite records are addressed with tenant-leading predicates or composite keys.
4. Greenlight applies only to the stored exact artifact IDs/hashes, current fencing token, channels and budget; it is not publication authority.
5. Sandbox adapters cannot create an external effect.
6. Backup manifests establish byte integrity relative to a trusted manifest, not authenticity or encryption.
7. CI/manifests prove only their tested scope; they do not prove a running workload or production control.

## 6. Principal data flows

### F1 — Bearer authentication

1. Client sends a configured API key in `Authorization: Bearer`.
2. Source and credential fingerprints are checked against durable rate-limit buckets.
3. `TenantAuthenticator` compares a digest in constant time and derives tenant, subject, role and key ID from server configuration.
4. Raw credentials are never stored in application tables, audit, logs or metrics.

### F2 — Browser session

1. Client exchanges an API key once at `/api/v1/sessions`.
2. Server returns a session cookie marked HttpOnly/SameSite and a separate CSRF token.
3. Only token hashes and a credential fingerprint are stored.
4. Mutations require the current session plus constant-time CSRF verification.
5. Credential deactivation, role changes, expiry or explicit revocation invalidate subsequent use.

### F3 — Run creation and agent orchestration

1. Request body is bounded globally and by field/list validators.
2. `runs:create` is authorized server-side and requires a bounded idempotency key.
3. The key is digested; operation/resource/payload/authenticated subject form the request fingerprint.
4. The deterministic orchestrator produces local evidence and artifact hashes once per concurrent command.
5. Run, replay snapshot and `run.created` receipt commit transactionally in one tenant scope.

### F4 — Greenlight

1. Approver/admin obtains a tenant-scoped run and submits a bounded idempotency key.
2. The authenticated subject, not client reviewer text, is persisted as decision authority.
3. One approve/reject/revoke mutation, replay snapshot and audit receipt commit transactionally.
4. Compatible replay returns the original document; incompatible key reuse returns uniform 409.
5. Approval starts fencing token `1`; revocation increments it and preserves evidence.
6. A future adapter must verify active status, Greenlight ID, current token, artifact IDs/hashes, channel and budget. No effectful adapter is enabled.

### F5 — Denial and incident evidence

- Authenticated RBAC and CSRF denials are appended to that principal's tenant audit ledger with request ID, actor, bounded reason/auth method/role and no credential/body/raw IP.
- Anonymous authentication failures are not attributed to an unproven tenant. They are represented by one-way rate buckets, bounded metrics and sanitized route logs.
- Public errors expose only a stable code, safe detail and request ID.

### F6 — Backup/restore

- SQLite online backup or PostgreSQL custom-format dump creates a private checksummed artifact and strict manifest.
- Restore verifies manifest/size/checksum/integrity and refuses unsafe targets.
- Production scheduling, encryption, immutable off-host storage and destructive restore remain deployment/human gates.

## 7. STRIDE analysis

| ID | Category | Threat / abuse case | Implemented controls and evidence | Residual risk / required action | Status |
|---|---|---|---|---|---|
| T-001 | Spoofing | Guess or reuse an API key. | Digest comparison, minimum key constraints, per-credential and trusted-source durable rate buckets, no raw key storage; identity/rate tests. | No managed IdP, MFA, recovery or automated lifecycle; edge/global DDoS controls depend on deployment. | MEDIUM open |
| T-002 | Spoofing | Steal/replay a browser session or CSRF token. | HttpOnly/SameSite cookie, Secure default, hashed tokens, expiry, credential fingerprint, constant-time CSRF, revocation and cross-instance tests. | No device binding/MFA; XSS defense also depends on reviewed CSP and frontend hygiene. | MEDIUM open |
| T-003 | Spoofing | Forge client IP via forwarding headers to evade limits. | Forwarded headers accepted only from configured trusted proxy networks; direct source otherwise. | Deployment must keep trusted CIDRs exact and prevent direct backend bypass. | Controlled / deployment gate |
| T-004 | Tampering | Supply client tenant/role/key ID or access guessed foreign run. | Principal derives only from server configuration/session; composite tenant keys and tenant-leading SQL; foreign/missing response is uniform; negative tests. | PostgreSQL Row Level Security is not implemented; application predicates remain the primary tenant boundary. | HIGH open |
| T-005 | Tampering | Alter reviewed artifacts, replay a command or use stale approval after Greenlight. | Durable tenant/operation-scoped receipts, exact compatible replay, uniform conflicts, authenticated decision identity, artifact hashes, revocation and fencing-token guard; SQLite/PostgreSQL concurrency tests. | External providers still require their own outbox, provider idempotency token and receipt before activation. | Controlled for current sandbox |
| T-006 | Tampering | Modify audit evidence. | Append-only application interface and transactional writes; tenant-scoped pagination; backup checksums. | Database owner/operator can alter rows; no hash chain, signature or immutable export. | HIGH open for production |
| T-007 | Tampering | Alter backup or restore into active/non-empty target. | Strict manifest, size/SHA-256, integrity/archive validation, atomic SQLite replacement, sidecar guard, empty PostgreSQL target and transactional restore; drills. | Manifest is not signed; external encryption/immutability/scheduling absent. | MEDIUM open |
| T-008 | Repudiation | Deny a mutation, approval or security denial. | Request IDs, actor/action/resource/payload audit; mutations and authenticated RBAC/CSRF denials durable across restart/replica. | Anonymous failures cannot be tenant-attributed; audit is not independently immutable or time-attested. | MEDIUM open |
| T-009 | Information disclosure | Enumerate session state, roles, permissions, run IDs or conflict state from errors. | Uniform `public-error.v1`, validation redaction, no-store/security headers, internal exception sanitization; SQLite/PostgreSQL/frontend tests. | Timing equalization is not formally measured; database/network side channels remain deployment concerns. | Controlled, monitor |
| T-010 | Information disclosure | Leak credentials/content through logs or metrics. | Route-template JSON logs omit query/body/token; metrics have bounded labels without tenant/identity/content; error log records exception type only; tests. | Reverse proxy, platform and database logs are outside application proof. | Controlled / deployment gate |
| T-011 | Information disclosure | Expose confidential database/backups. | Token hashes, URL/password kept out of argv/output, private backup modes, `.pgpass` disabled in tool. | Storage encryption, KMS, least-privilege backup role and off-host policy are not implemented in repository. | HIGH open for production |
| T-012 | Denial of service | Oversized or streamed JSON exhausts memory. | ASGI pre-dispatch body cap, 1 MiB default/configurable 1 KiB–10 MiB; chunked and declared-length tests; bounded fields/lists. | Large response generation and CPU-heavy future provider calls need separate budgets/timeouts. | Controlled for current API |
| T-013 | Denial of service | Brute-force credentials or spray many keys. | Atomic durable per-source/per-credential buckets in SQLite/PostgreSQL, retry header and bounded metrics; concurrency tests. | Valid principals can flood reads/denials/audit because no general authenticated request quota exists. | MEDIUM open (operations/rate policy) |
| T-014 | Denial of service | Exhaust PostgreSQL pool or hold transactions across external calls. | Bounded pool, deterministic local tools, no external calls inside transactions, readiness checks. | Capacity/soak/failover not measured; current deployment evidence has no running scheduler workload. | HIGH open for staging |
| T-015 | Elevation of privilege | Viewer/operator performs approval/admin action. | Explicit permission matrix enforced in dependencies; denials audited; role/session change tests. | Static configuration changes are operator-controlled and not independently approved. | Controlled / config governance |
| T-016 | Elevation of privilege | Compromise overprivileged PostgreSQL runtime account. | Exact-head CI and local verifier prove explicit initialize/validate separation, non-superuser/non-owner runtime, exact DML grants and DDL/TEMP/TRUNCATE/schema-metadata/role-escalation denial. | No persistent staging/production role has been observed; tracked by the environment gate. | Controlled in code/delivery; staging gate |
| T-017 | Elevation / supply chain | Malicious package/action/base image executes in build/runtime. | Hash locks, SHA/digest pins, SBOM, vulnerability/license policy, provenance, offline Cosign verification, non-root image. | Five expiring HIGH exceptions require remediation by 2026-08-21; external registry/publisher controls untested. | MEDIUM open |
| T-018 | Prompt/content injection | Campaign, page, media or transcript content instructs agents/tools to bypass policy or publish. | Deterministic local adapters, no provider/browser/publisher effect, explicit Greenlight boundary, exact `video-use` review manifest and no execution route. | Semantic prompt-injection and groundedness eval harness is incomplete; any future browser/video adapter is HIGH risk until isolated. | HIGH open before integrations |
| T-019 | Human authority | Technical success is mistaken for merge/deploy/publication authorization. | Program state explicitly separates committed/pushed/CI/deployed/observed; `DENY_RELEASE`/`DENY_APPLY`; no automatic merge/deploy. | Human process can still override; accountable release reviewer required. | Human gate |

## 8. Security controls verified in INC-003

- all public API failures include stable code, safe detail and request ID;
- all authentication-state variants return the same 401 contract;
- authorization responses omit role/permission/internal text;
- foreign and missing resources return the same 404 body;
- state conflicts return a generic 409;
- validation errors expose only bounded field location and error type, never submitted input/context;
- internal exceptions expose no exception message/content;
- authenticated RBAC/CSRF denials are durable and tenant-scoped in SQLite and PostgreSQL;
- denial metrics accept only `authorization` and `csrf` labels;
- API/operations responses add no-store, no-sniff, frame, referrer, permissions and same-origin resource headers;
- declared and chunked request bodies are bounded before authentication/application dispatch.

The exact commands and results are recorded in `program/reports/inc-003-review.md` once the increment is finalized.

## 9. Open HIGH findings and release gates

The following prevent a production-ready declaration:

1. PostgreSQL tenant isolation depends on application predicates; no RLS defense-in-depth is implemented.
2. Audit is not tamper-evident or immutably exported.
3. Database/backup encryption and production recovery controls are not demonstrated.
4. Runtime and migration database authority are not separated into a verified non-owner runtime role.
5. Durable API idempotency, Greenlight revocation/fencing and external-effect receipts are missing.
6. No authorized staging workload, capacity/soak/failover or incident evidence exists.
7. Semantic prompt-injection/adversarial evals remain incomplete.

## 10. Required security review for future integrations


The exact `browser-use/video-use` commit
`92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` has now been reviewed but not
adopted. The packaged manifest records open HIGH path-containment, external media
upload and missing product authority/receipt findings. Read-only API visibility
does not change the trust boundary or authorize execution.

Before activating `browser-use/video-use`, a publisher, model or media provider, require:

- fixed version/commit, license and dependency review;
- isolated process/container and minimal filesystem/network scope;
- untrusted-page/content classification and prompt-injection controls;
- explicit allowlist of domains/actions;
- bounded input/output/timeout/retries and cancellation;
- provider credentials stored server-side and revocable;
- durable idempotency/fencing, exact approval binding and human confirmation;
- immutable provider receipt and audit correlation;
- no hidden telemetry or data training use without privacy review;
- sandbox and red-team evidence;
- explicit external-effect and spend authorization.

## 11. Review cadence and ownership

Re-run this model when any trust boundary, identity provider, persistence role/schema, tenant model, external adapter, deployment target, retention rule or legal jurisdiction changes. CRITICAL/HIGH findings require closure or a demonstrated external blocker before release. The final release reviewer must be distinct and accountable; this document is not production approval.
