# INC-020 — Exact-once social publication authority

## Objective

Publish an approved X or Instagram artifact exactly once after account connection,
channel-specific media validation and Greenlight authority are proven.

## Required invariants

1. A durable publication intent exists before any provider request.
2. Intent identity binds tenant, account, run, channel, artifact ID/version/hash, media
   hash, Greenlight fencing token and budget/quota snapshot.
3. Only one fenced executor may call the provider.
4. Provider post/container IDs and sanitized receipt metadata persist before success.
5. Compatible replay returns the stored receipt without a second provider call.
6. Pending or unknown outcomes never retry automatically.
7. Greenlight revocation, account disconnect or artifact change invalidates unused intent.
8. X uses `POST /2/tweets`; Instagram creates a media container and then calls
   `/media_publish` only after media is reachable and supported.
9. Rate-limit, quota and spend errors are bounded and observable without provider bodies,
   tokens or content in logs.
10. CI and local verification use mock transports and perform zero real publication.

## Human gates

- current provider pricing/terms review;
- authorized X and Instagram sandbox accounts;
- explicit approval for one sandbox post per channel;
- production budget, rate limits and privacy/legal approval;
- merge and deployment approval.
