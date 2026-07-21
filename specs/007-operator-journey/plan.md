# Plan

1. Extend the typed runtime client with `getRun` and retry metadata.
2. Introduce a bounded operator-notice classifier.
3. Add explicit session-restore and audit state machines.
4. Derive capabilities from the server-owned role.
5. Add stale-run refresh and reauthentication recovery.
6. Add RED tests for role, error, audit and refresh behavior.
7. Run focused frontend gates, then cross-workstream package/program gates.
8. Critique for authorization leakage, misleading success and inaccessible state changes.
