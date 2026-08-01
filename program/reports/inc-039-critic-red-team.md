# INC-039 Critic / Red Team Review

Date: 2026-07-31
Reviewed implementation: `24b88e5adb9a9c436c617867d17ac50304ef13f4`
Decision: PASS AFTER LOCALIZED REPAIRS

## Attack surface reviewed

The critic attempted to bypass the cost ceiling, enable Cloud Run against an uninitialized database, inject mutable secret versions, expand runtime IAM, require disabled social-provider credentials, expose PostgreSQL directly, disable scale-to-zero, and claim deployment without external evidence.

## Findings

1. A boolean cost acknowledgement was not durable evidence. It was replaced by a required lowercase SHA-256 receipt bound to the reviewed estimate and cap.
2. A fresh PostgreSQL database would fail a runtime configured with `AGENCY_POSTGRES_SCHEMA_MODE=validate`. Cloud Run now requires a separate schema/role initialization receipt and retains that receipt as revision metadata.
3. Runtime secret IAM originally covered every managed secret container. It now covers only secret containers injected into the revision.
4. The old Cloud Run contract required X, Instagram and social-token secrets even though all corresponding capabilities were disabled. The minimum effects-off contract now requires only database, identity and audit-checkpoint secrets.
5. Absence of authorized networks was strengthened with `connector_enforcement=REQUIRED`, preventing direct database connections outside Cloud SQL connectors/proxy.
6. The prior scaling variables allowed values beyond the authorized pilot. They now require minimum zero and maximum one or two.
7. Default-plan tests did not explicitly assert zero Cloud SQL resources or IAM. Those assertions were added.

## Residual risks

Terraform validation does not authorize or observe a real deployment. Google Cloud budgets are alerting controls, not hard shutdowns. Pricing and exchange rates can change. Actual database-role initialization, secret versions, image bytes, public ingress, persistence, startup, login, Greenlight, audit continuity and rollback remain external staging gates.

No blocking code finding remains within INC-039's code-only scope.
