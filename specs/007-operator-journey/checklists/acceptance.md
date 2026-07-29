# Acceptance Checklist

- [x] Role capabilities are server-derived and visible.
- [x] Viewer/approver/operator/admin controls are correct.
- [x] Session restoration has loading and failure states.
- [x] 401 clears protected state.
- [x] 403 does not expose permission names.
- [x] Conflict/not-found can refresh a known run.
- [x] Rate limit and dependency outage have safe retry guidance.
- [x] Audit has loading, empty, success and error states.
- [x] Idempotency keys survive ambiguous retries.
- [x] Publication remains disabled.
