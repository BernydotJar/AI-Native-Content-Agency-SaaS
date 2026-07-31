from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/verify-repository-governance.py"
SPEC = importlib.util.spec_from_file_location("verify_repository_governance", MODULE)
assert SPEC and SPEC.loader
GOVERNANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GOVERNANCE)


class RepositoryGovernanceTests(unittest.TestCase):
    def copy_contract(self, directory: str) -> Path:
        root = Path(directory)
        for relative in (
            ".github/workflows/production-readiness.yml",
            "program/repository-governance.json",
            "program/superseded-work.json",
            "program/graph-harness.state.json",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def test_repository_contract_passes(self):
        result = GOVERNANCE.validate(ROOT)
        self.assertEqual(result["repository_mode"], "single_owner")
        self.assertEqual(result["required_checks"], 8)
        self.assertEqual(result["superseded_pull_requests"], 10)

    def test_impossible_approval_and_workflow_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            path = root / "program/repository-governance.json"
            data = json.loads(path.read_text())
            data["required_approving_review_count"] = 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                GOVERNANCE.GovernanceValidationError, "second-person"
            ):
                GOVERNANCE.validate(root)
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            path = root / ".github/workflows/production-readiness.yml"
            path.write_text(
                path.read_text().replace("  terraform:\n", "  old-terraform:\n", 1)
            )
            with self.assertRaisesRegex(
                GOVERNANCE.GovernanceValidationError, "workflow jobs"
            ):
                GOVERNANCE.validate(root)

    def test_superseded_work_cannot_be_marked_merged_or_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            path = root / "program/superseded-work.json"
            data = json.loads(path.read_text())
            data["pull_requests"][0]["merged"] = True
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                GOVERNANCE.GovernanceValidationError, "marked merged"
            ):
                GOVERNANCE.validate(root)
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            path = root / "program/superseded-work.json"
            data = json.loads(path.read_text())
            data["pull_requests"].pop()
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                GOVERNANCE.GovernanceValidationError, "incomplete"
            ):
                GOVERNANCE.validate(root)

    def test_remote_closure_gate_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_contract(directory)
            path = root / "program/superseded-work.json"
            data = json.loads(path.read_text())
            data["issue"]["remote_state"] = "open"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(
                GOVERNANCE.GovernanceValidationError, "not remotely closed"
            ):
                GOVERNANCE.validate(root, require_closed=True)
            data["issue"]["remote_state"] = "closed"
            for item in data["pull_requests"]:
                item["remote_state"] = "closed"
            path.write_text(json.dumps(data))
            result = GOVERNANCE.validate(root, require_closed=True)
            self.assertTrue(result["remote_closure_required"])

    def test_live_protection_must_match_policy_exactly(self):
        policy = json.loads((ROOT / "program/repository-governance.json").read_text())
        protection = {
            "enforce_admins": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False,
                "require_last_push_approval": False,
                "required_approving_review_count": 0,
            },
            "required_status_checks": {
                "strict": True,
                "checks": [
                    {"context": value, "app_id": 15368}
                    for value in policy["required_status_checks"]
                ],
            },
        }
        GOVERNANCE.validate_live_protection(policy, protection)
        protection["required_pull_request_reviews"][
            "required_approving_review_count"
        ] = 1
        with self.assertRaisesRegex(
            GOVERNANCE.GovernanceValidationError, "review protection"
        ):
            GOVERNANCE.validate_live_protection(policy, protection)


if __name__ == "__main__":
    unittest.main()
