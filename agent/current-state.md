# Current State

Updated: 2026-07-18T23:45:35Z

## Repository

- Branch: `feat/production-foundation-v1`
- Base and initial HEAD: `dcb1d1c567ad688b7fd78a219411b42d5806034c`
- Remote: `origin` (`BernydotJar/AI-Native-Content-Agency-SaaS`)
- Initial working tree: clean
- Tracking issue: `#1` — Production Foundation V1: unified control plane and GCP dev path
- Commits and draft PR: pending final independent gates

## Implemented local foundation

- FastAPI `/api/v1` is the authoritative control plane for missions, runs, steps, artifacts, evidence, events, audit, approvals and idempotency.
- SQLAlchemy/Alembic persist command-boundary state. SQLite is restricted to local/test use; Compose and the cloud design use PostgreSQL 15.
- Greenlight is tenant-scoped and bound to the exact pre-Publisher artifact SHA-256 plus `greenlight.v1`. Approval produces only a sandbox package with `publication_performed=false`.
- The default React UI uses the API, stable retry keys and authoritative polling. The timer-based UI is isolated behind `VITE_RUNTIME_MODE=demo`.
- A pinned non-root combined SPA/API image, PostgreSQL/Alembic Compose topology, CI, dependency gates and Terraform bootstrap/dev definitions now exist.
- Terraform defines only bootstrap/dev executable roots. Staging and production remain definition-only.

## Verified exact-tree gates

- Backend: 40/40 pytest and 16/16 legacy unittest; ruff, mypy and canonical OpenAPI check pass.
- Frontend: 45/45 tests; lint, typecheck, OpenAPI contract check and production build pass.
- Dependency gates: npm audit reports zero vulnerabilities; the exact Python runtime lock reports no known vulnerabilities after upgrading `setuptools` to 83.0.0.
- Platform: eight Terraform roots initialize readonly, validate, and pass two mock tests; locks include Linux AMD64 and macOS ARM64 checksums; YAML and 30/30 static policy checks pass.
- Container: image runs as UID/GID `10001:10001`; migrations complete; health/readiness pass; a full HTTP mission/run/approval flow completes with zero external effects.
- Persistence: the same completed run was restored after recreating the application and PostgreSQL containers with the named volume preserved.
- Interactive visual QA is unproven because the required in-app browser runtime exposed no browser instances. SPA delivery and component behavior remain covered by HTTP/build/component evidence.

## Mandatory gates in progress

- Independent cloud infrastructure critique is running read-only.
- The initial independent security review correctly failed on a medium `setuptools` advisory. The fixed lock now passes the exact audit; final independent re-audit is pending.
- Independent production-readiness evaluation follows the critique/security closure.

## Safety boundaries

- Current apply recommendation: `DENY_APPLY`.
- Bootstrap and dev may be applied only from an independently approved saved Terraform plan.
- Cloud Run dev remains IAM-private; no `allUsers` or `allAuthenticatedUsers` binding is permitted.
- No provider publication, Meta Ads activation, advertising spend, service-account key, destructive migration, staging/production apply or merge is authorized.

## External GCP blocker

Read-only discovery found six visible billing accounts and zero open accounts, no related target project, no visible organization, and no selected region. The active gcloud project `meridian-hr-crm` is unrelated and prohibited as a target. ADC refresh succeeded with token output discarded.

A real plan/apply requires an accessible account reporting `open=True`, explicit hierarchy/project/region selection, granular permissions/policy/quota/cost preflight, an immutable image in the target registry, a saved plan and independent `ALLOW_DEV_APPLY` for that exact plan. No GCP mutation has occurred.
