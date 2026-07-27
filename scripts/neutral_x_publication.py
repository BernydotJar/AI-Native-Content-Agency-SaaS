#!/usr/bin/env python3
"""Prepare and execute one bounded neutral X publication."""

from __future__ import annotations

import argparse
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import neutral_instagram_publication as common

SCHEMA = "neutral-x-publication.v1"
CHANNEL_ID = "x"
MAX_X_TEXT_CHARACTERS = 280


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_neutral_x_brief(operation_id: str = "neutral-x-template") -> dict[str, Any]:
    common.require(
        bool(common._OPERATION_PATTERN.fullmatch(operation_id)),
        "operation ID is invalid",
    )
    return {
        "title": "Prueba técnica neutral en X {}".format(operation_id),
        "objective": "Verificar publicación exact-once y lectura posterior en X",
        "audience": "equipo técnico de la cuenta de laboratorio",
        "platforms": [CHANNEL_ID],
        "budget_cents": 0,
        "source_asset": "sandbox://neutral-x/{}/text-only".format(operation_id),
        "campaign_goal": "technical_verification",
        "campaign_type": "political",
        "publication_mode": "organic",
        "locale": "es-GT",
        "jurisdiction": "Guatemala — prueba técnica sin campaña",
        "office": "prueba técnica",
        "candidate_name": "CampaignOS",
        "locality": "cuenta de laboratorio en X",
        "problem": "Validar una publicación orgánica neutral en X",
        "proposal": "Validar publicación exact-once y verificación posterior sin pauta",
        "desired_action": "No se requiere acción.",
        "disclosure": "Prueba técnica. No corresponde a una campaña electoral.",
        "legal_review_status": "approved",
        "legal_reviewed_by": "server-will-bind-authenticated-reviewer",
        "evidence_claims": [
            {
                "statement": "El flujo usa reserva exact-once y lectura posterior.",
                "source": "Runbook neutral",
                "locator": "X-1",
                "verification_status": "verified",
                "reviewed_by": "server-will-bind-authenticated-reviewer",
            }
        ],
    }


def expected_x_text(operation_id: str = "neutral-x-template") -> str:
    brief = build_neutral_x_brief(operation_id)
    hook = "Una propuesta verificable para {} en {}.".format(
        brief["office"], brief["locality"]
    )
    body = "{} propone: {}\n\nFuente: {} ({}).\n\n{}".format(
        brief["candidate_name"],
        brief["proposal"],
        brief["evidence_claims"][0]["source"],
        brief["evidence_claims"][0]["locator"],
        brief["disclosure"],
    )
    text = "\n\n".join((hook, body, brief["desired_action"]))
    common.require(
        len(text) <= MAX_X_TEXT_CHARACTERS,
        "neutral X text exceeds 280 characters",
    )
    return text


