# Open Issues

## OI-001 — Reconcile PR #2 and PR #3

Category: architecture / human decision

The branches implement incompatible production foundations. This program ports compatible controls to PR #3 but will not close, merge, or supersede either PR without a reviewed human decision.

## OI-002 — No authorized cloud target

Category: credential / permission / infrastructure / human decision

Evidence: active branch has no GCP path; issue #1 and PR #2 record no open accessible billing account, no selected parent/project/region, and no apply evidence.

Exact resume condition: one explicit authorized target with open billing, granular permissions, policy/quota/cost review, a saved plan bound to the source commit, independent `ALLOW_DEV_APPLY`, and approval to create external infrastructure/spend.

## OI-003 — Backup/restore and rollback evidence

Category: code / operations

Executable work remains and is assigned to `INC-002`. Persistent production restore remains human-gated after tooling and ephemeral drills pass.

## OI-004 — Idempotency and Greenlight revocation

Category: code / data correctness

Mutable API requests lack durable idempotency keys; approved Greenlight cannot be revoked before a future effect. Implement before any effectful adapter.

## OI-005 — Accessibility manual gate

Category: environment / review

Automated tests do not prove keyboard order, screen-reader output, contrast, zoom/reflow, or physical-device behavior. Exact resume condition for full evidence: an available visual browser plus keyboard, contrast tooling, and screen-reader review on the production bundle.

## OI-006 — Independent reviewer

Category: human decision

Producer/critic/fixer/verifier passes can be role-separated in-session, but final PR approval and any cloud apply require a distinct accountable human reviewer.


## OI-007 — PostgreSQL runtime role authority

Category: delivery / persistent-environment observation

Exact local commit `612e03c1a90f644a8cd26fde785f3980491bab9d` passes the complete non-owner PostgreSQL, migration, recovery, package, infrastructure, secret and supply-chain gates. The code defect is locally remediated. Push and exact-head CI remain executable delivery work; persistent managed-role observation remains a human/infrastructure gate.

Acceptance condition: remote SHA equals the reviewed head and all required CI jobs pass; production additionally requires authorized persistent-environment evidence.

## OI-008 — Retention, deletion and legal hold

Category: human decision / legal review / data

No jurisdiction, effective policy or accountable reviewer is selected. No destructive automation is authorized.

Exact resume condition for policy implementation: identified operating entity/customer/jurisdiction, approved source/version/effective date, retention/legal-hold/backup propagation decisions, privacy/legal reviewer, security reviewer and business data owner.
