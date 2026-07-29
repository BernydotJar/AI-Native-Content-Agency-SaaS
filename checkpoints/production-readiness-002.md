# Production Readiness Checkpoint 002

## Increment

Expose the existing eight-agent runtime as a network-addressable vertical slice without replacing the architecture or enabling external effects.

## Delivered

- FastAPI service with health, run creation/read, approval, and rejection endpoints.
- End-to-end brief → CEO → grounded sandbox research → Scholar → strategy → growth → copy → media → risk → Greenlight → campaign package flow.
- Scholar contract with the required three-part explanation.
- Greenlight bound to exact artifact IDs and hashes, channels, and authorized budget.
- Thread-safe SQLite access for HTTP worker execution.
- Unified production image serving SPA and API.
- Helm runtime configuration and CI Python verification.

## Verification evidence

- `npm run lint`: pass, zero findings.
- `npm test`: 28/28 pass.
- `npm run build`: pass.
- `.venv/bin/python -m unittest discover -s backend/tests -v`: 19/19 pass.
- Live API smoke: `/healthz` 200, `/api/v1/runs` 201, SPA `/` 200.
- Created run stopped at `awaiting_greenlight` with seven artifact kinds and all three Scholar fields.
- No network adapters, publishing, rendering, GitHub mutation, or ad spend were enabled.

## Constraints and dependencies

- External transcript files are absent; no content from them was inferred.
- Helm CLI is absent from this workstation; Helm lint/template remain CI gates.
- Docker execution is blocked by the workstation tool policy; image build remains a CI gate.
- Authentication, tenant isolation, durable run/approval persistence, secrets, and observability are still missing.

## Next highest-value increment

Introduce tenant-scoped authentication contracts and durable execution persistence before connecting the frontend to the API. A pilot must not depend on process-local run state.
