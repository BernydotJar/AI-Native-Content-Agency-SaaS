# Political Publication Runbook

## Purpose

This runbook governs political-content creation and organic social publication. It does not authorize paid political advertising, establish legal compliance, verify a candidate mandate or replace accountable human review.

## Independent kill switches

All switches default to `false` and must be evaluated independently:

```dotenv
AGENCY_POLITICAL_CONTENT_ENABLED=false
AGENCY_SOCIAL_PUBLICATION_ENABLED=false
AGENCY_POLITICAL_PUBLICATION_ENABLED=false
AGENCY_POLITICAL_PAID_MEDIA_ENABLED=false
```

- `AGENCY_POLITICAL_CONTENT_ENABLED` permits creation of structured political runs. It does not permit any external effect.
- `AGENCY_SOCIAL_PUBLICATION_ENABLED` enables the general durable social-publication authority.
- `AGENCY_POLITICAL_PUBLICATION_ENABLED` separately enables political organic publication.
- `AGENCY_POLITICAL_PAID_MEDIA_ENABLED` separately permits creation of paid-mode planning records. The organic endpoint still rejects `publication_mode=paid` and cannot execute ads.

## Required authorities

A political run can receive an approved Greenlight only when:

1. claims have source and locator evidence;
2. requested verified claims and legal approval were attested by an authenticated principal;
3. Critique reports `publication_eligible=true`;
4. the Greenlight approver is a different authenticated subject from the legal/electoral reviewer;
5. a `political_compliance_record` is generated and included in the approved artifact envelope.

The compliance record contains jurisdiction and publication mode plus SHA-256 digests for disclosure and claim/source bindings. It records the legal reviewer and independent Greenlight approver. Its retention state is `durable_until_governed_deletion`; this label is not a fabricated retention duration.

## Final organic-publication confirmation

Immediately before reserving a publication intent, the operator must type exactly:

```text
PUBLICAR POLITICA <run_id> <channel_id>
```

The server compares the exact phrase, computes SHA-256 and persists only the digest in the intent binding and audit evidence. The raw phrase is not stored in the run, intent, receipt or audit payload.

## Paid boundary

`publication_mode=paid` always fails closed on the organic endpoint with `paid_publication_requires_ads_authority`. Turning on `AGENCY_POLITICAL_PAID_MEDIA_ENABLED` does not change that behavior. Paid political advertising requires a future ads-specific authority with its own account, budget, targeting, disclosure, receipt and reconciliation controls.

## Neutral sandbox sequence

Use a dedicated authorized test account and this neutral content before candidate material:

> Prueba técnica de publicación
>
> Esta publicación verifica el flujo de aprobación, media y confirmación del sistema. No corresponde a una campaña electoral.

Execution order:

1. confirm the exact account ID and username;
2. keep paid mode disabled;
3. create an organic political run with jurisdiction, disclosure and evidence;
4. have reviewer A attest evidence/legal review;
5. have reviewer B issue Greenlight;
6. inspect the exact copy and media hashes in the approved envelope;
7. enable general and political publication switches for the controlled window;
8. type the exact final phrase;
9. verify the provider receipt, permalink, timestamp, account and content binding;
10. disable political publication immediately after the test window.

## Kill and rollback

For pre-publication stop:

1. set `AGENCY_POLITICAL_PUBLICATION_ENABLED=false`;
2. revoke Greenlight to fence unused authority;
3. disconnect the social account if credentials may be compromised;
4. reconcile any `unknown` intent before attempting another effect.

For a verified published post, disabling the local switch does not delete the provider object. Provider deletion is a separate external effect and requires explicit account authority, state inspection, evidence retention and accountable approval.

## Evidence required for production review

- exact repository SHA and exact-head CI receipt;
- independent reviewer decision;
- connected-account ownership evidence;
- final copy/media hashes and Greenlight envelope;
- durable intent and verified receipt;
- provider permalink/timestamp/account read-after-write evidence;
- rollback owner and decision record;
- jurisdiction-specific legal/campaign approval outside the software.

## Verified neutral sandbox execution — 2026-07-27

The governed neutral sequence completed successfully on the authorized laboratory account `@beesheep2`:

```text
operation_id: inc025-neutral-instagram-005
account_id: 27525095797156898
run_id: run-90534aa784e451aa
provider_container_id: 18609504208033520
provider_post_id: 18027585197670069
verification_status: verified
permalink: https://www.instagram.com/p/DbRpnHHoB7j/
```

Approved bindings:

```text
caption_sha256: be237c368962c6d180929a7a8489459c31f561565ecb7e8e854dc16684909803
media_sha256: e542083bf71fbf335539896dc5df79eb1d7eb24319c827948a21809ccf8286f5
media: JPEG 1080×1350
```

The effect used two distinct authenticated subjects, one exact-once durable intent and one read-after-write verified provider receipt. The raw political confirmation and public media capability URL were not persisted in the safe receipt. Both publication switches were closed automatically after the effect and paid media remained disabled.

This receipt proves one bounded sandbox publication. It does not change the global `DENY_RELEASE` or `DENY_APPLY` decisions and does not authorize candidate content, additional posts or paid media.
