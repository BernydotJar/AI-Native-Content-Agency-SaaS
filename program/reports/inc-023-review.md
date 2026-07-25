# INC-023 Role-Separated Review

Date: 2026-07-25

Increment: Political Compliance Mode

Implementation commit: `2315ac32f63958b83f26754e95a88f18b65028a6`

Review state: `CONDITIONAL_PASS_EXACT_HEAD_CI_PENDING`

Global state: `DENY_RELEASE` / `DENY_APPLY`

## Producer assessment

The implementation introduces a bounded political compliance contract without broadening external-effect authority:

- political content creation is separately disabled by default;
- organic and paid modes are explicit in the brief;
- paid mode requires its own switch for planning and is always rejected by the organic publication endpoint;
- legal/electoral attestation derives from the authenticated principal;
- Greenlight requires a distinct authenticated subject;
- an immutable political compliance artifact enters the Greenlight hash envelope;
- the final political phrase is checked before intent reservation;
- only its SHA-256 becomes part of the exact-once binding and durable audit evidence.

No real provider call, deployment, ad activation or cloud resource was created.

## Critic assessment

The RED suite first demonstrated that the prior product lacked:

1. `publication_mode`;
2. an independent political-content switch;
3. reviewer separation;
4. a compliance record inside Greenlight;
5. a server-enforced final phrase;
6. a durable confirmation digest;
7. an organic/paid authority boundary.

The focused suite now proves all seven original invariants plus independent paid-mode creation gating. Commercial creation and commercial publication confirmation remain backward compatible.

## Security assessment

PASS locally:

- missing/wrong final phrase produces no durable intent and zero provider requests;
- the SQLite file does not contain the raw final phrase;
- the digest participates in the exact-effect binding, so changing confirmation authority changes the binding;
- same-subject legal review and Greenlight approval are rejected;
- provider transport remains unreachable for paid mode;
- all four switches default to false in application, `.env`, Helm and Terraform surfaces;
- no credentials were added to source.

Residual security gates:

- PostgreSQL schema v6 and least-privilege behavior require exact-head CI because the local PostgreSQL executable is absent;
- production KMS, stable media origin, account ownership and secret rotation remain external deployment controls;
- local disablement cannot delete an already published provider object.

## Legal and policy boundary assessment

The software records accountable identities, jurisdiction, disclosure digest and evidence-source bindings. It does not determine whether a disclosure is legally sufficient, whether a candidate or party authorized the content, whether a source is authentic, or whether provider political-content policies are satisfied.

A green build is not legal approval. Real political use still requires an accountable jurisdiction-specific reviewer and campaign authorization outside this automated review.

## Red-team assessment

PASS locally:

- political creation with content switch off: 409, no provider call;
- paid planning with paid switch off: 409, no provider call;
- paid publication through organic endpoint: 409, no intent/provider call;
- same reviewer for legal and Greenlight: 409;
- wrong final phrase: 409, no intent/provider call;
- correct phrase: one effect and one persisted digest;
- general social enablement alone: political publication remains blocked;
- commercial defaults: unchanged.

## Verifier receipt

Observed local gates:

- focused political backend: PASS;
- broad backend compatibility: PASS;
- installed hash-locked wheel: 285 PASS, 25 PostgreSQL-only SKIP;
- frontend: 45 PASS;
- lint: zero warnings/errors;
- production build: PASS;
- program state: PASS;
- compliance: PASS with `DENY_RELEASE`;
- backup/schema CLI/political operability family: PASS;
- diff check: PASS;
- nested containers: zero.

Remote exact-head evidence:

- PostgreSQL shared-state schema v6: PASS;
- OCI image: PASS;
- Helm: PASS;
- Terraform: PASS;
- supply chain: PASS after one Docker Hub infrastructure retry;
- accessibility browser: PASS;
- remote head `e35fa74fa7704161ef81bf9dbe13cea7b761f5ab` and PR #15 verified.

## Decision

INC-023 is `done` at increment level: implementation and exact-head CI passed. All external effects remain disabled. A neutral sandbox post still requires a separate accountable approval of the exact account, copy, media hash, time window and rollback owner; automated validation is not legal authorization.
