# Acceptance Checklist

- [ ] No raw idempotency key persisted or returned.
- [ ] Compatible replay returns original response.
- [ ] Incompatible key reuse returns uniform 409.
- [ ] Provider/package work executes once.
- [ ] SQLite restart replay passes.
- [ ] PostgreSQL cross-replica concurrency passes.
- [ ] Greenlight revoke increments fence and preserves history.
- [ ] Stale or altered effect envelope is rejected.
- [ ] External effects remain disabled.
