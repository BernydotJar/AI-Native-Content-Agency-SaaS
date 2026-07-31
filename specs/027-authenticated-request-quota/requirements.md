# INC-027 Requirements — Durable Authenticated Request Quota

## Problem

`F-013` proves that authentication failures are rate limited, but a valid principal can repeatedly invoke forbidden or CSRF-invalid actions and create an unbounded sequence of denial-audit rows. HTTP metrics observe the traffic but do not bound durable write amplification.

## Required behavior

1. Every authenticated API request consumes exactly one durable quota unit before CSRF verification or permission authorization.
2. The quota uses two independent hashed buckets:
   - tenant + authenticated subject;
   - tenant aggregate.
3. Raw tenant IDs, subjects, session IDs, API keys and credential fingerprints never enter quota storage, logs, metrics, responses or evidence.
4. SQLite and PostgreSQL enforce and increment all buckets atomically. PostgreSQL behavior is shared across replicas.
5. The first configured number of requests in an active fixed window pass. The next request returns HTTP 429 with a bounded `Retry-After` value.
6. A quota rejection occurs before CSRF or authorization denial auditing and therefore creates no new denial-audit row.
7. Expired windows reset without operator action and stale bucket rows are bounded/cleaned.
8. Bearer and browser-session authentication for the same tenant/subject share the principal quota.
9. Configuration is validated at startup, defaults fail safe but remain practical for the product UI, and tenant quota cannot be lower than principal quota.
10. Low-cardinality metrics distinguish allowed and rate-limited authenticated requests without tenant or subject labels.
11. PostgreSQL migrates forward to schema v8; backup/restore and least-privilege checks preserve the new table.
12. Local runner, Helm and Terraform carry only non-secret quota values and enforce the same bounds.

## Evidence gates

- unit and API boundary tests;
- SQLite migration/storage tests;
- PostgreSQL multi-replica and schema-v8 tests;
- installed-wheel regression;
- package, Helm and Terraform verification;
- exact-head CI and retained evidence;
- critic, security and independent review.

## Safety boundary

This increment does not deploy, mutate cloud infrastructure, alter production secrets, publish content, call providers, spend money or grant release authority. Existing `DENY_RELEASE`, `DENY_APPLY` and effect kill switches remain unchanged.
