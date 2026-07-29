import hashlib
import tempfile
import unittest
from pathlib import Path

from agency_runtime.social_publication_store import (
    SQLiteSocialPublicationStore,
    SocialPublicationConflictError,
    SocialPublicationIntent,
    SocialPublicationStateError,
)


NOW = "2026-07-23T20:30:00+00:00"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def intent(**changes):
    values = {
        "intent_id": "publication-intent-001",
        "tenant_id": "tenant-alpha",
        "channel_id": "x",
        "account_id": "account-001",
        "run_id": "run-001",
        "artifact_id": "artifact-001",
        "artifact_hash": digest("artifact"),
        "content_hash": digest("content"),
        "media_url_hash": None,
        "media_hash": None,
        "confirmation_hash": None,
        "greenlight_id": "greenlight-001",
        "greenlight_fencing_token": 0,
        "budget_cents": 0,
        "idempotency_digest": digest("idempotency-key"),
        "binding_digest": digest("binding"),
        "status": "pending",
        "execution_fencing_token": 1,
        "provider_container_id": None,
        "provider_post_id": None,
        "receipt": {},
        "failure_reason": "",
        "created_at": NOW,
        "updated_at": NOW,
        "completed_at": None,
        "revoked_at": None,
    }
    values.update(changes)
    return SocialPublicationIntent(**values)


class SQLiteSocialPublicationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.store = SQLiteSocialPublicationStore(self.path, clock=lambda: NOW)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_reserve_success_and_replay_are_exact_once(self):
        reserved = self.store.reserve(intent())
        self.assertTrue(reserved.executable)
        self.assertFalse(reserved.replayed)
        completed = self.store.complete(
            "tenant-alpha",
            "publication-intent-001",
            1,
            "post-001",
            {
                "provider": "x",
                "provider_post_id": "post-001",
                "request_id": "provider-request-001",
            },
        )
        self.assertEqual(completed.status, "succeeded")
        replay = self.store.reserve(intent())
        self.assertFalse(replay.executable)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.intent.provider_post_id, "post-001")
        with self.assertRaises(SocialPublicationStateError):
            self.store.complete(
                "tenant-alpha",
                "publication-intent-001",
                1,
                "post-002",
                {"provider": "x", "provider_post_id": "post-002"},
            )

    def test_same_binding_with_different_key_returns_existing_intent(self):
        first = self.store.reserve(intent())
        second = self.store.reserve(
            intent(
                intent_id="publication-intent-different-key",
                idempotency_digest=digest("different-idempotency-key"),
            )
        )
        self.assertTrue(first.executable)
        self.assertFalse(second.executable)
        self.assertEqual(second.intent.intent_id, first.intent.intent_id)

    def test_same_key_with_changed_binding_conflicts(self):
        self.store.reserve(intent())
        with self.assertRaises(SocialPublicationConflictError):
            self.store.reserve(intent(binding_digest=digest("different-binding")))

    def test_pending_unknown_failed_and_revoked_never_replay_as_executable(self):
        pending = self.store.reserve(intent())
        self.assertTrue(pending.executable)
        duplicate_pending = self.store.reserve(intent())
        self.assertFalse(duplicate_pending.executable)
        self.assertFalse(duplicate_pending.replayed)

        unknown = self.store.mark_unknown(
            "tenant-alpha", "publication-intent-001", 1, "provider_outcome_unknown"
        )
        self.assertEqual(unknown.status, "unknown")
        duplicate_unknown = self.store.reserve(intent())
        self.assertFalse(duplicate_unknown.executable)
        self.assertFalse(duplicate_unknown.replayed)

        reconciled = self.store.reconcile_success(
            "tenant-alpha",
            "publication-intent-001",
            "post-reconciled-001",
            {
                "provider": "x",
                "provider_post_id": "post-reconciled-001",
                "reconciled": True,
                "reconciliation_binding_digest": digest("reconcile-binding"),
            },
        )
        self.assertEqual(reconciled.status, "succeeded")
        replayed = self.store.reconcile_success(
            "tenant-alpha",
            "publication-intent-001",
            "post-reconciled-001",
            {
                "provider": "x",
                "provider_post_id": "post-reconciled-001",
                "reconciled": True,
                "reconciliation_binding_digest": digest("reconcile-binding"),
            },
        )
        self.assertEqual(replayed, reconciled)
        with self.assertRaises(SocialPublicationStateError):
            self.store.reconcile_success(
                "tenant-alpha",
                "publication-intent-001",
                "post-conflicting-002",
                {
                    "provider": "x",
                    "provider_post_id": "post-conflicting-002",
                    "reconciled": True,
                    "reconciliation_binding_digest": digest("conflicting-binding"),
                },
            )

        failed_intent = intent(
            intent_id="publication-intent-002",
            idempotency_digest=digest("failed-key"),
            binding_digest=digest("failed-binding"),
        )
        self.store.reserve(failed_intent)
        failed = self.store.mark_failed(
            "tenant-alpha", "publication-intent-002", 1, "provider_rejected"
        )
        self.assertEqual(failed.status, "failed")
        self.assertFalse(self.store.reserve(failed_intent).executable)

    def test_instagram_container_is_durable_before_post_receipt(self):
        instagram = intent(
            intent_id="publication-intent-ig",
            channel_id="instagram",
            idempotency_digest=digest("instagram-key"),
            binding_digest=digest("instagram-binding"),
            media_url_hash=digest("https://cdn.example/media.jpg"),
            media_hash=digest("media-bytes"),
        )
        self.store.reserve(instagram)
        pending = self.store.record_container(
            "tenant-alpha", "publication-intent-ig", 1, "container-001"
        )
        self.assertEqual(pending.status, "pending")
        self.assertEqual(pending.provider_container_id, "container-001")
        unknown = self.store.mark_unknown(
            "tenant-alpha", "publication-intent-ig", 1, "publish_outcome_unknown"
        )
        self.assertEqual(unknown.provider_container_id, "container-001")
        self.assertEqual(unknown.status, "unknown")

    def test_disconnect_or_greenlight_revocation_only_revokes_unused_pending(self):
        first = intent()
        second = intent(
            intent_id="publication-intent-002",
            idempotency_digest=digest("second-key"),
            binding_digest=digest("second-binding"),
        )
        third = intent(
            intent_id="publication-intent-003",
            idempotency_digest=digest("third-key"),
            binding_digest=digest("third-binding"),
        )
        self.store.reserve(first)
        self.store.reserve(second)
        self.store.reserve(third)
        self.store.mark_unknown(
            "tenant-alpha", "publication-intent-003", 1, "provider_outcome_unknown"
        )
        self.assertEqual(
            self.store.revoke_unused(
                "tenant-alpha",
                channel_id="x",
                account_id="account-001",
                reason="account_disconnected",
            ),
            2,
        )
        self.assertEqual(self.store.get("tenant-alpha", first.intent_id).status, "revoked")
        self.assertEqual(self.store.get("tenant-alpha", second.intent_id).status, "revoked")
        self.assertEqual(self.store.get("tenant-alpha", third.intent_id).status, "unknown")

    def test_database_never_contains_idempotency_key_or_content(self):
        self.store.reserve(intent())
        raw = self.path.read_bytes()
        self.assertNotIn(b"idempotency-key", raw)
        self.assertNotIn(b"RAW COPY MUST NEVER PERSIST", raw)
        self.assertNotIn(b"https://cdn.example/media.jpg", raw)
        columns = {
            row[1]
            for row in self.store._connection.execute(
                "PRAGMA table_info(social_publication_intents)"
            ).fetchall()
        }
        self.assertNotIn("content_text", columns)
        self.assertNotIn("media_url", columns)


if __name__ == "__main__":
    unittest.main()
