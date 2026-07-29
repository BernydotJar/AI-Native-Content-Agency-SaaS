# Acceptance Checklist

- [x] Source remains readable and unchanged.
- [x] Manifest schema/checksum/size validate.
- [x] No credentials or content appear in logs/manifest.
- [x] Tamper fails before mutation.
- [x] Existing target is protected.
- [x] SQLite integrity and representative state pass.
- [x] PostgreSQL list/restore/schema/counts pass.
- [x] Cleanup removes ephemeral databases/artifacts.
- [x] Production restore remains human-gated.
