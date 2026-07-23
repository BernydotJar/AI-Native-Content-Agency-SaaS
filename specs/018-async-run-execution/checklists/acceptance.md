# Acceptance checklist

- [ ] Run returns before all stations complete.
- [ ] Only one fenced worker executes a run.
- [ ] Progress survives restart.
- [ ] Completed station cannot execute twice.
- [ ] UI observes at least queued, processing and terminal states.
- [ ] No fake timer or optimistic station completion exists.
