# INC-038 Tasks — Graph Harness SDLC Adoption

1. Pin the canonical framework revision as a gitlink.
2. Add the deterministic application adapter and lock contract.
3. Add INC-038 to the existing task ledger and dependency graph.
4. Generate the typed project projection.
5. Bootstrap the approved lifecycle through the framework runtime.
6. Persist review and production evidence without closing the feature.
7. Add CI and tests that execute the pinned framework.
8. Run all applicable local gates, commit, push, and open a draft PR.

## Stop Conditions

- framework revision cannot be fetched;
- graph projection is cyclic or inconsistent;
- event hash chain fails;
- any existing product gate regresses;
- action requires deployment, spending, secrets, or an external effect.
