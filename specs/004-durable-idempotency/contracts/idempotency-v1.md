# `idempotency.v1`

Required header for governed business mutations:

```http
Idempotency-Key: <8-200 safe characters>
```

Compatible replay returns the original success response. Incompatible reuse returns:

```json
{
  "code": "idempotency_conflict",
  "detail": "idempotency key conflicts with a prior request",
  "request_id": "..."
}
```

Missing or malformed headers use the standard sanitized validation contract. Keys are tenant- and operation-scoped and are never returned.
