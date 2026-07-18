import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agency_runtime.cli import main
from agency_runtime.memory import SQLiteMemory
from agency_runtime.models import (
    AGENT_SEQUENCE,
    AgentRole,
    AgentStatus,
    GreenlightDecision,
    MissionBrief,
    Platform,
    Provenance,
    RunStatus,
)
from agency_runtime.orchestrator import AgencyOrchestrator, GreenlightError
from agency_runtime.tools import MockCampaignPackagerTool, build_sandbox_toolset


FIXED_TIME = "2026-07-17T12:00:00+00:00"


def fixed_clock():
    return FIXED_TIME


def fixture_brief():
    return MissionBrief(
        title="Fixture launch",
        objective="Explain the agent operating model",
        audience="content leaders",
        platforms=(
            Platform.X,
            Platform.FACEBOOK,
            Platform.TIKTOK,
            Platform.INSTAGRAM,
        ),
        budget_cents=100000,
        source_asset="sandbox://fixtures/source.png",
        campaign_goal="qualified_demand",
    )


class SQLiteMemoryTests(unittest.TestCase):
    def test_observe_store_search_recall_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "memory.sqlite3"
            provenance = Provenance(
                source="test_fixture",
                locator="sandbox://tests/research/1",
                observed_at=FIXED_TIME,
                tool="test_tool",
                trace_id="trace-1",
            )
            with SQLiteMemory(database, clock=fixed_clock) as memory:
                observation = memory.observe(
                    "Audience prefers evidence-led launch stories",
                    provenance=provenance,
                    confidence=0.87,
                    tags=("audience", "greenlight"),
                )
                self.assertEqual(memory.count(), 0, "observe must not persist")
                stored = memory.store(observation)
                self.assertEqual(memory.count(), 1)
                found = memory.search("audience greenlight", min_confidence=0.8)
                self.assertEqual(found[0].record.memory_id, stored.memory_id)
                self.assertEqual(memory.recall(stored.memory_id).provenance, provenance)

            with SQLiteMemory(database, clock=fixed_clock) as reopened:
                recalled = reopened.recall(stored.memory_id)
                self.assertEqual(recalled.content, observation.content)
                self.assertEqual(recalled.tags, ("audience", "greenlight"))

    def test_memory_validation(self):
        provenance = Provenance(
            source="test",
            locator="sandbox://test",
            observed_at=FIXED_TIME,
        )
        with SQLiteMemory(clock=fixed_clock) as memory:
            with self.assertRaises(ValueError):
                memory.observe("invalid", provenance, confidence=1.1)
            with self.assertRaises(ValueError):
                memory.search("")


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.memory = SQLiteMemory(clock=fixed_clock)
        self.tools = build_sandbox_toolset()
        self.orchestrator = AgencyOrchestrator(
            tools=self.tools,
            memory=self.memory,
            clock=fixed_clock,
        )

    def tearDown(self):
        self.memory.close()

    def test_eight_agents_stop_at_greenlight_gate(self):
        run = self.orchestrator.start(fixture_brief())
        self.assertEqual(tuple(run.agent_states), AGENT_SEQUENCE)
        self.assertEqual(run.status, RunStatus.AWAITING_GREENLIGHT)
        for role in AGENT_SEQUENCE[:-1]:
            self.assertEqual(run.state_for(role).status, AgentStatus.READY)
        self.assertEqual(
            run.state_for(AgentRole.PUBLISHER).status,
            AgentStatus.WAITING_GREENLIGHT,
        )
        packager = self.tools.campaign_packager
        self.assertIsInstance(packager, MockCampaignPackagerTool)
        self.assertEqual(packager.call_count, 0)
        self.assertNotIn("campaign_package", [item.kind for item in run.artifacts])
        self.assertEqual(len(run.evidence), 7)
        self.assertTrue(all(item.sandbox for item in run.evidence))

    def test_approval_releases_packager_but_never_publishes(self):
        run = self.orchestrator.start(fixture_brief())
        approved = self.orchestrator.approve(
            run.run_id,
            reviewer="human-owner",
            note="Fixture approval",
        )
        self.assertEqual(approved.status, RunStatus.COMPLETED)
        self.assertEqual(approved.greenlight.decision, GreenlightDecision.APPROVED)
        self.assertEqual(
            approved.state_for(AgentRole.PUBLISHER).status,
            AgentStatus.READY,
        )
        package = approved.artifact("campaign_package")
        self.assertFalse(package.payload["publication_performed"])
        self.assertEqual(self.tools.campaign_packager.call_count, 1)
        self.assertEqual(len(approved.evidence), 8)
        with self.assertRaises(GreenlightError):
            self.orchestrator.approve(run.run_id, reviewer="second-reviewer")

    def test_rejection_keeps_packager_uninvoked(self):
        run = self.orchestrator.start(fixture_brief())
        rejected = self.orchestrator.reject(
            run.run_id,
            reviewer="human-owner",
            note="Claims need revision",
        )
        self.assertEqual(rejected.status, RunStatus.REJECTED)
        self.assertEqual(
            rejected.state_for(AgentRole.PUBLISHER).status,
            AgentStatus.BLOCKED,
        )
        self.assertEqual(self.tools.campaign_packager.call_count, 0)


class CliTests(unittest.TestCase):
    def _run_cli(self, *arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            return_code = main(["demo", *arguments])
        self.assertEqual(return_code, 0)
        return output.getvalue()

    def test_json_demo_is_deterministic_and_side_effect_free(self):
        first = self._run_cli("--approve", "--json")
        second = self._run_cli("--approve", "--json")
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertTrue(report["sandbox"])
        self.assertEqual(report["pre_greenlight_status"], "awaiting_greenlight")
        self.assertEqual(report["publisher_before_decision"], "waiting_greenlight")
        self.assertEqual(report["final_status"], "completed")
        self.assertEqual(len(report["agents"]), 8)
        self.assertEqual(len(report["evidence"]), 8)
        self.assertTrue(all(value == 0 for value in report["external_side_effects"].values()))

    def test_default_demo_leaves_publisher_waiting(self):
        report = json.loads(self._run_cli("--json"))
        self.assertEqual(report["final_status"], "awaiting_greenlight")
        self.assertIsNone(report["greenlight"])
        self.assertNotIn("campaign_package", report["artifact_kinds"])


if __name__ == "__main__":
    unittest.main()
