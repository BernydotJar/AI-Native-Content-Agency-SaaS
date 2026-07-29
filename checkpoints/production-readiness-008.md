# Production Readiness Checkpoint 008

## Increment

Remediate Terraform and Kubernetes validation dependencies and execute the infrastructure stack against a real local Kubernetes API.

## Installed tools

All binaries were installed reversibly in `/home/agent/.local/bin` and checksum verified:

- Terraform `1.15.8`, SHA-256 `8891e9dcedc9e3b8950bc6af9d4d8af1f4cfade3062f53b9dc403a89f6ce8c9c`;
- kubectl `v1.36.2`, SHA-256 `c957eb8c4bea27a3bb35b269edd9082e27f027f7b76b20b5bf4afebc726c6d3e`;
- K3s `v1.36.2+k3s1`, SHA-256 `0ea2000c70a1ec48bfa70c187643e4f0ced11875556b2f1f5edb6ef916176682`;
- Helm `v4.2.0` was already installed and checksum verified in checkpoint 003;
- actionlint `1.7.11`, SHA-256 `2b65d6542df67ed865349f37750738ec83e027f6acc17f6889a46dbd07a14335`.

Debian `iproute2 6.1.0-3` was installed to provide `ip` and `ss` diagnostics.

## Attempts and remediation

1. Terraform checksum initially referenced a renamed local archive and failed. The archive was redownloaded under its official filename and verified successfully.
2. A combined Terraform/kubectl download exceeded the command timeout. State inspection confirmed no kubectl binary had been installed; downloads were split and completed independently.
3. Terraform `1.15.7` was initially installed from an outdated installation-page signal. The official release index showed `1.15.8`; the binary was replaced and reverified.
4. Full K3s with `node-ip=127.0.0.1` was rejected because Kubernetes forbids loopback node IPs.
5. Full K3s with the non-loopback address started the API but kubelet failed on the host's read-only cgroup hierarchy (`cpu.max`, cpuset cgroup).
6. Official K3s agentless mode was evaluated and succeeded without kubelet/containerd/CNI.
7. The first CI insertion for actionlint contained an invalid YAML scalar around the shell command. actionlint rejected the workflow at line 16; the step was converted to a YAML block scalar and then passed.

## Delivered

- `scripts/install-local-infra-tools.sh` for checksum-verified local infrastructure tool bootstrap.
- `scripts/install-actionlint.sh` and a dedicated CI job for checksum-verified GitHub Actions validation.
- `scripts/verify-local-infrastructure.sh` for K3s agentless + Terraform + Helm apply/destroy.
- Terraform variables for namespace ownership, Helm wait/timeout, replica count, persistence, existing Secret, Secret key, and session cookie security.
- Terraform defaults to a preprovisioned namespace boundary so Secret values remain outside state.
- Terraform version constrained below 2.0.
- `docs/LOCAL_INFRASTRUCTURE_VALIDATION.md` with scope, commands, evidence, cleanup, limitations, and resume condition.

## Verification evidence

- actionlint 1.7.11: workflow syntax and expression validation pass.
- Terraform fmt/init/validate: pass with signed locked providers.
- Real K3s `/readyz`: pass.
- Helm direct install and Kubernetes server dry-run: pass.
- Terraform plan: creates Helm release and no Secret resource.
- Terraform apply: Deployment and Service accepted by Kubernetes API.
- Deployment references the expected existing Secret, image, and `/readyz` probe.
- Terraform destroy: pass; state empty.
- Namespace and K3s temporary data removed.
- No production infrastructure, external cluster, or protected branch was modified.

## Explicit limitation

`workload_execution=not_validated_agentless_control_plane`. Full Kubernetes pod scheduling requires a host/VM with writable delegated cgroups, an approved privileged nested-cluster environment, or authorized external cluster credentials. The application image itself remains independently executable and verified through Buildah.

## Next highest-value increment

Supply-chain hardening: immutable base-image digests, SBOM generation, vulnerability/license gates, and image provenance/signing design without publishing to a registry.
