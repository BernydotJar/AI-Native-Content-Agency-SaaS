# INC-024 Political Browser QA — Role-Separated Review

Date: 2026-07-26

Implementation commit: `4d0bc7472c6b4d9d2719f5275028f35de4341463`

State: `review` — local gates pass; exact-head CI pending.

Global decision: `DENY_RELEASE` / `DENY_APPLY`.

## Producer

Added a real Chromium/CDP journey using two isolated browser profiles and a test-only FastAPI fixture. The journey creates a political run through the actual UI, waits for durable station execution, denies same-subject Greenlight, approves from an independent identity, checks the compliance artifact, exercises the exact political phrase and observes one durable mock-provider receipt. Five screenshots and a sanitized JSON receipt are generated.

No Playwright package was installed. The repository's existing dependency-free CDP harness was used to avoid new supply-chain surface. No real provider, OAuth, social account, cloud resource or spend was contacted.

## Critic — RED findings

1. **Generic 409 UX:** reviewer separation was enforced server-side, but the UI said only that the run state changed.
2. **False transient failure:** while Research was still running, the output panel claimed Writer had failed to produce copy.
3. **Office-generic copy:** deputy copy reused a generic representation hook and Critique did not validate alignment to the office.
4. **Municipality duplication:** the first mayoral repair rendered “municipio de Municipio de prueba.”

All four findings were reproduced before repair and have regression tests.

## Fixer

- Maps political 409 codes to specific, actionable operator messages.
- Shows asynchronous copy progress for queued/running runs and reserves the missing-copy alert for terminal states.
- Generates explicit municipal and legislative hooks for mayor and deputy.
- Adds `office_message_alignment` to the semantic critique.
- Normalizes an already-prefixed municipal locality.
- Adds the browser journey to `production-readiness` and uploads evidence for 30 days.

## Security and privacy review

PASS locally:

- zero provider calls before exact final confirmation;
- wrong phrase cannot enable the confirm button;
- one exact phrase produces one mock effect;
- raw phrase is absent from SQLite and the response;
- evidence contains no fixture API keys, access tokens, OAuth codes or states;
- legal reviewer and Greenlight approver are distinct authenticated subjects;
- the live workstation keeps social and political publication switches disabled;
- nested container count remains zero.

The screenshots contain only generated test identities and content. Human visual review remains required before a real sandbox effect.

## Content and semantic review

The verified mayoral sample contains:

- a municipal-governance hook;
- candidate/proposal body;
- explicit source and locator;
- neutral non-electoral disclosure;
- citizen-action CTA.

The Critique receipt contains fourteen checks, including evidence verification, source visibility, disclosure, legal review, prohibited-promotion absence and office-message alignment. It also preserves explicit limitations: locale checks are not full linguistic review, source visibility is not source authenticity, and jurisdiction-specific legal review remains external.

## Independent verifier receipt

Observed locally on the implementation worktree:

- frontend: 47 PASS;
- lint: zero warnings/errors;
- production build: PASS;
- accessibility Chromium gate: PASS;
- existing social-publication Chromium gate: PASS;
- political Chromium gate in source mode: PASS;
- political Chromium gate from a clean installed wheel: PASS;
- hash-locked wheel: 286 PASS, 25 PostgreSQL-only skips;
- compliance: PASS with `DENY_RELEASE`;
- actionlint and diff check: PASS;
- secret/evidence leak scans: PASS;
- nested containers: zero.

Not yet observed on this SHA:

- GitHub exact-head eight-job workflow;
- PostgreSQL shared-state gate for this exact branch;
- OCI, Helm, Terraform and supply-chain gates for this exact branch;
- accountable human screenshot/editorial review;
- real neutral sandbox publication.

## Decision

INC-024 is suitable for a feature-branch checkpoint and remote exact-head evaluation. It remains `review`. External publication and the global release remain denied.

## Exact-head CI receipt

- Head: `eb4481c89bab440daa25b11e49799a47a276b194`
- Workflow: `production-readiness`
- Run: `30188644229`
- Result: 8/8 SUCCESS
- Installed-wheel political browser: PASS
- PostgreSQL shared-state: PASS after one Docker Hub service-image retry; the first attempt timed out before checkout or project code.
- OCI, Helm, Terraform, supply chain, workflow lint and Python locks: PASS.

INC-024 is `done` at increment level. External social/political effects remain disabled and no live provider call occurred.

## Merge receipt

- PR: `#17`
- Verified head: `ca10003d5337715ffb880a38651b7317cfa23055`
- Final exact-head workflow: `30188788859`, 8/8 SUCCESS
- Merge commit: `0b43be4f9b46d5ff7b272efca961d07db3a97433`
- Merge method: normal merge commit
- External effects: disabled
- Global decisions: `DENY_RELEASE` / `DENY_APPLY`
