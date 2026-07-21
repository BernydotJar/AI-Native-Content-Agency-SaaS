# Quickstart

```bash
python3 scripts/manage-runtime-backup.py sqlite-backup \
  --database /var/lib/agency/runtime.sqlite3 \
  --output-dir /secure/backup

python3 scripts/manage-runtime-backup.py sqlite-restore \
  --manifest /secure/backup/agency-sqlite-...json \
  --target /restore-test/runtime.sqlite3
```

Persistent target replacement requires `--replace` and an explicit human destructive-data gate.
