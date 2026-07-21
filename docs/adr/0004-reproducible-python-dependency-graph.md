# ADR 0004: Reproducible Python dependency and wheel pipeline

- Status: accepted
- Date: 2026-07-21

## Context

The backend declared version ranges in `setup.cfg`. Local tests and the production image resolved those ranges at different times and produced different Uvicorn and Starlette versions. Installing the source package directly also allowed pip's isolated build environment to fetch build dependencies outside the reviewed runtime graph.

## Decision

1. Keep small human-maintained `.in` files for runtime, test, and build constraints.
2. Commit hash-verified lockfiles for all three graphs.
3. Lock the lock generator and wheel toolchain, including pip-tools, pip, setuptools, wheel, and build.
4. Generate locks with Python 3.11 and verify runtime installation on Python 3.12.
5. Build a wheel with the locked toolchain and `--no-isolation`.
6. Install runtime/test locks with `--require-hashes`.
7. Install the application wheel with `--no-deps` and run `pip check`.
8. Fail CI when lock regeneration is not byte-identical.
9. Use the same wheel pipeline in local verification, CI, and the production image.

## Consequences

### Positive

- Local verification, CI, and image builds use one reviewed dependency graph.
- Package downloads are hash checked.
- The application build no longer performs an implicit dependency resolution.
- Dependency updates become explicit, reviewable diffs.

### Trade-offs

- Cross-platform locks contain multiple artifact hashes and are larger than source constraints.
- Updates require regenerating and reviewing three lockfiles.
- Locking Python packages does not pin base-image operating-system packages or GitHub Actions.
- A private package mirror and offline wheelhouse are not yet configured.

## Rejected alternatives

- Continue installing `pip install -e backend httpx`: rejected because it resolves a floating graph.
- Put exact versions only in `setup.cfg`: rejected because it does not hash artifacts or lock transitive/build dependencies.
- Rely on the Docker build as the only lock: rejected because local tests and CI could still drift.
