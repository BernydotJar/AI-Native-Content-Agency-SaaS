# INC-016 Cinematic Runtime UX Review

Updated: 2026-07-22
Branch: `agent/inc-016-cinematic-runtime-ux`
Status: `review`

## Corrected interpretation

The requested change was not to remove the cinematic product language. It was to stop
using simulations, oversized explanatory surfaces and descriptive mock tooling as if
they were product capabilities.

The previous implementation over-corrected by removing the cinematic hero and the
station-inspection rhythm. This increment restores that visual grammar while preserving
one real runtime architecture.

## Product decisions

- Restore the orbital cinematic hero with metrics derived from session, run, providers
  and durable artifacts.
- Preserve `LIVE TOPOLOGY / FABRIC FLOW` as a primary product surface.
- Add a station inspector backed by `run.agent_states` and artifact IDs.
- Keep theme selection behind Settings.
- Keep the one-time tenant credential inside the secure connection dialog.
- Present memory as applied context and decisions, not as a large explanation of the
  Observe/Store/Search/Recall implementation.
- Present Tool Fabric as provider, integration and output state returned by the backend.
- Do not restore `simulationRuntime`, browser timers, synthetic Ads metrics, local mock
  campaigns or descriptive MCP cards.

## Critic findings

| Finding | Resolution |
|---|---|
| Cinematic presentation was incorrectly treated as equivalent to a demo. | Restored visual composition independently from execution semantics. |
| Topology lacked a useful station-detail surface after the simplification. | Added a real run-backed station inspector. |
| Empty-state copy still taught architecture rather than helping the operator act. | Replaced with compact run-oriented prompts. |
| Theme and API key could regress into the command surface during restoration. | Existing progressive-disclosure dialogs remain unchanged and covered by tests. |
| Restoring old components could revive mock behavior. | No deleted simulation component or simulation runtime was restored. |

## Evidence

```text
Frontend tests                       PASS — 26/26
TypeScript                           PASS
Oxlint                               PASS
Vite production build               PASS
Chromium 320px reflow                PASS
Chromium skip link                   PASS
Chromium progressive disclosure      PASS
Chromium keyboard theme dialog       PASS
Chromium premium lock                PASS
Chromium reduced motion              PASS
Chromium accessibility tree          PASS
Local full-stack configuration       PASS
Cinematic mock runtime references    0
```

## Runtime boundary

DeepSeek, OpenAI, Anthropic, Moonshot/Kimi and Llama configuration remains server-side.
This branch can display provider readiness, but it does not claim that model inference is
already connected to governed runs. Durable model-effect authority continues separately
in `INC-015`.
