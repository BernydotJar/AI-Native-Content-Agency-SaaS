# ADR 0004 — Polling for V1 progress

- Decision: Use HTTP polling and refresh reconstruction for V1.
- Status: Accepted
- Context: The deterministic workflow runs inline and reaches Greenlight before the command response.
- Alternatives: Polling; SSE; WebSocket.
- Evidence: There is no asynchronous event producer or latency target that justifies a streaming connection.
- Chosen option: `GET /api/v1/runs/{run_id}` returns persisted steps, artifacts, evidence, and events.
- Trade-offs: Some repeated reads; fewer moving parts and truthful semantics.
- Consequences: Client reconnect is a normal read, not replay of browser timers.
- Review trigger: Work moves to a durable worker or sub-second live progress is required.
- Date: 2026-07-18
- Owner: Orchestrator
