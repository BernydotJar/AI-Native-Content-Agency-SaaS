from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from .memory import SQLiteMemory
from .models import AGENT_SEQUENCE, AgentRole, MissionBrief, Platform
from .orchestrator import AgencyOrchestrator
from .tools import build_sandbox_toolset
from .utils import to_primitive


DEMO_TIMESTAMP = "2026-07-17T12:00:00+00:00"
SAFETY_NOTICE = (
    "Deterministic sandbox only: no network calls, browser navigation, ad spend, "
    "GitHub changes, media rendering, or external publication."
)


def fixed_demo_clock() -> str:
    return DEMO_TIMESTAMP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agency-runtime",
        description="Run the deterministic eight-agent agency sandbox.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser(
        "demo",
        help="execute a fixture mission without external side effects",
    )
    decision = demo.add_mutually_exclusive_group()
    decision.add_argument(
        "--approve",
        action="store_true",
        help="record a local demo Greenlight and create a sandbox manifest",
    )
    decision.add_argument(
        "--reject",
        action="store_true",
        help="record a local demo rejection and keep Publisher blocked",
    )
    demo.add_argument(
        "--reviewer",
        default="demo-human-reviewer",
        help="reviewer label stored in the local Greenlight record",
    )
    demo.add_argument(
        "--db",
        default=":memory:",
        help="SQLite memory path; defaults to an ephemeral in-memory database",
    )
    demo.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable deterministic report",
    )
    return parser


def _demo_report(arguments: argparse.Namespace) -> dict:
    database_path = arguments.db
    if database_path != ":memory:":
        resolved_database = Path(database_path).expanduser().resolve()
        resolved_database.parent.mkdir(parents=True, exist_ok=True)
        database_path = str(resolved_database)

    memory = SQLiteMemory(database_path, clock=fixed_demo_clock)
    try:
        tools = build_sandbox_toolset()
        orchestrator = AgencyOrchestrator(
            tools=tools,
            memory=memory,
            clock=fixed_demo_clock,
        )
        brief = MissionBrief(
            title="Signal / Story / System",
            objective="Introduce an evidence-led AI-native content operating model",
            audience="growth and brand leaders at scaling companies",
            platforms=(
                Platform.X,
                Platform.FACEBOOK,
                Platform.TIKTOK,
                Platform.INSTAGRAM,
            ),
            budget_cents=250000,
            source_asset="sandbox://fixtures/hero-still.png",
            campaign_goal="qualified_demand",
        )
        run = orchestrator.start(brief)
        pre_greenlight_status = run.status.value
        publisher_before_decision = run.state_for(AgentRole.PUBLISHER).status.value

        if arguments.approve:
            run = orchestrator.approve(
                run.run_id,
                reviewer=arguments.reviewer,
                note="Local CLI demo approval; external publication remains disabled.",
            )
        elif arguments.reject:
            run = orchestrator.reject(
                run.run_id,
                reviewer=arguments.reviewer,
                note="Local CLI demo rejection.",
            )

        search_results = memory.search("greenlight", limit=5)
        recalled = memory.recall(search_results[0].record.memory_id)
        report = {
            "sandbox": True,
            "safety_notice": SAFETY_NOTICE,
            "deterministic_timestamp": DEMO_TIMESTAMP,
            "run_id": run.run_id,
            "pre_greenlight_status": pre_greenlight_status,
            "publisher_before_decision": publisher_before_decision,
            "final_status": run.status.value,
            "greenlight": to_primitive(run.greenlight),
            "agents": [
                {
                    "role": role.value,
                    "status": run.state_for(role).status.value,
                    "progress": run.state_for(role).progress,
                }
                for role in AGENT_SEQUENCE
            ],
            "artifact_kinds": [artifact.kind for artifact in run.artifacts],
            "evidence": [
                {
                    "tool": item.tool,
                    "operation": item.operation,
                    "sandbox": item.sandbox,
                    "summary": item.summary,
                }
                for item in run.evidence
            ],
            "trace_events": len(run.trace),
            "memory_cycle": {
                "records": memory.count(),
                "search_query": "greenlight",
                "search_result_ids": [item.record.memory_id for item in search_results],
                "recalled": {
                    "memory_id": recalled.memory_id,
                    "confidence": recalled.confidence,
                    "provenance": to_primitive(recalled.provenance),
                },
            },
            "external_side_effects": {
                "network_calls": 0,
                "browser_navigations": 0,
                "ad_spend_cents": 0,
                "github_changes": 0,
                "media_renders": 0,
                "publications": 0,
            },
        }
        return report
    finally:
        memory.close()


def _print_human(report: dict) -> None:
    greenlight = report["greenlight"]
    decision = greenlight["decision"] if greenlight is not None else "not_supplied"
    print("AGENCY RUNTIME · SANDBOX DEMO")
    print(SAFETY_NOTICE)
    print("run: {}".format(report["run_id"]))
    print("gate: {} -> {}".format(report["pre_greenlight_status"], report["final_status"]))
    print("greenlight: {}".format(decision))
    print("agents: {}".format(" -> ".join(item["role"] for item in report["agents"])))
    print("artifacts: {}".format(", ".join(report["artifact_kinds"])))
    print("sandbox evidence records: {}".format(len(report["evidence"])))
    print("persistent memory records: {}".format(report["memory_cycle"]["records"]))
    print("external side effects: all zero")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command != "demo":
        parser.error("unknown command")
    report = _demo_report(arguments)
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
