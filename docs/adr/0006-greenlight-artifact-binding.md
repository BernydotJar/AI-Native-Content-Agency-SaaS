# ADR 0006 — Greenlight artifact binding

- Decision: Bind Greenlight to `greenlight.v1` and a SHA-256 canonical pre-Publisher artifact manifest.
- Status: Accepted
- Context: Prior approval stored only decision/reviewer/note and could not detect changed artifacts.
- Alternatives: Bind IDs only; bind database version; canonical cryptographic manifest.
- Evidence: The manifesto requires approval of an exact artifact version; stale-artifact replay is a hard negative case.
- Chosen option: Deterministic JSON includes run, policy, artifact IDs/kinds/creators/payloads/evidence/ordinal; current hash is recomputed in the approval transaction.
- Trade-offs: Any artifact change forces review; integrity is favored over convenience.
- Consequences: One incompatible or concurrent decision is rejected; approval still produces only a sandbox package.
- Review trigger: Canonical contract version changes or signed attestations become necessary.
- Date: 2026-07-18
- Owner: Orchestrator

