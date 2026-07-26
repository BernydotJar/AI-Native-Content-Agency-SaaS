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


class PoliticalCampaignIntelligenceTests(unittest.TestCase):
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

    def test_political_brief_requires_grounded_context(self):
        with self.assertRaises(ValueError):
            MissionBrief(
                title="Campaña municipal",
                objective="Explicar una propuesta",
                audience="vecinos",
                platforms=(Platform.INSTAGRAM,),
                campaign_type="political",
                locale="es-GT",
                jurisdiction="Guatemala",
                office="alcalde",
                candidate_name="Candidatura de prueba",
                locality="Municipio de prueba",
                problem="Falta de información presupuestaria accesible",
                proposal="Publicar avances y ejecución presupuestaria",
                desired_action="Consultar el plan y enviar preguntas",
                disclosure="Contenido orgánico de campaña sujeto a revisión humana",
                evidence_claims=(),
            )

    def _office_specific_brief(self, office: str, locality: str) -> MissionBrief:
        return MissionBrief(
            title="Mensaje específico por cargo",
            objective="Explicar una propuesta verificable según las competencias del cargo",
            audience="ciudadanía del territorio",
            platforms=(Platform.INSTAGRAM,),
            campaign_type="political",
            locale="es-GT",
            jurisdiction="Guatemala",
            office=office,
            candidate_name="Candidatura de prueba",
            locality=locality,
            problem="La ciudadanía necesita información pública verificable",
            proposal="Publicar avances, decisiones y resultados verificables",
            desired_action="Consulta la propuesta y envía observaciones",
            disclosure="Contenido orgánico de una candidatura de prueba; requiere aprobación humana",
            legal_review_status="approved",
            legal_reviewed_by="legal-reviewer",
            evidence_claims=(
                {
                    "statement": "La propuesta contempla publicación periódica de información verificable.",
                    "source": "Plan de prueba 2027-2031",
                    "locator": "sección 2",
                    "verification_status": "verified",
                    "reviewed_by": "fact-reviewer",
                },
            ),
        )

    def test_writer_and_critique_are_office_specific_for_mayor_and_deputy(self):
        expectations = (
            ("alcalde", "Municipio de prueba", "municipio"),
            ("diputado", "Distrito de prueba", "legislativa"),
        )
        for office, locality, expected_term in expectations:
            with self.subTest(office=office):
                run = self.orchestrator.start(
                    self._office_specific_brief(office, locality)
                )
                writer = next(
                    item for item in run.artifacts if item.kind == "copy_deck"
                )
                risk = next(
                    item for item in run.artifacts if item.kind == "risk_report"
                )
                hook = writer.payload["variants"]["instagram"]["hook"].lower()
                self.assertIn(expected_term, hook)
                if office == "alcalde":
                    self.assertNotIn("municipio de municipio", hook)
                alignment = next(
                    item for item in risk.payload["checks"]
                    if item["name"] == "office_message_alignment"
                )
                self.assertTrue(alignment["passed"])
                self.assertTrue(risk.payload["publication_eligible"])

    def test_eight_station_political_run_is_spanish_grounded_and_critique_gated(self):
        brief = MissionBrief(
            title="Transparencia municipal verificable",
            objective="Explicar una propuesta de rendición de cuentas",
            audience="vecinas y vecinos del municipio",
            platforms=(Platform.INSTAGRAM, Platform.X),
            campaign_type="political",
            locale="es-GT",
            jurisdiction="Guatemala",
            office="alcalde",
            candidate_name="Candidatura de prueba",
            locality="Municipio de prueba",
            problem="La ciudadanía no encuentra avances y ejecución presupuestaria en un solo lugar",
            proposal="Publicar mensualmente avances, contratos y ejecución presupuestaria de prioridades municipales",
            desired_action="Consulta el plan completo y envía tus preguntas",
            disclosure="Contenido orgánico de una candidatura de prueba; requiere aprobación humana",
            legal_review_status="approved",
            legal_reviewed_by="human-legal-reviewer",
            evidence_claims=(
                {
                    "statement": "La propuesta contempla publicación mensual de avances y ejecución presupuestaria.",
                    "source": "Plan municipal de prueba 2027-2031",
                    "locator": "páginas 12-14",
                    "verification_status": "verified",
                    "reviewed_by": "human-fact-reviewer",
                },
            ),
        )
        run = self.orchestrator.start(brief)
        research = next(item for item in run.artifacts if item.kind == "research_dossier")
        writer = next(item for item in run.artifacts if item.kind == "copy_deck")
        media = next(item for item in run.artifacts if item.kind == "media_plan")
        risk = next(item for item in run.artifacts if item.kind == "risk_report")

        claims = research.payload["claim_ledger"]
        self.assertEqual(len(claims), 1)
        self.assertTrue(claims[0]["supported"])
        instagram = writer.payload["variants"]["instagram"]
        copy = " ".join((instagram["hook"], instagram["body"], instagram["cta"]))
        self.assertIn("municipio", copy.lower())
        self.assertNotIn("made clear", copy.lower())
        self.assertEqual(instagram["claim_map"], [claims[0]["claim_id"]])
        self.assertEqual(media.payload["instagram"]["format"], "carousel")
        self.assertTrue(media.payload["instagram"]["alt_text"])
        self.assertTrue(risk.payload["publication_eligible"])
        self.assertEqual(risk.payload["decision"], "pass")


    def test_pending_legal_review_blocks_greenlight_even_with_verified_claim(self):
        brief = MissionBrief(
            title="Revisión legal pendiente",
            objective="Preparar contenido para revisión legal",
            audience="vecinas y vecinos del municipio",
            platforms=(Platform.INSTAGRAM,),
            campaign_type="political",
            locale="es-GT",
            jurisdiction="Guatemala",
            office="alcalde",
            candidate_name="Candidatura de prueba",
            locality="Municipio de prueba",
            problem="Información pública dispersa",
            proposal="Publicar un tablero mensual de avances",
            desired_action="Consulta el borrador y envía observaciones",
            disclosure="Contenido orgánico de una candidatura de prueba; requiere aprobación humana",
            legal_review_status="pending",
            evidence_claims=(
                {
                    "statement": "La propuesta contempla un tablero mensual.",
                    "source": "Plan municipal revisado",
                    "locator": "sección 3",
                    "verification_status": "verified",
                    "reviewed_by": "human-fact-reviewer",
                },
            ),
        )
        run = self.orchestrator.start(brief)
        risk = next(item for item in run.artifacts if item.kind == "risk_report")
        self.assertFalse(risk.payload["publication_eligible"])
        legal_check = next(
            item for item in risk.payload["checks"]
            if item["name"] == "legal_review_approved"
        )
        self.assertFalse(legal_check["passed"])
        with self.assertRaises(GreenlightError):
            self.orchestrator.approve(run.run_id, reviewer="approver")

    def test_unverified_political_claim_blocks_greenlight(self):
        brief = MissionBrief(
            title="Propuesta todavía no verificada",
            objective="Preparar contenido para revisión",
            audience="vecinas y vecinos del municipio",
            platforms=(Platform.INSTAGRAM,),
            campaign_type="political",
            locale="es-GT",
            jurisdiction="Guatemala",
            office="alcalde",
            candidate_name="Candidatura de prueba",
            locality="Municipio de prueba",
            problem="Información pública dispersa",
            proposal="Publicar un tablero mensual de avances",
            desired_action="Consulta el borrador y envía observaciones",
            disclosure="Contenido orgánico de una candidatura de prueba; requiere aprobación humana",
            legal_review_status="approved",
            legal_reviewed_by="human-legal-reviewer",
            evidence_claims=(
                {
                    "statement": "La propuesta contempla un tablero mensual.",
                    "source": "Borrador de plan municipal",
                    "locator": "sección 3",
                    "verification_status": "unverified",
                    "reviewed_by": "",
                },
            ),
        )
        run = self.orchestrator.start(brief)
        risk = next(item for item in run.artifacts if item.kind == "risk_report")
        research = next(item for item in run.artifacts if item.kind == "research_dossier")
        self.assertFalse(research.payload["claim_ledger"][0]["supported"])
        self.assertFalse(risk.payload["publication_eligible"])
        self.assertEqual(risk.payload["decision"], "revise")
        self.assertEqual(
            run.state_for(AgentRole.PUBLISHER).status, AgentStatus.ATTENTION
        )
        with self.assertRaises(GreenlightError):
            self.orchestrator.approve(run.run_id, reviewer="approver")


if __name__ == "__main__":
    unittest.main()
