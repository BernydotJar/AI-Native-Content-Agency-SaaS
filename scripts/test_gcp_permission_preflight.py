from __future__ import annotations

import unittest

from scripts.gcp_permission_preflight import (
    PermissionError,
    evaluate,
    permission_targets,
    probe_state_access,
)


class GcpPermissionPreflightTest(unittest.TestCase):
    def test_each_phase_has_distinct_bounded_targets(self) -> None:
        build = permission_targets("build", "agency-dev-test", "us-central1", None, None)
        plan = permission_targets(
            "plan", "agency-dev-test", "us-central1", "agency-state-test", None
        )
        apply = permission_targets(
            "apply",
            "agency-dev-test",
            "us-central1",
            "agency-state-test",
            "agency-runtime-dev@agency-dev-test.iam.gserviceaccount.com",
        )

        self.assertEqual([target.name for target in build], ["artifact_registry"])
        self.assertEqual(
            [target.name for target in plan],
            ["project_runtime", "terraform_state"],
        )
        self.assertEqual(
            [target.name for target in apply],
            [
                "project_runtime",
                "terraform_state",
                "artifact_registry_read",
                "runtime_service_account",
            ],
        )
        serialized = repr((build, plan, apply))
        self.assertNotIn("projectIamAdmin", serialized)
        self.assertNotIn("serviceAccountAdmin", serialized)
        self.assertNotIn("run.admin", serialized)
        self.assertIn("run.operations.get", serialized)
        self.assertIn("artifactregistry.repositories.downloadArtifacts", serialized)

    def test_evaluate_fails_closed_on_one_missing_permission(self) -> None:
        targets = permission_targets(
            "plan", "agency-dev-test", "us-central1", "agency-state-test", None
        )

        def missing_last(target):
            return {"permissions": list(target.permissions[:-1])}

        with self.assertRaisesRegex(PermissionError, "missing required permissions"):
            evaluate(targets, missing_last)

    def test_evaluate_reports_counts_without_tokens_or_policy_payloads(self) -> None:
        targets = permission_targets("build", "agency-dev-test", "us-central1", None, None)
        report = evaluate(
            targets,
            lambda target: {"permissions": list(target.permissions)},
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["targets"][0]["required_permission_count"], 3)
        self.assertNotIn("token", repr(report).lower())

    def test_state_probe_reads_foundation_and_only_mutates_disposable_lock(self) -> None:
        methods = []

        def transport(request):
            methods.append(request.get_method())
            if request.get_method() == "GET":
                return b'{"name":"environments/dev/default.tfstate"}'
            if request.get_method() == "POST":
                return b'{"name":"environments/dev-runtime/permission-preflight-test.tflock","generation":"7"}'
            return b""

        report = probe_state_access(
            "agency-state-test",
            "short-lived-test-token",
            nonce="test",
            transport=transport,
        )

        self.assertEqual(methods, ["GET", "POST", "DELETE"])
        self.assertTrue(report["foundation_state_metadata_read"])
        self.assertTrue(report["runtime_lock_create_delete"])
        self.assertNotIn("token", repr(report).lower())


if __name__ == "__main__":
    unittest.main()
