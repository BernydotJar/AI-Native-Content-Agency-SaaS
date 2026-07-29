# Acceptance checklist

## Readiness slice

- [x] No social secret/token appears in browser storage, API payloads, screenshots, or logs.
- [x] X and Instagram readiness is visible in Settings/Admin.
- [x] Main output shows copy, asset, Greenlight, account, and publication status.
- [x] Instagram remains blocked without rendered media.
- [x] OAuth routes are governed; publication mutation routes remain absent.
- [x] CI/browser/package tests make zero real X or Meta requests.

## OAuth/publication slice

- [x] OAuth callback is state-, tenant-, and session-bound.
- [x] Connected account metadata is visible without token disclosure.
- [ ] Publication requires exact approved artifact/channel/media authority.
- [ ] Same publication intent cannot create two posts.
- [ ] Unknown provider outcome blocks retry.
- [x] Disconnect removes encrypted tokens and prevents future account use.
