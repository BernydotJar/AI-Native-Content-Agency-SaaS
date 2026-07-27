# INC-025 Completion and Recovery Receipt

Date completed: 2026-07-27

## Final result

The controlled neutral Instagram publication completed successfully on the authorized laboratory account `@beesheep2`.

```text
operation_id: inc025-neutral-instagram-005
account_id: 27525095797156898
run_id: run-90534aa784e451aa
intent_id: social-publication-intent-a9f246300d21bd0aee790fb33755385ba14150023e3f4587
provider_container_id: 18609504208033520
provider_post_id: 18027585197670069
verification_status: verified
permalink: https://www.instagram.com/p/DbRpnHHoB7j/
published_at: 2026-07-27T00:13:11+0000
```

Approved immutable bindings:

```text
caption_sha256: be237c368962c6d180929a7a8489459c31f561565ecb7e8e854dc16684909803
media_sha256: e542083bf71fbf335539896dc5df79eb1d7eb24319c827948a21809ccf8286f5
media dimensions: 1080×1350
```

The final durable state contains exactly one succeeded intent for the run. The raw confirmation phrase and public media capability URL are absent from the safe receipt. Both publication switches were returned to `false` automatically and paid media remained disabled.

## Historical failed attempts retained

Operations `001`, `003` and `004` remain immutable failed evidence and must never be retried. Operation `002` never reached the provider because its idempotency binding conflicted during preparation.

The diagnostic sequence established:

- earlier attempts were rejected before a provider container or post ID;
- attempt `004` preserved `instagram_container_create / HTTP 401 / code 190 / OAuthException`;
- two read-only profile probes returned the same `401 / 190` result;
- the invalid encrypted connection was removed through the governed disconnect path;
- no hidden retry or duplicate provider object existed.

## OAuth recovery and compatibility finding

The original working callback commit `bd9532e` stored the Instagram User credential returned by the authorization-code exchange after professional-profile validation. A later hardening change made a second long-lived exchange mandatory.

For this Instagram Login app, Meta rejected that extension with the exact safe tuple:

```text
phase: instagram_long_lived_token_exchange
HTTP: 400
provider code: 100
provider type: IGApiException
```

INC-027 restored compatibility without returning to an indefinite credential:

1. use an initial credential directly when its returned lifetime is already at least one day;
2. otherwise attempt the supported `GET /access_token` extension with Bearer authorization;
3. for the exact unsupported tuple only, validate the Professional account and use the initial encrypted credential for at most 3,300 seconds;
4. reject code `190`, personal accounts and every other tuple;
5. expire the connection locally and require fresh OAuth.

## Reviewed delivery chain

Relevant reviewed merges:

```text
PR #19 merge: f93ff8a74dd168f8e682ce5c65c6358c2ba51a9a
PR #20 merge: 82f3f8ee5f3bf1b838d5b7c131964eeac0d6e831
PR #21 merge: 4c02b12fca8d5463ccfda67a119c639f1648f0d1
```

Exact-head CI for the final OAuth compatibility fix:

```text
head: 660476f6e4b9e6aecf9d2435fd1e51d75ec8cd7d
workflow: 30224979325
result: 8/8 SUCCESS
```

Local freeze before merge:

```text
backend wheel: 301 PASS
PostgreSQL-only local: 25 expected skips
frontend: 50 PASS
lint/build: PASS
program/compliance: PASS
secret scan: PASS
nested containers: 0
```

## Final safety state

Immediately after the verified effect:

```text
AGENCY_SOCIAL_PUBLICATION_ENABLED=false
AGENCY_POLITICAL_PUBLICATION_ENABLED=false
AGENCY_POLITICAL_PAID_MEDIA_ENABLED=false
runtime health: 200
public health: 200
connection_state: connected
publishing_available: false
```

The connection was intentionally retained for read-only status and later governed use, but its bounded credential expiry requires reauthorization after the configured lifetime.

## Release decision

This receipt closes the neutral sandbox objective. It does not authorize additional external effects.

```text
release_decision: DENY_RELEASE
cloud_decision: DENY_APPLY
```
