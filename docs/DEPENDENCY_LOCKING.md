# Python Dependency Locking

Verified on 21 July 2026.

## Objective

The backend must install the same Python dependency graph in local verification, CI, the wheel build stage, and the production image. Runtime installation must not perform an unconstrained dependency resolution.

## Source inputs

Human-maintained constraints live in:

- `backend/requirements.in`: runtime dependencies;
- `backend/requirements-test.in`: runtime graph plus test-only dependencies;
- `backend/requirements-build.in`: wheel and lock-generation toolchain.

Generated, reviewed, and committed lockfiles live in:

- `backend/requirements.lock`;
- `backend/requirements-test.lock`;
- `backend/requirements-build.lock`.

Every resolved artifact is pinned and includes hashes accepted by `pip --require-hashes`.

## Locked toolchain

The lock generator is itself locked. `requirements-build.lock` contains `pip-tools==7.6.0` together with exact versions and hashes for `pip`, `setuptools`, `wheel`, `build`, and their transitive dependencies.

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
3. regenerates runtime, test, and build locks;
4. leaves reviewable lockfile changes in the working tree.

`check-python-locks.sh` regenerates all locks, compares them byte for byte with the committed files, and restores the originals before exiting. CI uses this as a drift gate.

## Verification workflow

`verify-python-locks.sh` creates two independent temporary environments:

1. a build environment installs `requirements-build.lock` and builds the backend wheel with `python -m build --no-isolation`;
2. a test environment installs `requirements-test.lock`, installs the wheel with `--no-deps`, runs `pip check`, and executes all backend tests.

The script prints the installed versions of the application and load-bearing framework packages so the observed graph is explicit.

## Production image workflow

The Dockerfile uses three stages:

1. Node builds the React bundle from `package-lock.json`;
2. Python 3.12 installs the hashed build lock and creates a wheel without isolated build dependency resolution;
3. Python 3.12 installs the hashed runtime lock, installs the wheel with `--no-deps`, runs `pip check`, and copies only the built SPA.

This prevents `pip install ./backend` from resolving a different graph during image creation.

## Verified graph

The current verified core includes:

- `agency-runtime==0.4.0`;
- `fastapi==0.139.2`;
- `starlette==1.3.1`;
- `uvicorn==0.51.0`;
- `pydantic==2.13.4`;
- `httpx==0.28.1` in the test graph.

The locks were generated and byte-regenerated with Python 3.11. The production image installed the same runtime pins under Python 3.12 and passed `pip check` plus the full packaged HTTP smoke.

## Rollback

A dependency update is rolled back by reverting the `.in` and generated lockfile changes together. Do not hand-edit pins or hashes. After rollback, rerun:

```bash
./scripts/check-python-locks.sh
./scripts/verify-python-locks.sh
./scripts/verify-production-package.sh
```

## Remaining supply-chain controls

The Python graph is reproducible at the package level, but this is not a complete software supply-chain program. Remaining controls include:

- pinning container base images by immutable digest;
- pinning GitHub Actions by commit SHA;
- generating and retaining SBOMs;
- vulnerability and license policy gates;
- signing images and provenance attestations;
- publishing through an immutable registry promotion workflow;
- verifying package indexes through an approved mirror or repository policy.
