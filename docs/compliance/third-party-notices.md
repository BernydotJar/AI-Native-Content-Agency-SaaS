# Third-party review inventory

Status: direct inventory and automated license evidence for sandbox candidate 0.7.0

This document summarizes machine-readable evidence. It is not legal advice and
does not replace license texts, attribution obligations, provider terms or final
counsel review before distribution.

## Repository license

The repository declares `MIT` in `LICENSE` with SHA-256 `b5915031a7d4c6d50a2e8530e2cf66f371c667793aebb7d3804d1410fdb08b2a`.

## Direct npm packages

| Package | Version | Scope | Declared license |
|---|---:|---|---|
| `@fontsource-variable/jetbrains-mono` | `5.2.8` | runtime | `OFL-1.1` |
| `@fontsource-variable/manrope` | `5.2.8` | runtime | `OFL-1.1` |
| `lucide-react` | `1.25.0` | runtime | `ISC` |
| `react` | `19.2.7` | runtime | `MIT` |
| `react-dom` | `19.2.7` | runtime | `MIT` |
| `@tailwindcss/vite` | `4.3.3` | development | `MIT` |
| `@testing-library/jest-dom` | `6.9.1` | development | `MIT` |
| `@testing-library/react` | `16.3.2` | development | `MIT` |
| `@testing-library/user-event` | `14.6.1` | development | `MIT` |
| `@types/node` | `24.13.3` | development | `MIT` |
| `@types/react` | `19.2.17` | development | `MIT` |
| `@types/react-dom` | `19.2.3` | development | `MIT` |
| `@vitejs/plugin-react` | `6.0.3` | development | `MIT` |
| `jsdom` | `29.1.1` | development | `MIT` |
| `oxlint` | `1.74.0` | development | `MIT` |
| `tailwindcss` | `4.3.3` | development | `MIT` |
| `typescript` | `6.0.3` | development | `Apache-2.0` |
| `vite` | `8.1.5` | development | `MIT` |
| `vitest` | `4.1.6` | development | `MIT` |

## Direct Python runtime packages

| Package | Version | License review |
|---|---:|---|
| `fastapi` | `0.139.2` | `MIT` |
| `pg8000` | `1.31.5` | `BSD-3-Clause` |
| `uvicorn` | `0.51.0` | `BSD-3-Clause` |

## OCI base images

| Image | Digest |
|---|---|
| `node:22-bookworm-slim` | `sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3` |
| `python:3.13-alpine3.23` | `sha256:9fdbf2e3e82628351513560b121e2ee6ce31cac212be9e070c5a5e2769fb5e76` |

## GitHub Actions

All workflow actions are build-only and pinned by full commit SHA.

| Action | Commit | Workflow |
|---|---|---|
| `actions/checkout` | `11d5960a326750d5838078e36cf38b85af677262` | `.github/workflows/production-readiness.yml` |
| `actions/setup-node` | `49933ea5288caeca8642d1e84afbd3f7d6820020` | `.github/workflows/production-readiness.yml` |
| `actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065` | `.github/workflows/production-readiness.yml` |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | `.github/workflows/production-readiness.yml` |
| `azure/setup-helm` | `bf6a7d304bc2fdb57e0331155b7ebf2c504acf0a` | `.github/workflows/production-readiness.yml` |
| `docker/build-push-action` | `10e90e3645eae34f1e60eeb005ba3a3d33f178e8` | `.github/workflows/production-readiness.yml` |
| `docker/setup-buildx-action` | `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f` | `.github/workflows/production-readiness.yml` |
| `hashicorp/setup-terraform` | `b9cd54a3c349d3f38e8881555d616ced269862dd` | `.github/workflows/production-readiness.yml` |

## External candidates

| Candidate | Commit | License | Runtime state |
|---|---|---|---|
| `video-use` | `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` | `MIT` | `reviewed_disabled`; enabled=`false` |

No external provider is active. The `video-use` candidate is source-review data
only; it is not installed or executed.

## Transitive evidence

- npm: `package-lock.json` plus CI/OCI SBOM evidence;
- Python: `backend/requirements.lock` plus CycloneDX OCI SBOM;
- operating system: OCI SBOM from `scripts/verify-supply-chain.sh`;
- automated policy: `artifacts/supply-chain/license-policy.json`.

The policy rejects known copyleft/business-source tokens for the current runtime
image and requires exact exceptions/mappings. Operating-system inventory and
generated SBOMs remain release artifacts; they require review at the exact release
tree because package contents can change with any base-image or lock update.

## Revalidation

Run `npm run validate:compliance` after any dependency, lock, base image, workflow
action, license policy or external-candidate change. Run the complete supply-chain
gate before any release candidate.
