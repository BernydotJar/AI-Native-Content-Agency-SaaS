# INC-014 — Bounded multi-provider model gateway

## Objective

Implement real HTTP protocol clients for OpenAI, Anthropic, DeepSeek, Moonshot/Kimi
and Llama while keeping execution disabled by default and disconnected from durable run
creation until an outbound intent/receipt boundary exists.

## Supported contracts

- OpenAI Responses API.
- Anthropic Messages API.
- OpenAI-compatible chat completions for DeepSeek, Moonshot/Kimi and Llama endpoints.

## Acceptance

1. Exact provider selection and host allowlist are server-owned.
2. Provider credentials never enter public API, logs, persistence or receipts.
3. Input, output-token, response-byte and timeout limits fail closed.
4. Redirects, environment proxies and automatic retries are disabled.
5. Errors do not reflect provider bodies, prompts or credentials.
6. Receipt metadata contains only provider/model/request ID/token counts and hashes.
7. Gateway is disabled by default.
8. No public inference route or automatic run integration exists.
9. Production package proves the disabled boundary.
10. Tests use local mock transports and make zero real provider calls.

## Non-goals

- enabling model execution for end users;
- connecting inference to `run.create`;
- spending provider credits;
- per-tenant provider routing;
- durable outbound intent/receipt reconciliation;
- privacy/legal approval for prompt transfer;
- final cross-product E2E.

## Next safety boundary

Before inference can be connected to a run, a separate increment must persist an
outbound intent before the request, fence ownership, persist the successful receipt
before completion, reuse compatible receipts and block uncertain states without retrying.
