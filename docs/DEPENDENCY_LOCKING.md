# Python Dependency Locking

Verified on 21 July 2026.

## Objective

The backend must install the same Python dependency graph in local verification, CI, the wheel build stage, and the production image. Runtime installation must not perform an unconstrained dependency resolution.

## Source inputs

Human-maintained constraints live in:

- `backend/requirements.in`: runtime dependencies;
- `backend/requirements-test.in`: runtime graph plus test-only dependencies;
- `backend/requirements-build.in`: production/CI wheel and lock-generation toolchain;
- `backend/requirements-local-build.in`: conservative local wheel toolchain for package mirrors that lag the primary index.

Generated, reviewed, and committed lockfiles live in:

- `backend/requirements.lock`;
- `backend/requirements-test.lock`;
- `backend/requirements-build.lock`;
- `backend/requirements-local-build.lock`.

Every resolved artifact is pinned and includes hashes accepted by `pip --require-hashes`.

## Locked toolchain

The lock generator is itself locked. `requirements-build.lock` contains `pip-tools==7.6.0` together with exact versions and hashes for `pip`, `setuptools`, `wheel`, `build`, and their transitive dependencies.

`requirements-local-build.lock` is intentionally smaller. It contains only a conservative, hash-pinned `pip`, `setuptools`, and `wheel` toolchain. When the primary build lock is unavailable from the operator's package index, `start:local` builds the same application wheel with `pip wheel --no-build-isolation` instead of importing the `build` package. This avoids Python-version-specific `importlib-metadata` markers while preserving a locked wheel build. Production images and CI continue to use the primary lock and `python -m build`.

The integrated local product launcher selects Python 3.11 through 3.13 and supports an explicit `AGENCY_PYTHON_BIN`. The runtime lock is generated on Python 3.11 and verified on Python 3.13; Python 3.10 is rejected before dependency installation because marker-only dependencies such as `exceptiongroup` are not part of the verified lock for that interpreter.

The first generation attempt used `pip-tools 7.5.2` with `pip 26.1` and failed with:

```text
TypeError: PackageFinder.__init__() got an unexpected keyword argument 'allow_all_prereleases'
```

The reversible temporary environment was updated to `pip-tools 7.6.0`, whose release added compatibility with pip 26.1. Lock generation then completed and was made self-hosting through `requirements-build.lock`.

## Update workflow

Edit only the `.in` files, then run:

```bash
PYTHON_BIN=python3.11 ./scripts/update-python-locks.sh
./scripts/check-python-locks.sh
./scripts/verify-python-locks.sh
```

`update-python-locks.sh`:

1. creates a temporary virtual environment;
2. installs the committed build toolchain with `--require-hashes`;
3. regenerates runtime, test, primary-build, and local-compatibility locks;
4. leaves reviewable lockfile changes in the working tree.

`check-python-locks.sh` regenerates all locks, compares them byte for byte with the committed files, and restores the originals before exiting. CI uses this as a drift gate.

## Verification workflow

`verify-python-locks.sh` creates two independent temporary environments:

1. a build environment installs `requirements-build.lock` and builds the backend wheel with `python -m build --no-isolation`;
2. an independent compatibility build environment installs `requirements-local-build.lock` and builds the same backend wheel;
3. a test environment installs `requirements-test.lock`, installs the primary wheel with `--no-deps`, runs `pip check`, and executes all backend tests.

The script prints the installed versions of the application and load-bearing framework packages so the observed graph is explicit.

## Production image workflow

The Dockerfile uses three stages:

1. Node builds the React bundle from `package-lock.json`;
2. Python 3.13 on Alpine 3.23 installs the hashed build lock and creates a wheel without isolated build dependency resolution;
3. Python 3.13 on Alpine 3.23 installs the hashed runtime lock, installs the wheel with `--no-deps`, runs `pip check`, and copies only the built SPA.

This prevents `pip install ./backend` from resolving a different graph during image creation.

## Verified graph

The current verified core includes:

- `agency-runtime==0.7.0`;
- `fastapi==0.139.2`;
- `starlette==1.3.1`;
- `uvicorn==0.51.0`;
- `pydantic==2.13.4`;
- `httpx==0.28.1` in the test graph.

The locks were generated and byte-regenerated with Python 3.11. CI verifies the wheel under Python 3.13, and the production image installs the same runtime pins under Python 3.13.14 on Alpine 3.23 before `pip check` and the full packaged HTTP smoke.

## Rollback

A dependency update is rolled back by reverting the `.in` and generated lockfile changes together. Do not hand-edit pins or hashes. After rollback, rerun:

```bash
./scripts/check-python-locks.sh
./scripts/verify-python-locks.sh
./scripts/verify-production-package.sh
```

## Supply-chain controls

The repository now pins container base images by digest and GitHub Actions by commit SHA. `verify-supply-chain.sh` generates a CycloneDX SBOM, Grype report, exact expiring vulnerability policy result, application license policy result, in-toto/SLSA-style provenance and offline Cosign verification evidence. See `docs/SUPPLY_CHAIN_SECURITY.md`.

Controls still required for an external production release are:

- immutable registry promotion by digest;
- protected keyless OIDC or KMS-backed signing identity;
- public transparency-log verification and deployment admission policy;
- approved Python/npm package mirrors or organization repository policy.
