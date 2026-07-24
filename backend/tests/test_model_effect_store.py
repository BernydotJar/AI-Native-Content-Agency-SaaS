import hashlib
import tempfile
import unittest
from pathlib import Path

from agency_runtime.model_effect_store import (
    ModelEffectConflictError,
    ModelEffectIntent,
    ModelEffectStateError,
    SQLiteModelEffectStore,
)

NOW = "2026-07-24T12:00:00+00:00"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def intent(**changes):
    values = {
        "effect_id": "model-effect-001",
        "tenant_id": "tenant-alpha",
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
        "idempotency_digest": digest("idempotency"),
        "binding_digest": digest("binding"),
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


class SQLiteModelEffectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.store = SQLiteModelEffectStore(self.path, clock=lambda: NOW)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_success_and_compatible_replay_are_exact_once(self):
        reserved = self.store.reserve(intent())
        self.assertTrue(reserved.executable)
        completed = self.store.complete(
            "tenant-alpha",
            "model-effect-001",
            1,
            "Governed model output",
            {
                "provider_id": "openai",
                "request_sha256": digest("request"),
                "output_sha256": digest("Governed model output"),
            },
        )
        self.assertEqual(completed.status, "succeeded")
        replay = self.store.reserve(intent())
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.intent.output_text, "Governed model output")
        with self.assertRaises(ModelEffectStateError):
            self.store.complete(
                "tenant-alpha",
                "model-effect-001",
                1,
                "Different output",
                {"provider_id": "openai"},
            )

    def test_same_binding_different_key_reuses_intent_and_changed_binding_conflicts(self):
        first = self.store.reserve(intent())
        second = self.store.reserve(
            intent(
                effect_id="model-effect-other-key",
                idempotency_digest=digest("other-key"),
            )
        )
        self.assertTrue(first.executable)
        self.assertFalse(second.executable)
        self.assertEqual(second.intent.effect_id, first.intent.effect_id)
        with self.assertRaises(ModelEffectConflictError):
            self.store.reserve(intent(binding_digest=digest("changed-binding")))

    def test_unknown_blocks_until_idempotent_reconciliation(self):
        self.store.reserve(intent())
        unknown = self.store.mark_unknown(
            "tenant-alpha", "model-effect-001", 1, "provider_outcome_unknown"
        )
        self.assertEqual(unknown.status, "unknown")
        blocked = self.store.reserve(intent())
        self.assertFalse(blocked.executable)
        self.assertFalse(blocked.replayed)
        receipt = {
            "provider_id": "openai",
            "reconciled": True,
            "reconciliation_binding_digest": digest("reconcile-binding"),
        }
        output = "Recovered provider output"
        reconciled = self.store.reconcile_success(
            "tenant-alpha", "model-effect-001", output, receipt
        )
        self.assertEqual(reconciled.status, "succeeded")
        self.assertEqual(
            self.store.reconcile_success(
                "tenant-alpha", "model-effect-001", output, receipt
            ),
            reconciled,
        )
        with self.assertRaises(ModelEffectStateError):
            self.store.reconcile_success(
                "tenant-alpha",
                "model-effect-001",
                "Conflicting output",
                {
                    "provider_id": "openai",
                    "reconciled": True,
                    "reconciliation_binding_digest": digest("conflict"),
                },
            )

    def test_revocation_increments_fence_and_preserves_unknown(self):
        self.store.reserve(intent())
        second = intent(
            effect_id="model-effect-002",
            idempotency_digest=digest("second-key"),
            binding_digest=digest("second-binding"),
        )
        self.store.reserve(second)
        self.store.mark_unknown(
            "tenant-alpha", "model-effect-002", 1, "provider_outcome_unknown"
        )
        self.assertEqual(
            self.store.revoke_unused(
                "tenant-alpha", run_id="run-001", reason="run_revoked"
            ),
            1,
        )
        revoked = self.store.get("tenant-alpha", "model-effect-001")
        self.assertEqual(revoked.status, "revoked")
        self.assertEqual(revoked.execution_fencing_token, 2)
        with self.assertRaises(ModelEffectStateError):
            self.store.complete(
                "tenant-alpha",
                "model-effect-001",
                1,
                "stale",
                {"provider_id": "openai"},
            )
        self.assertEqual(
            self.store.get("tenant-alpha", "model-effect-002").status, "unknown"
        )

    def test_database_stores_output_but_not_prompt_or_raw_idempotency_key(self):
        self.store.reserve(intent())
        self.store.complete(
            "tenant-alpha",
            "model-effect-001",
            1,
            "Output is governed retained content",
            {"provider_id": "openai"},
        )
        raw = self.path.read_bytes()
        self.assertIn(b"Output is governed retained content", raw)
        self.assertNotIn(b"raw prompt must never persist", raw)
        self.assertNotIn(b"raw idempotency key", raw)
        columns = {
            row[1]
            for row in self.store._connection.execute(
                "PRAGMA table_info(model_effect_intents)"
            ).fetchall()
        }
        self.assertNotIn("prompt_text", columns)
        self.assertNotIn("idempotency_key", columns)


if __name__ == "__main__":
    unittest.main()
