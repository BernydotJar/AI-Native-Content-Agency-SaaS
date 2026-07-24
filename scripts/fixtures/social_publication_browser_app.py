from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from threading import Lock

import httpx
from fastapi import FastAPI

from agency_runtime.api import create_app


API_KEY = "browser-publication-admin-key-material-2026"
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
        headers={"x-request-id": "browser-provider-request-{}".format(sequence)},
        json={"data": {"id": "browser-x-post-001"}},
    )


social_environment = {
    "AGENCY_X_CONSUMER_KEY": "browser-x-consumer-key",
    "AGENCY_X_CONSUMER_SECRET": "browser-x-consumer-secret",
    "AGENCY_X_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback",
    "AGENCY_INSTAGRAM_APP_ID": "browser-instagram-app-id",
    "AGENCY_INSTAGRAM_APP_SECRET": "browser-instagram-secret",
    "AGENCY_INSTAGRAM_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback",
    "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps(
        {"social-v1": _encryption_key()}
    ),
    "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "social-v1",
    "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true",
    "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "browser-publication-tenant",
    "AGENCY_X_USER_ACCESS_TOKEN": "browser-x-user-token",
    "AGENCY_X_USER_ACCESS_TOKEN_SECRET": "browser-x-user-secret",
    "AGENCY_X_ACCOUNT_ID": "browser-x-account-001",
    "AGENCY_X_ACCOUNT_USERNAME": "browser_publication_x",
}

app: FastAPI = create_app(
    database_path=os.environ["AGENCY_FIXTURE_DB_PATH"],
    static_dir=Path(os.environ["AGENCY_FIXTURE_STATIC_DIR"]),
    identity_credentials=[
        {
            "tenant_id": "browser-publication-tenant",
            "subject_id": "browser-publication-admin",
            "role": "admin",
            "key_id": "browser-publication-admin-v1",
            "api_key": API_KEY,
            "active": True,
        }
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

