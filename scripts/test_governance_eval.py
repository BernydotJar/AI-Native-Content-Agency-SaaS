from __future__ import annotations

import unittest

from scripts.governance_eval import (
    MANDATORY_PHASE_TASKS,
    _active_write_lock_check,
    _critical_path_check,
    _graph_check,
    _mandatory_phase_chain_check,
    _task_contract_check,
    _unique_nonempty,
)


def _task(task_id: str, **overrides: object) -> dict[str, object]:
    task: dict[str, object] = {
        "task_id": task_id,
        "role": "Test role",
        "objective": "Exercise governance validation.",
        "inputs": ["fixture"],
        "dependencies": [],
        "allowed_paths": ["repository read-only"],
        "read_only_paths": ["**"],
        "write_lock": [],
        "expected_outputs": ["verdict"],
        "acceptance_criteria": ["validation is fail closed"],
        "validation": ["unit test"],
        "prohibited_actions": ["fabricate evidence"],
        "status": "PASS",
        "owner": "test_owner",
    }
    task.update(overrides)
    return task


class GovernanceEvalTests(unittest.TestCase):
    def test_task_contract_requires_the_full_subagent_schema(self) -> None:
        passed, evidence = _task_contract_check(
            {"tasks": [{"task_id": "TASK-001", "role": "Producer"}]}
        )

        self.assertFalse(passed)
        self.assertIn("acceptance_criteria", evidence)
        self.assertIn("write_lock", evidence)

    def test_task_contract_rejects_blank_typed_fields_and_unknown_dependencies(
        self,
    ) -> None:
        ledger = {
            "tasks": [
                _task("TASK-001", owner="", dependencies=["TASK-MISSING"]),
            ]
        }

        passed, evidence = _task_contract_check(ledger)

        self.assertFalse(passed)
        self.assertIn("owner must be a non-empty string", evidence)
        self.assertIn("dependencies unknown: TASK-MISSING", evidence)

    def test_graph_rejects_unknown_tasks(self) -> None:
        graph = {
            "critical_path": ["TASK-001", "TASK-002"],
            "edges": [{"from": "TASK-001", "to": "TASK-002"}],
        }
        ledger = {"tasks": [_task("TASK-001")]}

        passed, evidence = _graph_check(graph, ledger)

        self.assertFalse(passed)
        self.assertIn("TASK-002", evidence)

    def test_graph_rejects_dependency_or_edge_cycles(self) -> None:
        ledger = {
            "tasks": [
                _task("TASK-001", dependencies=["TASK-002"]),
                _task("TASK-002"),
            ]
        }
        graph = {
            "critical_path": ["TASK-001", "TASK-002"],
            "edges": [{"from": "TASK-001", "to": "TASK-002"}],
        }

        passed, evidence = _graph_check(graph, ledger)

        self.assertFalse(passed)
        self.assertIn("cycle", evidence)

    def test_critical_path_requires_every_ordered_edge(self) -> None:
        graph = {
            "critical_path": ["TASK-001", "TASK-002", "TASK-003"],
            "edges": [{"from": "TASK-001", "to": "TASK-002"}],
        }

        passed, evidence = _critical_path_check(graph)

        self.assertFalse(passed)
        self.assertIn("TASK-002->TASK-003", evidence)

    def test_mandatory_phase_chain_rejects_disorder(self) -> None:
        reversed_path = list(reversed(MANDATORY_PHASE_TASKS))
        graph = {
            "critical_path": reversed_path,
            "edges": [
                {"from": source, "to": target}
                for source, target in zip(reversed_path, reversed_path[1:])
            ],
        }

        passed, evidence = _mandatory_phase_chain_check(graph)

        self.assertFalse(passed)
        self.assertIn("out of order", evidence)

    def test_active_write_lock_conflicts_fail_closed(self) -> None:
        ledger = {
            "tasks": [
                _task(
                    "TASK-001",
                    status="IN_PROGRESS",
                    write_lock=["agent/**"],
                ),
                _task(
                    "TASK-002",
                    status="IN_PROGRESS",
                    write_lock=["agent/eval-catalog.json"],
                ),
            ]
        }

        passed, evidence = _active_write_lock_check(ledger)

        self.assertFalse(passed)
        self.assertIn("TASK-001", evidence)
        self.assertIn("TASK-002", evidence)

    def test_unique_identifiers_fail_closed_on_blanks_and_duplicates(self) -> None:
        self.assertFalse(_unique_nonempty(["EVD-001", "EVD-001"], "evidence")[0])
        self.assertFalse(_unique_nonempty([""], "evidence")[0])
        self.assertTrue(_unique_nonempty(["EVD-001", "EVD-002"], "evidence")[0])


if __name__ == "__main__":
    unittest.main()
