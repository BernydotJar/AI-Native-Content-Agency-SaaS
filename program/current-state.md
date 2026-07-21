# Current Operational State

Updated: 2026-07-21
Program phase: active
Release recommendation: DENY_RELEASE
Cloud recommendation: DENY_APPLY

## Repository and delivery truth

- Root: `/workspace`
- Branch: `agent/production-readiness`
- Current committed HEAD: `e2d3e3c9d5a255fb55289d5b5bfd0786ec609df4`
- Remote branch HEAD: `e2d3e3c9d5a255fb55289d5b5bfd0786ec609df4`
- Upstream: not configured
- Draft PR: `#3`, open against `main`
- Exact-commit CI run: `29854004152`
- Exact-commit CI result: eight of eight jobs successful
- Merge: not authorized and not performed
- Production/external infrastructure: not authorized and not performed

The working tree currently contains the uncommitted INC-003 security/privacy slice described below. Local working-tree gates are not remote CI evidence until committed and pushed.

## Parallel implementation

PR `#2` (`feat/production-foundation-v1`) remains open and unmerged. It contains an alternate SQLAlchemy/Alembic control plane and a static GCP/Cloud Run path. It is a donor branch, not automatically compatible evidence for PR #3.

The selected architecture remains `backend/agency_runtime`. Closing, merging or superseding either PR remains a human architecture decision.

## Completed and remotely verified increments

### INC-001 — Trustworthy baseline and version contract

- Operational `program/` state, 12-workstream ledger, DAG, risk/finding/evidence registers and executable completion-audit validation.
- Version `0.7.0` aligned across npm, Python, FastAPI, health/readiness, metrics, OCI and Helm.
- README and implementation audit reconciled with the selected runtime and actual cloud/deployment evidence boundary.
- `DENY_APPLY` recorded: no GCP target, reviewed plan/apply, endpoint or runtime observation exists.

### INC-002 — SQLite/PostgreSQL backup and restore

- Strict `agency-runtime-backup.v1` manifests, size/SHA-256/integrity validation and private files.
- SQLite online backup, atomic restore, explicit replace and sidecar guard.
- Controlled PostgreSQL custom dump, empty-target transactional restore and ambient libpq credential/configuration rejection.
- Representative runs, audit, sessions, rate-limit state and memories survive both restore paths and remain application-readable.

Commit `e2d3e3c9d5a255fb55289d5b5bfd0786ec609df4` is pushed and exact-commit CI passed all eight jobs:

- `workflow-lint`
- `verify`
- `python-locks`
- `postgresql-shared-state`
- `container`
- `helm`
- `terraform`
- `supply-chain`

## Active review increment

### INC-003 — Security, privacy and uniform denial evidence

Status: `review`

Implemented in the current working tree:

- stable `public-error.v1` bodies with safe code/detail/request ID;
- one non-enumerating 401 contract for missing, invalid, expired, revoked and credential-deactivated authentication states;
- authorization, missing/foreign resource and state-conflict responses that omit role, permission, resource ID and internal state;
- validation responses that omit submitted values/context and expose only bounded locations/types;
- safe internal-error handling that logs request ID and exception type without exception message/content;
- transactional tenant-scoped `authorization.denied` and `request.verification_denied` events in SQLite/PostgreSQL;
- bounded `authorization|csrf` denial metrics with no tenant, identity, permission or content labels;
- no-store/no-cache, no-sniff, frame, referrer, permissions and same-origin resource headers;
- pre-dispatch request body limit, one MiB default and one KiB–ten MiB allowed range, including streamed/chunked and ambiguous-framing tests;
- Helm configuration for the same request-body limit;
- selected-runtime threat model, privacy model and data-classification/retention decision register.

Local working-tree verification already observed after critic repairs:

- locked wheel/backend: 78 tests pass with eight expected PostgreSQL-only skips;
- PostgreSQL shared-state/recovery: 78 of 78 pass, including cross-instance denial evidence, migration/replay and both restore drills;
- frontend: lint passes, 33 of 33 tests pass and production build passes;
- Helm schema/lint/render/safety guards pass;
- patch whitespace passes.

Detailed review: [`program/reports/inc-003-review.md`](reports/inc-003-review.md).

## Findings repaired by INC-003

