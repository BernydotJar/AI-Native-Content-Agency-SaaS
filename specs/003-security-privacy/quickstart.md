# Quickstart

```bash
python3 -m unittest backend.tests.test_security_privacy -v
python3 -m unittest backend.tests.test_identity_access backend.tests.test_sessions -v
npm test -- --reporter=dot
./scripts/verify-python-locks.sh
./scripts/verify-postgresql-runtime.sh
npm run validate:program
git diff --check
```

Inspect a denied response and matching audit event using the same `X-Request-ID`. Never enable raw exception detail to debug a test; use sanitized server diagnostics and reproduce locally.
