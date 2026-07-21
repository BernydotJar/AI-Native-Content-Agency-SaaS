# Quickstart

Validate the complete repository operability contract:

```bash
npm run validate:operability
```

Render alerts for a cluster that already has the Prometheus Operator:

```bash
helm template agency infra/helm/ai-native-content-agency \
  --set observability.prometheusRule.enabled=true
```

Emit backup freshness metrics after a validated SQLite backup:

```bash
python3 scripts/manage-runtime-backup.py sqlite-backup \
  --database /var/lib/agency/runtime.sqlite3 \
  --output-dir /var/backups/agency \
  --metrics-file /var/lib/node-exporter/textfile/agency-backup.prom
```

These commands create no external monitor, pager, object store, KMS key or cloud resource.
