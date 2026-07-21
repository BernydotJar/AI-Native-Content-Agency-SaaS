import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify-operability.py"
SPEC = importlib.util.spec_from_file_location("verify_operability", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load operability verifier")
OPERABILITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPERABILITY)


class OperabilityContractTests(unittest.TestCase):
    def test_repository_contract_and_synthetic_exercises_pass(self):
        result = OPERABILITY.validate_repository(ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertGreaterEqual(result["slos"], 4)
        self.assertGreaterEqual(result["alerts"], 6)
        self.assertGreaterEqual(result["exercises"], 7)

    def test_error_budget_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            OPERABILITY.copy_contract(ROOT, root)
            path = root / "ops" / "slo-catalog.json"
            data = json.loads(path.read_text())
            data["slos"][0]["error_budget_minutes"] += 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                OPERABILITY.OperabilityValidationError, "error budget"
            ):
                OPERABILITY.validate_repository(root)

    def test_missing_prometheus_rule_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            OPERABILITY.copy_contract(ROOT, root)
            for relative in (
                "infra/monitoring/prometheus-rules.yaml",
                "infra/helm/ai-native-content-agency/files/prometheus-rules.json",
            ):
                path = root / relative
                data = json.loads(path.read_text())
                data["groups"][0]["rules"] = data["groups"][0]["rules"][1:]
                path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                OPERABILITY.OperabilityValidationError, "parity mismatch"
            ):
                OPERABILITY.validate_repository(root)

    def test_missing_rule_or_runbook_anchor_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            OPERABILITY.copy_contract(ROOT, root)
            path = root / "ops" / "alert-catalog.json"
            data = json.loads(path.read_text())
            data["alerts"][0]["runbook"] = (
                "docs/runbooks/incident-response.md#missing-anchor"
            )
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                OPERABILITY.OperabilityValidationError, "runbook anchor"
            ):
                OPERABILITY.validate_repository(root)

    def test_unexpected_alert_exercise_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            OPERABILITY.copy_contract(ROOT, root)
            path = root / "ops" / "alert-exercises.json"
            data = json.loads(path.read_text())
            data["scenarios"][0]["expected_alerts"] = [
                "AgencyRuntimeUnavailable"
            ]
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                OPERABILITY.OperabilityValidationError, "exercise"
            ):
                OPERABILITY.validate_repository(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
