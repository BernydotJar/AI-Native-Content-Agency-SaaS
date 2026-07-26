from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from threading import Lock

import httpx
from fastapi import FastAPI

from agency_runtime.api import create_app


LEGAL_KEY = "browser-political-legal-key-material-2026"
APPROVER_KEY = "browser-political-approver-key-material-2026"
_LOCK = Lock()
_PROVIDER_CALLS = 0


def _encryption_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def _handler(request: httpx.Request) -> httpx.Response:
    global _PROVIDER_CALLS
    if str(request.url) != "https://api.x.com/2/tweets":
        raise AssertionError("unexpected provider request {}".format(request.url))
    with _LOCK:
        _PROVIDER_CALLS += 1
        sequence = _PROVIDER_CALLS
        Path(os.environ["AGENCY_FIXTURE_CALL_FILE"]).write_text(
            str(sequence), encoding="utf-8"
        )
    return httpx.Response(
        201,
        headers={"x-request-id": "political-browser-provider-{}".format(sequence)},
        json={"data": {"id": "political-browser-post-001"}},
    )


social_environment = {
    "AGENCY_POLITICAL_CONTENT_ENABLED": "true",
    "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true",
    "AGENCY_POLITICAL_PUBLICATION_ENABLED": "true",
    "AGENCY_POLITICAL_PAID_MEDIA_ENABLED": "false",
    "AGENCY_X_CONSUMER_KEY": "political-browser-x-consumer-key",
    "AGENCY_X_CONSUMER_SECRET": "political-browser-x-consumer-secret",
    "AGENCY_X_REDIRECT_URI": (
        "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback"
    ),
    "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps(
        {"social-v1": _encryption_key()}
    ),
    "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "social-v1",
    "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "political-browser-tenant",
    "AGENCY_X_USER_ACCESS_TOKEN": "political-browser-x-access-token",
    "AGENCY_X_USER_ACCESS_TOKEN_SECRET": "political-browser-x-access-secret",
    "AGENCY_X_ACCOUNT_ID": "political-browser-x-account",
    "AGENCY_X_ACCOUNT_USERNAME": "political_browser_sandbox",
}


app: FastAPI = create_app(
    database_path=os.environ["AGENCY_FIXTURE_DB_PATH"],
    static_dir=Path(os.environ["AGENCY_FIXTURE_STATIC_DIR"]),
    identity_credentials=[
        {
            "tenant_id": "political-browser-tenant",
            "subject_id": "legal.reviewer@browser.test",
            "role": "admin",
            "key_id": "political-browser-legal-v1",
            "api_key": LEGAL_KEY,
            "active": True,
        },
        {
            "tenant_id": "political-browser-tenant",
            "subject_id": "greenlight.approver@browser.test",
            "role": "admin",
            "key_id": "political-browser-approver-v1",
            "api_key": APPROVER_KEY,
            "active": True,
        },
    ],
    session_cookie_secure=False,
    social_environment=social_environment,
    social_oauth_transport=httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(
            AssertionError("OAuth provider HTTP is not expected")
        )
    ),
    social_publication_transport=httpx.MockTransport(_handler),
)
