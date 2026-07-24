# INC-015 — Durable model effect authority

## Problem

The bounded five-provider gateway can execute real protocols but has no durable economic
boundary. A provider may succeed and local persistence may fail; an automatic retry could
repeat token spend and return a different output. Provider readiness must not be treated as
run authority.

## Objective

Attach an explicit model-completion command to a governed run only after persisting an exact
intent and fencing token. Persist output and a bounded receipt before returning success,
reuse one result across compatible retries and block pending or unknown outcomes until an
administrator reconciles or revokes them.

## Exact binding

Each intent binds:

- tenant and run;
- target station and source artifact ID/hash;
- selected server-side provider, model and endpoint host;
- canonical system/user request hash and output-token cap;
- operator instruction hash;
- approved maximum cost in micros;
- idempotency-key digest and unique effect-binding digest.

Raw idempotency keys, provider credentials and prompt text are never stored in the intent
record, receipt, audit event or logs. Successful output is stored as governed run content and
is subject to retention, deletion and legal-hold policy.

## States

`pending → succeeded | unknown | failed | revoked`

- `pending`: one fenced executor may call the provider; replay is blocked.
- `succeeded`: compatible replay returns the stored output/receipt without HTTP.
- `unknown`: provider outcome is ambiguous; automatic retry is prohibited.
- `failed`: known pre-effect or provider rejection; automatic retry is prohibited.
- `revoked`: unused authority is invalidated and its fence incremented.

## API integration

An authenticated browser administrator explicitly invokes:

```text
POST /api/v1/runs/{run_id}/model-effects/{station}
```

The server loads the source artifact, constructs the prompt, resolves provider/model from
server configuration, executes through the durable authority and attaches one stable
`model_completion` artifact to the run. Runs must be `awaiting_greenlight`; completed,
rejected, revoked or actively running runs are not mutable through this command.

Manual reconciliation is a separate admin command with its own idempotency digest and exact
evidence binding. A compatible replay repairs missing run attachment/audit evidence without
a second provider request.

## Security and correctness invariants

1. Intent persists before provider HTTP.
2. Only one fenced executor owns one binding across SQLite/PostgreSQL replicas.
3. Provider/model cannot be selected by the browser.
4. A successful output and receipt persist before run attachment is acknowledged.
5. Different idempotency keys for one binding reuse one result.
6. Same key with changed binding conflicts before HTTP.
7. Pending/unknown/failed/revoked never execute automatically.
8. Persistence failure after provider success leaves a blocked uncertain state.
9. Run attachment and deterministic audit are repairable on replay.
10. Provider response text, prompts and credentials never enter logs or audit payloads.
11. Default configuration performs zero model HTTP and zero spend.
12. Verification uses MockTransport and a socket guard only.

## Non-goals

- Automatic model calls for every station.
- Browser entry of provider credentials.
- Dynamic provider/model selection by the tenant request.
- Provider pricing claims or production spend authorization.
- Real provider calls during CI/local verification.
- Replacing semantic/adversarial evaluations required by INC-010.
