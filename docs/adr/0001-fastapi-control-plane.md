# ADR 0001 — FastAPI control plane

- Decision: Make a versioned FastAPI service the sole authority for integrated mission/run state.
- Status: Accepted
- Context: React timers and Python `_runs` modeled the same workflow independently.
- Alternatives: Keep browser authority; expose a framework-specific agent server; use FastAPI.
- Evidence: Baseline mapper found no transport and no shared contracts; existing workflow is Python.
- Chosen option: FastAPI routes call application services, repository ports, and the existing provider-neutral workflow.
- Trade-offs: A service boundary adds deployment and contract work but removes state divergence.
- Consequences: Integrated UI never fabricates run progress; OpenAPI is a compatibility gate.
- Review trigger: A non-HTTP consumer or protocol requirement cannot use the application-service boundary.
- Date: 2026-07-18
- Owner: Orchestrator

