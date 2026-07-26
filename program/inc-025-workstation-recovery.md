# INC-025 Workstation Recovery Checkpoint

Date: 2026-07-26

## Result of the controlled external-effect program

No Instagram post was published.

Three governed provider attempts reached Instagram container creation and were rejected before a container ID or post ID was recorded. Operation `002` never reached the provider because its idempotency binding conflicted during preparation.

The final diagnostic attempt recorded this bounded tuple:

- phase: `instagram_container_create`
- HTTP status: `401`
- provider code: `190`
- provider subcode: `0`
- error type: `OAuthException`
- provider container ID: none
- provider post ID: none

Two separate read-only identity probes, one unversioned and one against Graph `v24.0`, returned the same `401 / 190` result. The stored Instagram User credential was therefore invalid or expired.

The invalid encrypted connection was removed through the governed disconnect endpoint. The tenant audit ledger contains `social.disconnected`. At the last verified workstation state:

- `AGENCY_SOCIAL_PUBLICATION_ENABLED=false`
- `AGENCY_POLITICAL_PUBLICATION_ENABLED=false`
- `AGENCY_POLITICAL_PAID_MEDIA_ENABLED=false`
- Instagram channel state: `not_connected`
- OAuth start: available
- publishing: unavailable

## Durable local commits in the persistent workstation

- `308599b` — prepare bounded neutral Instagram effect
- `6c8f815` — align Instagram container transport
- `1a0ad8b` — bind second neutral attempt to a unique run
- `50f9a17` — persist safe provider rejection diagnostics
- `6af2fb5` — freeze diagnostic neutral attempt
- `5d40ce4` — record invalid Instagram authorization

These commits were not pushed before the Cloud Sandbox MCP session terminated.

## OAuth lifecycle repair present but not yet frozen

The persistent worktree contains an uncommitted repair that:

1. exchanges the authorization-code credential for a long-lived Instagram User credential before creating a connection;
2. verifies the professional profile with the long-lived credential;
3. persists an explicit token expiry;
4. blocks expired credentials before intent reservation and provider HTTP;
5. deletes the encrypted connection and returns `social_connection_reauthorization_required` when Meta returns code `190`;
6. refreshes the console channel state and displays an explicit reconnect action.

Focused evidence completed before the workstation session ended:

- SocialOAuthService: 6 PASS
- Social OAuth API: 10 PASS
- SocialPublicationAuthority: 15 PASS
- code-190 connection invalidation API test: PASS
- frontend reconnect mapping: 2 PASS
- lint: 0 warnings/errors
- production frontend build: PASS

The final combined regression and hash-locked wheel were not completed after the last OAuth lifecycle edits because the Cloud Sandbox MCP session terminated.

## Exact resume condition

1. Reconnect workspace `7759306b-d1ea-40ed-92dc-b78424c749ba` without deleting its persistent checkout, home or SQLite state.
2. Inspect `agent/inc-025-neutral-instagram-publication`; do not reset the worktree.
3. Run the focused OAuth/publication suites, complete frontend regression and `./scripts/verify-python-locks.sh`.
4. Reconcile compliance hashes, program state and secret scans.
5. Commit the OAuth lifecycle repair, publish the exact local commit chain, open a draft PR and require all exact-head CI jobs.
6. Restart the public runtime from the reviewed head with all publication switches false.
7. Complete a fresh interactive Instagram OAuth flow.
8. Require a read-only Graph profile probe to return the expected account ID and username before creating any publication intent.
9. Only then create a new operation ID and permit one separately controlled neutral effect.

No retry of intents from operations `001`, `003` or `004` is permitted.
