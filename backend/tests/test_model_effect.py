import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from agency_runtime.model_effect import (
    ModelEffectAuthority,
    ModelEffectBlockedError,
    ModelEffectCommand,
    ModelEffectUnavailableError,
    ModelEffectUnknownError,
)
from agency_runtime.model_effect_store import (
    ModelEffectConflictError,
    SQLiteModelEffectStore,
)
from agency_runtime.model_gateway import ModelGateway, ModelRequest


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def environment():
    return {
        "AGENCY_MODEL_EXECUTION_ENABLED": "true",
        "AGENCY_MODEL_PROVIDER": "openai",
        "OPENAI_API_KEY": "model-secret-must-not-leak",
        "AGENCY_OPENAI_MODEL": "gpt-5.2",
        "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.openai.com",
        "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "128",
    }


def command(**changes):
    values = {
        "tenant_id": "tenant-alpha",
        "run_id": "run-001",
        "station": "writer",
        "source_artifact_id": "artifact-001",
        "source_artifact_hash": digest("source-artifact"),
        "instruction": "Improve the approved channel copy without inventing evidence.",
        "max_cost_micros": 500_000,
        "idempotency_key": "model-effect-command-001",
        "request": ModelRequest(
            request_id="model-effect-request-001",
            system="Return only governed campaign copy.",
            user="Improve the source artifact for the writer station.",
        ),
    }
    values.update(changes)
    return ModelEffectCommand(**values)


class FailingCompleteStore(SQLiteModelEffectStore):
    def complete(self, *args, **kwargs):
        raise OSError("simulated persistence failure after provider success")


class ModelEffectAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.store = SQLiteModelEffectStore(self.path)
        self.resources = []

    def tearDown(self):
        for item in self.resources:
            item.close()
        self.store.close()
        self.temp.cleanup()

    def authority(self, handler, *, enabled=True, store=None):
        gateway = ModelGateway.from_environment(
            environment(), transport=httpx.MockTransport(handler)
        )
        self.resources.append(gateway)
        return ModelEffectAuthority(
            store=store or self.store,
            gateway=gateway,
            enabled=enabled,
            clock=lambda: "2026-07-24T12:00:00+00:00",
        )

    def test_disabled_authority_never_reserves_or_calls_provider(self):
        calls = []
        authority = self.authority(lambda request: calls.append(request), enabled=False)
        with self.assertRaises(ModelEffectUnavailableError):
            authority.execute(command())
        self.assertEqual(calls, [])
        self.assertEqual(self.store.list_for_run("tenant-alpha", "run-001"), ())

    def test_success_and_different_key_replay_one_provider_result(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            body = json.loads(request.content)
            self.assertEqual(body["model"], "gpt-5.2")
            return httpx.Response(
                200,
                headers={"x-request-id": "provider-request-001"},
                json={
                    "id": "response-001",
                    "model": "gpt-5.2",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "A governed model-assisted draft.",
                                }
                            ],
                        }
                    ],
                    "usage": {
                        "input_tokens": 20,
                        "output_tokens": 7,
                        "total_tokens": 27,
                    },
                },
            )

        authority = self.authority(handler)
        first = authority.execute(command())
        second = authority.execute(
            command(idempotency_key="model-effect-compatible-key-002")
        )
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(first.effect_id, second.effect_id)
        self.assertEqual(second.output_text, "A governed model-assisted draft.")
        self.assertEqual(len(calls), 1)
        serialized = json.dumps(second.public_dict(), sort_keys=True)
        self.assertNotIn("model-secret-must-not-leak", serialized)
        self.assertNotIn("Improve the source artifact", serialized)
        self.assertNotIn("model-effect-compatible-key-002", serialized)

    def test_same_key_changed_instruction_conflicts_before_second_http(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(
                200,
                json={
                    "id": "response-001",
                    "output_text": "First output",
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                        "total_tokens": 2,
                    },
                },
            )

        authority = self.authority(handler)
        authority.execute(command())
        with self.assertRaises(Exception) as raised:
            authority.execute(command(instruction="Changed instruction"))
        self.assertEqual(type(raised.exception).__name__, "ModelEffectConflictError")
        self.assertEqual(len(calls), 1)

    def test_provider_error_is_unknown_and_blocks_retry(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503, text="ambiguous provider state")

        authority = self.authority(handler)
        with self.assertRaises(ModelEffectUnknownError):
            authority.execute(command())
        stored = self.store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(stored.status, "unknown")
        with self.assertRaises(ModelEffectBlockedError) as blocked:
            authority.execute(command())
        self.assertEqual(blocked.exception.status, "unknown")
        self.assertEqual(len(calls), 1)

    def test_persistence_failure_after_provider_success_blocks_retry(self):
        failing = FailingCompleteStore(self.path)
        self.addCleanup(failing.close)
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(
                200,
                json={
                    "id": "response-uncertain",
                    "output_text": "Provider may have completed",
                    "usage": {"input_tokens": 2, "output_tokens": 3},
                },
            )

        authority = self.authority(handler, store=failing)
        with self.assertRaises(ModelEffectUnknownError):
            authority.execute(command())
        stored = failing.list_for_run("tenant-alpha", "run-001")[0]
        self.assertIn(stored.status, {"pending", "unknown"})
        with self.assertRaises(ModelEffectBlockedError):
            authority.execute(command())
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
