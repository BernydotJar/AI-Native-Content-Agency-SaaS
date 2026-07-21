# Incident Response Runbook

Status: repository procedure; production paging and platform telemetry remain environment-specific.

## Evidence rules

- Do not paste tokens, database URLs, cookies, request bodies or tenant content into incident artifacts.
- Record exact UTC timestamps, commit/image digest, environment, alert name and bounded aggregate metrics.
- Distinguish alert expression validation from alert delivery and from a human incident drill.
- Production traffic changes, rollback, restore and external communications require an accountable operator.

## API availability burn

1. Confirm whether `AgencyApiAvailabilityFastBurn` or `AgencyApiAvailabilitySlowBurn` fired and preserve the query window.
2. Check `/healthz`, `/readyz`, aggregate 5xx rate and dependency errors without enumerating tenant data.
3. Compare the active image/Helm revision with the last known healthy release.
4. If a recent release correlates and rollback is approved, follow [Release Rollback](release-rollback.md).
5. If PostgreSQL is unhealthy, stop mutation traffic before considering restore. Follow the recovery runbook only with an approved recovery point.
6. Close the incident only after the burn-rate window returns below threshold and evidence is retained.

## API latency

1. Confirm p95 from `agency_http_request_duration_seconds_bucket` and identify bounded route labels.
2. Check pool saturation, request-size distribution, downstream database latency and replica count.
3. Do not increase pool or replica ceilings without recalculating the database connection budget.
4. Mitigate via approved rollback or capacity change; record before/after p95 and error rate.

## Runtime unavailable

1. Confirm whether scrape targets are absent versus `/readyz` failing.
2. Inspect rollout revision, pod scheduling, Secret references and PostgreSQL schema validation separately.
3. Never weaken readiness to make the alert clear.
4. Use rollback when the current release is defective; use the database rollout runbook when schema/role validation is the cause.

## Authentication abuse

1. Confirm `AgencyAuthenticationAbuse` using only bounded aggregate denial metrics.
2. Review edge/source rate limiting and credential rotation events without exposing credentials or source addresses in shared artifacts.
3. Do not reveal whether a specific credential, subject or tenant exists.
4. Escalate suspected credential compromise to the accountable security operator; real revocation is human-gated.

## Communications and closure

External customer, campaign, legal or public communications require human approval. Record root cause, containment, recovery, residual risk and follow-up owner. An alert exercise is not an incident drill until a human operator receives and acts on the alert in an authorized environment.
