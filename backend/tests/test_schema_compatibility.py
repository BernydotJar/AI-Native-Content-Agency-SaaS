from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify-schema-compatibility.py"
MANIFEST = ROOT / "contracts" / "runtime-schema-history.json"


class SchemaCompatibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("schema_compatibility", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load schema compatibility verifier")
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_contiguous_and_bound_to_historical_sources(self):
        versions = self.module.validate_manifest(self.manifest)
        self.assertEqual([item.version for item in versions], list(range(1, 10)))
        self.assertTrue(all(len(item.resolved_commit) == 40 for item in versions))

    def test_manifest_rejects_gap_duplicate_future_and_wrong_source(self):
        gap = copy.deepcopy(self.manifest)
        gap["versions"].pop(3)
        with self.assertRaisesRegex(ValueError, "contiguous"):
            self.module.validate_manifest(gap, resolve_commits=False)

        duplicate = copy.deepcopy(self.manifest)
        duplicate["versions"][1]["commit"] = duplicate["versions"][0]["commit"]
        with self.assertRaisesRegex(ValueError, "duplicate historical commit"):
            self.module.validate_manifest(duplicate, resolve_commits=False)

        future = copy.deepcopy(self.manifest)
        future["current_version"] = 10
        with self.assertRaisesRegex(ValueError, "contiguous"):
            self.module.validate_manifest(future, resolve_commits=False)

        wrong = copy.deepcopy(self.manifest)
        wrong["versions"][0]["commit"] = wrong["versions"][1]["commit"]
        wrong["versions"][1]["commit"] = "abcdef1"
        with self.assertRaises(ValueError):
            self.module.validate_manifest(wrong)

    def test_sqlite_historical_matrix_preserves_data_and_chain(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for version in range(1, 10):
            self.assertIn(f"sqlite_schema_upgrade_v{version}=pass", completed.stdout)
        self.assertIn("schema_compatibility=pass", completed.stdout)
        self.assertIn("historical_versions=9", completed.stdout)
        self.assertIn("external_effects=0", completed.stdout)


if __name__ == "__main__":
    unittest.main()
