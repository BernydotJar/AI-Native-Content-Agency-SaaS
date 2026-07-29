import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "watch-social-connection-backups.py"
SPEC = importlib.util.spec_from_file_location("social_backup_watcher", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load social connection backup watcher")
WATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCHER)


class SocialConnectionBackupWatcherTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        database = root / "runtime.sqlite3"
        connection = sqlite3.connect(database)
        connection.execute(
            """
            CREATE TABLE social_connections (
                tenant_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                account_username TEXT NOT NULL,
                encrypted_tokens TEXT NOT NULL,
                key_id TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                token_expires_at TEXT,
                connected_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, channel_id)
            )
            """
        )
        connection.commit()
        connection.close()
        return database

    def test_snapshot_runs_only_when_social_connection_state_changes(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            database = self._database(root)
            backup_dir = root / "backups"
            state_file = root / "state.sha256"
            manifest_file = root / "latest-manifest"

            first = WATCHER.snapshot_if_changed(
                database, backup_dir, state_file, manifest_file
            )
            first_manifest = Path(manifest_file.read_text().strip())
            repeated = WATCHER.snapshot_if_changed(
                database, backup_dir, state_file, manifest_file
            )

            connection = sqlite3.connect(database)
            connection.execute(
                """
                INSERT INTO social_connections(
                    tenant_id, channel_id, account_id, account_username,
                    encrypted_tokens, key_id, scopes_json, token_expires_at,
                    connected_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "local-tenant",
                    "x",
                    "12345",
                    "beesheep",
                    "encrypted-token-value",
                    "local-social-v1",
                    json.dumps(["tweet.read", "tweet.write"]),
                    None,
                    "2026-07-28T00:00:00+00:00",
                    "2026-07-28T00:00:00+00:00",
                ),
            )
            connection.commit()
            connection.close()

            changed = WATCHER.snapshot_if_changed(
                database, backup_dir, state_file, manifest_file
            )
            changed_manifest = Path(manifest_file.read_text().strip())

            self.assertEqual(first, "created")
            self.assertEqual(repeated, "unchanged")
            self.assertEqual(changed, "created")
            self.assertTrue(first_manifest.is_file())
            self.assertTrue(changed_manifest.is_file())
            self.assertNotEqual(first_manifest, changed_manifest)
            self.assertEqual(state_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(manifest_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backup_dir.stat().st_mode & 0o777, 0o700)

    def test_digest_changes_when_encrypted_token_changes(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            database = self._database(root)
            connection = sqlite3.connect(database)
            values = (
                "local-tenant",
                "instagram",
                "27525095797156898",
                "beesheep2",
                "ciphertext-one",
                "local-social-v1",
                json.dumps(["instagram_business_basic"]),
                None,
                "2026-07-28T00:00:00+00:00",
                "2026-07-28T00:00:00+00:00",
            )
            connection.execute(
                "INSERT INTO social_connections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
            connection.commit()
            first = WATCHER.social_connection_digest(database)
            connection.execute(
                "UPDATE social_connections SET encrypted_tokens = ?, updated_at = ?",
                ("ciphertext-two", "2026-07-28T00:01:00+00:00"),
            )
            connection.commit()
            connection.close()
            second = WATCHER.social_connection_digest(database)
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
