# Acceptance checklist

- [x] Intent exists before provider HTTP.
- [x] One exact binding has one fenced executor.
- [x] Compatible replay performs zero additional provider calls.
- [x] Changed binding conflicts before HTTP.
- [x] Output and bounded receipt are durable.
- [x] Persistence failure after provider success blocks retry.
- [x] Unknown outcome requires idempotent reconciliation.
- [x] Replay repairs run attachment and audit without provider HTTP.
- [ ] SQLite contracts passed locally; exact-head PostgreSQL rerun is delegated to CI by operator instruction.
- [x] Provider/model selection remains server-side.
- [x] Local MockTransport fixture blocks real sockets; installed-image rerun is delegated to exact-head CI.
- [x] Real provider credentials, egress and spend remain NOT_USED.
