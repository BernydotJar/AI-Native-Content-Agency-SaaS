# Research

SQLite WAL databases cannot be safely backed up by copying only the main file while writes may occur. Python's `sqlite3.Connection.backup` provides an online-consistent database copy and is available in the standard library.

PostgreSQL custom format supports validation with `pg_restore --list` and controlled restore with `pg_restore`. The active verifier already starts an ephemeral PostgreSQL cluster and has representative migrated data, making it the correct same-scope restore-drill harness.
