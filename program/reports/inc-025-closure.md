# INC-025 Closure — Public Media Signing Keyring

Date: 2026-07-29  
Exact PR head: `7f56f711abc5d13fb609e2fee5b04176ea4c4319`  
GitHub Actions run: `30500998431`  
Decision: PASS for increment closure; global `DENY_RELEASE` and `DENY_APPLY` remain.

## Exact-Head Evidence

- Eight of eight production-readiness jobs passed on the exact PR head.
- Supply-chain provenance SHA-256: `3ffcb74b2c8f62fdb8710799375145f3e2d70e60b578c918a2f60bb6bf66f112`.
- Supply-chain policy SHA-256: `1497bd6b65756988ef36877e132c5619b5d1f0b4b3a0f8d80c5fdfbddf356adb`; status PASS; 33 packages evaluated.
- Semantic report SHA-256: `6c872912a227341c396905c1dd39a3b2b70ca63482eb85cb8451d977997d21b6`.
- Semantic report: source and expected commit equal the PR head; worktree clean; 20/20 expectations; external effects 0.
- No unresolved PR review threads existed at closure.

## Acceptance Criteria

- Old binding replay remains byte-for-byte stable while a new key is active: PASS.
- New bindings persist the active key ID: PASS.
- Missing historical key fails closed without substitute signature or provider effect: PASS.
- Legacy SQLite/PostgreSQL rows migrate to explicit `legacy`: PASS.
- Key material is absent from durable storage, logs, responses, Git, Terraform state and evidence: PASS.
- SQLite, PostgreSQL schema v7, wheel, OCI, Helm, Terraform/K3s, supply-chain and exact-head CI gates: PASS.
- Open CRITICAL/HIGH findings in the INC-025 implementation slice: 0.

## Preserved Boundaries

No production Secret was created or rotated. No deployment, cloud apply, publication, deletion, model request, credential mutation or spend occurred. Post-publication deletion remains blocked under OI-016 and the legal/privacy program.
