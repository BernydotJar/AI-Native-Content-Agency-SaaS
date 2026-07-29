# Local Infrastructure Validation

Verified on 21 July 2026 in the persistent Debian 12 ARM64 workstation.

## Scope

The repository validates two independent concerns locally:

1. `scripts/verify-production-package.sh` builds and executes the real application image with Buildah, proving health, readiness, browser session security, API behavior, Greenlight, audit, metrics, and revocation.
2. `scripts/verify-local-infrastructure.sh` starts a real K3s Kubernetes API, applies the Terraform→Helm stack, performs server-side schema validation, verifies accepted resources, destroys the release, and removes all ephemeral state.

The K3s gate is intentionally **agentless**. It validates API admission and infrastructure orchestration, not pod scheduling or workload readiness. Workload execution is already validated separately by the package smoke.

## Tool bootstrap

Install checksum-verified workstation-local tools without modifying system package repositories:

```bash
./scripts/install-local-infra-tools.sh
export PATH="$HOME/.local/bin:$PATH"
```

Pinned defaults:

- Helm `v4.2.0`;
- Terraform `1.15.8`;
- kubectl `v1.36.2`;
- K3s `v1.36.2+k3s1`.

The installer supports Linux ARM64 and AMD64 and installs only into `$HOME/.local/bin` unless `INSTALL_DIR` is overridden. Removal is reversible:

```bash
rm -f "$HOME/.local/bin/helm" \
      "$HOME/.local/bin/terraform" \
      "$HOME/.local/bin/kubectl" \
      "$HOME/.local/bin/k3s"
```

`verify-local-infrastructure.sh` also requires `ip` and `ss` from the Debian `iproute2` package.

GitHub Actions workflows are validated independently with:

```bash
./scripts/install-actionlint.sh
export PATH="$HOME/.local/bin:$PATH"
actionlint .github/workflows/*.yml
```

## Gate

```bash
./scripts/verify-local-infrastructure.sh
```

The script:

1. copies `infra/` into a temporary directory so Terraform state and `.terraform` never touch the repository;
2. starts K3s with `--disable-agent`, no bundled ingress/storage/metrics/CNI components, and all data under `/tmp`;
3. waits for the real Kubernetes `/readyz` endpoint;
4. asserts the control plane has zero nodes;
5. creates an ephemeral namespace and Secret prerequisite outside Terraform state;
6. runs Terraform fmt, init, validate, and plan;
7. confirms the plan creates the Helm release and does not manage a Kubernetes Secret;
8. applies the release against the Kubernetes API;
9. verifies Deployment, Service, Secret reference, image, and `/readyz` probe;
10. pipes the chart through `kubectl apply --dry-run=server`;
11. destroys Terraform-managed resources, deletes the namespace, terminates K3s, unmounts temporary paths, and removes all files.

Successful output includes:

```text
kubernetes_api=pass
helm_server_dry_run=pass
terraform_plan_apply_destroy=pass
workload_execution=not_validated_agentless_control_plane
cleanup=pass
```

## Why the control plane is agentless

A full K3s server was attempted with native snapshotter and CNI/kube-proxy disabled. The API became ready, but kubelet could not register a node because the workstation container inherits a read-only host cgroup hierarchy:

```text
failed to write 0 to cpu.max: read-only file system
failed to find cpuset cgroup
```

The first attempt also used loopback as `node-ip` and was rejected as invalid. A second attempt used the workstation's non-loopback address and reached the host cgroup limitation above.

K3s agentless mode omits kubelet, container runtime, and CNI while retaining a real Kubernetes control plane. This is a compatible and honest validation of Terraform, Helm, Kubernetes admission, and resource contracts.

## Exact condition for full-node validation

Pod scheduling and Kubernetes probe readiness can be added when the environment provides one of:

- a VM or host with a writable, delegated cgroup v2 subtree for kubelet;
- a privileged container runtime explicitly authorized for nested Kubernetes;
- a managed or disposable external Kubernetes cluster with credentials and human approval.

Until then, do not interpret the agentless gate as pod execution evidence. Use the independent Buildah package smoke for executable workload evidence.

## Terraform namespace and Secret boundary

The application Terraform module defaults to `create_namespace=false`. A platform/bootstrap layer must provision the namespace and runtime Secret before applying the application release. This preserves secret values outside Terraform state.

For an environment whose namespace is safely managed by this module, set `create_namespace=true`, but ensure a secret controller or other approved process creates the required Secret before Helm waits for workload readiness.
