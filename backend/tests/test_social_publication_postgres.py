import hashlib
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from agency_runtime.postgres import PostgresRuntimeDatabase, _connect_database_url
from agency_runtime.social_publication_postgres import PostgresSocialPublicationStore
from agency_runtime.social_publication_store import (
    SocialPublicationConflictError,
    SocialPublicationIntent,
    SocialPublicationStateError,
)


DATABASE_URL = os.environ.get("AGENCY_TEST_DATABASE_URL", "")
MIGRATION_DATABASE_URL = os.environ.get(
    "AGENCY_TEST_MIGRATION_DATABASE_URL", DATABASE_URL
)
NOW = "2026-07-23T20:30:00+00:00"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@unittest.skipUnless(DATABASE_URL, "AGENCY_TEST_DATABASE_URL is not configured")
class PostgresSocialPublicationStoreTests(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.tenant = "publication-tenant-{}".format(suffix)
        self.intent_id = "publication-intent-{}".format(suffix)
        self.database_a = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.database_b = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.store_a = PostgresSocialPublicationStore(
            self.database_a, clock=lambda: NOW
        )
        self.store_b = PostgresSocialPublicationStore(
            self.database_b, clock=lambda: NOW
        )

    def tearDown(self):
        self.database_a.close()
        self.database_b.close()
        connection = _connect_database_url(
            MIGRATION_DATABASE_URL, timeout_seconds=10
        )
        try:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM public.social_publication_intents WHERE tenant_id = %s",
                (self.tenant,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def intent(self, **changes):
        values = {
            "intent_id": self.intent_id,
            "tenant_id": self.tenant,
            "channel_id": "x",
            "account_id": "account-001",
            "run_id": "run-001",
            "artifact_id": "artifact-001",
            "artifact_hash": digest("artifact"),
            "content_hash": digest("content"),
            "media_url_hash": None,
            "media_hash": None,
            "greenlight_id": "greenlight-001",
            "greenlight_fencing_token": 0,
            "budget_cents": 0,
            "idempotency_digest": digest("{}:idempotency".format(self.tenant)),
            "binding_digest": digest("{}:binding".format(self.tenant)),
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

    def test_two_workers_reserve_one_exact_binding_and_replay_receipt(self):
        publication = self.intent()
        with ThreadPoolExecutor(max_workers=2) as executor:
            reservations = [
                future.result()
                for future in (
                    executor.submit(self.store_a.reserve, publication),
                    executor.submit(self.store_b.reserve, publication),
                )
            ]
        self.assertEqual(
            sorted(item.executable for item in reservations), [False, True]
        )
        self.assertTrue(
            all(item.intent.binding_digest == publication.binding_digest for item in reservations)
        )
        executable = next(item for item in reservations if item.executable)
        completed = self.store_a.complete(
            self.tenant,
            executable.intent.intent_id,
            1,
            "post-001",
            {
                "provider": "x",
                "provider_post_id": "post-001",
                "request_id": "provider-request-001",
            },
        )
        self.assertEqual(completed.status, "succeeded")
        replay = self.store_b.reserve(publication)
        self.assertFalse(replay.executable)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.intent.provider_post_id, "post-001")

    def test_same_binding_with_different_keys_has_one_executor_across_workers(self):
        first = self.intent()
        second = self.intent(
            intent_id="{}-other".format(self.intent_id),
            idempotency_digest=digest("{}:other-key".format(self.tenant)),
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            reservations = [
                future.result()
                for future in (
                    executor.submit(self.store_a.reserve, first),
                    executor.submit(self.store_b.reserve, second),
                )
            ]
        self.assertEqual(
            sorted(item.executable for item in reservations), [False, True]
        )
        self.assertEqual(
            len({item.intent.intent_id for item in reservations}), 1
        )

    def test_changed_binding_conflicts_and_stale_fence_is_rejected(self):
        publication = self.intent()
        self.store_a.reserve(publication)
        with self.assertRaises(SocialPublicationConflictError):
            self.store_b.reserve(
                self.intent(binding_digest=digest("different-binding"))
            )
        with self.assertRaises(SocialPublicationStateError):
            self.store_a.complete(
                self.tenant,
                self.intent_id,
                2,
                "post-002",
                {"provider": "x", "provider_post_id": "post-002"},
            )

    def test_unknown_blocks_replay_until_manual_reconciliation(self):
        publication = self.intent()
        self.store_a.reserve(publication)
        unknown = self.store_a.mark_unknown(
            self.tenant, self.intent_id, 1, "provider_outcome_unknown"
        )
        self.assertEqual(unknown.status, "unknown")
        blocked = self.store_b.reserve(publication)
        self.assertFalse(blocked.executable)
        self.assertFalse(blocked.replayed)
        reconciled = self.store_b.reconcile_success(
            self.tenant,
            self.intent_id,
            "post-reconciled-001",
            {
                "provider": "x",
                "provider_post_id": "post-reconciled-001",
                "reconciled": True,
                "reconciliation_binding_digest": digest("reconcile-binding"),
            },
        )
        self.assertEqual(reconciled.status, "succeeded")
        replayed = self.store_b.reconcile_success(
            self.tenant,
            self.intent_id,
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
            self.store_b.reconcile_success(
                self.tenant,
                self.intent_id,
                "post-conflicting-002",
                {
                    "provider": "x",
                    "provider_post_id": "post-conflicting-002",
                    "reconciled": True,
                    "reconciliation_binding_digest": digest("conflicting-binding"),
                },
            )


if __name__ == "__main__":
    unittest.main()
