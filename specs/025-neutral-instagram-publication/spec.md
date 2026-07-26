# INC-025 — Neutral Instagram Publication Receipt

## Objective

Execute exactly one neutral, organic Instagram image publication on the authorized laboratory account through the governed product path, then disable publication authority and preserve a read-after-write verified receipt.

## Safety boundary

- Account is fixed by both username and provider account ID.
- Payload is a technical verification notice with no electoral persuasion, no targeting and no paid media.
- Two existing authenticated subjects remain responsible for legal/evidence review and Greenlight.
- Media is an immutable 1080×1350 JPEG stored in Media Vault and included in the Greenlight envelope.
- Preparation requires general and political publication flags to be false.
- Execution requires both flags true, paid media false, an unexpired manifest and the exact political confirmation.
- One idempotency binding is used; a second effect is not attempted.
- Provider success requires read-after-write verification of account, caption hash, media hash, media type, permalink and timestamp.
- Raw credentials, provider token, public capability URL and raw final confirmation are never written to receipts.
- Publication authority is disabled immediately after the controlled effect.

## Acceptance criteria

1. `prepare` fails if either publication switch is enabled.
2. `prepare` proves account/scopes, creates a durable run, validates Critique, attaches governed media, verifies public bytes and obtains independent Greenlight.
3. The manifest contains exact copy/media hashes and no secret/capability/raw-confirmation value.
4. `execute` fails unless both publication switches are enabled and paid mode remains disabled.
5. `execute` requires the exact confirmation and explicit external-effect acknowledgement.
6. Exactly one durable publication intent reaches `succeeded`.
7. Provider read-after-write verification matches account, caption and media.
8. A safe receipt records permalink, timestamp, provider IDs and hashes.
9. Both publication switches return to false immediately after execution.
10. Program state keeps `DENY_RELEASE` and `DENY_APPLY`; one sandbox post is not production authorization.

## First controlled attempt and transport correction

The first controlled attempt reserved one exact-once intent and was rejected before a provider container ID was recorded. No provider post ID or verified receipt exists. Both publication switches were closed automatically and the failed intent remains immutable.

The investigation found that the publication client differed from Meta's current Instagram Login contract in three ways. INC-025 now:

- pins `AGENCY_INSTAGRAM_GRAPH_API_VERSION=v24.0`;
- creates image containers with `multipart/form-data` fields for `image_url` and `caption`;
- supplies `creation_id` as the `media_publish` request parameter;
- captures only safe structured rejection metadata: phase, HTTP status, provider code, subcode and error type.

Provider messages, response bodies, tokens, captions and media capability URLs are not logged. A later attempt must use a new operation, run and idempotency binding; the failed intent is never retried.

The second governed attempt used the versioned multipart contract and a distinct run, but Meta again rejected before a container ID was recorded. Its switches were closed automatically and no post exists. Because the runtime restart replaced the transient log, INC-025 now persists the bounded safe rejection tuple in the durable intent failure reason before any further attempt.
