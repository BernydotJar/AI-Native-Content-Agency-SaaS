# Environment and Dependency Remediation

Verified on 21 July 2026 in the persistent Production Readiness workstation.

## Workstation identity

- Debian GNU/Linux 12 (`bookworm`)
- Linux ARM64 (`aarch64`)
- Available package managers: APT, pip, npm
- Network access confirmed for Helm, Kubernetes downloads, GitHub, Debian, Docker Hub, and PyPI

## Helm

Helm was installed as a reversible workstation-local binary rather than adding a third-party APT repository.

- Version: `v4.2.0`
- Source: `https://get.helm.sh/helm-v4.2.0-linux-arm64.tar.gz`
- Destination: `/home/agent/.local/bin/helm`
- Verified SHA-256: `1f8de130dfbd04de64978e7b852a7a547be1404956a366608276d2520b678670`

Validation:

```bash
export PATH=/home/agent/.local/bin:$PATH
helm lint infra/helm/ai-native-content-agency
helm template agency infra/helm/ai-native-content-agency
```

Result: one chart linted with zero failures; Service, Deployment, and PodDisruptionBudget rendered with the expected port and health probes.

## Container build remediation

The installed Docker client and daemon were reachable, but the first production build failed while importing the official Node base image:

```text
failed to register layer: operation not supported
```

The daemon used the `vfs` storage driver inside the nested workstation. Retrying the same storage path would not address the layer-registration failure.

Buildah was evaluated as the compatible daemonless alternative. It was installed from the signed Debian 12 repository:

- Package: `buildah`
- Version: `1.28.2+ds1-3+deb12u1+b3`
- Repository: `http://deb.debian.org/debian bookworm/main arm64`
- Added disk usage reported by APT: 66.1 MB

The successful build used:

```bash
buildah --storage-driver vfs bud \
  --isolation chroot \
  --format docker \
  --layers=false \
  --tag ai-native-content-agency:production-readiness-buildah .
```

This route built both stages, pulled the official ARM64 Node and Python images, installed backend dependencies, and produced image ID `9bfdc93ba084...` during the recorded run.

Runtime smoke evidence:

- configured user: `10001:10001`;
- `/healthz`: HTTP 200;
- SPA `/`: HTTP 200;
- `POST /api/v1/runs`: HTTP 201;
- run status: `awaiting_greenlight`;
- Publisher status: `waiting_greenlight`;
- seven pre-approval artifacts created;
- external side effects remained disabled.

## Reproducible command

The repository now provides:

```bash
CONTAINER_BUILDER=buildah \
HELM_BIN=/home/agent/.local/bin/helm \
./scripts/verify-production-package.sh
```

`CONTAINER_BUILDER=auto` attempts Docker first and falls back to Buildah when Buildah is installed. Temporary Buildah storage and runtime containers are removed when the script exits.

## Reversal

Helm can be removed with:

```bash
rm -f /home/agent/.local/bin/helm
```

Buildah and packages installed with it can be removed with:

```bash
apt-get remove --purge buildah
apt-get autoremove --purge
```
