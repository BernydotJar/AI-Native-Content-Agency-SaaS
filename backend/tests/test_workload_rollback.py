from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify-workload-rollback.py"
CONTRACT = ROOT / "contracts" / "workload-rollback-v1.json"


class WorkloadRollbackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("workload_rollback", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load workload rollback verifier")
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_binds_compatible_ancestor_and_paths(self):
        binding = self.module.validate_contract(self.contract)
        self.assertNotEqual(binding["candidate_commit"], binding["rollback_commit"])
        self.assertEqual(binding["runtime_schema_version"], 9)
        self.assertEqual(len(binding["candidate_tree"]), 40)
        self.assertEqual(len(binding["rollback_tree"]), 40)
        self.assertEqual(binding["maximum_local_rto_seconds"], 30)

    def test_contract_rejects_same_commit_schema_drift_and_path_drift(self):
        current = self.module.git_text("rev-parse", "HEAD")
        same = copy.deepcopy(self.contract)
        same["rollback_commit"] = current
        with self.assertRaisesRegex(ValueError, "must differ"):
            self.module.validate_contract(same, current_commit=current)

        schema = copy.deepcopy(self.contract)
        schema["required_runtime_schema_version"] = 8
        with self.assertRaisesRegex(ValueError, "incompatible"):
            self.module.validate_contract(schema)

        paths = copy.deepcopy(self.contract)
        paths["stable_path_contract"].append("/api/v1/unsafe")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.module.validate_contract(paths)

    def test_report_rejects_credentials_rto_and_security_drift(self):
        report = {
            "schema_version": "agency-workload-rollback-report.v1",
            "status": "pass",
            "candidate": {"commit": "a" * 40},
            "rollback": {"commit": "b" * 40},
            "runtime_schema_version": 9,
            "stable_port": 18080,
            "rto_milliseconds": 100,
            "maximum_rto_milliseconds": 30000,
            "runs": {},
            "audit": {},
            "database": {},
            "security": {
                "candidate_non_root": True,
                "candidate_read_only": True,
                "rollback_non_root": True,
                "rollback_read_only": True,
                "providers_enabled": False,
                "database_restore_performed": False,
                "writers_overlapped": False,
            },
            "external_effects": 0,
        }
        self.module.validate_report(report)

        excessive = copy.deepcopy(report)
        excessive["rto_milliseconds"] = 30001
        with self.assertRaisesRegex(ValueError, "RTO exceeded"):
            self.module.validate_report(excessive)

        writable = copy.deepcopy(report)
        writable["security"]["rollback_read_only"] = False
        with self.assertRaisesRegex(ValueError, "security evidence"):
            self.module.validate_report(writable)

        secret = copy.deepcopy(report)
        secret["candidate"]["credential"] = self.module.IDENTITY_KEY
        with self.assertRaisesRegex(ValueError, "fields are invalid|credential material"):
            self.module.validate_report(secret)


if __name__ == "__main__":
    unittest.main()
