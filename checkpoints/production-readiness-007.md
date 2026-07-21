# Production Readiness Checkpoint 007

## Increment

Eliminate Python dependency drift across local verification, CI, wheel construction, and the production image.

## Dependency remediation evidence

The first lock-generation attempt combined `pip-tools 7.5.2` with `pip 26.1` and failed in `PackageFinder`. The toolchain was upgraded in an isolated temporary environment to `pip-tools 7.6.0`, then locked with hashes in `backend/requirements-build.lock`. No system Python packages were modified.

## Delivered

- Runtime, test, and build `.in` constraint files.
- Runtime, test, and build lockfiles with exact versions and hashes.
- Self-hosted locked build toolchain containing pip-tools.
- `scripts/update-python-locks.sh` for controlled regeneration.
- `scripts/check-python-locks.sh` for byte-identical CI drift detection.
- `scripts/verify-python-locks.sh` for clean build/test environments, wheel installation, `pip check`, and backend tests.
- Docker wheel build using the hashed build lock and `--no-isolation`.
- Docker runtime installation using the hashed runtime lock, wheel `--no-deps`, and `pip check`.
- CI wheel and test path using the same locks.
- Dedicated Python 3.11 lock-regeneration CI gate.
- ADR 0004 and dependency operations documentation.

## Verification evidence

- All three lockfiles regenerate byte-identically.
- Clean Python 3.11 build and test environments pass `pip check` and 28/28 backend tests.
- Observed test graph: agency-runtime 0.4.0, FastAPI 0.139.2, Starlette 1.3.1, Uvicorn 0.51.0, Pydantic 2.13.4, HTTPX 0.28.1.
- Python 3.12 production image installs the same runtime graph and passes `pip check`.
- Packaged image passes health, readiness, SPA, HttpOnly session, CSRF rotation, run creation, Greenlight, sandbox package, audit, metrics, revocation, and post-revocation denial.
- External side effects remain disabled.

## Remaining supply-chain work

- Pin base images by digest.
- Pin GitHub Actions by commit SHA.
- Generate SBOM and vulnerability/license evidence.
- Sign images and provenance attestations.
- Add immutable registry publication and release promotion.
