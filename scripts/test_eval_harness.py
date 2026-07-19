from __future__ import annotations

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.eval_harness import (
    CatalogError,
    DEFAULT_CATALOG,
    build_evaluations,
    build_report,
    load_catalog,
    run_gate,
    traceability_statuses,
    validate_catalog_coverage,
    validate_report,
)


class EvalHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.traceability = self.root / "traceability.csv"
        with self.traceability.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["requirement_id", "status"])
            writer.writeheader()
            writer.writerow({"requirement_id": "REQ-001", "status": "PASS"})
            writer.writerow(
                {
                    "requirement_id": "REQ-002",
                    "status": "BLOCKED_BY_EXTERNAL_DEPENDENCY",
                }
            )
        self.catalog_path = self.root / "catalog.json"
        self.catalog = {
            "schema_version": 1,
            "catalog_id": "test-catalog",
            "gates": [
                {
                    "gate_id": "PASS-GATE",
                    "type": "command",
                    "command": [sys.executable, "-c", "print('safe evidence')"],
                    "timeout_seconds": 30,
                },
                {
                    "gate_id": "BLOCKED-GATE",
                    "type": "external_blocker",
                    "actual": "No authorized target exists.",
                    "required_fix": "Authorize a target.",
                    "reproducibility": "Repeat read-only target discovery.",
                },
            ],
            "requirements": [
                {
                    "requirement_id": "REQ-001",
                    "target": "executable behavior",
                    "severity": "HIGH",
                    "expected": "The command exits zero.",
                    "required_fix": "Repair the command.",
                    "gate_ids": ["PASS-GATE"],
                },
                {
                    "requirement_id": "REQ-002",
                    "target": "external target",
                    "severity": "HIGH",
                    "expected": "An authorized target exists.",
                    "required_fix": "Authorize a target.",
                    "gate_ids": ["BLOCKED-GATE"],
                },
            ],
        }
        self.catalog_path.write_text(json.dumps(self.catalog), encoding="utf-8")
        (self.root / "source.txt").write_text("evaluated source\n", encoding="utf-8")
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "eval@example.invalid"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Eval Test"], cwd=self.root, check=True
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "fixture"],
            cwd=self.root,
            check=True,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_executes_commands_and_preserves_explicit_external_blockers(self) -> None:
        catalog = load_catalog(self.catalog_path)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        evaluations = build_evaluations(
            catalog, results, traceability_statuses(self.traceability)
        )
        report = build_report(catalog, evaluations, root=self.root)

        self.assertEqual([item["status"] for item in evaluations], ["PASS", "BLOCKED"])
        self.assertEqual(
            [item["evaluator"] for item in evaluations], ["deterministic", "llm-judge"]
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["apply_recommendation"], "DENY_APPLY")
        self.assertEqual(report["summary"]["requirements_passed"], 1)
        self.assertEqual(report["summary"]["requirements_blocked"], 1)
        self.assertRegex(report["source_tree_sha256"], r"^[0-9a-f]{64}$")
        validate_report(
            report,
            catalog,
            traceability_statuses(self.traceability),
            root=self.root,
        )

    def test_failed_command_cannot_be_reported_as_pass(self) -> None:
        gate = {
            "gate_id": "FAIL-GATE",
            "type": "command",
            "command": [sys.executable, "-c", "raise SystemExit(7)"],
            "timeout_seconds": 30,
        }
        result = run_gate(gate, self.root)

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.exit_code, 7)

    def test_partial_traceability_cannot_be_reported_as_pass(self) -> None:
        catalog = load_catalog(self.catalog_path)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        with self.traceability.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["requirement_id", "status"])
            writer.writeheader()
            writer.writerow({"requirement_id": "REQ-001", "status": "PARTIAL"})
            writer.writerow(
                {
                    "requirement_id": "REQ-002",
                    "status": "BLOCKED_BY_EXTERNAL_DEPENDENCY",
                }
            )

        evaluations = build_evaluations(
            catalog, results, traceability_statuses(self.traceability)
        )

        self.assertEqual(evaluations[0]["status"], "FAIL")
        self.assertIn("TRACEABILITY=PARTIAL", evaluations[0]["evidence"])

    def test_catalog_must_cover_traceability_exactly(self) -> None:
        catalog = load_catalog(self.catalog_path)
        validate_catalog_coverage(catalog, self.traceability)
        catalog["requirements"].pop()
        self.catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

        with self.assertRaisesRegex(CatalogError, "missing=REQ-002"):
            validate_catalog_coverage(
                load_catalog(self.catalog_path), self.traceability
            )

    def test_result_schema_rejects_unsupported_claims_and_missing_fixes(self) -> None:
        catalog = load_catalog(self.catalog_path)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        statuses = traceability_statuses(self.traceability)
        report = build_report(
            catalog,
            build_evaluations(catalog, results, statuses),
            root=self.root,
        )
        report["evaluations"][1]["required_fix"] = ""

        with self.assertRaisesRegex(CatalogError, "required_fix is not catalog-bound"):
            validate_report(report, catalog, statuses, root=self.root)

    def test_fabricated_all_pass_report_is_rejected(self) -> None:
        catalog = load_catalog(self.catalog_path)
        statuses = traceability_statuses(self.traceability)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        report = build_report(
            catalog,
            build_evaluations(catalog, results, statuses),
            root=self.root,
        )
        forged = copy.deepcopy(report)
        for evaluation in forged["evaluations"]:
            evaluation["status"] = "PASS"
            evaluation["required_fix"] = ""
            evaluation["evidence"] = (
                evaluation["evidence"]
                .replace("BLOCKED_BY_EXTERNAL_DEPENDENCY", "PASS")
                .replace("BLOCKED exit=n/a", "PASS exit=0")
            )
            evaluation["actual"] = evaluation["actual"].replace(
                "BLOCKED_BY_EXTERNAL_DEPENDENCY", "PASS"
            )
        forged["status"] = "PASS"
        forged["summary"] = {
            "requirements_total": 2,
            "requirements_passed": 2,
            "requirements_failed": 0,
            "requirements_blocked": 0,
            "requirements_not_run": 0,
            "completed_requirements_pass_rate": 100.0,
            "open_critical": 0,
            "open_high": 0,
        }

        with self.assertRaisesRegex(CatalogError, "trace status is not catalog-bound"):
            validate_report(forged, catalog, statuses, root=self.root)

    def test_catalog_bound_fields_and_gate_set_reject_tampering(self) -> None:
        catalog = load_catalog(self.catalog_path)
        statuses = traceability_statuses(self.traceability)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        report = build_report(
            catalog,
            build_evaluations(catalog, results, statuses),
            root=self.root,
        )
        validate_report(report, catalog, statuses, root=self.root)

        field_mutations = {
            "eval_id": "EVAL-FORGED",
            "target": "fabricated target",
            "severity": "LOW",
            "expected": "fabricated expectation",
            "required_fix": "fabricated fix",
            "evaluator": "human",
            "reproducibility": "fabricated reproduction",
        }
        for key, value in field_mutations.items():
            with self.subTest(key=key):
                field_tamper = copy.deepcopy(report)
                field_tamper["evaluations"][0][key] = value
                with self.assertRaisesRegex(
                    CatalogError, f"{key} is not catalog-bound"
                ):
                    validate_report(field_tamper, catalog, statuses, root=self.root)

        gate_tamper = copy.deepcopy(report)
        evidence_parts = gate_tamper["evaluations"][0]["evidence"].split("; ")
        gate_tamper["evaluations"][0]["evidence"] = evidence_parts[0]
        with self.assertRaisesRegex(CatalogError, "gate set is not catalog-bound"):
            validate_report(gate_tamper, catalog, statuses, root=self.root)

    def test_source_and_top_level_tampering_is_rejected(self) -> None:
        catalog = load_catalog(self.catalog_path)
        statuses = traceability_statuses(self.traceability)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        report = build_report(
            catalog,
            build_evaluations(catalog, results, statuses),
            root=self.root,
        )

        mutations = {
            "schema_version": True,
            "catalog_id": "other-catalog",
            "source_commit": "0" * 40,
            "source_tree_sha256": "0" * 64,
            "source_file_count": report["source_file_count"] + 1,
            "apply_recommendation": "ALLOW_DEV_APPLY",
            "status": "PASS",
            "hard_gates": {
                **report["hard_gates"],
                "required_tests_pass_rate": 100.0,
            },
            "summary": {
                **report["summary"],
                "requirements_total": float(report["summary"]["requirements_total"]),
            },
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                tampered = copy.deepcopy(report)
                tampered[key] = value
                with self.assertRaises(CatalogError):
                    validate_report(tampered, catalog, statuses, root=self.root)

        extra = copy.deepcopy(report)
        extra["unsupported"] = True
        with self.assertRaisesRegex(CatalogError, "results schema mismatch"):
            validate_report(extra, catalog, statuses, root=self.root)

    def test_checked_in_result_commit_preserves_source_provenance(self) -> None:
        catalog = load_catalog(self.catalog_path)
        statuses = traceability_statuses(self.traceability)
        results = {
            gate["gate_id"]: run_gate(gate, self.root) for gate in catalog["gates"]
        }
        report = build_report(
            catalog,
            build_evaluations(catalog, results, statuses),
            root=self.root,
        )
        result_path = self.root / "agent" / "eval-results.json"
        result_path.parent.mkdir()
        result_path.write_text(json.dumps(report), encoding="utf-8")
        subprocess.run(
            ["git", "add", "agent/eval-results.json"], cwd=self.root, check=True
        )
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "record evaluation"],
            cwd=self.root,
            check=True,
        )

        validate_report(report, catalog, statuses, root=self.root)

    def test_production_catalog_maps_the_fresh_postgres_gate(self) -> None:
        catalog = load_catalog(DEFAULT_CATALOG)
        gates = {gate["gate_id"]: gate for gate in catalog["gates"]}
        requirements = {
            requirement["requirement_id"]: requirement
            for requirement in catalog["requirements"]
        }

        self.assertEqual(
            gates["POSTGRES-INTEGRATION"]["command"],
            ["bash", "e2e/postgres-integration.sh"],
        )
        for requirement_id in ("APP-002", "APP-004", "APP-008", "SEC-001", "DLV-002"):
            with self.subTest(requirement_id=requirement_id):
                self.assertIn(
                    "POSTGRES-INTEGRATION",
                    requirements[requirement_id]["gate_ids"],
                )

    def test_output_redacts_personal_paths_and_tokens(self) -> None:
        gate = {
            "gate_id": "REDACTION-GATE",
            "type": "command",
            "command": [
                sys.executable,
                "-c",
                "print('/"
                + "Users/example/private Authorization: Bearer ghp_"
                + "A" * 40
                + "')",
            ],
            "timeout_seconds": 30,
        }
        result = run_gate(gate, self.root)

        self.assertNotIn("/" + "Users/example", result.output_excerpt)
        self.assertNotIn("ghp_", result.output_excerpt)
        self.assertIn("[WORKSPACE]", result.output_excerpt)
        self.assertIn("[REDACTED]", result.output_excerpt)


if __name__ == "__main__":
    unittest.main()
