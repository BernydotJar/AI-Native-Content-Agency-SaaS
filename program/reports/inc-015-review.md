# INC-015 producer / critic / verifier review

Date: 2026-07-24  
Technical commit: `6eb7fa070bcbe71c840ca316fc86d369d9d1691b`  
Branch: `agent/inc-015-model-effect-authority-v2`

## Producer

Implemented a default-disabled durable model-effect authority for the five-provider gateway:

- SQLite and PostgreSQL schema v4 intents and bounded receipts;
- exact tenant/run/station/source/provider/model/request/cost binding;
- one fenced executor and compatible replay without another provider call;
- `pending`, `succeeded`, `unknown`, `failed` and `revoked` states;
- admin-only HttpOnly-session + CSRF execution and reconciliation routes;
- stable `model_completion` attachment and deterministic audit repair;
- Helm/Terraform flags and provider-key Secret references;
- installed-image MockTransport fixture with real socket denial.

## Critic

The review focused on duplicate spend, ambiguous outcomes and browser authority.
Provider/model selection is server-owned. Raw idempotency keys, credentials and prompt text are
not stored in intent records or returned by operational listings. A provider error becomes
`unknown` and blocks automatic retry and Greenlight approval until idempotent reconciliation.
The deployment defaults keep both `AGENCY_MODEL_EXECUTION_ENABLED` and
`AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED` false.

No automatic station integration was added: an administrator must explicitly invoke the
model-effect command for an `awaiting_greenlight` run. Real provider activation remains a
separate privacy, terms, budget and release decision.

## Verifier

| Gate | Result | Evidence |
|---|---|---|
| Locked wheel | PASS | 245 tests; 23 PostgreSQL-only skips |
| Focused model API/contracts | PASS | exact-once, default-disabled, RBAC/CSRF, conflict, unknown and reconciliation |
| MockTransport socket guard | PASS | one provider effect, compatible replay remains one call, real sockets zero |
| PostgreSQL v4 exact-head rerun | PENDING CI | not repeated after final edits by explicit operator instruction |
| Installed-image/package rerun | PENDING CI | gate and fixture committed; exact-head CI is next arbiter |
| Helm/Terraform/supply-chain rerun | PENDING CI | defaults/Secret refs committed; not repeated locally |
| Real provider request | NOT RUN | no credentials, egress, prompt transfer or spend |

## Decision

`INC-015` is ready for remote review, not release. Preserve `DENY_RELEASE`, `DENY_APPLY`,
`active_external_providers=0`, model flags false and zero spend until exact-head CI and human
provider/privacy/budget authorization are complete.
