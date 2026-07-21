import contextlib
import importlib.util
import io
import json
import os
import stat
import sqlite3
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "manage-runtime-backup.py"
SPEC = importlib.util.spec_from_file_location("manage_runtime_backup", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load runtime backup tool")
BACKUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKUP)
FIXED_TIME = datetime(2026, 7, 21, 18, 0, 0, tzinfo=timezone.utc)


def seed_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            "CREATE TABLE runtime_runs(tenant_id TEXT, run_id TEXT, status TEXT)"
        )
        connection.execute(
            "CREATE TABLE audit_events(sequence INTEGER PRIMARY KEY, action TEXT)"
        )
        connection.executemany(
            "INSERT INTO runtime_runs VALUES (?, ?, ?)",
            (
                ("tenant-alpha", "run-1", "awaiting_greenlight"),
                ("tenant-beta", "run-2", "completed"),
            ),
        )
        connection.execute(
            "INSERT INTO audit_events(sequence, action) VALUES (1, 'run.created')"
        )


class RuntimeBackupRestoreTests(unittest.TestCase):
    def test_sqlite_backup_restore_preserves_rows_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            backup_dir = root / "backups"
            restored = root / "restored.sqlite3"
            seed_database(source)

            manifest_path = BACKUP.create_sqlite_backup(
                source, backup_dir, now=FIXED_TIME
            )
            manifest = json.loads(manifest_path.read_text())

            self.assertEqual(manifest["schema_version"], "agency-runtime-backup.v1")
            self.assertEqual(manifest["backend"], "sqlite")
            self.assertEqual(manifest["validation"], "integrity_check_ok")
            self.assertEqual(manifest["tool"]["version"], "0.7.0")
            self.assertNotIn(str(source), json.dumps(manifest))
            backup_path = backup_dir / manifest["backup_file"]
            self.assertTrue(backup_path.is_file())
            self.assertEqual(stat.S_IMODE(backup_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(manifest_path.stat().st_mode), 0o600)

            result = BACKUP.restore_sqlite_backup(manifest_path, restored)
            self.assertEqual(result["status"], "restored")
            self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o600)
            with sqlite3.connect(restored) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute("SELECT action FROM audit_events").fetchone()[0],
                    "run.created",
                )
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )

    def test_tampered_backup_fails_before_target_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            target = root / "target.sqlite3"
            seed_database(source)
            manifest_path = BACKUP.create_sqlite_backup(
                source, root / "backups", now=FIXED_TIME
            )
            manifest = json.loads(manifest_path.read_text())
            backup_path = manifest_path.parent / manifest["backup_file"]
            contents = bytearray(backup_path.read_bytes())
            contents[-1] ^= 1
            backup_path.write_bytes(contents)

            with self.assertRaisesRegex(BACKUP.BackupError, "checksum mismatch"):
                BACKUP.restore_sqlite_backup(manifest_path, target)
            self.assertFalse(target.exists())

    def test_existing_target_is_preserved_without_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            target = root / "target.sqlite3"
            seed_database(source)
            target.write_bytes(b"preserve-me")
            manifest_path = BACKUP.create_sqlite_backup(
                source, root / "backups", now=FIXED_TIME
            )

            with self.assertRaisesRegex(BACKUP.BackupError, "target already exists"):
                BACKUP.restore_sqlite_backup(manifest_path, target)
            self.assertEqual(target.read_bytes(), b"preserve-me")

    def test_replace_is_atomic_and_rejects_active_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            target = root / "target.sqlite3"
            seed_database(source)
            seed_database(target)
            manifest_path = BACKUP.create_sqlite_backup(
                source, root / "backups", now=FIXED_TIME
            )
            sidecar = Path(str(target) + "-wal")
            sidecar.write_bytes(b"active")

            with self.assertRaisesRegex(BACKUP.BackupError, "sidecar"):
                BACKUP.restore_sqlite_backup(manifest_path, target, replace=True)
            self.assertTrue(target.exists())
            for suffix in ("-wal", "-shm"):
                Path(str(target) + suffix).unlink(missing_ok=True)
            BACKUP.restore_sqlite_backup(manifest_path, target, replace=True)
            with sqlite3.connect(target) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM runtime_runs").fetchone()[0],
                    2,
                )

    def test_manifest_unknown_field_and_path_traversal_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            seed_database(source)
            manifest_path = BACKUP.create_sqlite_backup(
                source, root / "backups", now=FIXED_TIME
            )
            manifest = json.loads(manifest_path.read_text())
            manifest["unexpected"] = True
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(BACKUP.BackupError, "unexpected fields"):
                BACKUP.load_and_verify_manifest(manifest_path, expected_backend="sqlite")

            manifest.pop("unexpected")
            manifest["backup_file"] = "../outside.sqlite3"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(BACKUP.BackupError, "basename"):
                BACKUP.load_and_verify_manifest(manifest_path, expected_backend="sqlite")

    def test_postgresql_url_is_converted_to_environment_without_secret_argv(self):
        url = (
            "postgresql://operator:super-secret@db.internal:5433/agency"
            "?sslmode=require&application_name=backup-test"
        )
        previous_pgoptions = os.environ.get("PGOPTIONS")
        os.environ["PGOPTIONS"] = "-c search_path=attacker"
        try:
            environment, source_hash = BACKUP.postgres_environment(url)
        finally:
            if previous_pgoptions is None:
                os.environ.pop("PGOPTIONS", None)
            else:
                os.environ["PGOPTIONS"] = previous_pgoptions
        command = BACKUP.postgres_backup_command(Path("/tmp/runtime.dump"))

        self.assertNotIn("PGOPTIONS", environment)
        self.assertEqual(environment["PGPASSFILE"], os.devnull)
        self.assertEqual(environment["PGCONNECT_TIMEOUT"], "15")
        self.assertEqual(environment["PGHOST"], "db.internal")
        self.assertEqual(environment["PGPORT"], "5433")
        self.assertEqual(environment["PGUSER"], "operator")
        self.assertEqual(environment["PGPASSWORD"], "super-secret")
        self.assertEqual(environment["PGDATABASE"], "agency")
        self.assertEqual(environment["PGSSLMODE"], "require")
        self.assertEqual(environment["PGAPPNAME"], "backup-test")
        self.assertEqual(len(source_hash), 64)
        self.assertNotIn("super-secret", " ".join(command))
        self.assertNotIn(url, " ".join(command))
        self.assertNotIn("super-secret", source_hash)

    def test_manifest_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            seed_database(source)
            manifest_path = BACKUP.create_sqlite_backup(
                source, root / "backups", now=FIXED_TIME
            )
            manifest_path.write_bytes(
                manifest_path.read_bytes()
                + b" " * (BACKUP.MAX_MANIFEST_BYTES + 1)
            )
            with self.assertRaisesRegex(BACKUP.BackupError, "maximum size"):
                BACKUP.load_and_verify_manifest(
                    manifest_path, expected_backend="sqlite"
                )

    def test_subprocess_timeout_is_bounded_and_sanitized(self):
        environment = {
            "PGPASSWORD": "never-print-this",
            "AGENCY_BACKUP_COMMAND_TIMEOUT_SECONDS": "1",
        }
        with mock.patch.object(
            BACKUP.subprocess,
            "run",
            side_effect=BACKUP.subprocess.TimeoutExpired(["pg_dump"], 1),
        ):
            with self.assertRaisesRegex(
                BACKUP.BackupError, "configured command timeout"
            ) as raised:
                BACKUP.run_command(["pg_dump"], environment)
        self.assertNotIn("never-print-this", str(raised.exception))

    def test_restore_reports_post_install_durability_failure_truthfully(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            target = root / "target.sqlite3"
            seed_database(source)
            manifest_path = BACKUP.create_sqlite_backup(
                source, root / "backups", now=FIXED_TIME
            )
            with mock.patch.object(
                BACKUP, "fsync_directory", side_effect=OSError("simulated")
            ):
                with self.assertRaisesRegex(
                    BACKUP.BackupError, "was installed.*inspect the target"
                ):
                    BACKUP.restore_sqlite_backup(manifest_path, target)
            self.assertTrue(target.is_file())
            with sqlite3.connect(target) as connection:
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )

    def test_postgresql_url_rejects_unsupported_or_duplicate_options(self):
        with self.assertRaisesRegex(BACKUP.BackupError, "unsupported PostgreSQL"):
            BACKUP.postgres_environment(
                "postgresql://user@localhost/db?target_session_attrs=read-write"
            )
        with self.assertRaisesRegex(BACKUP.BackupError, "duplicate option"):
            BACKUP.postgres_environment(
                "postgresql://user@localhost/db?sslmode=require&sslmode=disable"
            )

    def test_cli_error_never_echoes_database_secret(self):
        old_value = os.environ.get("SENSITIVE_DATABASE_URL")
        os.environ["SENSITIVE_DATABASE_URL"] = (
            "postgresql://operator:do-not-print@localhost/agency?bad=value"
        )
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = BACKUP.main(
                    [
                        "postgres-backup",
                        "--database-url-env",
                        "SENSITIVE_DATABASE_URL",
                        "--output-dir",
                        tempfile.gettempdir(),
                    ]
                )
            self.assertEqual(status, 1)
            self.assertIn("unsupported PostgreSQL", stderr.getvalue())
            self.assertNotIn("do-not-print", stderr.getvalue())
        finally:
            if old_value is None:
                os.environ.pop("SENSITIVE_DATABASE_URL", None)
            else:
                os.environ["SENSITIVE_DATABASE_URL"] = old_value


if __name__ == "__main__":
    unittest.main()
