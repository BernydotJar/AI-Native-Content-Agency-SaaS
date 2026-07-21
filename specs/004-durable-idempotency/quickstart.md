# Quickstart

```bash
curl -X POST /api/v1/runs \
  -H 'Authorization: Bearer ...' \
  -H 'Idempotency-Key: run-create-client-0001' \
  -H 'Content-Type: application/json' \
  --data @brief.json
```

Retry the exact request with the exact key. Use a new key for a genuinely new command. Never reuse a key with changed content.
