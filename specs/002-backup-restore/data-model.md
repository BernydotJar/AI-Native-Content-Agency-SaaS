# Backup Manifest

```json
{
  "schema_version": "agency-runtime-backup.v1",
  "backend": "sqlite | postgresql",
  "created_at": "RFC3339 UTC",
  "backup_file": "basename only",
  "bytes": 123,
  "sha256": "64 lowercase hex",
  "validation": "integrity_check_ok | pg_restore_list_ok",
  "source_identifier_sha256": "optional opaque digest",
  "tool": {"name": "manage-runtime-backup", "version": "0.7.0"}
}
```
