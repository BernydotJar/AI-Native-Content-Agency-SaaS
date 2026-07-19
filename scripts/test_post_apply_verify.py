from __future__ import annotations

import unittest

from scripts.post_apply_verify import (
    EvidenceError,
    EXPECTED_CLOUD_SQL_PROXY_IMAGE,
    ROLLBACK_TAG_OPERATOR_PERMISSIONS,
    RUNTIME_DEPLOYER_PERMISSIONS,
    WIF_ATTRIBUTE_MAPPING,
    verify,
)


IMAGE = "us-central1-docker.pkg.dev/agency-dev/agency-images/app@sha256:" + "a" * 64
ARTIFACT_REPOSITORY = "us-central1-docker.pkg.dev/agency-dev/agency-images"
RUNTIME = "agency-runtime-dev@agency-dev.iam.gserviceaccount.com"
BUILD = "github-image-dev@agency-bootstrap.iam.gserviceaccount.com"
PLAN = "github-plan-dev@agency-bootstrap.iam.gserviceaccount.com"
DEPLOY = "github-deploy-dev@agency-bootstrap.iam.gserviceaccount.com"
PROJECT_ID = "agency-dev"
BOOTSTRAP_PROJECT_ID = "agency-bootstrap"
STATE_BUCKET = "agency-bootstrap-tfstate"
GITHUB_REPOSITORY = "example-owner/example-repository"
OWNER_ID = "12345678"
REPOSITORY_ID = "87654321"
POOL = "projects/123456789012/locations/global/workloadIdentityPools/github-actions"
LABELS = {
    "application": "ai-native-content-agency",
    "environment": "dev",
    "managed_by": "terraform",
}


def iam_policy(bindings):
    return {"bindings": bindings}


def wif_condition(environment):
    return " && ".join(
        (
            "assertion.repository_owner == 'example-owner'",
            "assertion.repository_owner_id == '12345678'",
            "assertion.repository == 'example-owner/example-repository'",
            "assertion.repository_id == '87654321'",
            "assertion.ref == 'refs/heads/main'",
            "assertion.ref_type == 'branch'",
            "assertion.environment == '{}'".format(environment),
            "assertion.workflow_ref == "
            "'example-owner/example-repository/.github/workflows/"
            "deploy-dev.yml@refs/heads/main'",
        )
    )


def wif_provider(provider_id, environment):
    return {
        "name": "{}/providers/{}".format(POOL, provider_id),
        "attributeMapping": WIF_ATTRIBUTE_MAPPING,
        "attributeCondition": wif_condition(environment),
        "oidc": {"issuerUri": "https://token.actions.githubusercontent.com"},
        "state": "ACTIVE",
    }


def impersonation_policy(environment):
    return iam_policy(
        [
            {
                "role": "roles/iam.workloadIdentityUser",
                "members": [
                    "principalSet://iam.googleapis.com/{}/attribute.environment/{}".format(
                        POOL, environment
                    )
                ],
            }
        ]
    )


