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

## Token health blocker

Attempt `004` preserved the safe provider tuple `instagram_container_create / HTTP 401 / code 190 / OAuthException` and no container or post ID. Two separate read-only identity probes, one against the unversioned profile route and one against the pinned Graph version, returned the same `401 / 190` result. This proves the stored Instagram User access token is invalid or expired rather than a media, caption or publish-parameter defect.

No further publication attempt is permitted until a fresh interactive OAuth flow succeeds. The callback must exchange the authorization-code token for a long-lived Instagram User token, persist its expiry, verify the profile with that long-lived token and force the UI back to `not_connected` when Meta later returns code `190`.

## Final verified outcome

INC-025 completed on 2026-07-27 with operation `inc025-neutral-instagram-005` after a fresh OAuth connection to the fixed account ID and username.

The final execution satisfied all acceptance criteria:

- exactly one new run and idempotency binding;
- two distinct authenticated reviewers;
- approved `political_compliance_record` in the Greenlight envelope;
- immutable JPEG `1080×1350` with SHA-256 `e542083bf71fbf335539896dc5df79eb1d7eb24319c827948a21809ccf8286f5`;
- caption SHA-256 `be237c368962c6d180929a7a8489459c31f561565ecb7e8e854dc16684909803`;
- one provider container and one provider post;
- provider read-after-write status `verified`;
- account username `beesheep2` and account ID `27525095797156898` matched;
- one durable intent with `status=succeeded`;
- raw confirmation absent from durable state and safe receipts;
- both publication switches returned to `false` through the bounded window cleanup.

Safe receipt identifiers:

```text
run_id: run-90534aa784e451aa
intent_id: social-publication-intent-a9f246300d21bd0aee790fb33755385ba14150023e3f4587
provider_container_id: 18609504208033520
provider_post_id: 18027585197670069
permalink: https://www.instagram.com/p/DbRpnHHoB7j/
published_at: 2026-07-27T00:13:11+0000
```

The OAuth recovery required a bounded compatibility path for the exact unsupported extension response `HTTP 400 / code 100 / IGApiException`. The initial Instagram User credential is accepted only after professional-profile validation, is encrypted server-side and is assigned a maximum local lifetime of 3,300 seconds. Code `190` and all other rejection tuples remain fail-closed.

One sandbox success is evidence for the controlled integration path only. Release and cloud-apply recommendations remain denied pending the wider production program.
