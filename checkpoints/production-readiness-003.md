# Production Readiness Checkpoint 003

## Increment

Remediate missing validation dependencies and execute the Helm and production-image checks locally instead of delegating them to CI.

## Environment discovery

- Debian GNU/Linux 12 on ARM64.
- APT, pip, npm, curl, wget, tar, and SHA-256 tooling available.
- Docker CLI and daemon available; daemon storage driver is `vfs`.
- Helm, kubectl, Terraform, Buildah, Podman, and related builders were initially absent.

## Dependencies installed

- Helm `v4.2.0`, official ARM64 binary, verified against the official SHA-256 file, installed at `/home/agent/.local/bin/helm`.
- Buildah `1.28.2+ds1-3+deb12u1+b3`, installed from Debian bookworm main after the Docker storage path failed.

## Original validation retries

### Helm

Commands:

```bash
helm lint infra/helm/ai-native-content-agency
helm template agency infra/helm/ai-native-content-agency
```

Result: pass. One chart linted, zero failed; three Kubernetes resources rendered and probes verified.

### Docker

Command:

```bash
docker build --pull --tag ai-native-content-agency:production-readiness-local .
```

Result: failed while registering the first official base-image layer with `operation not supported`.

### Compatible alternative

Buildah with `vfs`, `chroot`, Docker image format, and disabled layers completed the same multi-stage Dockerfile. The resulting image was then executed and verified over HTTP.

## Runtime evidence

- Image user `10001:10001`.
- Health endpoint returned HTTP 200 and declared external effects disabled.
- SPA returned HTTP 200.
- Campaign run endpoint returned HTTP 201.
- Run stopped at `awaiting_greenlight` with seven pre-approval artifacts.
- Publisher remained `waiting_greenlight`.

## Repository changes

- Added `scripts/verify-production-package.sh` with Docker/Buildah selection and HTTP contract checks.
- Added `docs/ENVIRONMENT_REMEDIATION.md` with versions, sources, commands, errors, alternatives, evidence, and reversal instructions.

## Remaining program work

Environment validation is no longer blocked. The next product increment remains tenant-scoped authentication and durable execution/approval persistence.
