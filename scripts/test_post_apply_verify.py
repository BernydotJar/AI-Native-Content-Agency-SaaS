from __future__ import annotations

import unittest

from scripts.post_apply_verify import EvidenceError, verify


IMAGE = "us-central1-docker.pkg.dev/agency-dev/agency-images/app@sha256:" + "a" * 64
RUNTIME = "agency-runtime-dev@agency-dev.iam.gserviceaccount.com"
PLAN = "github-plan-dev@agency-bootstrap.iam.gserviceaccount.com"
DEPLOY = "github-deploy-dev@agency-bootstrap.iam.gserviceaccount.com"
PROJECT_ID = "agency-dev"
LABELS = {
    "application": "ai-native-content-agency",
    "environment": "dev",
    "managed_by": "terraform",
}


def iam_policy(bindings):
    return {"bindings": bindings}


class PostApplyVerifyTest(unittest.TestCase):
    def evidence(self):
        resource = {
            "metadata": {"labels": LABELS},
            "spec": {"template": {"spec": {"serviceAccountName": RUNTIME, "containers": [{"image": IMAGE}]}}},
        }
        service_iam = iam_policy([
            {"role": "roles/run.invoker", "members": ["serviceAccount:" + DEPLOY]},
        ])
        project_bindings = [
            {"role": "roles/run.viewer", "members": ["serviceAccount:" + PLAN]},
        ] + [
            {"role": role, "members": ["serviceAccount:" + DEPLOY]}
            for role in (
                "roles/cloudsql.viewer",
                "roles/iam.securityReviewer",
                "roles/logging.viewer",
                "roles/monitoring.viewer",
                "projects/{}/roles/agencyRuntimeDeployer".format(PROJECT_ID),
            )
        ]
        return {
            "service": resource,
            "service_iam": service_iam,
            "job": resource,
            "sql": {"settings": {"connectorEnforcement": "REQUIRED", "ipConfiguration": {}}},
            "logs": [{"textPayload": '{"event":"http_request","status_code":200}'}],
            "project_iam": iam_policy(project_bindings),
            "artifact_iam": iam_policy([
                {
                    "role": "roles/artifactregistry.reader",
                    "members": ["serviceAccount:" + DEPLOY],
                },
            ]),
            "outputs": {
                "foundation_budget_enabled": {"value": True},
                "foundation_notification_channel_ids": {"value": ["projects/dev/notificationChannels/1"]},
            },
        }

    def run_verify(self, evidence):
        return verify(
            evidence["service"], evidence["service_iam"], evidence["job"],
            evidence["sql"], evidence["logs"], evidence["project_iam"],
            evidence["artifact_iam"], evidence["outputs"], IMAGE, RUNTIME, PLAN, DEPLOY,
            PROJECT_ID,
        )

    def test_complete_private_evidence_passes(self) -> None:
        self.assertEqual(self.run_verify(self.evidence())["status"], "PASS")

    def test_public_invoker_is_rejected(self) -> None:
        evidence = self.evidence()
        evidence["service_iam"]["bindings"].append(
            {"role": "roles/run.invoker", "members": ["allUsers"]}
        )
        with self.assertRaisesRegex(EvidenceError, "public IAM"):
            self.run_verify(evidence)

    def test_broad_deploy_role_is_rejected(self) -> None:
        evidence = self.evidence()
        evidence["project_iam"]["bindings"].append(
            {"role": "roles/resourcemanager.projectIamAdmin", "members": ["serviceAccount:" + DEPLOY]}
        )
        with self.assertRaisesRegex(EvidenceError, "forbidden administration role"):
            self.run_verify(evidence)

    def test_cloud_run_admin_is_rejected(self) -> None:
        evidence = self.evidence()
        evidence["project_iam"]["bindings"].append(
            {"role": "roles/run.admin", "members": ["serviceAccount:" + DEPLOY]}
        )
        with self.assertRaisesRegex(EvidenceError, "forbidden administration role"):
            self.run_verify(evidence)

    def test_missing_repository_reader_is_rejected(self) -> None:
        evidence = self.evidence()
        evidence["artifact_iam"] = iam_policy([])
        with self.assertRaisesRegex(EvidenceError, "repository roles differ"):
            self.run_verify(evidence)

    def test_missing_logs_or_notification_delivery_is_rejected(self) -> None:
        evidence = self.evidence()
        evidence["logs"] = []
        with self.assertRaisesRegex(EvidenceError, "no post-smoke"):
            self.run_verify(evidence)


if __name__ == "__main__":
    unittest.main()
