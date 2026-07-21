# Acceptance Checklist

- [x] No raw idempotency key persisted or returned.
- [x] Compatible replay returns original response.
- [x] Incompatible key reuse returns uniform 409.
- [x] Provider/package work executes once.
- [x] SQLite restart replay passes.
- [x] PostgreSQL cross-replica concurrency passes.
- [x] Greenlight revoke increments fence and preserves history.
- [x] Stale or altered effect envelope is rejected.
- [x] External effects remain disabled.

- [x] Exact remote SHA and CI verified.
