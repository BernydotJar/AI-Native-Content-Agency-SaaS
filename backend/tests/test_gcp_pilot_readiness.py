import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify-gcp-pilot-readiness.py"
SPEC = importlib.util.spec_from_file_location("verify_gcp_pilot_readiness", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load GCP pilot readiness verifier")
GCP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GCP)


class GCPPilotReadinessTests(unittest.TestCase):
    def test_repository_contract_passes_and_denies_apply(self):
        result = GCP.validate_repository(ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["decision"], "DENY_APPLY")
        self.assertEqual(result["authorized_monthly_cap_cop"], 4000)
        self.assertEqual(result["minimum_compute_monthly_cop"], 24609)
        self.assertEqual(result["external_effects"], 0)

    def test_cost_understatement_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            GCP.copy_contract(ROOT, root)
            path = root / "infra/gcp/pilot-cost-review.json"
            data = json.loads(path.read_text())
            data["minimum_compute_assumption"]["rounded_monthly_cop"] = 4000
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(GCP.GCPPilotReadinessError, "rounded"):
                GCP.validate_repository(root)

    def test_missing_cost_cap_guard_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            GCP.copy_contract(ROOT, root)
            path = root / "infra/gcp/variables.tf"
            text = path.read_text().replace(
                "var.reviewed_monthly_cost_estimate_units <= var.authorized_monthly_cost_cap_units",
                "var.reviewed_monthly_cost_estimate_units > 0",
            )
            path.write_text(text)
            with self.assertRaisesRegex(GCP.GCPPilotReadinessError, "cost gate"):
                GCP.validate_repository(root)

    def test_runtime_cloud_sql_admin_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            GCP.copy_contract(ROOT, root)
            path = root / "infra/gcp/iam.tf"
            text = path.read_text().replace(
                'resource "google_project_iam_member" "runtime_cloud_sql_client" {',
                'resource "google_project_iam_member" "runtime_cloud_sql_client" {\n  # roles/cloudsql.admin must never be granted here',
            )
            path.write_text(text)
            with self.assertRaisesRegex(GCP.GCPPilotReadinessError, "runtime Cloud SQL IAM"):
                GCP.validate_repository(root)

    def test_provider_credentials_become_required_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            GCP.copy_contract(ROOT, root)
            path = root / "infra/gcp/variables.tf"
            marker = '        "AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID",'
            path.write_text(path.read_text().replace(marker, marker + '\n        "AGENCY_X_CONSUMER_KEY",'))
            with self.assertRaisesRegex(GCP.GCPPilotReadinessError, "forbidden"):
                GCP.validate_repository(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
