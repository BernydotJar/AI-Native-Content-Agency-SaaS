import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


BRIEF = {
    "title": "Evidence-led launch",
    "objective": "Turn a campaign brief into a governed campaign package",
    "audience": "growth leaders",
    "platforms": ["x", "instagram"],
    "budget_cents": 50000,
    "campaign_goal": "qualified_demand",
}


class ApiVerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database = str(Path(self.temp.name) / "memory.sqlite3")
        self.client = TestClient(create_app(database_path=database, static_dir=Path(self.temp.name) / "missing"))

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_health_contract_is_explicitly_side_effect_free(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["external_side_effects_enabled"])

    def test_brief_to_scholar_to_greenlight_to_campaign_package(self):
        created = self.client.post("/api/v1/runs", json=BRIEF)
        self.assertEqual(created.status_code, 201)
        run = created.json()
        self.assertEqual(run["status"], "awaiting_greenlight")
        self.assertEqual(len(run["artifacts"]), 7)
        research = next(item for item in run["artifacts"] if item["kind"] == "research_dossier")
        self.assertEqual(
            set(research["payload"]["scholar"]),
            {"reencuadre_cognitivo", "tension_del_trade_off", "resolucion_operativa"},
        )
        self.assertEqual(run["agent_states"]["publisher"]["status"], "waiting_greenlight")

        approved = self.client.post(
            "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
            json={"reviewer": "commercial-owner", "note": "Approved sandbox package"},
        )
        self.assertEqual(approved.status_code, 200)
        completed = approved.json()
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(len(completed["greenlight"]["approved_artifact_ids"]), 7)
        self.assertEqual(len(completed["greenlight"]["approved_artifact_hashes"]), 7)
        self.assertEqual(completed["greenlight"]["authorized_channels"], ["x", "instagram"])
        package = next(item for item in completed["artifacts"] if item["kind"] == "campaign_package")
        self.assertFalse(package["payload"]["publication_performed"])

    def test_duplicate_run_and_second_decision_are_conflicts(self):
        first = self.client.post("/api/v1/runs", json=BRIEF)
        run_id = first.json()["run_id"]
        self.assertEqual(self.client.post("/api/v1/runs", json=BRIEF).status_code, 409)
        decision = {"reviewer": "owner", "note": "reject"}
        self.assertEqual(
            self.client.post(f"/api/v1/runs/{run_id}/greenlight/reject", json=decision).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/runs/{run_id}/greenlight/approve", json=decision).status_code,
            409,
        )


if __name__ == "__main__":
    unittest.main()