def state_bucket_policy():
    prefix = "projects/_/buckets/{}/objects".format(STATE_BUCKET)
    lister = "projects/{}/roles/terraformStateLister".format(BOOTSTRAP_PROJECT_ID)
    return iam_policy(
        [
            {
                "role": lister,
                "members": ["serviceAccount:" + PLAN, "serviceAccount:" + DEPLOY],
            },
            {
                "role": "projects/{}/roles/terraformStateReader".format(BOOTSTRAP_PROJECT_ID),
                "members": ["serviceAccount:" + PLAN],
                "condition": {
                    "title": "plan-state-read",
                    "expression": (
                        "resource.type == 'storage.googleapis.com/Object' && "
                        "(resource.name.startsWith('{}/environments/dev/') || "
                        "resource.name.startsWith('{}/environments/dev-runtime/'))"
                    ).format(prefix, prefix),
                },
            },
            {
                "role": "projects/{}/roles/terraformStateReader".format(BOOTSTRAP_PROJECT_ID),
                "members": ["serviceAccount:" + DEPLOY],
                "condition": {
                    "title": "apply-state-read",
                    "expression": (
                        "resource.type == 'storage.googleapis.com/Object' && "
                        "(resource.name.startsWith('{}/environments/dev/'))"
                    ).format(prefix),
                },
            },
            {
                "role": "projects/{}/roles/terraformStateLocker".format(BOOTSTRAP_PROJECT_ID),
                "members": ["serviceAccount:" + PLAN],
                "condition": {
                    "title": "plan-runtime-lock-only",
                    "expression": (
                        "resource.type == 'storage.googleapis.com/Object' && "
                        "resource.name.startsWith("
                        "'{}/environments/dev-runtime/') && "
                        "resource.name.endsWith('.tflock')"
                    ).format(prefix),
                },
            },
            {
                "role": "roles/storage.objectAdmin",
                "members": ["serviceAccount:" + DEPLOY],
                "condition": {
                    "title": "apply-runtime-state-only",
                    "expression": (
                        "resource.type == 'storage.googleapis.com/Object' && "
                        "resource.name.startsWith("
                        "'{}/environments/dev-runtime/')"
                    ).format(prefix),
                },
            },
        ]
    )


