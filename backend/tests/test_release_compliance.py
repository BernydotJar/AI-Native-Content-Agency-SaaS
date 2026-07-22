import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify-release-compliance.py"
SPEC = importlib.util.spec_from_file_location("verify_release_compliance", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load release compliance verifier")
COMPLIANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPLIANCE)


class ReleaseComplianceTests(unittest.TestCase):
    def test_repository_contract_passes_and_denies_release(self):
        result = COMPLIANCE.validate_repository(ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["release_decision"], "DENY_RELEASE")
        self.assertEqual(result["active_external_providers"], 0)
        self.assertGreaterEqual(result["third_party_components"], 30)
        self.assertGreaterEqual(result["open_human_decisions"], 7)

    def mutate(self, relative, transform):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        COMPLIANCE.copy_contract(ROOT, root)
        path = root / relative
        data = json.loads(path.read_text())
        transform(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return temporary, root

    def test_stale_inventory_hash_fails_closed(self):
        temporary, root = self.mutate(
            "compliance/third-party-inventory.json",
            lambda data: data["evidence_files"][0].update({"sha256": "0" * 64}),
        )
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "evidence hash"
        ):
            COMPLIANCE.validate_repository(root)

    def test_unlocked_direct_dependency_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            COMPLIANCE.copy_contract(ROOT, root)
            path = root / "package.json"
            data = json.loads(path.read_text())
            data["dependencies"]["unreviewed-package"] = "1.0.0"
            path.write_text(json.dumps(data, indent=2) + "\n")
            with self.assertRaisesRegex(
                COMPLIANCE.ComplianceValidationError, "package.json"
            ):
                COMPLIANCE.validate_repository(root)

    def test_enabled_unknown_provider_fails_closed(self):
        def transform(data):
            provider = data["external_provider_decisions"][0]
            provider["enabled"] = True
            provider["contract_status"] = "UNKNOWN"

        temporary, root = self.mutate(
            "compliance/privacy-decision-register.json", transform
        )
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "provider"
        ):
            COMPLIANCE.validate_repository(root)

    def test_invented_retention_and_unsupported_approval_fail_closed(self):
        temporary, root = self.mutate(
            "compliance/privacy-decision-register.json",
            lambda data: data["policy_decisions"][0].update({"retention_days": 365}),
        )
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "retention"
        ):
            COMPLIANCE.validate_repository(root)

        def approval(data):
            data["jurisdiction"] = "US"
            data["release_recommendation"] = "ALLOW_RELEASE"

        temporary, root = self.mutate(
            "compliance/privacy-decision-register.json", approval
        )
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "UNKNOWN|approval|release"
        ):
            COMPLIANCE.validate_repository(root)

    def test_prohibited_claim_and_missing_disclosure_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            COMPLIANCE.copy_contract(ROOT, root)
            readme = root / "README.md"
            readme.write_text(readme.read_text() + "\nThis product is production-ready.\n")
            with self.assertRaisesRegex(
                COMPLIANCE.ComplianceValidationError, "prohibited public claim"
            ):
                COMPLIANCE.validate_repository(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            COMPLIANCE.copy_contract(ROOT, root)
            readme = root / "README.md"
            readme.write_text(
                readme.read_text().replace(
                    "No existe evidencia de deployment GCP/staging/producción", ""
                )
            )
            with self.assertRaisesRegex(
                COMPLIANCE.ComplianceValidationError, "required disclosure"
            ):
                COMPLIANCE.validate_repository(root)

    def test_release_cannot_be_allowed_with_open_blockers(self):
        def transform(data):
            data["allow_release"] = True
            data["decision"] = "ALLOW_RELEASE"

        temporary, root = self.mutate("compliance/release-decision.json", transform)
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "release"
        ):
            COMPLIANCE.validate_repository(root)

    def test_nested_schema_and_resolved_blockers_fail_closed(self):
        temporary, root = self.mutate(
            "compliance/privacy-decision-register.json",
            lambda data: data["external_provider_decisions"][0].update(
                {"unexpected_authority": True}
            ),
        )
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "field mismatch"
        ):
            COMPLIANCE.validate_repository(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            COMPLIANCE.copy_contract(ROOT, root)
            path = root / "program/critique-findings.json"
            data = json.loads(path.read_text())
            for finding in data["findings"]:
                if finding.get("id") == "F-010":
                    finding["status"] = "CLOSED"
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(
                COMPLIANCE.ComplianceValidationError, "unresolved HIGH"
            ):
                COMPLIANCE.validate_repository(root)

    def test_video_use_commit_and_status_must_match_review_manifest(self):
        temporary, root = self.mutate(
            "compliance/third-party-inventory.json",
            lambda data: data["external_candidates"][0].update({"commit": "0" * 40}),
        )
        with temporary, self.assertRaisesRegex(
            COMPLIANCE.ComplianceValidationError, "video-use"
        ):
            COMPLIANCE.validate_repository(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
