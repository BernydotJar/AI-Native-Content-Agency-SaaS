import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app
from agency_runtime.orchestrator import GreenlightError


ALPHA_KEY = "tenant-alpha-idempotency-key-2026"
BETA_KEY = "tenant-beta-idempotency-key-2026"
BRIEF = {
    "title": "Idempotent governed launch",
    "objective": "Prove compatible replay without duplicate provider work",
    "audience": "operations leaders",
    "platforms": ["x", "instagram"],
    "budget_cents": 42000,
    "campaign_goal": "qualified_demand",
}


def headers(api_key, idempotency_key=None):
    result = {"Authorization": "Bearer {}".format(api_key)}
    if idempotency_key is not None:
        result["Idempotency-Key"] = idempotency_key
    return result


class DurableIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "runtime.sqlite3")
        self.keys = {"tenant-alpha": ALPHA_KEY, "tenant-beta": BETA_KEY}

    def tearDown(self):
        self.temp.cleanup()

    def client(self):
        return TestClient(
            create_app(
                database_path=self.database,
                static_dir=Path(self.temp.name) / "missing",
                tenant_api_keys=self.keys,
            )
        )

    def test_governed_mutations_require_bounded_idempotency_key(self):
        with self.client() as client:
            missing = client.post("/api/v1/runs", json=BRIEF, headers=headers(ALPHA_KEY))
            self.assertEqual(missing.status_code, 422)
            self.assertEqual(missing.json()["code"], "request_validation_failed")
            self.assertEqual(
                missing.json()["errors"],
                [{"location": ["header", "Idempotency-Key"], "type": "missing"}],
            )

            malformed = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=headers(ALPHA_KEY, "bad key"),
            )
            self.assertEqual(malformed.status_code, 422)
            self.assertEqual(malformed.json()["code"], "request_validation_failed")
            self.assertNotIn("bad key", malformed.text)

    def test_openapi_requires_idempotency_header_and_exposes_revocation(self):
        with self.client() as client:
            schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        governed = (
            ("/api/v1/runs", "post"),
            ("/api/v1/runs/{run_id}/greenlight/approve", "post"),
            ("/api/v1/runs/{run_id}/greenlight/reject", "post"),
            ("/api/v1/runs/{run_id}/greenlight/revoke", "post"),
            ("/api/v1/runs/{run_id}/social-publications/{channel_id}", "post"),
            ("/api/v1/social-publications/{intent_id}/reconcile", "post"),
        )
        for path, method_name in governed:
            with self.subTest(path=path):
                operation = paths[path][method_name]
                header = next(
                    item
                    for item in operation["parameters"]
                    if item["in"] == "header" and item["name"] == "Idempotency-Key"
                )
                self.assertTrue(header["required"])
                self.assertEqual(header["schema"]["minLength"], 8)
                self.assertEqual(header["schema"]["maxLength"], 200)
                self.assertIn({"HTTPBearer": []}, operation["security"])

    def test_create_replay_returns_original_response_and_runs_provider_once(self):
        key = "run-create-replay-0001"
        with self.client() as client:
            first = client.post(
                "/api/v1/runs", json=BRIEF, headers=headers(ALPHA_KEY, key)
            )
            second = client.post(
                "/api/v1/runs", json=BRIEF, headers=headers(ALPHA_KEY, key)
            )
            self.assertEqual(first.status_code, 201)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.headers["X-Command-Replayed"], "true")
            self.assertEqual(second.json(), first.json())

            events = client.get(
                "/api/v1/audit-events", headers=headers(ALPHA_KEY)
            ).json()["events"]
            created = [event for event in events if event["action"] == "run.created"]
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0]["resource_id"], first.json()["run_id"])
            self.assertIn("idempotency", created[0]["payload"])
            self.assertNotIn(key, repr(created[0]))

        with sqlite3.connect(self.database) as connection:
            serialized = repr(
                connection.execute(
                    "SELECT event_id, payload_json FROM audit_events"
                ).fetchall()
            )
            self.assertNotIn(key, serialized)

    def test_create_replay_survives_restart_and_is_tenant_scoped(self):
        key = "run-create-restart-0001"
        with self.client() as first_client:
            first = first_client.post(
                "/api/v1/runs", json=BRIEF, headers=headers(ALPHA_KEY, key)
            )
            self.assertEqual(first.status_code, 201)

        with self.client() as restarted:
            replay = restarted.post(
                "/api/v1/runs", json=BRIEF, headers=headers(ALPHA_KEY, key)
            )
            beta = restarted.post(
                "/api/v1/runs", json=BRIEF, headers=headers(BETA_KEY, key)
            )
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertEqual(replay.json(), first.json())
            self.assertEqual(beta.status_code, 201)
            self.assertEqual(beta.json()["run_id"], first.json()["run_id"])
            self.assertEqual(beta.json()["tenant_id"], "tenant-beta")

    def test_same_key_changed_payload_returns_uniform_conflict_without_mutation(self):
        key = "run-create-conflict-0001"
        changed = dict(BRIEF, title="Different command")
        with self.client() as client:
            first = client.post(
                "/api/v1/runs", json=BRIEF, headers=headers(ALPHA_KEY, key)
            )
            conflict = client.post(
                "/api/v1/runs", json=changed, headers=headers(ALPHA_KEY, key)
            )
            self.assertEqual(first.status_code, 201)
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.json()["code"], "idempotency_conflict")
            self.assertEqual(
                conflict.json()["detail"],
                "idempotency key conflicts with a prior request",
            )
            self.assertNotIn(key, conflict.text)

            service = client.app.state.runtime_service
            self.assertEqual(service.run_store.count("tenant-alpha"), 1)
            self.assertEqual(service.run_store.audit_count("tenant-alpha"), 1)

    def test_different_key_for_same_deterministic_run_reuses_resource_and_records_receipt(self):
        with self.client() as client:
            first = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=headers(ALPHA_KEY, "run-create-first-0001"),
            )
            replay = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=headers(ALPHA_KEY, "run-create-second-0001"),
            )
            self.assertEqual(first.status_code, 201)
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertEqual(replay.json(), first.json())

            service = client.app.state.runtime_service
            self.assertEqual(service.run_store.count("tenant-alpha"), 1)
            self.assertEqual(service.run_store.audit_count("tenant-alpha"), 2)
            actions = [event.action for event in service.audit_events("tenant-alpha", 0, 100)]
            self.assertEqual(actions, ["run.created", "run.reused"])

    def test_greenlight_replay_executes_packager_once_and_changed_payload_conflicts(self):
        with self.client() as client:
            created = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=headers(ALPHA_KEY, "run-create-decision-0001"),
            )
            run_id = created.json()["run_id"]
            decision = {"reviewer": "owner", "note": "approved once"}
            key = "greenlight-approve-replay-0001"

            first = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json=decision,
                headers=headers(ALPHA_KEY, key),
            )
            replay = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json=decision,
                headers=headers(ALPHA_KEY, key),
            )
            conflict = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={"reviewer": "owner", "note": "changed"},
                headers=headers(ALPHA_KEY, key),
            )
            self.assertEqual(first.status_code, 200)
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.json(), first.json())
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.json()["code"], "idempotency_conflict")

            packages = [
                item for item in first.json()["artifacts"] if item["kind"] == "campaign_package"
            ]
            self.assertEqual(len(packages), 1)
            events = client.get(
                "/api/v1/audit-events", headers=headers(ALPHA_KEY)
            ).json()["events"]
            self.assertEqual(
                len([event for event in events if event["action"] == "greenlight.approved"]),
                1,
            )

    def test_greenlight_revocation_is_idempotent_and_fences_stale_authority(self):
        with self.client() as client:
            created = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=headers(ALPHA_KEY, "run-create-revoke-0001"),
            )
            run_id = created.json()["run_id"]
            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={"reviewer": "owner", "note": "temporary approval"},
                headers=headers(ALPHA_KEY, "greenlight-approve-revoke-0001"),
            )
            self.assertEqual(approved.status_code, 200)
            greenlight = approved.json()["greenlight"]
            self.assertEqual(greenlight["fencing_token"], 1)
            self.assertIsNone(greenlight["revoked_at"])

            service = client.app.state.runtime_service
            service.assert_greenlight_effect_authorized(
                "tenant-alpha",
                run_id,
                greenlight["greenlight_id"],
                1,
                tuple(greenlight["approved_artifact_ids"]),
                tuple(greenlight["approved_artifact_hashes"]),
                "x",
                42000,
            )

            request = {"reviewer": "owner", "reason": "campaign paused"}
            key = "greenlight-revoke-replay-0001"
            revoked = client.post(
                "/api/v1/runs/{}/greenlight/revoke".format(run_id),
                json=request,
                headers=headers(ALPHA_KEY, key),
            )
            replay = client.post(
                "/api/v1/runs/{}/greenlight/revoke".format(run_id),
                json=request,
                headers=headers(ALPHA_KEY, key),
            )
            conflict = client.post(
                "/api/v1/runs/{}/greenlight/revoke".format(run_id),
                json={"reviewer": "owner", "reason": "different reason"},
                headers=headers(ALPHA_KEY, key),
            )
            self.assertEqual(revoked.status_code, 200)
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.json(), revoked.json())
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.json()["code"], "idempotency_conflict")
            self.assertEqual(revoked.json()["status"], "revoked")
            self.assertEqual(revoked.json()["greenlight"]["fencing_token"], 2)
            self.assertIsNotNone(revoked.json()["greenlight"]["revoked_at"])

            with self.assertRaisesRegex(GreenlightError, "not active"):
                service.assert_greenlight_effect_authorized(
                    "tenant-alpha",
                    run_id,
                    greenlight["greenlight_id"],
                    1,
                    tuple(greenlight["approved_artifact_ids"]),
                    tuple(greenlight["approved_artifact_hashes"]),
                    "x",
                    42000,
                )

            events = client.get(
                "/api/v1/audit-events", headers=headers(ALPHA_KEY)
            ).json()["events"]
            self.assertEqual(
                len([event for event in events if event["action"] == "greenlight.revoked"]),
                1,
            )

    def test_effect_guard_rejects_altered_envelope_before_revocation(self):
        with self.client() as client:
            created = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=headers(ALPHA_KEY, "run-create-envelope-0001"),
            )
            run_id = created.json()["run_id"]
            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={"reviewer": "owner", "note": "bounded"},
                headers=headers(ALPHA_KEY, "greenlight-approve-envelope-0001"),
            ).json()
            greenlight = approved["greenlight"]
            service = client.app.state.runtime_service

            approved_ids = tuple(greenlight["approved_artifact_ids"])
            approved_hashes = tuple(greenlight["approved_artifact_hashes"])
            cases = [
                ("wrong-greenlight", 1, approved_ids, approved_hashes, "x", 42000),
                (greenlight["greenlight_id"], 2, approved_ids, approved_hashes, "x", 42000),
                (greenlight["greenlight_id"], 1, ("altered",), approved_hashes, "x", 42000),
                (
                    greenlight["greenlight_id"],
                    1,
                    approved_ids,
                    approved_hashes,
                    "facebook",
                    42000,
                ),
                (greenlight["greenlight_id"], 1, approved_ids, approved_hashes, "x", 42001),
            ]
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    with self.assertRaises(GreenlightError):
                        service.assert_greenlight_effect_authorized(
                            "tenant-alpha", run_id, *arguments
                        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
