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

Category: human decision / review

Real Chromium automation now proves 320 CSS px reflow, minimum theme targets, skip-link focus transfer, keyboard activation, reduced-motion behavior and accessibility-tree names/states. It does not prove human screen-reader output, rendered contrast quality, 400% zoom behavior, visual hierarchy or physical-device behavior.

Exact resume condition: an accountable human reviewer executes `docs/accessibility/manual-review-protocol.md` against the exact production bundle using a screen reader, keyboard, contrast tool, 400% zoom and representative viewports, records artifacts, and closes or repairs every CRITICAL/HIGH finding.

## OI-006 — Independent reviewer

Category: human decision

Producer/critic/fixer/verifier passes can be role-separated in-session, but final PR approval and any cloud apply require a distinct accountable human reviewer.


## OI-007 — PostgreSQL runtime role authority — resolved

Exact published head `1002d077564618623fe00f27ffae23c2b410aca8` passed all eight jobs in GitHub Actions run `29868899218` after complete local least-privilege, migration and recovery verification. The code/delivery issue is resolved. Persistent staging observation remains tracked by `F-004`, `BLK-GCP-001` and `SEC-013`.

## OI-008 — Retention, deletion and legal hold

Category: human decision / legal review / data

Implementation `1843aa93c7675c6f5f10254ee3b7cffc020f9fd5` adds a fail-closed privacy decision register and release gate. Operating entity, jurisdiction and controller/processor role remain `UNKNOWN`; seven policy scopes remain unapproved with null retention and no deletion/legal-hold automation. Zero providers are active and `DENY_RELEASE` is machine-enforced.

Exact resume condition for policy implementation: privacy/legal, security and business/data-owner reviewers identify operating entity/customer scope/jurisdiction, approve controller/processor role and exact source/version/effective date, retention start/duration/exceptions, deletion/correction/legal-hold/backup propagation and provider terms. Then implement and independently verify the approved policy; destructive execution remains separately human-gated.

## OI-009 — Production backup and alert delivery

Category: infrastructure / credential / human decision / data

Exact local commit `6a885827b7e89d06111c87c34293250eab196d47` implements and exercises backup freshness signals, stale/missing rules, restore regression and alert-contract validation. No authorized scheduler, KMS/key lifecycle, encrypted immutable off-host destination, approved retention or persistent alert delivery exists.

Acceptance condition: authorized target and credentials; reviewed scheduler; encryption/KMS; immutable off-host retention; approved policy; rules loaded; paging delivered; and a staging restore/incident exercise with retained evidence.

## OI-010 — Video Use activation remains denied

Category: integration / security / privacy / supply chain / human decision

Exact commit `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` is reproducibly reviewed and
packaged as `reviewed_disabled`. The current runtime exposes review data only and
has no executor. Upstream path containment, media disclosure, reproducibility and
product authority/receipt gaps remain unresolved for activation.

Exact resume condition: select a patched exact source commit; close every HIGH
finding; hash-lock dependencies/binaries; implement an isolated non-root worker,
exact egress, short-lived secret references, tenant/artifact-bound Greenlight,
outbound idempotency/outbox/fence/receipt/revocation, resource/cost limits,
semantic adversarial tests, provider privacy/legal approval, incident/rollback
and deletion evidence; then obtain explicit external-effect authorization.


## OI-011 — Sandbox push connector failure

Category: tooling / infrastructure / permission

The official `Cloud_Sandbox_MCP.git_push` action fails before Git because its ownership
wrapper starts Docker and Docker cannot create the NAT chain without host iptables
permission. The failure repeated for the clean INC-020 checkpoint
`50b55f3791fad030710b567e297c0704532cddee`; local commits, `git fsck` and all local gates
remain valid, but no remote SHA, PR or exact-head CI can be claimed. No force push or
alternate ref API was used.

Exact resume condition: repair the connector so it invokes Git without privileged Docker
startup, or publish the exact branch from an authenticated user checkout.

## OI-012 — Durable model effect authority

Category: distributed systems / financial safety / integration

Implemented locally at `6eb7fa070bcbe71c840ca316fc86d369d9d1691b`: schema v4 SQLite/PostgreSQL intent stores, exact binding,
fenced execution, durable output/receipt, replay reuse, `unknown` blocking, idempotent
reconciliation, run attachment/audit repair and default-disabled deployment controls.

Exact resume condition: publish the branch and pass exact-head PostgreSQL, package,
infrastructure and supply-chain CI. Real credentials, prompt transfer, egress and spend still
require separate provider/privacy/budget/release approval.


## OI-013 — Authorized social publication observation

Category: integration / privacy / external effect / human authorization

INC-020 is implemented locally at `8eb0cf7dee9b3400351a8b7d603a94666253f1e7`: exact binding, fenced execution, durable
receipts, compatible replay, unknown blocking, idempotent reconciliation and
MockTransport/browser/package gates pass. Publication remains disabled by default and no
real X or Instagram request was made.

Exact resume condition: publish the branch and pass exact-head CI; approve current provider
terms/privacy/account scope; register exact callbacks; authorize one sandbox post per
channel; record and reconcile provider receipts. Production enablement remains a separate
release decision.

## OI-014 — Governed publication media and verified Instagram receipt

Category: product / media / distributed systems / external effect

INC-021 produces an accessible non-rendered media plan, but Instagram still requires an approved `publication_media` artifact containing governed bytes, a reachable HTTPS URL and exact SHA-256. The current INC-020 receipt stores provider/container IDs but does not independently read the resulting media, verify the exact account/caption binding or persist a permalink.

Exact resume condition: complete INC-022 with bounded media ingestion/rendering, rights and accessibility metadata, content/hash binding to Greenlight, container status polling, `media_publish`, read-after-write verification, durable verified receipt and unknown-state reconciliation. One real sandbox post requires separate explicit authorization.

## OI-015 — Political publication authority remains intentionally denied

Category: legal / campaign authorization / external effect / human decision

Commit `6ebbd634bd32408db0a7678289b0f906cda014c0` adds server-bound evidence and legal-review authority plus the independent `AGENCY_POLITICAL_PUBLICATION_ENABLED=false` kill switch. Deterministic tests prove that general social publication enablement does not enable political effects and performs zero provider calls.

Exact resume condition: exact-head CI; accountable jurisdiction-specific legal review; verified candidate/campaign authority; provider policy/account review; approved content and media; explicit enablement and one separately authorized sandbox post. Production remains a distinct release decision.