class PostApplyVerifyTest(unittest.TestCase):
    def evidence(self):
        service = {
            "metadata": {"labels": LABELS},
            "spec": {
                "template": {
                    "spec": {
                        "serviceAccountName": RUNTIME,
                        "containers": [
                            {"name": "application", "image": IMAGE},
                            {
                                "name": "cloud-sql-proxy",
                                "image": EXPECTED_CLOUD_SQL_PROXY_IMAGE,
                            },
                        ],
                    }
                }
            },
        }
        job = {
            "metadata": {"labels": LABELS},
            "spec": {
                "template": {
                    "spec": {
                        "serviceAccountName": RUNTIME,
                        "containers": [{"name": "migration", "image": IMAGE}],
                    }
                }
            },
        }
        project_bindings = [
            {"role": "roles/run.viewer", "members": ["serviceAccount:" + BUILD]},
            {"role": "roles/run.viewer", "members": ["serviceAccount:" + PLAN]},
        ]
        project_bindings.extend(
            {"role": role, "members": ["serviceAccount:" + DEPLOY]}
            for role in (
                "roles/cloudsql.viewer",
                "roles/iam.securityReviewer",
                "roles/logging.viewer",
                "roles/monitoring.viewer",
                "roles/run.servicesInvoker",
                "projects/{}/roles/agencyRuntimeDeployer".format(PROJECT_ID),
            )
        )
        project_bindings.extend(
            {"role": role, "members": ["serviceAccount:" + RUNTIME]}
            for role in (
                "roles/cloudsql.client",
                "roles/cloudsql.instanceUser",
                "roles/logging.logWriter",
                "roles/monitoring.metricWriter",
            )
        )
        return {
            "service": service,
            "service_iam": iam_policy([]),
            "job": job,
            "sql": {"settings": {"connectorEnforcement": "REQUIRED", "ipConfiguration": {}}},
            "logs": [{"textPayload": '{"event":"http_request","status_code":200}'}],
            "project_iam": iam_policy(project_bindings),
            "artifact_iam": iam_policy(
                [
                    {
                        "role": "roles/artifactregistry.writer",
                        "members": ["serviceAccount:" + BUILD],
                    },
                    {
                        "role": "roles/artifactregistry.reader",
                        "members": [
                            "serviceAccount:" + PLAN,
                            "serviceAccount:" + DEPLOY,
                        ],
                    },
                    {
                        "role": "projects/{}/roles/agencyRollbackTagOperator".format(PROJECT_ID),
                        "members": ["serviceAccount:" + DEPLOY],
                    },
                ]
            ),
            "outputs": {
                "foundation_budget_enabled": {"value": True},
                "foundation_notification_channel_ids": {
                    "value": ["projects/dev/notificationChannels/1"]
                },
            },
            "foundation": {
                "wif_providers": {
                    "build": wif_provider("github-build", "dev-build"),
                    "plan": wif_provider("github-plan", "dev-plan"),
                    "apply": wif_provider("github-apply", "dev"),
                },
                "phase_service_account_iam": {
                    "build": impersonation_policy("dev-build"),
                    "plan": impersonation_policy("dev-plan"),
                    "apply": impersonation_policy("dev"),
                },
                "state_bucket_iam": state_bucket_policy(),
                "runtime_custom_role": {
                    "name": "projects/{}/roles/agencyRuntimeDeployer".format(PROJECT_ID),
                    "includedPermissions": sorted(RUNTIME_DEPLOYER_PERMISSIONS),
                    "stage": "GA",
                },
                "rollback_custom_role": {
                    "name": "projects/{}/roles/agencyRollbackTagOperator".format(PROJECT_ID),
                    "includedPermissions": sorted(ROLLBACK_TAG_OPERATOR_PERMISSIONS),
                    "stage": "GA",
                },
                "rollback": {
                    "schema_version": "artifact-rollback-evidence.v1",
                    "status": "PASS",
                    "artifact_repository": ARTIFACT_REPOSITORY,
                    "desired_image": IMAGE,
                    "rollback_image": ARTIFACT_REPOSITORY + "/app@sha256:" + "b" * 64,
                    "rollback_depth": 1,
                    "retention_tag": "rollback-current",
                    "retention_verified": True,
                    "first_deployment": False,
                },
            },
        }

    def expectations(self):
        return {
            "bootstrap_project_id": BOOTSTRAP_PROJECT_ID,
            "state_bucket_name": STATE_BUCKET,
            "artifact_repository": ARTIFACT_REPOSITORY,
            "image_pusher_service_account": BUILD,
            "github_repository": GITHUB_REPOSITORY,
            "github_repository_owner_id": OWNER_ID,
            "github_repository_id": REPOSITORY_ID,
        }

    def run_verify(self, evidence):
        return verify(
            evidence["service"],
            evidence["service_iam"],
            evidence["job"],
            evidence["sql"],
            evidence["logs"],
            evidence["project_iam"],
            evidence["artifact_iam"],
            evidence["outputs"],
            IMAGE,
            RUNTIME,
            PLAN,
            DEPLOY,
            PROJECT_ID,
            evidence["foundation"],
            self.expectations(),
        )

    def test_complete_private_and_foundation_drift_evidence_passes(self):
        self.assertEqual(self.run_verify(self.evidence())["status"], "PASS")

    def test_public_invoker_is_rejected(self):
        evidence = self.evidence()
        evidence["service_iam"]["bindings"].append(
            {"role": "roles/run.servicesInvoker", "members": ["allUsers"]}
        )
        with self.assertRaisesRegex(EvidenceError, "public IAM"):
            self.run_verify(evidence)

    def test_wrong_named_proxy_image_is_rejected(self):
        evidence = self.evidence()
        evidence["service"]["spec"]["template"]["spec"]["containers"][1]["image"] = (
            "evil.invalid/proxy@sha256:" + "f" * 64
        )
        with self.assertRaisesRegex(EvidenceError, "image provenance"):
            self.run_verify(evidence)

    def test_application_digest_in_wrong_container_is_rejected(self):
        evidence = self.evidence()
        containers = evidence["service"]["spec"]["template"]["spec"]["containers"]
        containers[0]["name"] = "unexpected"
        with self.assertRaisesRegex(EvidenceError, "image provenance"):
            self.run_verify(evidence)

    def test_service_level_deploy_binding_is_rejected(self):
        evidence = self.evidence()
        evidence["service_iam"]["bindings"].append(
            {
                "role": "roles/run.servicesInvoker",
                "members": ["serviceAccount:" + DEPLOY],
            }
        )
        with self.assertRaisesRegex(EvidenceError, "unexpected service IAM"):
            self.run_verify(evidence)

    def test_broad_deploy_role_is_rejected(self):
        evidence = self.evidence()
        evidence["project_iam"]["bindings"].append(
            {
                "role": "roles/resourcemanager.projectIamAdmin",
                "members": ["serviceAccount:" + DEPLOY],
            }
        )
        with self.assertRaisesRegex(EvidenceError, "forbidden administration role"):
            self.run_verify(evidence)

    def test_runtime_identity_missing_role_is_rejected(self):
        evidence = self.evidence()
        evidence["project_iam"]["bindings"] = [
            binding
            for binding in evidence["project_iam"]["bindings"]
            if not (
                binding["role"] == "roles/cloudsql.client"
                and "serviceAccount:" + RUNTIME in binding["members"]
            )
        ]
        with self.assertRaisesRegex(EvidenceError, "runtime identity project roles"):
            self.run_verify(evidence)

    def test_runtime_identity_extra_role_is_rejected(self):
        evidence = self.evidence()
        evidence["project_iam"]["bindings"].append(
            {
                "role": "roles/storage.objectViewer",
                "members": ["serviceAccount:" + RUNTIME],
            }
        )
        with self.assertRaisesRegex(EvidenceError, "runtime identity project roles"):
            self.run_verify(evidence)

    def test_missing_repository_reader_is_rejected(self):
        evidence = self.evidence()
        evidence["artifact_iam"]["bindings"] = [
            binding
            for binding in evidence["artifact_iam"]["bindings"]
            if "serviceAccount:" + DEPLOY not in binding["members"]
        ]
        with self.assertRaisesRegex(EvidenceError, "repository roles differ"):
            self.run_verify(evidence)

    def test_unreviewed_repository_principal_is_rejected(self):
        evidence = self.evidence()
        evidence["artifact_iam"]["bindings"].append(
            {
                "role": "roles/artifactregistry.reader",
                "members": ["serviceAccount:attacker@example.iam.gserviceaccount.com"],
            }
        )
        with self.assertRaisesRegex(EvidenceError, "repository IAM policy"):
            self.run_verify(evidence)

    def test_wif_condition_drift_is_rejected(self):
        evidence = self.evidence()
        evidence["foundation"]["wif_providers"]["apply"]["attributeCondition"] = (
            "assertion.repository == 'attacker/repository'"
        )
        with self.assertRaisesRegex(EvidenceError, "WIF attribute condition"):
            self.run_verify(evidence)

    def test_extra_impersonation_principal_is_rejected(self):
        evidence = self.evidence()
        evidence["foundation"]["phase_service_account_iam"]["apply"]["bindings"][0][
            "members"
        ].append("principal://iam.googleapis.com/attacker")
        with self.assertRaisesRegex(EvidenceError, "extra impersonation"):
            self.run_verify(evidence)

    def test_state_prefix_drift_is_rejected(self):
        evidence = self.evidence()
        state_bindings = evidence["foundation"]["state_bucket_iam"]["bindings"]
        state_bindings[-1]["condition"]["expression"] = "resource.name.startsWith('/')"
        with self.assertRaisesRegex(EvidenceError, "state-bucket boundary"):
            self.run_verify(evidence)

    def test_custom_role_permission_drift_is_rejected(self):
        evidence = self.evidence()
        evidence["foundation"]["runtime_custom_role"]["includedPermissions"].append(
            "run.services.delete"
        )
        with self.assertRaisesRegex(EvidenceError, "custom-role permissions"):
            self.run_verify(evidence)

    def test_rollback_role_permission_drift_is_rejected(self):
        evidence = self.evidence()
        evidence["foundation"]["rollback_custom_role"]["includedPermissions"].append(
            "artifactregistry.versions.delete"
        )
        with self.assertRaisesRegex(EvidenceError, "rollback tag operator custom-role permissions"):
            self.run_verify(evidence)

    def test_unprotected_rollback_digest_is_rejected(self):
        evidence = self.evidence()
        evidence["foundation"]["rollback"]["retention_verified"] = False
        with self.assertRaisesRegex(EvidenceError, "not protected"):
            self.run_verify(evidence)

    def test_missing_logs_or_notification_delivery_is_rejected(self):
        evidence = self.evidence()
        evidence["logs"] = []
        with self.assertRaisesRegex(EvidenceError, "no post-smoke"):
            self.run_verify(evidence)


if __name__ == "__main__":
    unittest.main()
