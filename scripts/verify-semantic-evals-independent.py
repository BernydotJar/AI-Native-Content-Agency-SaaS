#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "program/evals/semantic-adversarial-corpus.json"
DEFAULT_REPORT = ROOT / "artifacts/semantic-evals/generated/report.json"
CORPUS_SCHEMA = "agency.semantic-adversarial-corpus.v1"
REPORT_SCHEMA = "agency.semantic-eval-report.v1"
REQUIRED_CATEGORIES = {
    "groundedness", "citation", "authority", "injection",
    "overclaim", "numeric", "boundary",
}
FORBIDDEN_IMPORT_ROOTS = {"aiohttp", "anthropic", "httpx", "openai", "requests", "socket", "urllib"}


class IndependentVerificationError(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()


def load(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IndependentVerificationError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(value, Mapping):
        raise IndependentVerificationError(f"{path}: root must be an object")
    return value


def verify_no_network_imports(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    forbidden = sorted(roots & FORBIDDEN_IMPORT_ROOTS)
    if forbidden:
        raise IndependentVerificationError(f"network-capable imports are forbidden: {forbidden}")


def verify(corpus_path: Path, report_path: Path, *, allow_dirty: bool) -> None:
    corpus, report = load(corpus_path), load(report_path)
    if corpus.get("schema_version") != CORPUS_SCHEMA or report.get("schema_version") != REPORT_SCHEMA:
        raise IndependentVerificationError("schema mismatch")
    expected_keys = {
        "schema_version", "source_commit", "source_tree", "worktree_dirty",
        "corpus_path", "corpus_sha256", "evaluator_sha256", "case_count",
        "expectations_met", "external_effects_observed", "results",
    }
    if set(report) != expected_keys:
        raise IndependentVerificationError("report keys are not exact")
    dirty = bool(git_value("status", "--porcelain", "--untracked-files=all"))
    if dirty and not allow_dirty:
        raise IndependentVerificationError("exact-tree verification requires a clean worktree")
    if report.get("source_commit") != git_value("rev-parse", "HEAD"):
        raise IndependentVerificationError("report commit mismatch")
    if report.get("source_tree") != git_value("rev-parse", "HEAD^{tree}"):
        raise IndependentVerificationError("report tree mismatch")
    if report.get("worktree_dirty") is not dirty:
        raise IndependentVerificationError("report dirty-state mismatch")
    if report.get("corpus_sha256") != digest(corpus_path):
        raise IndependentVerificationError("corpus digest mismatch")
    evaluator = ROOT / "backend/agency_runtime/semantic_evals.py"
    if report.get("evaluator_sha256") != digest(evaluator):
        raise IndependentVerificationError("evaluator digest mismatch")
    verify_no_network_imports(evaluator)

    cases, results = corpus.get("cases"), report.get("results")
    if not isinstance(cases, list) or not isinstance(results, list):
        raise IndependentVerificationError("cases and results must be lists")
    if report.get("case_count") != len(cases) or len(results) != len(cases):
        raise IndependentVerificationError("case cardinality mismatch")
    expected: dict[str, tuple[str, str]] = {}
    categories: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise IndependentVerificationError("corpus case is not an object")
        if set(case) != {"id", "category", "expected", "mutations"}:
            raise IndependentVerificationError("corpus case keys are not exact")
        if not isinstance(case.get("mutations"), list):
            raise IndependentVerificationError("corpus mutations must be a list")
        case_id, verdict, category = case.get("id"), case.get("expected"), case.get("category")
        if not isinstance(case_id, str) or case_id in expected:
            raise IndependentVerificationError("case IDs are invalid or duplicate")
        if verdict not in {"PASS", "FAIL"} or not isinstance(category, str):
            raise IndependentVerificationError(f"case {case_id} metadata is invalid")
        expected[case_id] = (verdict, category)
        categories.add(category)
    if not REQUIRED_CATEGORIES.issubset(categories):
        raise IndependentVerificationError(f"missing categories: {sorted(REQUIRED_CATEGORIES-categories)}")

    observed: set[str] = set()
    for result in results:
        if not isinstance(result, Mapping):
            raise IndependentVerificationError("result is not an object")
        if set(result) != {
            "id", "category", "expected", "actual", "expectation_met",
            "finding_codes", "finding_count", "metrics",
        }:
            raise IndependentVerificationError("result keys are not exact")
        case_id = result.get("id")
        if case_id not in expected or case_id in observed:
            raise IndependentVerificationError("result case is unknown or duplicate")
        observed.add(case_id)
        verdict, category = expected[case_id]
        if result.get("expected") != verdict or result.get("category") != category:
            raise IndependentVerificationError(f"metadata mismatch for {case_id}")
        if result.get("actual") != verdict or result.get("expectation_met") is not True:
            raise IndependentVerificationError(f"expectation failed for {case_id}")
        codes = result.get("finding_codes")
        if not isinstance(codes, list) or codes != sorted(set(codes)):
            raise IndependentVerificationError(f"finding codes are not canonical for {case_id}")
        finding_count = result.get("finding_count")
        if not isinstance(finding_count, int) or finding_count < len(codes):
            raise IndependentVerificationError(f"finding count is invalid for {case_id}")
        metrics = result.get("metrics")
        if not isinstance(metrics, Mapping) or set(metrics) != {
            "claims", "mapped_claims", "rendered_characters", "variants"
        } or not all(isinstance(value, int) and value >= 0 for value in metrics.values()):
            raise IndependentVerificationError(f"metrics are invalid for {case_id}")
        if (verdict == "PASS" and (codes or finding_count)) or (verdict == "FAIL" and not codes):
            raise IndependentVerificationError(f"finding/verdict mismatch for {case_id}")
    if observed != set(expected):
        raise IndependentVerificationError("report omitted cases")
    if report.get("expectations_met") != len(cases):
        raise IndependentVerificationError("not all expectations met")
    if report.get("external_effects_observed") != 0:
        raise IndependentVerificationError("external effects were observed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    try:
        verify(args.corpus.resolve(), args.report.resolve(), allow_dirty=args.allow_dirty)
        report = load(args.report.resolve())
        print(
            f"semantic_independent_verifier=pass cases={report['case_count']} "
            f"commit={report['source_commit']} tree={report['source_tree']}"
        )
        return 0
    except (IndependentVerificationError, OSError, subprocess.CalledProcessError) as error:
        print(f"semantic_independent_verifier=fail reason={type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
