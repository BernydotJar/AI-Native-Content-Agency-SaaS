# Acceptance checklist

- [x] Publication intent persists before the provider request.
- [x] One fenced executor may publish.
- [x] Compatible replay never creates a second post.
- [x] Replay repairs a missing success-audit event without a second provider call.
- [x] Manual reconciliation is idempotent for identical evidence and conflicts on drift.
- [x] Unknown outcome blocks automatic retry.
- [x] Disconnect and Greenlight revocation invalidate unused authority.
- [x] Instagram cannot publish without supported reachable media.
- [x] Tokens, provider bodies and post content stay out of logs/audit.
- [x] CI makes zero real X or Meta publication requests.
- [x] Package smoke executes the installed authority with MockTransport and a socket guard.
- [x] Async worker resolves tenant runtime before the durable run lock; no lock inversion remains.
- [ ] Authorized sandbox receipts are reconciled before production review.
