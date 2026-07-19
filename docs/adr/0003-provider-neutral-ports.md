# ADR 0003 — Provider-neutral ports

- Decision: Keep domain/application behavior independent of model, cloud, MCP, and platform vendors.
- Status: Accepted
- Context: External integrations are not authorized and current fixtures are intentionally sandbox-only.
- Alternatives: Bind directly to one vendor SDK; framework-owned domain state; explicit ports/adapters.
- Evidence: Existing sandbox tool protocols already separate most provider operations.
- Chosen option: Repository, identity, tool, and future storage/model adapters sit outside domain policy.
- Trade-offs: More interfaces and configuration now; lower lock-in and safer activation later.
- Consequences: No adapter is called live without explicit configuration, auth, audit, retry, and approval semantics.
- Review trigger: A stable cross-provider capability cannot be represented without harmful abstraction leakage.
- Date: 2026-07-18
- Owner: Orchestrator
