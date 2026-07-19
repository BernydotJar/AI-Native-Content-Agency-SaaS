# ADR 0009 — No Kubernetes or self-hosted inference yet

- Decision: Do not add GKE/OpenShift, service mesh, GPUs, vLLM, llm-d, Redis, vector storage, or overlapping gateways.
- Status: Accepted
- Context: The vertical slice is one short control plane with sandbox providers.
- Alternatives: Distributed platform now; managed proportional services; defer.
- Evidence: No load, latency, model-serving, retrieval, or isolation requirement needs those systems.
- Chosen option: Cloud Run plus relational state; add services only from implemented behavior and measured need.
- Trade-offs: Less speculative capacity; substantially lower operations and cost.
- Consequences: Future options remain ports/ADRs, not deployed resources.
- Review trigger: Documented load, latency, tenancy, inference, or retrieval evidence crosses a managed-service limit.
- Date: 2026-07-18
- Owner: Orchestrator
