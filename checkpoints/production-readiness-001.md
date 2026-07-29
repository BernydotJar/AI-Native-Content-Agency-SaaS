# Production Readiness Checkpoint 001

## Scope

Bootstrap the persistent Production Readiness session and establish deployable container, Helm, Terraform, and CI foundations.

## Acceptance evidence

- Session and execution policy persisted without modeling `/goal` as a project object.
- Multi-stage non-root production container with `/healthz`.
- Helm chart with probes, resource bounds, restricted security context, and disruption budget.
- Terraform module installs the chart into a managed namespace.
- GitHub Actions validates application, container, Helm, and Terraform.

## Remaining program work

- Run local image and health smoke test.
- Validate Helm against a local Kubernetes cluster.
- Add registry publishing and immutable release promotion.
- Introduce backend service/API packaging when the runtime becomes network-addressable.
- Add observability, secrets, ingress, TLS, backups, and environment-specific cloud modules.
