# INC-025 Tasks — Public Media Signing Keyring

1. Add `INC-025` to the canonical task ledger and dependency graph.
2. Record the bounded spec and approval through Graph Harness SDLC.
3. Implement strict preferred and legacy keyring parsing.
4. Persist `public_signing_key_id` in SQLite and PostgreSQL schema v7.
5. Sign new media with the active key and replay existing media with its stored key.
6. Add migration, restart, mixed-key, missing-key, malformed-config and tamper-negative tests.
7. Wire local runner, neutral exercise, Helm and Terraform to pre-existing secret references.
8. Update the runbook, critique findings, open issues, risk/traceability and production review.
9. Execute producer, critic/red-team, localized fixer, independent verifier and production gates.
10. Publish a draft PR, verify exact-head CI, close the node and merge only after all gates pass.

## Stop Conditions

- a change would expose or create key material;
- migration cannot preserve existing records;
- replay can silently sign with a different key;
- PostgreSQL compatibility or rollback is not proven;
- an action requires deployment, infrastructure apply, provider deletion, publication or another external effect.
