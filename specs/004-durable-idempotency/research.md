# Research

The existing audit ledger already commits in the same transaction as run creation and Greenlight decisions and has a globally unique event ID. A deterministic event ID therefore provides a durable command claim without a parallel table or migration, while preserving backup/restore and SQLite→PostgreSQL migration behavior automatically.

A receipt lookup before execution handles normal replay. The unique event ID handles races: a losing incompatible transaction rolls back its mutation; a compatible loser reloads the committed receipt and resource. The request fingerprint includes the authenticated subject to prevent cross-principal key reuse.

Session creation is deliberately excluded because replaying the original response would require storing recoverable raw session and CSRF secrets, violating the existing secret boundary.
