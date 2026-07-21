# Acceptance Checklist

- [x] SLO/error-budget catalog validates.
- [x] Request histogram is cumulative and bounded-label.
- [x] Prometheus rule/catalog parity validates.
- [x] Healthy and failure alert exercises pass.
- [x] Backup freshness textfile is private and atomic.
- [x] Helm rules are opt-in and render correctly.
- [x] Rollback drill restores previous revision/configuration.
- [x] No external resource, pager or object store is created.
- [ ] Exact remote SHA and CI verified.
