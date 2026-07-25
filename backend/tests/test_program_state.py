import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "validate-program-state.py"
SPEC = importlib.util.spec_from_file_location("validate_program_state", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load program-state validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ProgramStateValidationTests(unittest.TestCase):
    def test_repository_program_state_is_valid(self):
        result = VALIDATOR.validate_repository(ROOT)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["version"], "0.7.0")
        self.assertGreaterEqual(result["requirements"], 60)
        self.assertEqual(result["tasks"], 22)

    def test_duplicate_task_id_is_rejected(self):
        ledger = json.loads((ROOT / "program/task-ledger.yaml").read_text())
        duplicate = copy.deepcopy(ledger["tasks"][0])
        ledger["tasks"].append(duplicate)

        with self.assertRaisesRegex(
            VALIDATOR.ProgramValidationError, "duplicate task_id"
        ):
            VALIDATOR.validate_task_ledger(ledger)

    def test_task_dependency_cycle_is_rejected(self):
        graph = json.loads((ROOT / "program/task-graph.yaml").read_text())
        graph["nodes"][0]["depends_on"] = ["INC-002"]
        task_ids = {node["id"] for node in graph["nodes"]}

        with self.assertRaisesRegex(
            VALIDATOR.ProgramValidationError, "dependency cycle"
        ):
            VALIDATOR.validate_task_graph(graph, task_ids)

    def test_invalid_traceability_classification_is_rejected(self):
        rows = VALIDATOR.load_traceability(
            ROOT / "program/requirements-traceability.csv"
        )
        rows[0]["classification"] = "almost_done"

        with self.assertRaisesRegex(
            VALIDATOR.ProgramValidationError, "classification: invalid"
        ):
            VALIDATOR.validate_traceability(rows)

    def test_version_drift_is_rejected(self):
        required = (
            "package.json",
            "package-lock.json",
            "backend/setup.cfg",
            "backend/agency_runtime/version.py",
            "backend/agency_runtime/api.py",
            "backend/agency_runtime/observability.py",
            "infra/helm/ai-native-content-agency/Chart.yaml",
            "Dockerfile",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            for relative_path in required:
                source = ROOT / relative_path
                target = temporary_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            package_path = temporary_root / "package.json"
            package = json.loads(package_path.read_text())
            package["version"] = "9.9.9"
            package_path.write_text(json.dumps(package), encoding="utf-8")

            with self.assertRaisesRegex(
                VALIDATOR.ProgramValidationError, "version drift"
            ):
                VALIDATOR.validate_versions(temporary_root)

    def test_blocker_without_resume_condition_is_rejected(self):
        graph = json.loads((ROOT / "program/task-graph.yaml").read_text())
        graph["blockers"][0]["exact_resume_condition"] = ""
        task_ids = {node["id"] for node in graph["nodes"]}

        with self.assertRaisesRegex(
            VALIDATOR.ProgramValidationError, "exact_resume_condition"
        ):
            VALIDATOR.validate_task_graph(graph, task_ids)


if __name__ == "__main__":
    unittest.main()
