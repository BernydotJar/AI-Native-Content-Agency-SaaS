# INC-022 Role-Separated Review

Date: 2026-07-25  
Branch: `agent/inc-022-governed-media-verification`  
Implementation commit: `3d8ed72332d29b161a48c1201e627a9c016ec6ac`  
Program state: `review`

## Producer

Status: PASS

Outputs:

- Pillow-verified bounded JPEG ingestion;
- durable SQLite/PostgreSQL Media Vault and schema v5;
- opaque expiring/revocable public capability;
- pre-Greenlight media attach/remove UI and API;
- exact media binding into Greenlight;
- Instagram container status polling;
- read-after-write verification and durable receipt history;
- fail-closed Helm/Terraform/local configuration.

## Critic

Status: PASS after repair

Findings and repairs:

1. Raw Unicode alt text cannot be transported portably in HTTP headers. Repaired with base64url UTF-8 and server decode/length validation.
2. A generic request-body limit blocked valid media while chunked requests could evade a Content-Length-only limit. Repaired with route-specific 8 MiB middleware and bounded streaming at the endpoint.
3. Reserving a second different media object before checking the run could leave publicly accessible orphan bytes. Repaired by conflict preflight before durable reservation and compensation on run-save failure.
4. Public `immutable` caching contradicted rights revocation. Repaired with max-age at most 300 seconds and no immutable directive.
5. A provider media ID alone was presented as success. Repaired with `FINISHED` polling and independent post verification.
6. Immediate toast evidence disappeared after reload. Repaired with a tenant/run-scoped durable publication-history endpoint and safe permalink reconstruction.

## Security Reviewer

Status: PASS for implemented scope

- CSRF and `social:publish` protect mutation routes.
- Rights attestation identity is server-authoritative.
- Public capability is 256-bit HMAC-derived; only SHA-256 digest is indexed publicly.
- Public route reveals no tenant/run/account metadata and returns generic 404.
- Random, expired and revoked capabilities fail closed.
- Exact bytes and SHA-256 are revalidated before provider HTTP.
- General and political publication flags remain separately disabled by default.
- Unknown provider outcomes block replay.
- No raw caption, token, signing key or image bytes enter receipts/logs.

## Privacy Reviewer

Status: PARTIAL — human/production storage gate retained

- Alt text and rights subject are tenant-bound; public delivery exposes only image bytes.
- Capability TTL defaults to 24 hours and is bounded to 15 minutes–7 days.
- Pre-Greenlight revocation immediately invalidates origin access; caches may retain content for at most 300 seconds.
- Production object retention, deletion SLA, DPA/residency and post-publication provider deletion remain external decisions.

## Red Team Agent

Status: PASS

Scenarios:

- wrong MIME/truncated JPEG/wrong aspect/oversize/missing rights/missing alt → rejected;
- valid image above global 1 MiB limit → accepted only on media route;
- 8 MiB + 1 → HTTP 413;
- random/expired/revoked capability → generic 404;
- tenant mismatch → no media disclosure;
- media upload after Greenlight → 409;
- media revocation after Greenlight → 409;
- expired approved media → 409 before provider HTTP, call count zero;
- container ERROR → failed, no media_publish;
- processing exhaustion → unknown, replay blocked;
- read-after-write mismatch → unknown;
- verified replay → same receipt, no second provider effect;
- unverified/non-Instagram permalink → no external link in UI.

## Independent Verifier

Status: PASS for deterministic local scope

- `./scripts/verify-python-locks.sh` → PASS (277 tests, 0 PostgreSQL-only skips locally);
- `npm test` → PASS (0 tests);
- `npm run lint` → PASS, zero warnings/errors;
- `npm run build` → PASS;
- focused Media Vault/publication/schema/backup/local-runner families → PASS;
- `git diff --check` → PASS;
- dependency lock/supply-chain review for Pillow 12.3.0 → PASS;
- nested containers → 0.

Not run locally:

- PostgreSQL tests requiring `AGENCY_TEST_DATABASE_URL`;
- K3s/Helm/Terraform apply-destroy verifier;
- real provider publication or deletion;
- cloud object storage;
- human accessibility/privacy/legal/campaign review.

## Release Gate

Decision: `DENY_RELEASE`

INC-022 is locally review-ready. Exact resume condition: publish exact branch SHA, pass exact-head CI including PostgreSQL/schema v5/package/Helm/Terraform/supply chain, complete distinct review, keep effects disabled, and require separate authorization for one sandbox post.
