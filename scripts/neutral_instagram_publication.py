#!/usr/bin/env python3
"""Prepare and execute one bounded neutral Instagram publication."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from dotenv import dotenv_values
from PIL import Image, ImageDraw, ImageFont

SCHEMA = "neutral-instagram-publication.v1"
CHANNEL_ID = "instagram"
LEGAL_SUBJECT = "legal.reviewer@local.test"
APPROVER_SUBJECT = "greenlight.approver@local.test"
EXPECTED_WIDTH = 1080
EXPECTED_HEIGHT = 1350
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_OPERATION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{7,79}$")
_CONTENT_VARIANTS: dict[str, dict[str, str]] = {
    "baseline-v1": {
        "title": "Prueba técnica neutral de publicación",
        "objective": "Verificar el flujo gobernado de aprobación, media y confirmación",
        "office": "prueba técnica no electoral",
        "candidate_name": "Sistema de verificación",
        "problem": "Validar de extremo a extremo el control de una publicación orgánica neutral",
        "proposal": "Verificar el flujo de aprobación, media y confirmación sin contenido electoral ni pauta",
        "disclosure": "Prueba técnica de publicación. No corresponde a una campaña electoral.",
        "evidence_statement": "La publicación verifica el flujo de aprobación, media y confirmación del sistema.",
        "media_badge": "PRUEBA TÉCNICA",
        "media_title": "Publicación\nneutral",
        "media_subtitle": "Verificación de flujo gobernado",
        "media_process": "Aprobación · Media · Confirmación",
        "media_footer": "No corresponde a una campaña electoral",
        "alt_text": (
            "Tarjeta gráfica de prueba técnica con el texto Publicación neutral, "
            "verificación de flujo gobernado, sin pauta y sin llamado electoral."
        ),
    },
    "repeatability-v2": {
        "title": "Segunda prueba técnica neutral de publicación",
        "objective": (
            "Confirmar la repetibilidad del flujo gobernado de aprobación, media, "
            "publicación y verificación posterior"
        ),
        "office": "segunda verificación técnica no electoral",
        "candidate_name": "CampaignOS",
        "problem": (
            "Confirmar que una segunda publicación orgánica neutral conserva los "
            "mismos controles"
        ),
        "proposal": (
            "Repetir el flujo de aprobación independiente, media gobernada, "
            "publicación y verificación posterior sin contenido electoral ni pauta"
        ),
        "disclosure": (
            "Segunda prueba técnica de publicación. No corresponde a una campaña electoral."
        ),
        "evidence_statement": (
            "La publicación confirma la repetibilidad del flujo gobernado y su "
            "verificación posterior."
        ),
        "media_badge": "SEGUNDA PRUEBA",
        "media_title": "Flujo\nrepetible",
        "media_subtitle": "Publicación y verificación posterior",
        "media_process": "Aprobación · Media · Receipt",
        "media_footer": "Prueba neutral · Sin campaña electoral",
        "alt_text": (
            "Tarjeta gráfica de segunda prueba técnica con el texto Flujo repetible, "
            "publicación y verificación posterior, sin pauta y sin llamado electoral."
        ),
    },
}


class NeutralPublicationError(RuntimeError):
    """Raised when a publication invariant fails closed."""


@dataclass(frozen=True)
class Identity:
    subject_id: str
    api_key: str
    tenant_id: str
    role: str


@dataclass(frozen=True)
class ApiResponse:
    status: int
    headers: Mapping[str, str]
    body: Mapping[str, Any]


@dataclass(frozen=True)
class BrowserSession:
    cookie: str
    csrf_token: str
    subject_id: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    return sha256_bytes(content.encode("utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise NeutralPublicationError(message)


def env_bool(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def load_environment(path: Path) -> dict[str, str]:
    values = {
        key: value
        for key, value in dotenv_values(path).items()
        if isinstance(key, str) and isinstance(value, str)
    }
    values.update({key: value for key, value in os.environ.items() if isinstance(value, str)})
    return values


def load_identities(env: Mapping[str, str]) -> dict[str, Identity]:
    raw = env.get("AGENCY_IDENTITY_CREDENTIALS_JSON", "")
    require(bool(raw), "AGENCY_IDENTITY_CREDENTIALS_JSON is required")
    try:
        records = json.loads(raw)
    except json.JSONDecodeError as error:
        raise NeutralPublicationError("identity credential JSON is invalid") from error
    require(isinstance(records, list), "identity credential JSON must be a list")
    identities: dict[str, Identity] = {}
    for record in records:
        if not isinstance(record, Mapping) or record.get("active") is False:
            continue
        subject = str(record.get("subject_id", "")).strip()
        api_key = str(record.get("api_key", "")).strip()
        tenant = str(record.get("tenant_id", "")).strip()
        role = str(record.get("role", "")).strip()
        if subject and api_key and tenant:
            identities[subject] = Identity(subject, api_key, tenant, role)
    require(LEGAL_SUBJECT in identities, f"required identity is missing: {LEGAL_SUBJECT}")
    require(APPROVER_SUBJECT in identities, f"required identity is missing: {APPROVER_SUBJECT}")
    require(
        identities[LEGAL_SUBJECT].tenant_id == identities[APPROVER_SUBJECT].tenant_id,
        "review identities must belong to the same tenant",
    )
    return identities


def validate_prepare_flags(env: Mapping[str, str]) -> None:
    require(env_bool(env, "AGENCY_POLITICAL_CONTENT_ENABLED"), "political content preparation is disabled")
    require(not env_bool(env, "AGENCY_SOCIAL_PUBLICATION_ENABLED"), "general publication must remain disabled during prepare")
    require(not env_bool(env, "AGENCY_POLITICAL_PUBLICATION_ENABLED"), "political publication must remain disabled during prepare")
    require(not env_bool(env, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED"), "paid political media must remain disabled")
    require(bool(env.get("AGENCY_PUBLIC_MEDIA_BASE_URL", "").strip()), "public media base URL is not configured")
    legacy_key = bool(env.get("AGENCY_PUBLIC_MEDIA_SIGNING_KEY", ""))
    keyring = bool(env.get("AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON", "").strip())
    active_key = bool(env.get("AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID", "").strip())
    require(not (legacy_key and (keyring or active_key)), "public media signing configuration is ambiguous")
    require(legacy_key or (keyring and active_key), "public media signing keyring is not configured")


def validate_execute_flags(env: Mapping[str, str]) -> None:
    require(env_bool(env, "AGENCY_POLITICAL_CONTENT_ENABLED"), "political content is disabled")
    require(env_bool(env, "AGENCY_SOCIAL_PUBLICATION_ENABLED"), "general publication authority is disabled")
    require(env_bool(env, "AGENCY_POLITICAL_PUBLICATION_ENABLED"), "political publication authority is disabled")
    require(not env_bool(env, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED"), "paid political media must remain disabled")


def api_request(
    base_url: str,
    method: str,
    path: str,
    identity: Identity | None,
    *,
    session: BrowserSession | None = None,
    json_body: Mapping[str, Any] | None = None,
    raw_body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 90.0,
) -> ApiResponse:
    require(not (json_body is not None and raw_body is not None), "request body is ambiguous")
    require((identity is None) != (session is None), "exactly one authentication method is required")
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "agency-neutral-instagram-publication/1",
    }
    if session is not None:
        request_headers["Cookie"] = session.cookie
        request_headers["X-CSRF-Token"] = session.csrf_token
    else:
        require(identity is not None, "identity is required")
        request_headers["Authorization"] = f"Bearer {identity.api_key}"
    request_headers.update(dict(headers or {}))
    data: bytes | None = raw_body
    if json_body is not None:
        data = json.dumps(json_body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            require(len(content) <= MAX_RESPONSE_BYTES, "runtime API response exceeded size limit")
            body = json.loads(content.decode("utf-8")) if content else {}
            require(isinstance(body, Mapping), "runtime API response must be an object")
            return ApiResponse(response.status, dict(response.headers.items()), body)
    except HTTPError as error:
        content = error.read(128 * 1024)
        code = "request_failed"
        detail = "runtime API rejected the request"
        try:
            parsed = json.loads(content.decode("utf-8"))
            if isinstance(parsed, Mapping):
                error_body = parsed.get("error")
                if isinstance(error_body, Mapping):
                    code = str(error_body.get("code", code))[:128]
                    detail = str(error_body.get("detail", detail))[:500]
                elif "detail" in parsed:
                    detail = str(parsed.get("detail", detail))[:500]
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        raise NeutralPublicationError(
            f"{method} {path} failed with HTTP {error.code}: {code}: {detail}"
        ) from error
    except URLError as error:
        raise NeutralPublicationError(f"runtime API is unreachable for {method} {path}") from error


def create_browser_session(base_url: str, identity: Identity) -> BrowserSession:
    body = json.dumps({"api_key": identity.api_key}, separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/api/v1/sessions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "agency-neutral-instagram-publication/1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read(128 * 1024)
            payload = json.loads(content.decode("utf-8"))
            set_cookie = response.headers.get("Set-Cookie", "")
    except (HTTPError, URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NeutralPublicationError("browser session creation failed") from error
    require(isinstance(payload, Mapping), "browser session response is invalid")
    require(
        payload.get("subject_id") == identity.subject_id,
        "browser session subject does not match",
    )
    csrf_token = str(payload.get("csrf_token", ""))
    cookie = set_cookie.split(";", 1)[0].strip()
    require(
        bool(csrf_token) and "=" in cookie,
        "browser session cookie or CSRF token is missing",
    )
    return BrowserSession(cookie=cookie, csrf_token=csrf_token, subject_id=identity.subject_id)


def neutral_variant(name: str) -> Mapping[str, str]:
    variant = _CONTENT_VARIANTS.get(name)
    require(variant is not None, "neutral content variant is unsupported")
    return variant


def build_neutral_brief(
    operation_id: str = "neutral-template",
    content_variant: str = "baseline-v1",
) -> dict[str, Any]:
    require(bool(_OPERATION_PATTERN.fullmatch(operation_id)), "operation ID is invalid")
    variant = neutral_variant(content_variant)
    return {
        "title": "{} {}".format(variant["title"], operation_id),
        "objective": variant["objective"],
        "audience": "equipo técnico de la cuenta de laboratorio",
        "platforms": [CHANNEL_ID],
        "budget_cents": 0,
        "source_asset": "sandbox://neutral-instagram/{}/{}/neutral-publication-card.jpg".format(
            content_variant, operation_id
        ),
        "campaign_goal": "technical_verification",
        "campaign_type": "political",
        "publication_mode": "organic",
        "locale": "es-GT",
        "jurisdiction": "Guatemala — prueba técnica sin campaña",
        "office": variant["office"],
        "candidate_name": variant["candidate_name"],
        "locality": "cuenta de laboratorio @beesheep2",
        "problem": variant["problem"],
        "proposal": variant["proposal"],
        "desired_action": "No se requiere ninguna acción",
        "disclosure": variant["disclosure"],
        "legal_review_status": "approved",
        "legal_reviewed_by": "server-will-bind-authenticated-reviewer",
        "evidence_claims": [{
            "statement": variant["evidence_statement"],
            "source": "Runbook interno de publicación neutral",
            "locator": "docs/runbooks/political-publication.md, sección Neutral sandbox sequence",
            "verification_status": "verified",
            "reviewed_by": "server-will-bind-authenticated-reviewer",
        }],
    }


def expected_caption(
    operation_id: str = "neutral-template",
    content_variant: str = "baseline-v1",
) -> str:
    brief = build_neutral_brief(operation_id, content_variant)
    hook = "Una propuesta verificable para {} en {}.".format(brief["office"], brief["locality"])
    body = "{} propone: {}\n\nFuente: {} ({}).\n\n{}".format(
        brief["candidate_name"], brief["proposal"], brief["evidence_claims"][0]["source"],
        brief["evidence_claims"][0]["locator"], brief["disclosure"],
    )
    return "\n\n".join((hook, body, brief["desired_action"]))


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    width: int,
) -> int:
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=12, align="center")
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    draw.multiline_text(
        ((width - text_width) / 2, y),
        text,
        font=font,
        fill=fill,
        spacing=12,
        align="center",
    )
    return y + text_height


def generate_neutral_media(
    path: Path, content_variant: str = "baseline-v1"
) -> dict[str, Any]:
    variant = neutral_variant(content_variant)
    image = Image.new("RGB", (EXPECTED_WIDTH, EXPECTED_HEIGHT), (17, 22, 34))
    draw = ImageDraw.Draw(image)
    for y in range(EXPECTED_HEIGHT):
        ratio = y / (EXPECTED_HEIGHT - 1)
        draw.line(
            (0, y, EXPECTED_WIDTH, y),
            fill=(int(17 + 19 * ratio), int(22 + 25 * ratio), int(34 + 31 * ratio)),
        )
    draw.rounded_rectangle(
        (90, 105, 990, 1245), radius=42, fill=(27, 35, 52), outline=(103, 232, 249), width=4
    )
    draw.rounded_rectangle(
        (176, 170, 904, 252), radius=34, fill=(12, 18, 28), outline=(103, 232, 249), width=2
    )
    _draw_centered(draw, variant["media_badge"], 191, _font(34, bold=True), (155, 246, 255), EXPECTED_WIDTH)
    y = _draw_centered(draw, variant["media_title"], 365, _font(82, bold=True), (250, 252, 255), EXPECTED_WIDTH)
    y = _draw_centered(draw, variant["media_subtitle"], y + 72, _font(35), (201, 213, 228), EXPECTED_WIDTH)
    draw.line((220, y + 72, 860, y + 72), fill=(103, 232, 249), width=3)
    y = _draw_centered(
        draw, variant["media_process"], y + 130, _font(31, bold=True), (225, 232, 241), EXPECTED_WIDTH
    )
    y = _draw_centered(draw, "Sin pauta\nSin llamado electoral", y + 75, _font(34), (180, 195, 214), EXPECTED_WIDTH)
    _draw_centered(
        draw, variant["media_footer"], 1110, _font(25), (155, 246, 255), EXPECTED_WIDTH
    )
    image.info.clear()
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=92, optimize=True, progressive=False, exif=b"")
    content = path.read_bytes()
    with Image.open(path) as decoded:
        require(decoded.format == "JPEG", "generated media is not JPEG")
        require(decoded.size == (EXPECTED_WIDTH, EXPECTED_HEIGHT), "generated media dimensions are invalid")
        decoded.load()
    require(len(content) <= 8 * 1024 * 1024, "generated media exceeds the upload limit")
    return {
        "path": str(path),
        "sha256": sha256_bytes(content),
        "byte_size": len(content),
        "width": EXPECTED_WIDTH,
        "height": EXPECTED_HEIGHT,
        "content_type": "image/jpeg",
    }


def channel_snapshot(
    base_url: str,
    identity: Identity,
    expected_username: str,
    expected_account_id: str,
) -> Mapping[str, Any]:
    response = api_request(base_url, "GET", "/api/v1/social-channels", identity)
    channels = response.body.get("channels")
    require(isinstance(channels, list), "social channel response is invalid")
    channel = next(
        (
            item
            for item in channels
            if isinstance(item, Mapping) and item.get("channel_id") == CHANNEL_ID
        ),
        None,
    )
    require(isinstance(channel, Mapping), "Instagram channel is unavailable")
    connected = channel.get("connected_account")
    require(isinstance(connected, Mapping), "Instagram is not connected")
    require(channel.get("connection_state") == "connected", "Instagram connection is not active")
    require(
        connected.get("account_username") == expected_username,
        "connected Instagram username does not match",
    )
    require(
        str(connected.get("account_id")) == expected_account_id,
        "connected Instagram account ID does not match",
    )
    scopes = connected.get("scopes")
    require(
        isinstance(scopes, list) and "instagram_business_content_publish" in scopes,
        "Instagram publish scope is missing",
    )
    return channel


def find_artifact(
    run: Mapping[str, Any],
    kind: str,
    *,
    channel: str | None = None,
) -> Mapping[str, Any]:
    artifacts = run.get("artifacts")
    require(isinstance(artifacts, list), "run artifacts are invalid")
    matches = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or artifact.get("kind") != kind:
            continue
        payload = artifact.get("payload")
        if channel is not None and (
            not isinstance(payload, Mapping) or payload.get("channel") != channel
        ):
            continue
        matches.append(artifact)
    require(len(matches) == 1, f"expected exactly one {kind} artifact")
    return matches[0]


def wait_for_run(
    base_url: str,
    identity: Identity,
    run_id: str,
    timeout_seconds: int = 180,
) -> Mapping[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status = ""
    while time.monotonic() < deadline:
        run = api_request(base_url, "GET", f"/api/v1/runs/{run_id}", identity).body
        status = str(run.get("status", ""))
        if status != last_status:
            print(f"neutral_instagram_run_status={status}")
            last_status = status
        if status not in {"queued", "running"}:
            return run
        time.sleep(0.5)
    raise NeutralPublicationError("run did not reach a durable review state before timeout")


def safe_public_fetch(media_url: str, expected_sha256: str) -> bool:
    parsed = urlsplit(media_url)
    require(parsed.scheme == "https", "public media URL must use HTTPS")
    require(
        parsed.username is None and parsed.password is None,
        "public media URL contains credentials",
    )
    request = Request(
        media_url,
        headers={"User-Agent": "agency-neutral-media-verifier/1"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read(8 * 1024 * 1024 + 1)
    except (HTTPError, URLError) as error:
        raise NeutralPublicationError("public media capability is not reachable") from error
    require(len(content) <= 8 * 1024 * 1024, "public media response exceeds limit")
    require(
        sha256_bytes(content) == expected_sha256,
        "public media bytes do not match the approved hash",
    )
    return True


def prepare(args: argparse.Namespace) -> int:
    require(
        bool(_OPERATION_PATTERN.fullmatch(args.operation_id)),
        "operation ID must be lowercase kebab-case",
    )
    env = load_environment(args.env_file)
    validate_prepare_flags(env)
    identities = load_identities(env)
    legal = identities[LEGAL_SUBJECT]
    approver = identities[APPROVER_SUBJECT]
    legal_session = create_browser_session(args.base_url, legal)
    approver_session = create_browser_session(args.base_url, approver)
    channel = channel_snapshot(
        args.base_url,
        legal,
        args.expected_account_username,
        args.expected_account_id,
    )
    require(
        channel.get("publication_execution_enabled") is False,
        "publication execution must be disabled during prepare",
    )

    output_dir = args.output_dir / args.operation_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    require(not manifest_path.exists(), "manifest already exists for this operation ID")
    media_path = output_dir / "neutral-instagram-card.jpg"
    media = generate_neutral_media(media_path, args.content_variant)

    created = api_request(
        args.base_url,
        "POST",
        "/api/v1/runs",
        legal,
        json_body=build_neutral_brief(args.operation_id, args.content_variant),
        headers={
            "Idempotency-Key": f"{args.operation_id}-run",
            "Prefer": "respond-async",
        },
    ).body
    run_id = str(created.get("run_id", ""))
    require(run_id.startswith("run-"), "runtime did not return a run ID")
    run = wait_for_run(args.base_url, legal, run_id)
    require(
        run.get("status") in {"awaiting_greenlight", "completed"},
        "neutral run is not in a resumable review state",
    )
    risk = find_artifact(run, "risk_report")
    risk_payload = risk.get("payload")
    require(isinstance(risk_payload, Mapping), "risk report payload is invalid")
    require(
        risk_payload.get("publication_eligible") is True,
        "Critique did not mark the neutral run publication eligible",
    )

    alt_text = neutral_variant(args.content_variant)["alt_text"]
    alt_header = base64.urlsafe_b64encode(alt_text.encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")
    if run.get("status") == "awaiting_greenlight":
        attached = api_request(
            args.base_url,
            "POST",
            f"/api/v1/runs/{run_id}/publication-media/{CHANNEL_ID}",
            None,
            session=legal_session,
            raw_body=media_path.read_bytes(),
            headers={
                "Content-Type": "image/jpeg",
                "Idempotency-Key": f"{args.operation_id}-media",
                "X-Media-Alt-Text-Base64": alt_header,
                "X-Media-Rights-Confirmed": "true",
            },
        ).body
    else:
        attached = run
    media_artifact = find_artifact(
        attached,
        "publication_media",
        channel=CHANNEL_ID,
    )
    media_payload = media_artifact.get("payload")
    require(
        isinstance(media_payload, Mapping),
        "publication media payload is invalid",
    )
    require(
        media_payload.get("sha256") == media["sha256"],
        "Media Vault hash differs from generated bytes",
    )
    media_url = media_payload.get("media_url")
    require(
        isinstance(media_url, str),
        "publication media capability URL is missing",
    )
    safe_public_fetch(media_url, media["sha256"])

    if attached.get("status") == "awaiting_greenlight":
        approved = api_request(
            args.base_url,
            "POST",
            f"/api/v1/runs/{run_id}/greenlight/approve",
            None,
            session=approver_session,
            json_body={
                "reviewer": APPROVER_SUBJECT,
                "note": "Aprobación independiente de una única publicación técnica neutral.",
            },
            headers={"Idempotency-Key": f"{args.operation_id}-greenlight"},
        ).body
    else:
        approved = attached
    require(
        approved.get("status") == "completed",
        "Greenlight approval did not complete the run",
    )
    greenlight = approved.get("greenlight")
    require(isinstance(greenlight, Mapping), "Greenlight record is missing")
    require(
        greenlight.get("reviewer") == APPROVER_SUBJECT,
        "Greenlight reviewer binding is incorrect",
    )

    copy_artifact = find_artifact(approved, "copy_deck")
    media_artifact = find_artifact(
        approved,
        "publication_media",
        channel=CHANNEL_ID,
    )
    copy_payload = copy_artifact.get("payload")
    require(isinstance(copy_payload, Mapping), "copy deck payload is invalid")
    variants = copy_payload.get("variants")
    require(isinstance(variants, Mapping), "copy variants are invalid")
    variant = variants.get(CHANNEL_ID)
    require(isinstance(variant, Mapping), "Instagram copy variant is missing")
    caption = "\n\n".join(
        str(variant.get(field, "")).strip()
        for field in ("hook", "body", "cta")
        if str(variant.get(field, "")).strip()
    )
    require(
        hmac.compare_digest(
            caption.encode("utf-8"),
            expected_caption(args.operation_id, args.content_variant).encode("utf-8"),
        ),
        "generated neutral caption differs from the approved template",
    )
    require(
        "No corresponde a una campaña electoral" in caption,
        "neutral disclosure is missing",
    )
    require(
        "No se requiere ninguna acción" in caption,
        "neutral no-action CTA is missing",
    )

    approved_ids = greenlight.get("approved_artifact_ids")
    require(
        isinstance(approved_ids, list),
        "Greenlight artifact envelope is invalid",
    )
    require(
        copy_artifact.get("artifact_id") in approved_ids,
        "copy artifact is outside the Greenlight envelope",
    )
    require(
        media_artifact.get("artifact_id") in approved_ids,
        "media artifact is outside the Greenlight envelope",
    )
    compliance = find_artifact(approved, "political_compliance_record")
    require(
        compliance.get("artifact_id") in approved_ids,
        "compliance record is outside the Greenlight envelope",
    )

    prepared_at = utc_now()
    expires_at = prepared_at + timedelta(minutes=args.window_minutes)
    manifest = {
        "schema": SCHEMA,
        "phase": "approved_ready_for_execution",
        "operation_id": args.operation_id,
        "content_variant": args.content_variant,
        "prepared_at": isoformat(prepared_at),
        "execute_before": isoformat(expires_at),
        "window_minutes": args.window_minutes,
        "rollback_owner": args.rollback_owner,
        "tenant_id": legal.tenant_id,
        "account": {
            "channel_id": CHANNEL_ID,
            "account_id": args.expected_account_id,
            "account_username": args.expected_account_username,
        },
        "review": {
            "legal_reviewer": LEGAL_SUBJECT,
            "greenlight_approver": APPROVER_SUBJECT,
            "subjects_distinct": True,
        },
        "run": {
            "run_id": run_id,
            "status": approved.get("status"),
            "copy_artifact_id": copy_artifact.get("artifact_id"),
            "media_artifact_id": media_artifact.get("artifact_id"),
            "compliance_artifact_id": compliance.get("artifact_id"),
            "greenlight_id": greenlight.get("greenlight_id"),
            "greenlight_fencing_token": greenlight.get("fencing_token"),
        },
        "copy": {
            "caption": caption,
            "caption_sha256": sha256_text(caption),
            "neutral_disclosure_present": True,
            "no_action_cta_present": True,
        },
        "media": {
            "file": media_path.name,
            "sha256": media["sha256"],
            "byte_size": media["byte_size"],
            "width": media["width"],
            "height": media["height"],
            "alt_text": alt_text,
            "rights_attested_by": LEGAL_SUBJECT,
            "public_fetch_verified": True,
            "capability_url_persisted_in_receipt": False,
        },
        "confirmation": {
            "format": "PUBLICAR POLITICA <run_id> instagram",
            "sha256": sha256_text(
                f"PUBLICAR POLITICA {run_id} {CHANNEL_ID}"
            ),
            "raw_value_persisted": False,
        },
        "provider_effects": {"attempted": 0, "completed": 0},
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"neutral_instagram_phase={manifest['phase']}")
    print(f"neutral_instagram_manifest={manifest_path}")
    print(f"neutral_instagram_run_id={run_id}")
    print(
        "neutral_instagram_caption_sha256="
        f"{manifest['copy']['caption_sha256']}"
    )
    print(f"neutral_instagram_media_sha256={manifest['media']['sha256']}")
    print("neutral_instagram_provider_effects=0")
    return 0


def execute(args: argparse.Namespace) -> int:
    env = load_environment(args.env_file)
    validate_execute_flags(env)
    identities = load_identities(env)
    approver = identities[APPROVER_SUBJECT]
    approver_session = create_browser_session(args.base_url, approver)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require(isinstance(manifest, Mapping), "manifest must be a JSON object")
    require(manifest.get("schema") == SCHEMA, "manifest schema is unsupported")
    require(
        manifest.get("phase") == "approved_ready_for_execution",
        "manifest is not ready for execution",
    )
    require(
        args.acknowledge_external_effect,
        "--acknowledge-external-effect is required",
    )
    execute_before = datetime.fromisoformat(str(manifest.get("execute_before", "")))
    require(execute_before.tzinfo is not None, "execution deadline is invalid")
    require(
        utc_now() <= execute_before,
        "controlled publication window has expired",
    )

    account = manifest.get("account")
    run = manifest.get("run")
    copy = manifest.get("copy")
    media = manifest.get("media")
    confirmation_record = manifest.get("confirmation")
    require(
        all(
            isinstance(item, Mapping)
            for item in (account, run, copy, media, confirmation_record)
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
    require(
        channel.get("publication_execution_enabled") is True,
        "runtime publication execution is not enabled",
    )
    require(
        channel.get("external_effects_enabled") is True,
        "runtime external effect authority is not enabled",
    )
    require(
        channel.get("publishing_available") is True,
        "Instagram publication is not currently available",
    )

    run_id = str(run.get("run_id", ""))
    expected_confirmation = f"PUBLICAR POLITICA {run_id} {CHANNEL_ID}"
    require(
        hmac.compare_digest(args.confirmation, expected_confirmation),
        "exact political confirmation does not match",
    )
    require(
        sha256_text(expected_confirmation) == confirmation_record.get("sha256"),
        "confirmation digest differs from prepared authority",
    )

    payload = {
        "artifact_id": run.get("copy_artifact_id"),
        "media_artifact_id": run.get("media_artifact_id"),
        "greenlight_id": run.get("greenlight_id"),
        "greenlight_fencing_token": run.get("greenlight_fencing_token"),
        "political_confirmation": args.confirmation,
    }
    operation_id = str(manifest.get("operation_id", ""))
    result = api_request(
        args.base_url,
        "POST",
        f"/api/v1/runs/{run_id}/social-publications/{CHANNEL_ID}",
        None,
        session=approver_session,
        json_body=payload,
        headers={"Idempotency-Key": f"{operation_id}-publish"},
        timeout=180.0,
    ).body
    require(
        result.get("status") == "succeeded",
        "publication did not reach succeeded state",
    )
    require(
        result.get("replayed") is False,
        "first controlled effect unexpectedly replayed",
    )
    require(
        str(result.get("account_id")) == expected_account_id,
        "provider receipt account ID does not match",
    )
    receipt = result.get("receipt")
    require(isinstance(receipt, Mapping), "verified provider receipt is missing")
    require(
        receipt.get("verification_status") == "verified",
        "provider read-after-write verification did not pass",
    )
    require(
        receipt.get("username") == expected_username,
        "verified provider username does not match",
    )
    require(
        receipt.get("caption_sha256") == copy.get("caption_sha256"),
        "verified caption hash does not match",
    )
    require(
        receipt.get("media_sha256") == media.get("sha256"),
        "verified media hash does not match",
    )
    permalink = str(receipt.get("permalink", ""))
    parsed = urlsplit(permalink)
    require(
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and (
            parsed.hostname == "instagram.com"
            or parsed.hostname.endswith(".instagram.com")
        ),
        "verified permalink is invalid",
    )

    publications = api_request(
        args.base_url,
        "GET",
        f"/api/v1/runs/{run_id}/social-publications",
        approver,
    ).body
    items = publications.get("publications")
    require(
        isinstance(items, list) and len(items) == 1,
        "expected exactly one durable publication intent",
    )
    durable = items[0]
    require(
        isinstance(durable, Mapping) and durable.get("status") == "succeeded",
        "durable publication intent is not succeeded",
    )
    require(
        durable.get("intent_id") == result.get("intent_id"),
        "durable intent identity does not match",
    )

    receipt_path = args.manifest.parent / "verified-receipt.json"
    safe_receipt = {
        "schema": SCHEMA,
        "phase": "published_verified",
        "operation_id": operation_id,
        "verified_at": isoformat(utc_now()),
        "rollback_owner": manifest.get("rollback_owner"),
        "account": account,
        "run_id": run_id,
        "intent_id": result.get("intent_id"),
        "provider_container_id": result.get("provider_container_id"),
        "provider_post_id": result.get("provider_post_id"),
        "status": result.get("status"),
        "execution_fencing_token": result.get("execution_fencing_token"),
        "verification_status": receipt.get("verification_status"),
        "permalink": permalink,
        "published_at": receipt.get("published_at"),
        "username": receipt.get("username"),
        "caption_sha256": receipt.get("caption_sha256"),
        "media_sha256": receipt.get("media_sha256"),
        "durable_intent_count": len(items),
        "raw_confirmation_persisted": False,
        "capability_url_persisted": False,
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

    print("neutral_instagram_phase=published_verified")
    print(f"neutral_instagram_receipt={receipt_path}")
    print(f"neutral_instagram_intent_id={result.get('intent_id')}")
    print(f"neutral_instagram_provider_post_id={result.get('provider_post_id')}")
    print(f"neutral_instagram_permalink={permalink}")
    print("neutral_instagram_provider_effects=1")
    return 0


def inspect_attempt(args: argparse.Namespace) -> int:
    env = load_environment(args.env_file)
    identities = load_identities(env)
    approver = identities[APPROVER_SUBJECT]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require(isinstance(manifest, Mapping), "manifest must be a JSON object")
    require(manifest.get("schema") == SCHEMA, "manifest schema is unsupported")
    run = manifest.get("run")
    account = manifest.get("account")
    require(isinstance(run, Mapping) and isinstance(account, Mapping), "manifest contract is incomplete")
    run_id = str(run.get("run_id", ""))
    publications = api_request(
        args.base_url,
        "GET",
        f"/api/v1/runs/{run_id}/social-publications",
        approver,
    ).body
    items = publications.get("publications")
    require(isinstance(items, list) and len(items) == 1, "expected exactly one durable publication intent")
    durable = items[0]
    require(isinstance(durable, Mapping), "durable publication intent is invalid")
    status = str(durable.get("status", ""))
    container_id = durable.get("provider_container_id")
    post_id = durable.get("provider_post_id")
    if status == "failed" and not container_id and not post_id:
        phase = "provider_rejected_before_container_recorded"
        manifest_phase = "provider_rejected_no_post"
    elif status == "unknown":
        phase = "provider_outcome_unknown"
        manifest_phase = "provider_outcome_unknown"
    elif status == "succeeded":
        phase = "provider_verified_success"
        manifest_phase = "published_verified"
    else:
        phase = "durable_{}".format(status or "unclassified")
        manifest_phase = phase
    receipt_path = args.manifest.parent / "attempt-receipt.json"
    safe_receipt = {
        "schema": SCHEMA,
        "phase": phase,
        "operation_id": manifest.get("operation_id"),
        "observed_at": isoformat(utc_now()),
        "account": account,
        "run_id": run_id,
        "intent_id": durable.get("intent_id"),
        "status": status,
        "failure_reason": durable.get("failure_reason"),
        "provider_container_id": container_id,
        "provider_post_id": post_id,
        "confirmation_sha256": durable.get("confirmation_hash"),
        "media_sha256": durable.get("media_hash"),
        "publication_switches_closed": (
            not env_bool(env, "AGENCY_SOCIAL_PUBLICATION_ENABLED")
            and not env_bool(env, "AGENCY_POLITICAL_PUBLICATION_ENABLED")
        ),
        "paid_media_enabled": env_bool(env, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED"),
        "raw_confirmation_persisted": False,
        "capability_url_persisted": False,
        "provider_error_body_persisted": False,
    }
    receipt_path.write_text(
        json.dumps(safe_receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    updated = dict(manifest)
    updated["phase"] = manifest_phase
    updated["provider_effects"] = {
        "attempted": 1,
        "completed": 1 if status == "succeeded" else 0,
    }
    updated["attempt_receipt_file"] = receipt_path.name
    args.manifest.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"neutral_instagram_phase={manifest_phase}")
    print(f"neutral_instagram_attempt_receipt={receipt_path}")
    print(f"neutral_instagram_intent_status={status}")
    print(f"neutral_instagram_provider_container_recorded={bool(container_id)}")
    print(f"neutral_instagram_provider_post_recorded={bool(post_id)}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--env-file", type=Path, default=Path(".env.local"))
    result.add_argument("--base-url", default="http://127.0.0.1:4175")
    subparsers = result.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="prepare media, run and independent Greenlight with effects disabled",
    )
    prepare_parser.add_argument("--operation-id", required=True)
    prepare_parser.add_argument(
        "--content-variant",
        choices=tuple(sorted(_CONTENT_VARIANTS)),
        default="baseline-v1",
    )
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
        default=Path("artifacts/neutral-instagram/generated"),
    )
    prepare_parser.set_defaults(handler=prepare)

    execute_parser = subparsers.add_parser(
        "execute",
        help="execute exactly one prepared external effect",
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
        help="record the current durable intent state without provider HTTP",
    )
    inspect_parser.add_argument("--manifest", type=Path, required=True)
    inspect_parser.set_defaults(handler=inspect_attempt)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except NeutralPublicationError as error:
        print(f"neutral_instagram_error={error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
