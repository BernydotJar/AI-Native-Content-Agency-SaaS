# INC-018 Durable Asynchronous Run Execution Review

Updated: 2026-07-23
Implementation commit: `3cc304d10b64b8cb32bffeee52f36e583c46f844`
Branch: `agent/inc-018-durable-run-execution`
Status: `review`

## Objective

Replace terminal-only topology data with a restart-safe worker contract whose queued,
processing, ready and Greenlight states are persisted before the browser renders them.

## Implemented

- `Prefer: respond-async` creates a durable `queued` run and returns `202 Accepted`,
  `Preference-Applied` and `Location`.
- An in-process worker loop treats SQLite/PostgreSQL as queue authority; business state is
  not owned by the thread.
- Per-run command locks, expiring leases, attempt counters and monotonic fencing tokens.
- Two checkpoints for each pre-Publisher station: `processing` then `ready` with artifact.
- Fourteen station checkpoints before Publisher enters `waiting_greenlight`.
- Restart recovery after lease expiry; a live lease blocks a replacement worker.
- PostgreSQL cross-replica serialization without duplicate station artifacts.
- SPA polling only while the persisted run is `queued` or `running`.
- Readiness exposes whether the durable worker loop is active.
- Synchronous API/CLI behavior remains available for backward compatibility.

## Critic findings

| Finding | Severity | Resolution |
|---|---:|---|
| A browser animation could misrepresent nonexistent work. | HIGH | The SPA sends `Prefer: respond-async` and renders only authenticated `GET /runs/{id}` documents. Chromium observes backend fences and station states. |
| Two replicas could execute the same station concurrently. | HIGH | PostgreSQL advisory command lock serializes the run; fences are monotonic and the CEO artifact is created once in a two-worker race. |
| A crash after claim could strand the run. | HIGH | Lease metadata is persisted before execution; another worker waits for expiry and claims with a higher fence. |
| A completed station could run again. | HIGH | `advance()` skips every persisted `ready` station and resumes at the first nonterminal station. Current station tools are deterministic and sandbox-only. |
| Greenlight might become available before Risk. | HIGH | Publisher transitions only after Risk is `ready`; package and browser gates finish with seven artifacts and `awaiting_greenlight`. |
| The worker could imply provider/model/publication authority. | HIGH product | All existing station adapters remain deterministic sandbox tools. Model calls, social publication, media rendering and spend stay disabled. |

## Verification

```text
Locked Python wheel                       PASS — 196 tests, 15 PostgreSQL skips
PostgreSQL shared runtime                 PASS — 196/196
SQLite active/expired lease recovery      PASS
PostgreSQL two-worker fence/artifact race PASS
Frontend                                  PASS — 36/36
Oxlint / TypeScript / Vite                PASS
Chromium accessibility                    PASS
Chromium social output/OAuth regression   PASS
Chromium asynchronous topology            PASS — 7 stations, 14 checkpoint values
Final browser fencing token               PASS — 14
Buildah production image async smoke      PASS — 202 + fences 1..14 + Greenlight
K3s/Helm/Terraform                        PASS
Actionlint / Gitleaks                     PASS
Compliance                               PASS — DENY_RELEASE, 0 active providers
Clean-source supply chain                 PASS — 3cc304d, registry_publication=false
Real model/provider/publication effects   NOT_RUN
Push / PR / exact-head CI                 BLOCKED — Cloud Sandbox git_push wrapper
```

## Residual boundaries

- The worker is packaged inside the API process. PostgreSQL permits multiple replicas;
  production scheduler placement and persistent-environment observation remain external.
- A station computation that crashes before checkpoint persistence may be recomputed. That
  is safe for the current deterministic sandbox tools; future economic/external effects
  must use INC-015/INC-020 intent-and-receipt authorities.
- Global release remains denied by accessibility, privacy/legal, cloud, backup operations,
  semantic evaluation, model-effect and social-publication gates.
