#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

from agency_runtime.memory import SQLiteMemory  # noqa: E402
from agency_runtime.models import MissionBrief, Platform  # noqa: E402
from agency_runtime.orchestrator import AgencyOrchestrator  # noqa: E402
from agency_runtime.semantic_evals import (  # noqa: E402
    CORPUS_SCHEMA,
    REPORT_SCHEMA,
    SemanticEvalInputError,
    apply_mutations,
    bundle_from_run,
    evaluate_bundle,
)
from agency_runtime.tools import build_sandbox_toolset  # noqa: E402

DEFAULT_CORPUS = ROOT / "program/evals/semantic-adversarial-corpus.json"
DEFAULT_OUTPUT = ROOT / "artifacts/semantic-evals/generated/report.json"
FIXED_TIME = "2026-07-29T12:00:00+00:00"


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()


def is_dirty() -> bool:
    return bool(git_value("status", "--porcelain", "--untracked-files=all"))


def load_corpus(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SemanticEvalInputError(f"invalid corpus: {error}") from error
    if not isinstance(value, Mapping) or value.get("schema_version") != CORPUS_SCHEMA:
        raise SemanticEvalInputError("unsupported corpus schema")
    if set(value) != {"schema_version", "base_fixture", "cases"}:
        raise SemanticEvalInputError("corpus keys are not exact")
    if not isinstance(value.get("cases"), list) or not value["cases"]:
        raise SemanticEvalInputError("corpus cases must be non-empty")
    return value


def build_brief(raw: Mapping[str, Any]) -> MissionBrief:
    fields = dict(raw)
    platforms = fields.get("platforms")
    claims = fields.get("evidence_claims")
    if not isinstance(platforms, list) or not isinstance(claims, list):
        raise SemanticEvalInputError("base fixture collections are invalid")
    fields["platforms"] = tuple(Platform(item) for item in platforms)
    fields["evidence_claims"] = tuple(dict(item) for item in claims)
    return MissionBrief(**fields)


def build_bundle(base: Mapping[str, Any]) -> dict[str, object]:
    if set(base) != {"brief", "actors"}:
        raise SemanticEvalInputError("base fixture keys are not exact")
    brief_raw, actors = base.get("brief"), base.get("actors")
    if not isinstance(brief_raw, Mapping) or not isinstance(actors, Mapping):
        raise SemanticEvalInputError("base fixture values must be objects")
    if set(actors) != {"producer_subject", "greenlight_reviewer"}:
        raise SemanticEvalInputError("base actor keys are not exact")
    with tempfile.TemporaryDirectory(prefix="semantic-eval-") as directory:
        memory = SQLiteMemory(Path(directory) / "memory.sqlite3", clock=lambda: FIXED_TIME)
        try:
            run = AgencyOrchestrator(
                tools=build_sandbox_toolset(), memory=memory, clock=lambda: FIXED_TIME
            ).start(build_brief(brief_raw))
            return bundle_from_run(
                run,
                producer_subject=str(actors["producer_subject"]),
                greenlight_reviewer=str(actors["greenlight_reviewer"]),
            )
        finally:
            memory.close()


def run_corpus(corpus_path: Path, *, allow_dirty: bool) -> dict[str, object]:
    corpus = load_corpus(corpus_path)
    dirty = is_dirty()
    if dirty and not allow_dirty:
        raise SemanticEvalInputError("exact-tree evaluation requires a clean worktree")
    source_commit = git_value("rev-parse", "HEAD")
    expected_source_commit = os.environ.get(
        "SEMANTIC_EVAL_EXPECTED_COMMIT", source_commit
    ).strip()
    if not expected_source_commit or source_commit != expected_source_commit:
        raise SemanticEvalInputError(
            "checked out commit does not match SEMANTIC_EVAL_EXPECTED_COMMIT"
        )
    baseline = build_bundle(corpus["base_fixture"])
    results: list[dict[str, object]] = []
    seen: set[str] = set()
    expected_case_keys = {
        "id", "category", "expected", "mutations", "expected_finding_codes",
        "expected_finding_count", "expected_metrics",
    }
    expected_metric_keys = {"claims", "mapped_claims", "rendered_characters", "variants"}
    for index, raw in enumerate(corpus["cases"]):
        if not isinstance(raw, Mapping) or set(raw) != expected_case_keys:
            raise SemanticEvalInputError(f"case {index} keys are not exact")
        case_id, category, expected, mutations = (
            raw.get("id"), raw.get("category"), raw.get("expected"), raw.get("mutations")
        )
        expected_codes = raw.get("expected_finding_codes")
        expected_count = raw.get("expected_finding_count")
        expected_metrics = raw.get("expected_metrics")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise SemanticEvalInputError("case IDs must be unique")
        if not isinstance(category, str) or expected not in {"PASS", "FAIL"} or not isinstance(mutations, list):
            raise SemanticEvalInputError(f"case {case_id} metadata is invalid")
        if (
            not isinstance(expected_codes, list)
            or not all(isinstance(code, str) and code for code in expected_codes)
            or expected_codes != sorted(set(expected_codes))
        ):
            raise SemanticEvalInputError(f"case {case_id} expected finding codes are invalid")
        if type(expected_count) is not int or expected_count < len(expected_codes):
            raise SemanticEvalInputError(f"case {case_id} expected finding count is invalid")
        if (
            not isinstance(expected_metrics, Mapping)
            or set(expected_metrics) != expected_metric_keys
            or not all(type(value) is int and value >= 0 for value in expected_metrics.values())
        ):
            raise SemanticEvalInputError(f"case {case_id} expected metrics are invalid")
        if (expected == "PASS" and (expected_codes or expected_count)) or (
            expected == "FAIL" and not expected_codes
        ):
            raise SemanticEvalInputError(f"case {case_id} expected findings contradict verdict")
        seen.add(case_id)
        evaluation = evaluate_bundle(apply_mutations(baseline, mutations))
        actual = "PASS" if evaluation.passed else "FAIL"
        finding_codes = sorted({item.code for item in evaluation.findings})
        finding_count = len(evaluation.findings)
        metrics = dict(sorted(evaluation.metrics.items()))
        results.append({
            "id": case_id,
            "category": category,
            "expected": expected,
            "actual": actual,
            "expectation_met": (
                actual == expected
                and finding_codes == expected_codes
                and finding_count == expected_count
                and metrics == dict(expected_metrics)
            ),
            "finding_codes": finding_codes,
            "finding_count": finding_count,
            "metrics": metrics,
        })
    return {
        "schema_version": REPORT_SCHEMA,
        "source_commit": source_commit,
        "expected_source_commit": expected_source_commit,
        "source_tree": git_value("rev-parse", "HEAD^{tree}"),
        "worktree_dirty": dirty,
        "corpus_path": str(corpus_path.relative_to(ROOT)),
        "corpus_sha256": digest(corpus_path),
        "evaluator_sha256": digest(BACKEND / "agency_runtime/semantic_evals.py"),
        "case_count": len(results),
        "expectations_met": sum(bool(item["expectation_met"]) for item in results),
        "external_effects_observed": 0,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    try:
        report = run_corpus(args.corpus.resolve(), allow_dirty=args.allow_dirty)
        if report["expectations_met"] != report["case_count"]:
            failed = [item["id"] for item in report["results"] if not item["expectation_met"]]
            raise SemanticEvalInputError(f"semantic expectations failed: {failed}")
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + f".tmp-{os.getpid()}")
        temporary.write_bytes(canonical(report))
        os.replace(temporary, output)
        print(
            f"semantic_evals=pass cases={report['case_count']} commit={report['source_commit']} "
            f"tree={report['source_tree']} dirty={str(report['worktree_dirty']).lower()}"
        )
        return 0
    except (SemanticEvalInputError, OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"semantic_evals=fail reason={type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
