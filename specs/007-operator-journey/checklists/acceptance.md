# Acceptance Checklist

- [ ] Role capabilities are server-derived and visible.
- [ ] Viewer/approver/operator/admin controls are correct.
- [ ] Session restoration has loading and failure states.
- [ ] 401 clears protected state.
- [ ] 403 does not expose permission names.
- [ ] Conflict/not-found can refresh a known run.
- [ ] Rate limit and dependency outage have safe retry guidance.
- [ ] Audit has loading, empty, success and error states.
- [ ] Idempotency keys survive ambiguous retries.
- [ ] Publication remains disabled.
