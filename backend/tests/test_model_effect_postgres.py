import hashlib
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from agency_runtime.model_effect_postgres import PostgresModelEffectStore
from agency_runtime.model_effect_store import (
    ModelEffectConflictError,
    ModelEffectIntent,
    ModelEffectStateError,
)
from agency_runtime.postgres import PostgresRuntimeDatabase, _connect_database_url

DATABASE_URL = os.environ.get("AGENCY_TEST_DATABASE_URL", "")
MIGRATION_DATABASE_URL = os.environ.get(
    "AGENCY_TEST_MIGRATION_DATABASE_URL", DATABASE_URL
)
NOW = "2026-07-24T13:00:00+00:00"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@unittest.skipUnless(DATABASE_URL, "AGENCY_TEST_DATABASE_URL is not configured")
class PostgresModelEffectStoreTests(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.tenant = "model-effect-tenant-{}".format(suffix)
        self.effect_id = "model-effect-{}".format(suffix)
        self.database_a = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.database_b = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.store_a = PostgresModelEffectStore(
            self.database_a, clock=lambda: NOW
        )
        self.store_b = PostgresModelEffectStore(
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
                "DELETE FROM public.model_effect_intents WHERE tenant_id = %s",
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
            "effect_id": self.effect_id,
            "tenant_id": self.tenant,
            "run_id": "run-001",
            "station": "writer",
            "source_artifact_id": "artifact-001",
            "source_artifact_hash": digest("artifact"),
            "instruction_hash": digest("instruction"),
            "provider_id": "openai",
            "model": "gpt-5.2",
            "endpoint_host": "api.openai.com",
            "request_sha256": digest("request"),
            "max_output_tokens": 128,
            "max_cost_micros": 500_000,
            "idempotency_digest": digest(
                "{}:idempotency".format(self.tenant)
            ),
            "binding_digest": digest("{}:binding".format(self.tenant)),
            "status": "pending",
            "execution_fencing_token": 1,
            "output_text": "",
            "output_sha256": "",
            "receipt": {},
            "failure_reason": "",
            "created_at": NOW,
            "updated_at": NOW,
            "completed_at": None,
            "revoked_at": None,
        }
        values.update(changes)
        return ModelEffectIntent(**values)

    def test_two_replicas_reserve_one_exact_binding_and_replay_result(self):
        model_effect = self.intent()
        with ThreadPoolExecutor(max_workers=2) as executor:
            reservations = [
                future.result()
                for future in (
                    executor.submit(self.store_a.reserve, model_effect),
                    executor.submit(self.store_b.reserve, model_effect),
                )
            ]
        self.assertEqual(
            sorted(item.executable for item in reservations), [False, True]
        )
        executable = next(item for item in reservations if item.executable)
        completed = self.store_a.complete(
            self.tenant,
            executable.intent.effect_id,
            1,
            "PostgreSQL governed model output",
            {
                "provider_id": "openai",
                "request_sha256": digest("request"),
                "output_sha256": digest(
                    "PostgreSQL governed model output"
                ),
            },
        )
        self.assertEqual(completed.status, "succeeded")
        replay = self.store_b.reserve(model_effect)
        self.assertTrue(replay.replayed)
        self.assertEqual(
            replay.intent.output_text, "PostgreSQL governed model output"
        )

    def test_different_keys_same_binding_have_one_executor(self):
        first = self.intent()
        second = self.intent(
            effect_id="{}-other".format(self.effect_id),
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
        self.assertEqual(len({item.intent.effect_id for item in reservations}), 1)

    def test_same_key_changed_binding_conflicts_across_replicas(self):
        self.store_a.reserve(self.intent())
        with self.assertRaises(ModelEffectConflictError):
            self.store_b.reserve(
                self.intent(binding_digest=digest("different-binding"))
            )

    def test_unknown_reconciliation_is_idempotent_and_conflict_safe(self):
        self.store_a.reserve(self.intent())
        self.store_a.mark_unknown(
            self.tenant, self.effect_id, 1, "provider_outcome_unknown"
        )
        blocked = self.store_b.reserve(self.intent())
        self.assertFalse(blocked.executable)
        receipt = {
            "provider_id": "openai",
            "reconciled": True,
            "reconciliation_binding_digest": digest("reconcile-binding"),
        }
        output = "Reconciled PostgreSQL output"
        reconciled = self.store_b.reconcile_success(
            self.tenant, self.effect_id, output, receipt
        )
        self.assertEqual(
            self.store_a.reconcile_success(
                self.tenant, self.effect_id, output, receipt
            ),
            reconciled,
        )
        with self.assertRaises(ModelEffectStateError):
            self.store_b.reconcile_success(
                self.tenant,
                self.effect_id,
                "Conflicting output",
                {
                    "provider_id": "openai",
                    "reconciled": True,
                    "reconciliation_binding_digest": digest("conflict"),
                },
            )


if __name__ == "__main__":
    unittest.main()
