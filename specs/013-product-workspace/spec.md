# INC-013 — Product workspace and provider control plane

## Objective

Replace the primary demo-oriented surface with a tenant-scoped product workspace that
prioritizes campaign execution, evidence, outputs and Greenlight. Move infrequent
appearance and connection settings behind progressive disclosure and expose truthful
server-derived provider configuration without sending secrets to the browser.

## User outcomes

1. An operator sees the governed mission form first.
2. A tenant credential is entered once inside a modal and disappears after the
   HttpOnly session exchange.
3. Appearance is managed in Settings and never competes with the mission.
4. The topology remains visible and reflects the current durable run.
5. Memory is represented as applied context/evidence, not an implementation tutorial.
6. Tool Fabric is represented as operational provider, integration and station state.
7. The product can run locally as SPA + FastAPI + SQLite from one command.

## Provider catalog

The authenticated read-only catalog contains exactly:

- OpenAI;
- Anthropic;
- DeepSeek;
- Moonshot / Kimi;
- Llama.

Configuration state is derived exclusively server-side. Raw credentials and credential
environment names never appear in API responses, logs, persistence or browser storage.

## Non-goals

- executing paid model inference;
- enabling media, ads, browser automation or publication adapters;
- selecting a provider from untrusted browser input;
- storing provider secrets in the application database;
- claiming production release approval;
- running the final cross-product E2E suite before the planned final gate.

## Security and privacy invariants

- provider endpoints are absolute HTTPS URLs without embedded credentials;
- provider API is GET-only and authenticated;
- tenant identity remains server-derived;
- all external effects remain disabled;
- release and cloud decisions remain `DENY_RELEASE` / `DENY_APPLY`;
- provider readiness is configuration evidence, not execution evidence.