- authentication/session state leaked through 401 detail;
- role and permission leaked through authorization detail;
- requested foreign/missing IDs and current conflict state leaked through 404/409 detail;
- validation could reflect API keys or campaign text;
- internal exception content could reach a client/diagnostic;
- authenticated RBAC/CSRF denials lacked durable tenant evidence;
- denial metrics had no enforced bounded-label contract;
- declared or streamed bodies lacked a global pre-dispatch byte limit;
- selected runtime lacked authoritative threat/privacy/data-classification models.

No CRITICAL or HIGH implementation finding remains open inside the bounded public-error/denial/body-limit code after repair.

## Open global HIGH release findings

1. **Durable command idempotency and Greenlight revocation/fencing** — identical retries cannot yet replay a committed response and a future external effect lacks a post-approval revocation boundary. Owner: `INC-004`.
2. **Authorized staging/workload evidence** — no selected cloud target, scheduler workload, endpoint, capacity/soak/failover or runtime observation exists. Owner: `INC-006`; cloud portion externally/human blocked.
3. **Manual accessibility evidence** — keyboard, screen reader, measured contrast, zoom/reflow and reduced-motion review is absent. Owner: `INC-008`.
4. **Production backup controls** — scheduling, encryption/KMS, immutable/off-host storage, retention and alerting are absent despite passing local restores. Owner: `INC-005`.
5. **PostgreSQL runtime authority** — schema migration/bootstrap and runtime authority are not separated and a non-owner least-privilege runtime role is not demonstrated. Owner: ready task `INC-012`.
6. **Retention/deletion/legal hold** — jurisdiction, effective policy, accountable reviewers and tested propagation through primary data, telemetry, backups and providers are unresolved. Owner: `INC-011` plus human privacy/legal reviewers.
7. **Semantic/adversarial quality** — prompt injection, groundedness, citation fidelity, harmful use and legal-overclaim evals lack a complete release threshold. Owner: `INC-010`.

Open CRITICAL findings: zero.

## Other material gaps

- audit ledger is transactional but not hash-chained, signed or immutably exported;
- a valid principal can amplify denial-audit storage because no general authenticated request quota exists;
- managed identity, SSO/MFA, recovery and lifecycle provisioning are absent;
- TLS/HSTS/CSP and proxy/platform/database telemetry are not staging-verified;
- application/data rollback against immutable image/schema compatibility is not exercised in an authorized environment;
- SLOs, alert rules, alert exercise, incident response and tracing decision remain incomplete;
- complete loading/empty/partial/degraded/conflict/read-only UI states remain incomplete;
- four accessible political themes and a real entitlement-gated premium theme are absent;
- external adapters, including any `browser-use/video-use` integration, remain unreviewed for activation and disabled.

## Ready work

Priority order after persisting INC-003:

1. `INC-012` — separate PostgreSQL migration/runtime authority and prove non-owner exact grants.
2. `INC-004` — durable idempotency-key replay, races and Greenlight revocation/fencing.
3. `INC-005` — SLOs, alert rules/exercise, authenticated quota/audit growth policy, immutable audit/export decision, rollback and production backup controls.
4. `INC-010` — semantic/adversarial eval harness.
5. `INC-008` — complete operator states, themes and manual accessibility evidence.

## Exact blockers and resume conditions

### BLK-GCP-001

- Category: credential / permission / infrastructure / human decision
- Evidence: no authorized cloud target/open billing/reviewed saved plan/apply; issue #1 and PR #2 remain `DENY_APPLY`.
- Independent work remaining: yes.
- Resume condition: explicit authorized target with open billing, granular preflight, reviewed saved plan bound to source commit, independent `ALLOW_DEV_APPLY`, and explicit authorization for external infrastructure/spend.

### Privacy/legal policy

- Category: human decision / legal review / data
- Evidence: jurisdiction and entity/customer role are unknown; no effective retention/deletion/legal-hold source exists.
- Independent work remaining: yes.
- Resume condition: identified entity/customer/jurisdiction, approved source/version/effective date, retention/legal-hold/backup propagation rules, accountable privacy/legal reviewer, security reviewer and business data owner.

## Human gates

- merge or close either PR;
- publish a release, image or package externally;
- select/create/apply external infrastructure or incur spend;
- create/rotate production credentials or database roles;
- execute persistent schema migration or destructive restore/deletion;
- enable browser/video automation, real model/media generation, publishing, ads or spend;
- approve retention, privacy or sensitive legal decisions;
- approve production deployment.
