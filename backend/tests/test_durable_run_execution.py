import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


API_KEY = "durable-run-operator-key-material-2026"
BRIEF = {
    "title": "Durable asynchronous campaign",
    "objective": "Expose truthful station progress from durable checkpoints",
    "audience": "campaign operators",
    "platforms": ["x", "instagram"],
    "budget_cents": 0,
    "campaign_goal": "verification",
}


def headers(key="durable-run-create-0001"):
    return {
        "Authorization": "Bearer {}".format(API_KEY),
        "Idempotency-Key": key,
        "Prefer": "respond-async",
    }


class DurableRunExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "runtime.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def app(self):
        return create_app(
            database_path=self.database,
            static_dir=Path(self.temp.name) / "missing",
            tenant_api_keys={"tenant-async": API_KEY},
            run_worker_poll_interval_seconds=60,
            run_lease_seconds=30,
        )

    def test_async_preference_returns_202_and_each_claim_persists_one_checkpoint(self):
        app = self.app()
        with TestClient(app) as client:
            created = client.post("/api/v1/runs", json=BRIEF, headers=headers())
            self.assertEqual(created.status_code, 202)
            self.assertEqual(created.headers["Preference-Applied"], "respond-async")
            self.assertEqual(created.headers["Location"], "/api/v1/runs/{}".format(created.json()["run_id"]))
            initial = created.json()
            self.assertEqual(initial["status"], "queued")
            self.assertEqual(initial["artifacts"], [])
            self.assertEqual(initial["execution"]["fencing_token"], 0)

            service = app.state.runtime_service
            run_id = initial["run_id"]
            snapshots = []
            for expected_fence in range(1, 15):
                self.assertTrue(service.execute_one_queued_run("test-worker"))
                current = client.get(
                    "/api/v1/runs/{}".format(run_id),
                    headers={"Authorization": "Bearer {}".format(API_KEY)},
                ).json()
                snapshots.append(current)
                self.assertEqual(current["execution"]["fencing_token"], expected_fence)
                self.assertEqual(current["execution"]["lease_owner"], "")
                self.assertIsNone(current["execution"]["lease_expires_at"])

            final = snapshots[-1]
            self.assertEqual(final["status"], "awaiting_greenlight")
            self.assertEqual(final["execution"]["state"], "awaiting_greenlight")
            self.assertEqual(final["execution"]["next_station"], "publisher")
            self.assertEqual(len(final["artifacts"]), 7)
            self.assertEqual(
                [item["kind"] for item in final["artifacts"]],
                [
                    "mission_charter",
                    "research_dossier",
                    "channel_strategy",
                    "growth_forecast",
                    "copy_deck",
                    "media_plan",
                    "risk_report",
                ],
            )
            self.assertEqual(snapshots[0]["agent_states"]["ceo"]["status"], "processing")
            self.assertEqual(snapshots[1]["agent_states"]["ceo"]["status"], "ready")
            self.assertEqual(snapshots[2]["agent_states"]["research"]["status"], "processing")

            events = client.get(
                "/api/v1/audit-events",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            ).json()["events"]
            checkpoints = [event for event in events if event["action"] == "run.checkpointed"]
            self.assertEqual(len(checkpoints), 14)
            self.assertEqual(
                [event["payload"]["fencing_token"] for event in checkpoints],
                list(range(1, 15)),
            )

    def test_active_lease_blocks_and_expired_lease_is_recovered_after_restart(self):
        first_app = self.app()
        with TestClient(first_app) as first:
            created = first.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Lease recovery campaign"),
                headers=headers("durable-run-lease-0001"),
            )
            self.assertEqual(created.status_code, 202)
            run_id = created.json()["run_id"]
            store = first_app.state.runtime_service.run_store
            run = store.get("tenant-async", run_id)
            run.execution.state = "leased"
            run.execution.lease_owner = "crashed-worker"
            run.execution.lease_expires_at = (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat()
            run.execution.fencing_token = 7
            store.save("tenant-async", run, expected_status="queued")
            self.assertFalse(first_app.state.runtime_service.execute_one_queued_run("replacement-worker"))

        second_app = self.app()
        with TestClient(second_app) as second:
            store = second_app.state.runtime_service.run_store
            recovered = store.get("tenant-async", run_id)
            recovered.execution.lease_expires_at = (
                datetime.now(timezone.utc) - timedelta(seconds=1)
            ).isoformat()
            store.save("tenant-async", recovered, expected_status="queued")
            self.assertTrue(second_app.state.runtime_service.execute_one_queued_run("replacement-worker"))
            checkpoint = store.get("tenant-async", run_id)
            self.assertEqual(checkpoint.status.value, "running")
            self.assertEqual(checkpoint.execution.fencing_token, 8)
            self.assertEqual(checkpoint.execution.lease_owner, "")
            self.assertEqual(checkpoint.state_for(next(iter(checkpoint.agent_states))).status.value, "processing")

    def test_without_preference_preserves_inline_contract(self):
        with TestClient(self.app()) as client:
            inline = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Inline compatibility campaign"),
                headers={
                    "Authorization": "Bearer {}".format(API_KEY),
                    "Idempotency-Key": "durable-run-inline-0001",
                },
            )
            self.assertEqual(inline.status_code, 201)
            self.assertEqual(inline.json()["status"], "awaiting_greenlight")
            self.assertEqual(inline.json()["execution"]["state"], "awaiting_greenlight")


if __name__ == "__main__":
    unittest.main()
