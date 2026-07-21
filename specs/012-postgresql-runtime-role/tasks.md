# Tasks

- [x] Record the least-privilege finding and bounded spec.
- [x] Write failing ephemeral role/ownership gate.
- [x] Write failing absent/incompatible schema validation tests.
- [x] Implement explicit initialize/validate adapter behavior.
- [x] Implement packaged schema operator command.
- [x] Create migration/runtime roles and exact grants in verifier.
- [x] Encode runtime negative DDL/ownership capability checks; execution pending.
- [ ] Run complete application suite under runtime role.
- [x] Update Helm, Terraform and operator/security documentation.
- [x] Complete static critic pass over grants, startup, migration, recovery and credential boundaries.
- [ ] Run full independent regression.
- [ ] Persist state, commit, push, update PR and verify CI.

## Current verification boundary

Implementation and static review are present. Per the active user instruction, no focused, PostgreSQL, regression, Helm, Terraform, frontend or CI gate was rerun in this iteration. The remaining unchecked tasks are mandatory before `INC-012` can leave `in_progress`.
