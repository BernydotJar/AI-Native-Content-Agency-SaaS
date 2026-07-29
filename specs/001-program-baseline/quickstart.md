# Quickstart

```bash
python3 scripts/validate-program-state.py
npm run lint
npm test
npm run build
./scripts/verify-python-locks.sh
git diff --check
```

A nonzero program validator result is a release-gate failure. Do not delete the failing requirement or weaken the vocabulary to make the gate pass.
