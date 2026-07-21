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


## Terraform and Kubernetes tooling

Additional production-readiness tooling was installed locally and checksum verified:

| Tool | Version | SHA-256 | Source type |
|---|---|---|---|
| Terraform | 1.15.8 | `8891e9dcedc9e3b8950bc6af9d4d8af1f4cfade3062f53b9dc403a89f6ce8c9c` | Official HashiCorp ARM64 release archive and SHA256SUMS |
| kubectl | v1.36.2 | `c957eb8c4bea27a3bb35b269edd9082e27f027f7b76b20b5bf4afebc726c6d3e` | Official Kubernetes ARM64 binary and checksum |
| K3s | v1.36.2+k3s1 | `0ea2000c70a1ec48bfa70c187643e4f0ced11875556b2f1f5edb6ef916176682` | Official K3s ARM64 release and checksum |

`iproute2 6.1.0-3` was installed from Debian bookworm to provide interface and socket diagnostics.

Terraform fmt/init/validate passed locally with locked, signed providers. Full-node K3s reached API readiness but kubelet could not write the host's read-only cgroup hierarchy. Agentless K3s then validated Helm and Terraform against a real Kubernetes API. See [Local Infrastructure Validation](LOCAL_INFRASTRUCTURE_VALIDATION.md) and checkpoint 008 for commands, errors, alternatives, evidence, cleanup, and the exact condition for full-node validation.


## GitHub Actions workflow validation

`actionlint 1.7.12` is installed as a checksum-verified local binary from the official release archive. The installer maps the host `x86_64` architecture to the upstream `amd64` asset name.

- SHA-256: `2b65d6542df67ed865349f37750738ec83e027f6acc17f6889a46dbd07a14335`
- Destination: `/home/agent/.local/bin/actionlint`
- Reproducible installer: `scripts/install-actionlint.sh`

The production-readiness workflow passes actionlint locally, and CI now installs the same pinned release before validating all workflow YAML files. Removal is reversible with `rm -f /home/agent/.local/bin/actionlint`.

During integration, actionlint caught an invalid YAML command scalar in the new workflow job. The command was changed to a block scalar and the workflow then passed. This failure and correction demonstrate that the gate validates the actual workflow rather than only confirming the binary is installed.
## Supply-chain tooling — 21 July 2026

The following release binaries were installed reversibly in `$HOME/.local/bin` with official SHA-256 verification and then codified in `scripts/install-supply-chain-tools.sh`:

- Syft `1.48.0`;
- Grype `0.116.0`;
- Cosign `3.1.2`;
- Crane `0.21.7`.

The first Debian-slim scans exposed a substantially larger operating-system vulnerability surface. Python 3.13.14 on Alpine 3.23 was evaluated, passed runtime verification and reduced the observed result to 0 Critical and 5 High findings. See `docs/SUPPLY_CHAIN_SECURITY.md` for exact policy and limitations.
