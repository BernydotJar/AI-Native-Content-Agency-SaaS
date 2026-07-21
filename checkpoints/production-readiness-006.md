# Production Readiness Checkpoint 006

## Increment

Connect the React frontend to the durable backend through a browser-safe session boundary.

## Delivered

- One-time tenant API-key exchange for an HttpOnly browser session.
- `Secure` and `SameSite=Strict` cookie defaults.
- SQLite session persistence with only SHA-256 token hashes.
- CSRF requirement for cookie-authenticated mutations.
- CSRF rotation and session recovery after page/service restart.
- Session revocation and durable session lifecycle audit events.
- Production Runtime panel in React:
  - secure tenant exchange;
  - real brief execution;
  - Scholar three-part display;
  - versioned artifact display;
  - exact-artifact Greenlight approval/rejection;
  - sandbox package confirmation;
  - tenant audit display;
  - session revocation.
- Typed same-origin API client with request-correlation errors.
- Explicit tests proving no browser storage use.
- Helm configuration for cookie name, secure mode, and TTL.
- ADR 0003.

## Verification evidence

- Python: 28/28 tests pass.
- Frontend: 33/33 tests pass.
- Oxlint: zero findings.
- Vite production build: pass.
- Helm lint/template: pass.
- Helm unsafe-replica and missing-Secret guards: pass.
- Browser session tests cover HttpOnly/SameSite/Secure, CSRF, rotation, expiry, restart, hashing, and revocation.
- Frontend tests cover one-time key exchange, no local/session storage writes, real run, Scholar, approval, package, error correlation, and session resume.
- Packaged Buildah smoke covers session exchange, CSRF rotation, run, approval, package, audit, metrics, and revocation with external side effects disabled.

## Remaining program work

- The original cinematic simulator still exists beside the production console and should be retired only after feature parity is proven.
- Login rate limiting, managed user identity, MFA, RBAC, and key rotation are missing.
- TLS/ingress and network policy are not yet represented in the chart.
- Python dependency resolution is not yet locked to the exact graph used by CI and the image.
