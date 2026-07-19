# ADR 0002 — PostgreSQL source of truth

- Decision: Use PostgreSQL for runtime control-plane state and SQLite only for isolated local/tests.
- Status: Accepted
- Context: Memory SQLite did not persist missions, runs, artifacts, approvals, or audit events.
- Alternatives: In-memory state; SQLite runtime; relational repository with PostgreSQL runtime.
- Evidence: Greenlight needs transactions, uniqueness, version checks, restart recovery, and concurrent replay control.
- Chosen option: SQLAlchemy repository plus Alembic migrations, exercised against SQLite and PostgreSQL-capable configuration.
- Trade-offs: Database operations and migrations add complexity; constraints make integrity enforceable.
- Consequences: Database command boundaries are durable; no claim is made for mid-step workflow resume.
- Review trigger: Measured load or compliance demands a different storage topology.
- Date: 2026-07-18
- Owner: Orchestrator

