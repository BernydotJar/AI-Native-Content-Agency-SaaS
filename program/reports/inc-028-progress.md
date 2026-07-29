# INC-028 Progress — Repeatable Social Sandbox

## Implemented

- distinct Instagram `repeatability-v2` copy and JPEG variant;
- deterministic caption/media hashes;
- X read-after-write verification after `POST /2/tweets`;
- verified X receipt fields: author, timestamp, permalink and content hash;
- mismatch-to-unknown and no-retry tests;
- neutral X prepare/execute/inspect harness;
- active local X callback updated to the current public origin.

## Verified locally so far

- neutral Instagram harness tests: 6 PASS;
- neutral X harness tests: 4 PASS;
- social publication authority/API: 25 PASS;
- no real provider effect executed in INC-028 yet.

## External gates

- Instagram channel is currently `not_connected` because the deliberately bounded credential expired.
- X app credentials are absent; OAuth start remains unavailable until an API Key and Secret are configured.

## Safety state

- general publication: false;
- political publication: false;
- political paid media: false;
- no new durable provider intent reserved.
