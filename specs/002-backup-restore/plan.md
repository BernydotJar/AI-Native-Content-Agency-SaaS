# Plan

1. Add unit tests for manifest validation, SQLite backup/restore, tamper and overwrite refusal.
2. Implement `scripts/manage-runtime-backup.py` with SQLite and PostgreSQL subcommands.
3. Extend the existing PostgreSQL verifier with a custom-format dump/restore into an ephemeral empty database.
4. Compare schema version and row counts after restore.
5. Add operations/runbook documentation and exact human gates.
6. Run focused tests, PostgreSQL gate, locked wheel gate, critic and independent verification.
