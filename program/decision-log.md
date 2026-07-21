# Decision Log

## D-001 — Select `agency_runtime` as the active runtime on PR #3

- Date: 2026-07-21
- Status: accepted for this branch
- Decision: Preserve the current FastAPI/RBAC/PostgreSQL implementation as the source of truth. Treat PR #2 as a donor branch rather than merging its alternate `control_plane` wholesale.
- Reason: The branches diverged and contain incompatible persistence, API, authentication, packaging, CI, and infrastructure designs. Blind integration would create two authorities and invalidate existing evidence.
- Reversal condition: a reviewed replacement plan with API/data migration, rollback, compatibility tests, and explicit ownership.

## D-002 — GCP deployment is not proven

- Date: 2026-07-21
- Status: accepted
- Decision: Record the current cloud state as `not deployed / not observed`.
- Evidence: the active branch has no GCP resources; issue #1 and PR #2 record `DENY_APPLY`, closed billing accounts, no authorized target, and no apply evidence.
- Resume condition: an explicitly authorized target, open billing, granular permission preflight, reviewed saved plan, apply record, endpoint smoke, and no-drift plan.

## D-003 — Keep all external effects disabled

- Date: 2026-07-21
- Status: accepted
- Decision: Do not activate `video-use`, browser automation, publisher APIs, media generation, advertising, or spend during this program slice.
- Reason: no versioned effect contract, credentials, idempotency/receipt/revocation controls, or external authorization exists.

## D-004 — Normalize product version at 0.7.0

- Date: 2026-07-21
- Status: accepted
- Decision: Align frontend package, Python runtime, FastAPI metadata, metrics, Helm chart, and OCI metadata at `0.7.0`; enforce consistency with a repository gate.
- Reason: frontend `0.0.0` contradicted runtime/chart `0.7.0` and made release artifacts ambiguous.

## D-005 — Backup tools must fail closed

- Date: 2026-07-21
- Status: accepted
- Decision: Backup manifests include backend, size, SHA-256, timestamp, tool version, and validation result. Restore verifies integrity and refuses an existing target unless an explicit replacement flag is supplied. Production restore remains a human destructive-data gate.
