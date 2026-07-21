import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "evaluate-supply-chain.py"
SPEC = importlib.util.spec_from_file_location("evaluate_supply_chain", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load supply-chain policy evaluator")
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def component(name="safe-package", version="1.0.0", license_name="MIT"):
    licenses = [] if license_name is None else [{"license": {"id": license_name}}]
    return {
        "name": name,
        "version": version,
        "licenses": licenses,
        "properties": [{"name": "syft:package:type", "value": "python"}],
    }


def finding(
    vulnerability="CVE-2099-0001",
    severity="High",
    package_type="python",
    package="safe-package",
    version="1.0.0",
    fixes=(),
):
    return {
        "artifact": {
            "type": package_type,
            "name": package,
            "version": version,
        },
        "vulnerability": {
            "id": vulnerability,
            "severity": severity,
            "fix": {"versions": list(fixes), "state": "fixed" if fixes else "not-fixed"},
        },
    }


def baseline_entry(
    vulnerability="CVE-2099-0001",
    severity="High",
    package_type="python",
    package="safe-package",
    version="1.0.0",
):
    return {
        "package_type": package_type,
        "package": package,
        "version": version,
        "vulnerability": vulnerability,
        "severity": severity,
        "reason": "Test-only accepted finding.",
    }


class SupplyChainPolicyTests(unittest.TestCase):
    def test_exact_baseline_and_allowed_license_pass(self):
        counts, vulnerability_errors = POLICY.evaluate_vulnerabilities(
            {"matches": [finding()]},
            {"expires_on": "2999-12-31", "accepted": [baseline_entry()]},
        )
        license_summary, license_errors = POLICY.evaluate_licenses(
            {"components": [component()]},
            {
                "package_types": ["python"],
                "allowed_licenses": ["MIT"],
                "denied_tokens": ["GPL"],
                "missing_license_exceptions": [],
            },
        )
        self.assertEqual(counts["counts"], {"High": 1})
        self.assertEqual(counts["accepted_high_findings"], 1)
        self.assertEqual(vulnerability_errors, [])
        self.assertEqual(license_errors, [])
        self.assertEqual(license_summary["packages_evaluated"], 1)

    def test_new_critical_and_stale_baseline_are_rejected(self):
        _, errors = POLICY.evaluate_vulnerabilities(
            {"matches": [finding(vulnerability="CVE-2099-9999", severity="Critical")]},
            {"expires_on": "2999-12-31", "accepted": [baseline_entry()]},
        )
        self.assertTrue(any("unaccepted Critical finding" in item for item in errors))
        self.assertTrue(any("stale baseline entry" in item for item in errors))

    def test_expired_baseline_is_rejected(self):
        _, errors = POLICY.evaluate_vulnerabilities(
            {"matches": [finding()]},
            {"expires_on": "2000-01-01", "accepted": [baseline_entry()]},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("vulnerability baseline expired", errors[0])


    def test_fixable_high_requires_explicit_compatibility_exception(self):
        report = {"matches": [finding(fixes=("1.0.1",))]}
        baseline = {"expires_on": "2999-12-31", "accepted": [baseline_entry()]}
        summary, errors = POLICY.evaluate_vulnerabilities(report, baseline)
        self.assertEqual(summary["fixable_counts"], {"High": 1})
        self.assertTrue(any("fixable High finding" in item for item in errors))

        accepted = baseline_entry()
        accepted["fix_exception"] = "The scanner fix is outside the supported runtime line."
        summary, errors = POLICY.evaluate_vulnerabilities(
            report, {"expires_on": "2999-12-31", "accepted": [accepted]}
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(summary["accepted_fix_exceptions"]), 1)

    def test_denied_missing_and_stale_license_exceptions_are_rejected(self):
        _, errors = POLICY.evaluate_licenses(
            {
                "components": [
                    component(name="copyleft", license_name="GPL-3.0-only"),
                    component(name="unlicensed", license_name=None),
                ]
            },
            {
                "package_types": ["python"],
                "allowed_licenses": ["MIT"],
                "denied_tokens": ["GPL"],
                "missing_license_exceptions": [
                    {"package": "unused-exception", "version": "1.0.0"}
                ],
            },
        )
        self.assertTrue(any("denied license" in item for item in errors))
        self.assertTrue(any("missing license metadata" in item for item in errors))
        self.assertTrue(any("stale missing-license exception" in item for item in errors))

    def test_exact_reviewed_license_mapping_passes(self):
        summary, errors = POLICY.evaluate_licenses(
            {
                "components": [
                    component(
                        name="dual-package",
                        version="2.0.0",
                        license_name="Dual License",
                    )
                ]
            },
            {
                "package_types": ["python"],
                "allowed_licenses": ["Apache-2.0", "BSD-3-Clause"],
                "denied_tokens": ["GPL"],
                "reviewed_license_mappings": [
                    {
                        "package": "dual-package",
                        "version": "2.0.0",
                        "reported_license": "Dual License",
                        "normalized_licenses": ["Apache-2.0", "BSD-3-Clause"],
                        "reason": "Exact package metadata was reviewed.",
                    }
                ],
                "missing_license_exceptions": [],
            },
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            summary["reviewed_license_mappings_used"],
            ["dual-package@2.0.0: Dual License"],
        )

    def test_stale_reviewed_license_mapping_is_rejected(self):
        _, errors = POLICY.evaluate_licenses(
            {"components": [component()]},
            {
                "package_types": ["python"],
                "allowed_licenses": ["MIT"],
                "denied_tokens": ["GPL"],
                "reviewed_license_mappings": [
                    {
                        "package": "unused-package",
                        "version": "1.0.0",
                        "reported_license": "Custom License",
                        "normalized_licenses": ["Unknown-License"],
                        "reason": "Test-only mapping.",
                    }
                ],
                "missing_license_exceptions": [],
            },
        )
        self.assertTrue(any("stale reviewed license mapping" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
