from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/verify_graph_harness.py"
FRAMEWORK = ROOT / "vendor/graph-harness-sdlc"
if str(FRAMEWORK) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK))
SPEC = importlib.util.spec_from_file_location("verify_graph_harness", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GraphHarnessAdapterTests(unittest.TestCase):
    def test_projection_matches_task_sources(self) -> None:
        generated = MODULE.build_project()
        checked_in = json.loads(MODULE.PROJECT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(generated, checked_in)
        self.assertEqual(len(generated["nodes"]), 29)

    def test_adoption_is_done_with_close_gate_passed(self) -> None:
        runtime = MODULE.GraphRuntime.from_paths(MODULE.PROJECT_PATH, MODULE.EVENTS_PATH)
        node = runtime.state().nodes[MODULE.ADOPTION_NODE]
        self.assertEqual(node.status.value, "done")
        self.assertEqual(node.gates["close-gate"].result.value, "PASS")
        self.assertEqual(node.gates["production-gate"].result.value, "PASS")

    def test_framework_gitlink_matches_lock(self) -> None:
        lock = MODULE.verify_lock()
        self.assertEqual(MODULE.framework_head(), lock["commit"])


if __name__ == "__main__":
    unittest.main()
