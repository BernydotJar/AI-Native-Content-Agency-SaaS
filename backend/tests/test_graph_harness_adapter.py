from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/verify_graph_harness.py"
SPEC = importlib.util.spec_from_file_location("verify_graph_harness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GraphHarnessAdapterTests(unittest.TestCase):
    def test_projection_matches_task_sources(self) -> None:
        generated = MODULE.build_project()
        checked_in = json.loads(MODULE.PROJECT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(generated, checked_in)
        self.assertEqual(len(generated["nodes"]), 25)

    def test_adoption_remains_review_with_close_gate_open(self) -> None:
        runtime = MODULE.GraphRuntime.from_paths(MODULE.PROJECT_PATH, MODULE.EVENTS_PATH)
        node = runtime.state().nodes[MODULE.ADOPTION_NODE]
        self.assertEqual(node.status.value, "review")
        self.assertNotIn("close-gate", node.gates)
        self.assertEqual(node.gates["production-gate"].result.value, "PASS")

    def test_framework_gitlink_matches_lock(self) -> None:
        lock = MODULE.verify_lock()
        self.assertEqual(MODULE.framework_head(), lock["commit"])


if __name__ == "__main__":
    unittest.main()
