# Research

## Repository observations

- PR #3 baseline: `agency_runtime`, direct SQLite/PostgreSQL adapters, application-managed identity/RBAC, browser sessions, Helm/Kubernetes and supply-chain gates.
- PR #2: alternate `control_plane`, SQLAlchemy/Alembic, Cloud Run/GCP Terraform and a larger eval harness.
- The branches diverged 24 and 14 commits from their common base.

## Decision

Do not merge the alternate backend into PR #3. Port compatible controls behind bounded specs. This prevents dual runtime authority while preserving reusable security/operations work.

## Version decision

Use 0.7.0 because Python package, API, metrics and Helm already identify the implementation as 0.7.0. The frontend 0.0.0 is stale metadata, not a reason to retroactively rename the existing runtime.
