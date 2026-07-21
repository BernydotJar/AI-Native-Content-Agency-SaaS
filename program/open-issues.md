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

## OI-004 — Idempotency and Greenlight revocation — resolved

Exact published head `bc01fa7b54341865f848c0754884cc83f660a0c7` passed all eight jobs in GitHub Actions run `29871278876` after complete SQLite/PostgreSQL concurrency, replay, authorization, revocation and fencing verification. Future external providers remain disabled and require separate outbound outbox/idempotency/receipt controls.

## OI-005 — Accessibility manual gate

Category: environment / review

Automated tests do not prove keyboard order, screen-reader output, contrast, zoom/reflow, or physical-device behavior. Exact resume condition for full evidence: an available visual browser plus keyboard, contrast tooling, and screen-reader review on the production bundle.

## OI-006 — Independent reviewer

Category: human decision

Producer/critic/fixer/verifier passes can be role-separated in-session, but final PR approval and any cloud apply require a distinct accountable human reviewer.


## OI-007 — PostgreSQL runtime role authority — resolved

Exact published head `1002d077564618623fe00f27ffae23c2b410aca8` passed all eight jobs in GitHub Actions run `29868899218` after complete local least-privilege, migration and recovery verification. The code/delivery issue is resolved. Persistent staging observation remains tracked by `F-004`, `BLK-GCP-001` and `SEC-013`.

## OI-008 — Retention, deletion and legal hold

Category: human decision / legal review / data

No jurisdiction, effective policy or accountable reviewer is selected. No destructive automation is authorized.

Exact resume condition for policy implementation: identified operating entity/customer/jurisdiction, approved source/version/effective date, retention/legal-hold/backup propagation decisions, privacy/legal reviewer, security reviewer and business data owner.
