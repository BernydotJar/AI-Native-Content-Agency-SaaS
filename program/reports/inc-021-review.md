# INC-021 Role-Separated Review

Date: 2026-07-25  
Branch: `agent/inc-021-campaign-intelligence`  
Implementation commit: `6ebbd634bd32408db0a7678289b0f906cda014c0`  
Program state: `review`

## Producer

Status: PASS

Outputs:

- structured commercial/political brief contract;
- claim ledger with source, locator, verification state and authenticated reviewer;
- Spanish platform variants with claim mapping and disclosure;
- Instagram carousel plan with dimensions, slide purposes and alt text;
- explicit Critique Agent result;
- separate default-off political publication authority.

## Critic

Status: PASS after repair

Initial findings:

1. A supplied source was incorrectly treated as verified evidence.
2. A failed critique still displayed `Risk passed` at the publisher station.
3. Generic copy remained susceptible to mixed-language fixtures.

Repairs:

- `verification_status=verified` now requires server-bound reviewer authority;
- unverified content stays reviewable but receives `decision=revise`, publisher `ATTENTION`, and no Greenlight;
- deterministic Spanish copy rules replace the prior `made clear` fixture for new defaults and political campaigns.

## Security Reviewer

Status: PASS for implemented scope

Evidence:

- operators cannot self-attest verified evidence or legal approval;
- the server replaces client reviewer names with authenticated `subject_id`;
- unverified/pending reviewer values are cleared;
- general social publication enabled + political publication disabled produces `409 political_publication_disabled` and zero provider calls;
- OAuth callback requires `state`, is tenant/session/channel bound and wrong-session callbacks redirect to a safe error without provider HTTP;
- diff and untracked secret scans returned zero findings.

## Legal and Compliance Reviewer

Status: PARTIAL — external human gate retained

Implemented controls:

- explicit `legal_review_status` and server-bound `legal_reviewed_by`;
- legal approval is required for `publication_eligible=true`;
- UI states that the system does not infer legal compliance;
- political publication has a separate disabled-by-default flag.

Limitations:

- no jurisdiction-specific legal conclusion was made;
- source authenticity is not independently established by the software;
- no candidate, party, campaign, paid-ad or election authority approved a real use;
- `DENY_RELEASE` remains authoritative.

## Red Team Agent

Status: PASS

Scenarios:

- missing evidence → HTTP 422;
- unverified evidence → reviewable run, `revise`, Greenlight denied;
- legal review pending → `revise`, Greenlight denied;
- operator self-attestation → HTTP 403;
- general publication enabled while political flag false → HTTP 409, zero provider requests;
- OAuth callback from a different browser session → safe error redirect, zero provider requests;
- OAuth callback without `state` → HTTP 422.

## Fixer

Status: PASS

The full locked-wheel regression exposed two defects inherited from the preceding OAuth hotfix:

- `MockTransport` responses were already materialized and `iter_raw()` raised `StreamConsumed`;
- a preexisting test expected HTTP 400 even though the product intentionally redirects callback errors to the SPA.

Repairs:

- bounded OAuth response reader supports streamed and already-materialized responses;
- `state` is mandatory; the unused no-state fallback was removed;
- test asserts safe error redirect and zero provider calls.

## Independent Verifier

Status: PASS for deterministic local scope

Commands and outcomes:

- `./scripts/verify-python-locks.sh` → PASS, 261 tests, 23 PostgreSQL-only skips;
- focused OAuth service/API/store family → PASS, 18 executed, 2 PostgreSQL-only skips;
- `npm test` → PASS, 39 tests;
- `npm run lint` → PASS, 0 warnings, 0 errors;
- `npm run build` → PASS;
- `git diff --check` → PASS;
- tracked and untracked secret-pattern scans → 0 findings;
- nested container count → 0.

Not run locally:

- PostgreSQL tests requiring `AGENCY_TEST_DATABASE_URL`;
- K3s/Helm/Terraform apply-destroy verifier, because it creates an auxiliary local control plane and required CLIs were not loaded;
- real X/Instagram publication;
- real model/provider effects;
- cloud deployment or spend;
- human accessibility, legal, privacy or campaign review.

## Release Gate

Decision: `DENY_RELEASE`

INC-021 is locally review-ready, not globally done. Exact resume condition:

1. publish the exact branch SHA;
2. pass exact-head CI including PostgreSQL, package, Helm/Terraform and supply-chain jobs;
3. complete distinct accountable review;
4. keep all external effects disabled;
5. proceed to INC-022 for governed media and read-after-write publication verification.
