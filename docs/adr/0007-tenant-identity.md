# ADR 0007 — Tenant and identity boundary

- Decision: Scope every resource by tenant and derive tenant/principal from one deny-by-default auth dependency.
- Status: Accepted for V1
- Context: The baseline had no identity boundary.
- Alternatives: Trust request payload identity; development headers everywhere; centralized adapter.
- Evidence: Cross-tenant reads and approvals must fail and development auth must never start in production.
- Chosen option: Explicit non-production headers for local/dev, rejected by production settings; Cloud dev additionally requires Cloud Run IAM invocation.
- Trade-offs: Enables safe isolated development; a production end-user identity adapter is deferred.
- Consequences: Payloads cannot select another tenant; audit records include the authenticated principal.
- Review trigger: First external tenant or production identity-provider selection.
- Date: 2026-07-18
- Owner: Orchestrator

