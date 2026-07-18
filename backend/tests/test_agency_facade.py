import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "repository_agency_facade", REPOSITORY_ROOT / "agency.py"
)
AGENCY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGENCY)


class AgencyFacadeTests(unittest.TestCase):
    def test_facade_exposes_local_eight_agent_runtime(self):
        self.assertFalse(AGENCY.EXTERNAL_FRAMEWORK_REQUIRED)
        self.assertEqual(AGENCY.RUNTIME_MODE, "deterministic_sandbox")
        self.assertEqual(len(AGENCY.AGENT_SEQUENCE), 8)
        orchestrator = AGENCY.build_orchestrator(
            clock=lambda: "2026-07-17T12:00:00+00:00"
        )
        try:
            self.assertEqual(len(orchestrator.tools.__dict__), 8)
        finally:
            orchestrator.memory.close()

    def test_facade_cli_defaults_to_safe_demo(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            return_code = AGENCY.main(["demo", "--json"])
        report = json.loads(output.getvalue())
        self.assertEqual(return_code, 0)
        self.assertTrue(report["sandbox"])
        self.assertEqual(report["final_status"], "awaiting_greenlight")
        self.assertEqual(report["external_side_effects"]["publications"], 0)


if __name__ == "__main__":
    unittest.main()
