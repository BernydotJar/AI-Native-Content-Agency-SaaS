# Acceptance Checklist

- [x] Public 401 variants are uniform and non-enumerating.
- [x] Authorization and CSRF 403 responses reveal no role/permission/token state.
- [x] Missing and foreign 404 responses are uniform and do not echo IDs.
- [x] Conflict responses reveal no current state or decision detail.
- [x] Validation errors omit submitted values and secret material.
- [x] Response headers include request correlation, no-store and baseline browser protections.
- [x] SQLite authorization/CSRF denials persist across restart and stay tenant-scoped.
- [x] PostgreSQL denial written by one instance is visible to another.
- [x] Audit/metrics/logs contain no credentials, tokens, request body or raw IP.
- [x] Threat model covers every trust boundary and STRIDE class.
- [x] Privacy model covers purpose, minimization, retention, deletion, backups and human/legal gates.
- [x] Full deterministic and PostgreSQL/recovery regressions pass.
- [x] Critic finds zero open CRITICAL/HIGH code findings in the slice.
