# Production Readiness Checkpoint 004

## Increment

Introduce tenant-scoped authentication and durable execution/approval persistence without enabling external integrations.

## Delivered

- Bearer-token authentication for every `/api/v1/*` endpoint.
- Tenant identity derived only from server-configured credentials.
- Constant-time credential comparison with no raw key returned by the API.
- `/api/v1/me` tenant identity endpoint.
- `/readyz` readiness gate that fails when authentication is absent.
- Tenant-scoped SQLite run store with complete execution, evidence, trace, artifact, and Greenlight serialization.
- Run restoration before approve/reject, allowing decisions after process restart.
- Tenant namespaces for SQLite memory search, recall, and counts.
- Cross-tenant requests return `404` even when the run exists for another tenant.
- Kubernetes Secret reference, PVC, non-root UID/GID `10001`, writable `/tmp`, and durable database mount.
- Single SQLite replica with `Recreate` rollout strategy and Helm guard against unsafe scaling.
- ADR 0001 documenting the decision and trade-offs.

## Verification evidence

- Python: 23/23 tests pass.
- Frontend: 28/28 tests pass.
- Oxlint: zero findings.
- Vite production build: pass.
- Helm lint: one chart, zero failures.
- Helm render: Service, Deployment, and PersistentVolumeClaim.
- Helm negative test: `replicaCount=2` with persistence is rejected.
- Helm negative test: missing existing Secret name is rejected.
- Buildah production package: pass.
- Packaged `/healthz`, `/readyz`, SPA, bearer auth, run creation, and Publisher gate: pass.
- Durable API test: create before restart, approve after restart, read completed state after a second restart.
- Tenant isolation test: one tenant cannot read another tenant's run.

## Safety

- External adapters remain sandbox fixtures.
- Publisher still creates only `publication_performed=false` packages.
- No credentials are committed.
- No Kubernetes Secret resource with credential values is generated.
- No deployment, publication, media render, ad spend, or protected-branch mutation occurred.

## Next highest-value increment

Connect the production frontend to the authenticated API through an explicit session boundary, then add structured observability and audit export. User-level identity and PostgreSQL remain required before horizontal scaling or a public pilot.
