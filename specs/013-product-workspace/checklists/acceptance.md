# Acceptance checklist

- [x] Mission execution is the primary content.
- [x] Theme controls are absent from the primary mission flow.
- [x] Tenant credential field is absent until Connect is activated.
- [x] Credential field is removed after session exchange or dialog close.
- [x] Settings and connection dialogs trap focus and restore it.
- [x] Five providers are derived by the server in exact order.
- [x] Provider responses contain no credential values or credential environment names.
- [x] Provider endpoints reject non-HTTPS and embedded credentials.
- [x] Applied context replaces the large memory-internals panel.
- [x] Operational Fabric reflects providers, reviewed integrations and run stations.
- [x] Topology remains available and derives state from the current run.
- [x] `npm run start:local` serves SPA + FastAPI + SQLite on loopback.
- [x] Static preview is documented as visual-only.
- [x] 320 CSS px reflow, keyboard, reduced motion and AX-tree automation pass.
- [x] Compliance remains `DENY_RELEASE` with zero active external providers.
- [ ] Exact clean-source delivery and CI pass.
- [ ] Real provider inference remains disabled until a separate authorized gateway passes.
