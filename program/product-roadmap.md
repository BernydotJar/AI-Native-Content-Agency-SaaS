# Product Roadmap

Updated: 2026-07-21

## P0 — Establish trustworthy release state

- `INC-001` Program state, architecture reconciliation, version consistency, and documentation truth.
- `INC-002` Backup/restore tooling and drills for SQLite and PostgreSQL.
- `INC-003` Threat model, privacy model, data classification, retention decision, and adversarial coverage.
- `INC-004` Durable idempotency keys and structured error contracts for mutable API commands.
- `INC-005` SLOs, alert rules, alert exercise harness, incident and rollback runbooks.
- `INC-006` Staging strategy and real workload execution evidence in an authorized environment.

## P1 — Product and operator experience

- unify cinematic simulation and backend-backed console around one explicit source of truth;
- add complete loading, empty, partial, degraded, conflict, denied, rate-limited, and read-only states;
- implement four accessible political color themes plus a visibly gated premium theme without inventing billing entitlement;
- complete keyboard, focus, contrast, zoom/reflow, screen-reader, and reduced-motion review;
- add tenant administration, identity lifecycle boundaries, and narrower audit visibility;
- add semantic evals for groundedness, contradiction visibility, missing evidence, prompt injection, and legal overclaim.

## P2 — Authorized external capabilities

- select and authorize one deployment target;
- reconcile Kubernetes versus Cloud Run based on operational evidence and cost;
- introduce managed identity, secrets, object storage, and immutable audit export;
- evaluate `browser-use/video-use` behind a versioned, sandboxed, approval-gated adapter;
- activate external platform adapters one at a time only after auth, idempotency, bounded retries, receipts, revocation, observability, and human approval exist;
- perform staging soak, capacity, backup/restore, rollback, incident, and disaster-recovery exercises.

## Critical path

```text
truthful baseline
  -> versioned specs and traceability
  -> backup/restore + rollback
  -> idempotency + threat/privacy controls
  -> SLO/alerts + staging workload evidence
  -> accessibility/manual review
  -> independent release review
  -> human merge gate
  -> human production gate
```

## 2026-07-25 — Campaign intelligence delivery sequence

### INC-021 — review

- structured political brief and server-authoritative evidence/legal review;
- Spanish channel copy and claim mapping;
- accessible Instagram carousel plan;
- Critique Agent fail-closed Greenlight gate;
- separate political publication kill switch.

### INC-022 — next ready

- governed `publication_media` generation or ingestion;
- HTTPS delivery and exact media hash;
- media rights and alt-text metadata;
- Instagram container processing/status polling;
- independent post read-after-write verification;
- verified permalink/receipt and reconciliation UI.

### Later gated work

- semantic prompt-injection and externally sourced evidence evals;
- authorized cloud target and object storage;
- human accessibility/privacy/legal/campaign review;
- one authorized sandbox post before any production enablement.

## 2026-07-25 — Governed media and verified effects

### INC-022 — review

- immutable JPEG Media Vault in SQLite/PostgreSQL schema v5;
- server-verified dimensions/bytes/hash, alt text and rights identity;
- opaque expiring/revocable public delivery;
- upload/remove workflow before Greenlight;
- Instagram container polling and independent post verification;
- durable receipt history and safe permalink UI;
- fail-closed local/Helm/Terraform configuration.

### Next gated work

- exact-head CI and independent review;
- keyring-based signing-key rotation;
- post-publication provider deletion/reconciliation;
- authorized production object storage and retention policy;
- carousel/reel child-level exact-once protocols;
- one separately authorized sandbox publication.

## 2026-07-25 — Political compliance authority

### INC-023 — review

- independent default-off political content, publication and paid-planning switches;
- explicit `publication_mode=organic|paid`;
- authenticated legal/electoral reviewer separated from Greenlight approver;
- `political_compliance_record` included in the approved envelope;
- exact typed confirmation bound durably only by SHA-256;
- organic endpoint rejects paid mode before intent/provider HTTP;
- PostgreSQL schema v6 preserves prior media state and adds confirmation authority;
- operator UI and neutral sandbox/rollback runbook.

### Exact resume condition

- freeze and commit the implementation;
- publish an exact remote branch and draft PR;
- pass workflow-lint, verify, python-locks, postgresql-shared-state, container, Helm, Terraform and supply-chain at the exact head;
- complete a distinct accountable review;
- separately authorize the exact `@beesheep2` account, copy, media, time window and rollback owner before any provider effect.