def validate_prepare_flags(env: Mapping[str, str]) -> None:
    common.require(
        common.env_bool(env, "AGENCY_POLITICAL_CONTENT_ENABLED"),
        "political content preparation is disabled",
    )
    common.require(
        not common.env_bool(env, "AGENCY_SOCIAL_PUBLICATION_ENABLED"),
        "general publication must remain disabled during prepare",
    )
    common.require(
        not common.env_bool(env, "AGENCY_POLITICAL_PUBLICATION_ENABLED"),
        "political publication must remain disabled during prepare",
    )
    common.require(
        not common.env_bool(env, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED"),
        "paid political media must remain disabled",
    )


def validate_execute_flags(env: Mapping[str, str]) -> None:
    common.require(
        common.env_bool(env, "AGENCY_POLITICAL_CONTENT_ENABLED"),
        "political content is disabled",
    )
    common.require(
        common.env_bool(env, "AGENCY_SOCIAL_PUBLICATION_ENABLED"),
        "general publication authority is disabled",
    )
    common.require(
        common.env_bool(env, "AGENCY_POLITICAL_PUBLICATION_ENABLED"),
        "political publication authority is disabled",
    )
    common.require(
        not common.env_bool(env, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED"),
        "paid political media must remain disabled",
    )


def channel_snapshot(
    base_url: str,
    identity: common.Identity,
    expected_username: str,
    expected_account_id: str,
) -> Mapping[str, Any]:
    response = common.api_request(
        base_url, "GET", "/api/v1/social-channels", identity
    )
    channels = response.body.get("channels")
    common.require(isinstance(channels, list), "social channel response is invalid")
    channel = next(
        (
            item
            for item in channels
            if isinstance(item, Mapping) and item.get("channel_id") == CHANNEL_ID
        ),
        None,
    )
    common.require(isinstance(channel, Mapping), "X channel is unavailable")
    connected = channel.get("connected_account")
    common.require(isinstance(connected, Mapping), "X is not connected")
    common.require(
        channel.get("connection_state") == "connected",
        "X connection is not active",
    )
    common.require(
        connected.get("account_username") == expected_username,
        "connected X username does not match",
    )
    common.require(
        str(connected.get("account_id")) == expected_account_id,
        "connected X account ID does not match",
    )
    scopes = connected.get("scopes")
    common.require(
        isinstance(scopes, list) and "tweet.write" in scopes,
        "X write scope is missing",
    )
    return channel


def prepare(args: argparse.Namespace) -> int:
    common.require(
        bool(common._OPERATION_PATTERN.fullmatch(args.operation_id)),
        "operation ID must be lowercase kebab-case",
    )
    env = common.load_environment(args.env_file)
    validate_prepare_flags(env)
    identities = common.load_identities(env)
    legal = identities[common.LEGAL_SUBJECT]
    approver = identities[common.APPROVER_SUBJECT]
    approver_session = common.create_browser_session(args.base_url, approver)
    channel = channel_snapshot(
        args.base_url,
        legal,
        args.expected_account_username,
        args.expected_account_id,
    )
    common.require(
        channel.get("publication_execution_enabled") is False,
        "publication execution must be disabled during prepare",
    )

    output_dir = args.output_dir / args.operation_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    common.require(
        not manifest_path.exists(),
        "manifest already exists for this operation ID",
    )

    created = common.api_request(
        args.base_url,
        "POST",
        "/api/v1/runs",
        legal,
        json_body=build_neutral_x_brief(args.operation_id),
        headers={
            "Idempotency-Key": "{}-run".format(args.operation_id),
            "Prefer": "respond-async",
        },
    ).body
    run_id = str(created.get("run_id", ""))
    common.require(run_id.startswith("run-"), "runtime did not return a run ID")
    run = common.wait_for_run(args.base_url, legal, run_id)
    common.require(
        run.get("status") in {"awaiting_greenlight", "completed"},
        "neutral X run is not in a resumable review state",
    )
    risk = common.find_artifact(run, "risk_report")
    risk_payload = risk.get("payload")
    common.require(isinstance(risk_payload, Mapping), "risk report payload is invalid")
    common.require(
        risk_payload.get("publication_eligible") is True,
        "Critique did not mark the neutral X run publication eligible",
    )

    if run.get("status") == "awaiting_greenlight":
        approved = common.api_request(
            args.base_url,
            "POST",
            "/api/v1/runs/{}/greenlight/approve".format(run_id),
            None,
            session=approver_session,
            json_body={
                "reviewer": common.APPROVER_SUBJECT,
                "note": "Aprobación independiente de una única publicación técnica neutral en X.",
            },
            headers={
                "Idempotency-Key": "{}-greenlight".format(args.operation_id)
            },
        ).body
    else:
        approved = run
    common.require(
        approved.get("status") == "completed",
        "Greenlight approval did not complete the X run",
    )
    greenlight = approved.get("greenlight")
    common.require(isinstance(greenlight, Mapping), "Greenlight record is missing")
    common.require(
        greenlight.get("reviewer") == common.APPROVER_SUBJECT,
        "Greenlight reviewer binding is incorrect",
    )

    copy_artifact = common.find_artifact(approved, "copy_deck")
    copy_payload = copy_artifact.get("payload")
    common.require(isinstance(copy_payload, Mapping), "copy deck payload is invalid")
    variants = copy_payload.get("variants")
    common.require(isinstance(variants, Mapping), "copy variants are invalid")
    variant = variants.get(CHANNEL_ID)
    common.require(isinstance(variant, Mapping), "X copy variant is missing")
    text = "\n\n".join(
        str(variant.get(field, "")).strip()
        for field in ("hook", "body", "cta")
        if str(variant.get(field, "")).strip()
    )
    common.require(
        hmac.compare_digest(
            text.encode("utf-8"),
            expected_x_text(args.operation_id).encode("utf-8"),
        ),
        "generated neutral X text differs from the approved template",
    )
    common.require(
        len(text) <= MAX_X_TEXT_CHARACTERS,
        "approved X text exceeds 280 characters",
    )
    common.require(
        "No corresponde a una campaña electoral" in text,
        "neutral disclosure is missing",
    )
    common.require(
        "No se requiere acción" in text,
        "neutral no-action CTA is missing",
    )

    compliance = common.find_artifact(approved, "political_compliance_record")
    approved_ids = greenlight.get("approved_artifact_ids")
    common.require(
        isinstance(approved_ids, list),
        "Greenlight artifact envelope is invalid",
    )
    common.require(
        copy_artifact.get("artifact_id") in approved_ids,
        "copy artifact is outside the Greenlight envelope",
    )
    common.require(
        compliance.get("artifact_id") in approved_ids,
        "compliance record is outside the Greenlight envelope",
    )

    prepared_at = utc_now()
    manifest = {
        "schema": SCHEMA,
        "phase": "approved_ready_for_execution",
        "operation_id": args.operation_id,
        "prepared_at": common.isoformat(prepared_at),
        "execute_before": common.isoformat(
            prepared_at + timedelta(minutes=args.window_minutes)
        ),
        "window_minutes": args.window_minutes,
        "rollback_owner": args.rollback_owner,
        "tenant_id": legal.tenant_id,
        "account": {
            "channel_id": CHANNEL_ID,
            "account_id": args.expected_account_id,
            "account_username": args.expected_account_username,
        },
        "review": {
            "legal_reviewer": common.LEGAL_SUBJECT,
            "greenlight_approver": common.APPROVER_SUBJECT,
            "subjects_distinct": True,
        },
        "run": {
            "run_id": run_id,
            "status": approved.get("status"),
            "copy_artifact_id": copy_artifact.get("artifact_id"),
            "compliance_artifact_id": compliance.get("artifact_id"),
            "greenlight_id": greenlight.get("greenlight_id"),
            "greenlight_fencing_token": greenlight.get("fencing_token"),
        },
        "copy": {
            "text": text,
            "content_sha256": common.sha256_text(text),
            "character_count": len(text),
            "neutral_disclosure_present": True,
            "no_action_cta_present": True,
        },
        "confirmation": {
            "format": "PUBLICAR POLITICA <run_id> x",
            "sha256": common.sha256_text(
                "PUBLICAR POLITICA {} {}".format(run_id, CHANNEL_ID)
            ),
            "raw_value_persisted": False,
        },
        "provider_effects": {"attempted": 0, "completed": 0},
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("neutral_x_phase=approved_ready_for_execution")
    print("neutral_x_manifest={}".format(manifest_path))
    print("neutral_x_run_id={}".format(run_id))
    print("neutral_x_content_sha256={}".format(manifest["copy"]["content_sha256"]))
    print("neutral_x_character_count={}".format(len(text)))
    print("neutral_x_provider_effects=0")
    return 0


def execute(args: argparse.Namespace) -> int:
    env = common.load_environment(args.env_file)
    validate_execute_flags(env)
    identities = common.load_identities(env)
    approver = identities[common.APPROVER_SUBJECT]
    approver_session = common.create_browser_session(args.base_url, approver)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    common.require(isinstance(manifest, Mapping), "manifest must be a JSON object")
    common.require(manifest.get("schema") == SCHEMA, "manifest schema is unsupported")
    common.require(
        manifest.get("phase") == "approved_ready_for_execution",
        "manifest is not ready for execution",
    )
    common.require(
        args.acknowledge_external_effect,
        "--acknowledge-external-effect is required",
    )
    execute_before = datetime.fromisoformat(str(manifest.get("execute_before", "")))
    common.require(execute_before.tzinfo is not None, "execution deadline is invalid")
    common.require(
        utc_now() <= execute_before,
        "controlled publication window has expired",
    )

    account = manifest.get("account")
    run = manifest.get("run")
    copy = manifest.get("copy")
    confirmation_record = manifest.get("confirmation")
    common.require(
        all(
            isinstance(item, Mapping)
            for item in (account, run, copy, confirmation_record)
        ),
        "manifest contract is incomplete",
    )
    expected_username = str(account.get("account_username", ""))
    expected_account_id = str(account.get("account_id", ""))
    channel = channel_snapshot(
        args.base_url,
        approver,
        expected_username,
        expected_account_id,
    )
    common.require(
        channel.get("publication_execution_enabled") is True,
        "runtime publication execution is not enabled",
    )
    common.require(
        channel.get("external_effects_enabled") is True,
        "runtime external effect authority is not enabled",
    )
    common.require(
        channel.get("publishing_available") is True,
        "X publication is not currently available",
    )

    run_id = str(run.get("run_id", ""))
    expected_confirmation = "PUBLICAR POLITICA {} {}".format(run_id, CHANNEL_ID)
    common.require(
        hmac.compare_digest(args.confirmation, expected_confirmation),
        "exact political confirmation does not match",
    )
    common.require(
        common.sha256_text(expected_confirmation)
        == confirmation_record.get("sha256"),
        "confirmation digest differs from prepared authority",
    )
    result = common.api_request(
        args.base_url,
        "POST",
        "/api/v1/runs/{}/social-publications/{}".format(run_id, CHANNEL_ID),
        None,
        session=approver_session,
        json_body={
            "artifact_id": run.get("copy_artifact_id"),
            "greenlight_id": run.get("greenlight_id"),
            "greenlight_fencing_token": run.get("greenlight_fencing_token"),
            "political_confirmation": args.confirmation,
        },
        headers={
            "Idempotency-Key": "{}-publish".format(
                manifest.get("operation_id")
            )
        },
        timeout=180.0,
    ).body
    common.require(
        result.get("status") == "succeeded",
        "X publication did not succeed",
    )
    common.require(
        result.get("replayed") is False,
        "first X effect unexpectedly replayed",
    )
    common.require(
        str(result.get("account_id")) == expected_account_id,
        "provider receipt account ID does not match",
    )
    receipt = result.get("receipt")
    common.require(
        isinstance(receipt, Mapping),
        "verified X provider receipt is missing",
    )
    common.require(
        receipt.get("verification_status") == "verified",
        "X read-after-write verification did not pass",
    )
    common.require(
        receipt.get("username") == expected_username,
        "verified X username does not match",
    )
    common.require(
        receipt.get("author_id") == expected_account_id,
        "verified X author ID does not match",
    )
    common.require(
        receipt.get("content_sha256") == copy.get("content_sha256"),
        "verified X content hash does not match",
    )
    permalink = str(receipt.get("permalink", ""))
    parsed = urlsplit(permalink)
    common.require(
        parsed.scheme == "https"
        and parsed.hostname in {"x.com", "www.x.com"}
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment,
        "verified X permalink is invalid",
    )

    publications = common.api_request(
        args.base_url,
        "GET",
        "/api/v1/runs/{}/social-publications".format(run_id),
        approver,
    ).body
    items = publications.get("publications")
    common.require(
        isinstance(items, list) and len(items) == 1,
        "expected exactly one durable X publication intent",
    )
    durable = items[0]
    common.require(
        isinstance(durable, Mapping) and durable.get("status") == "succeeded",
        "durable X publication intent is not succeeded",
    )
    common.require(
        durable.get("intent_id") == result.get("intent_id"),
        "durable X intent identity does not match",
    )

    receipt_path = args.manifest.parent / "verified-receipt.json"
    safe_receipt = {
        "schema": SCHEMA,
        "phase": "published_verified",
        "operation_id": manifest.get("operation_id"),
        "verified_at": common.isoformat(utc_now()),
        "rollback_owner": manifest.get("rollback_owner"),
        "account": account,
        "run_id": run_id,
        "intent_id": result.get("intent_id"),
        "provider_post_id": result.get("provider_post_id"),
        "status": result.get("status"),
        "execution_fencing_token": result.get("execution_fencing_token"),
        "verification_status": receipt.get("verification_status"),
        "permalink": permalink,
        "published_at": receipt.get("published_at"),
        "username": receipt.get("username"),
        "author_id": receipt.get("author_id"),
        "content_sha256": receipt.get("content_sha256"),
        "durable_intent_count": len(items),
        "raw_confirmation_persisted": False,
    }
    receipt_path.write_text(
        json.dumps(safe_receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    updated = dict(manifest)
    updated["phase"] = "published_verified"
    updated["provider_effects"] = {"attempted": 1, "completed": 1}
    updated["receipt_file"] = receipt_path.name
    args.manifest.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("neutral_x_phase=published_verified")
    print("neutral_x_receipt={}".format(receipt_path))
    print("neutral_x_intent_id={}".format(result.get("intent_id")))
    print("neutral_x_provider_post_id={}".format(result.get("provider_post_id")))
    print("neutral_x_permalink={}".format(permalink))
    print("neutral_x_provider_effects=1")
    return 0


def inspect_attempt(args: argparse.Namespace) -> int:
    env = common.load_environment(args.env_file)
    identities = common.load_identities(env)
    approver = identities[common.APPROVER_SUBJECT]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    common.require(isinstance(manifest, Mapping), "manifest must be a JSON object")
    common.require(manifest.get("schema") == SCHEMA, "manifest schema is unsupported")
    run = manifest.get("run")
    account = manifest.get("account")
    common.require(
        isinstance(run, Mapping) and isinstance(account, Mapping),
        "manifest contract is incomplete",
    )
    run_id = str(run.get("run_id", ""))
    publications = common.api_request(
        args.base_url,
        "GET",
        "/api/v1/runs/{}/social-publications".format(run_id),
        approver,
    ).body
    items = publications.get("publications")
    common.require(
        isinstance(items, list) and len(items) == 1,
        "expected exactly one durable X intent",
    )
    durable = items[0]
    common.require(isinstance(durable, Mapping), "durable X intent is invalid")
    status = str(durable.get("status", ""))
    if status == "succeeded":
        phase = "published_verified"
    elif status == "unknown":
        phase = "provider_outcome_unknown"
    elif status == "failed":
        phase = "provider_rejected_no_verified_post"
    else:
        phase = "durable_{}".format(status or "unclassified")
    receipt_path = args.manifest.parent / "attempt-receipt.json"
    safe_receipt = {
        "schema": SCHEMA,
        "phase": phase,
        "operation_id": manifest.get("operation_id"),
        "observed_at": common.isoformat(utc_now()),
        "account": account,
        "run_id": run_id,
        "intent_id": durable.get("intent_id"),
        "status": status,
        "failure_reason": durable.get("failure_reason"),
        "provider_post_id": durable.get("provider_post_id"),
        "confirmation_sha256": durable.get("confirmation_hash"),
        "publication_switches_closed": (
            not common.env_bool(env, "AGENCY_SOCIAL_PUBLICATION_ENABLED")
            and not common.env_bool(
                env, "AGENCY_POLITICAL_PUBLICATION_ENABLED"
            )
        ),
        "paid_media_enabled": common.env_bool(
            env, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED"
        ),
        "raw_confirmation_persisted": False,
        "provider_error_body_persisted": False,
    }
    receipt_path.write_text(
        json.dumps(safe_receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    updated = dict(manifest)
    updated["phase"] = phase
    updated["provider_effects"] = {
        "attempted": 1,
        "completed": 1 if status == "succeeded" else 0,
    }
    updated["attempt_receipt_file"] = receipt_path.name
    args.manifest.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("neutral_x_phase={}".format(phase))
    print("neutral_x_attempt_receipt={}".format(receipt_path))
    print("neutral_x_intent_status={}".format(status))
    print(
        "neutral_x_provider_post_recorded={}".format(
            bool(durable.get("provider_post_id"))
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--env-file", type=Path, default=Path(".env.local"))
    result.add_argument("--base-url", default="http://127.0.0.1:4175")
    subparsers = result.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="prepare a neutral X run and independent Greenlight with effects disabled",
    )
    prepare_parser.add_argument("--operation-id", required=True)
    prepare_parser.add_argument("--expected-account-username", required=True)
    prepare_parser.add_argument("--expected-account-id", required=True)
    prepare_parser.add_argument("--rollback-owner", required=True)
    prepare_parser.add_argument(
        "--window-minutes",
        type=int,
        default=15,
        choices=range(5, 31),
        metavar="5-30",
    )
    prepare_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/neutral-x/generated"),
    )
    prepare_parser.set_defaults(handler=prepare)

    execute_parser = subparsers.add_parser(
        "execute",
        help="execute exactly one prepared X external effect",
    )
    execute_parser.add_argument("--manifest", type=Path, required=True)
    execute_parser.add_argument("--confirmation", required=True)
    execute_parser.add_argument(
        "--acknowledge-external-effect",
        action="store_true",
    )
    execute_parser.set_defaults(handler=execute)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="record the current durable X intent state without provider HTTP",
    )
    inspect_parser.add_argument("--manifest", type=Path, required=True)
    inspect_parser.set_defaults(handler=inspect_attempt)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except common.NeutralPublicationError as error:
        print("neutral_x_error={}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
