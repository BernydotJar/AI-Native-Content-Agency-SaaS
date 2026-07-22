# INC-014 Bounded Model Gateway Review

Updated: 2026-07-22
Implementation commit: `56f9ee8`
Branch: `agent/inc-014-model-gateway`
Status: `review`

## Objective

Implement real provider protocol clients and strict execution policy without exposing a
public inference route, connecting external effects to durable runs or using real
credentials/spend during verification.

## Implemented

- OpenAI Responses client.
- Anthropic Messages client.
- OpenAI-compatible chat clients for DeepSeek, Moonshot/Kimi K3 and Llama.
- Exact server-side provider selection and egress-host allowlist.
- HTTPS-only endpoints without embedded credentials, query strings or fragments.
- IP literal, localhost and `.local` egress rejection.
- Environment proxy and redirect disabling.
- One attempt only; no automatic retry.
- Input-character, output-token, response-byte and timeout limits.
- Strict provider response parsing and sanitized errors.
- Secret-free in-memory receipt with provider/model/request ID/token counts and request/output hashes.
- Safe gateway status in authenticated `GET /api/v1/providers`.
- `httpx==0.28.1` moved into the hash-locked runtime dependency set and license inventory.
- Production package assertions that the gateway is disabled and no inference route exists.

## Critic findings

| Finding | Severity | Resolution |
|---|---:|---|
| Protocol-ready provider state could be mistaken for active run integration. | HIGH | UI/API expose `durable_outbound_receipt=false` and `automatic_run_integration=false`; no POST route exists. |
| Runtime package initially omitted `httpx`. | HIGH delivery | Added it to `setup.cfg`/runtime input, regenerated locks, updated license inventory and reverified the image. |
| Provider errors could reflect prompt, upstream body or secret. | HIGH security | Errors use fixed bounded messages and never include response body, request content or credential. |
| Automatic retries could duplicate spend. | HIGH financial/idempotency | Gateway performs one attempt only; no retry loop or transport retry is configured. |
| Host allowlist could accept local/IP targets. | HIGH SSRF | Exact hosts only; IP literals, localhost and `.local` fail closed; redirects and env proxies are disabled. |
| Connecting the gateway directly to current `run.create` could duplicate spend after a persistence failure. | CRITICAL design | Gateway remains disconnected. Next increment must persist outbound intent/fence/receipt before activation. |

## Verifier evidence

```text
Locked Python wheel                       PASS — 145 tests, 11 PostgreSQL skips
PostgreSQL shared runtime                 PASS — 145/145
Frontend                                  PASS — 26/26
Oxlint / TypeScript / Vite                 PASS
Chromium accessibility regression          PASS
Buildah non-root package                   PASS
Packaged gateway disabled                  PASS
Packaged inference route absent            PASS
Provider secrets absent                    PASS
K3s/Helm/Terraform plan/apply/destroy      PASS — agentless control plane
Actionlint                                 PASS
Gitleaks history/worktree                  PASS — zero leaks
Compliance                                PASS — DENY_RELEASE, 0 active providers
Real provider network calls                NOT_RUN BY DESIGN
Provider credentials/spend                 NOT_USED
Final cross-product E2E                    DEFERRED TO FINAL PROGRAM GATE
```

## Exact boundary

`ModelGateway.complete()` is exercised only by tests with `httpx.MockTransport`. No
application route, orchestrator or run service invokes it. `AGENCY_MODEL_EXECUTION_ENABLED`
defaults to `false`; production package verification requires that disabled state.

## Required next increment

Before any real inference can be attached to a run:

1. persist an outbound intent before the provider request;
2. bind it to tenant, run, command, provider, model, payload hash and budget;
3. fence exclusive execution;
4. persist the successful receipt before completing the run;
5. reuse compatible receipts on replay;
6. block `pending/unknown` states without another provider call;
7. provide reconciliation and circuit-breaker controls;
8. obtain privacy/legal and explicit egress/spend authorization.

## Delivery blocker

The official Cloud Sandbox `git_push` connector fails before invoking Git because its
internal ownership setup attempts to start Docker and cannot create the Docker NAT
chain in this environment. Repository ownership was normalized and `git fsck` passed;
the connector failed again with the same pre-Git error. No force push or alternate ref
creation mechanism was used.
