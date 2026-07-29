from __future__ import annotations

import base64
import json
import socket
import tempfile
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app


ADMIN_KEY = "package-publication-admin-key-material-2026"
X_SECRET = "package-publication-x-secret-must-not-leak"
X_ACCESS_TOKEN = "package-publication-x-access-token-must-not-leak"
X_ACCESS_SECRET = "package-publication-x-access-secret-must-not-leak"
X_POST_ID = "1800000000000000303"


def encryption_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def environment() -> dict[str, str]:
    return {
        "AGENCY_X_CONSUMER_KEY": "package-publication-x-consumer-key",
        "AGENCY_X_CONSUMER_SECRET": X_SECRET,
        "AGENCY_X_REDIRECT_URI": (
            "https://package.invalid/api/v1/social-channels/x/oauth/callback"
        ),
        "AGENCY_INSTAGRAM_APP_ID": "package-publication-instagram-app-id",
        "AGENCY_INSTAGRAM_APP_SECRET": "package-publication-instagram-secret",
        "AGENCY_INSTAGRAM_REDIRECT_URI": (
            "https://package.invalid/api/v1/social-channels/instagram/oauth/callback"
        ),
        "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps(
            {"package-social-v1": encryption_key()}
        ),
        "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "package-social-v1",
        "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true",
        "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "package-publication-tenant",
        "AGENCY_X_USER_ACCESS_TOKEN": X_ACCESS_TOKEN,
        "AGENCY_X_USER_ACCESS_TOKEN_SECRET": X_ACCESS_SECRET,
        "AGENCY_X_ACCOUNT_ID": "package-x-account-001",
        "AGENCY_X_ACCOUNT_USERNAME": "package_publication_x",
    }


def identity() -> list[dict[str, object]]:
    return [
        {
            "tenant_id": "package-publication-tenant",
            "subject_id": "package-publication-admin",
            "role": "admin",
            "key_id": "package-publication-admin-v1",
            "api_key": ADMIN_KEY,
            "active": True,
        }
    ]


def main() -> int:
    provider_calls: list[httpx.Request] = []
    attempted_sockets: list[object] = []

    def deny_socket_connect(_socket: socket.socket, address: object) -> None:
        attempted_sockets.append(address)
        raise AssertionError("real network sockets are disabled in the package fixture")

    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    socket.socket.connect = deny_socket_connect
    socket.create_connection = lambda *args, **kwargs: deny_socket_connect(  # type: ignore[assignment]
        socket.socket(), args[0] if args else None
    )

    created_text: dict[str, str] = {}

    def provider(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and str(request.url) == "https://api.x.com/2/tweets":
            provider_calls.append(request)
            created_text["value"] = json.loads(request.content)["text"]
            return httpx.Response(
                201,
                headers={"x-request-id": "package-create-request-001"},
                json={"data": {"id": X_POST_ID}},
            )
        if request.method == "GET" and request.url.path == "/2/tweets/{}".format(X_POST_ID):
            return httpx.Response(
                200,
                headers={"x-request-id": "package-verify-request-001"},
                json={
                    "data": {
                        "id": X_POST_ID,
                        "text": created_text["value"],
                        "author_id": "package-x-account-001",
                        "created_at": "2026-07-27T01:58:00Z",
                    }
                },
            )
        raise AssertionError("unexpected provider request")

    def no_oauth(request: httpx.Request) -> httpx.Response:
        raise AssertionError("OAuth provider HTTP is not expected")

    with tempfile.TemporaryDirectory(prefix="agency-package-publication-") as directory:
        root = Path(directory)
        app = create_app(
            database_path=str(root / "runtime.sqlite3"),
            static_dir=root / "missing-static",
            identity_credentials=identity(),
            session_cookie_secure=False,
            social_environment=environment(),
            social_oauth_transport=httpx.MockTransport(no_oauth),
            social_publication_transport=httpx.MockTransport(provider),
        )
        with TestClient(app) as client:
            session = client.post(
                "/api/v1/sessions",
                json={"api_key": ADMIN_KEY},
            )
            assert session.status_code == 201, session.text
            csrf = session.json()["csrf_token"]

            run = client.post(
                "/api/v1/runs",
                json={
                    "title": "Packaged exact-once publication",
                    "objective": "Prove the installed image publication authority",
                    "audience": "production reviewers",
                    "platforms": ["x"],
                    "budget_cents": 0,
                    "campaign_goal": "verification",
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "package-publication-run-001",
                },
            )
            assert run.status_code == 201, run.text
            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run.json()["run_id"]),
                json={"reviewer": "package-reviewer", "note": "package verification"},
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "package-publication-greenlight-001",
                },
            )
            assert approved.status_code == 200, approved.text
            document = approved.json()
            copy_deck = next(
                artifact
                for artifact in document["artifacts"]
                if artifact["kind"] == "copy_deck"
            )
            publication_body = {
                "artifact_id": copy_deck["artifact_id"],
                "greenlight_id": document["greenlight"]["greenlight_id"],
                "greenlight_fencing_token": document["greenlight"]["fencing_token"],
            }
            path = "/api/v1/runs/{}/social-publications/x".format(
                document["run_id"]
            )
            first = client.post(
                path,
                json=publication_body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "package-publication-effect-001",
                },
            )
            assert first.status_code == 201, first.text
            assert first.json()["provider_post_id"] == X_POST_ID
            assert first.json()["replayed"] is False
            assert first.json()["receipt"]["verification_status"] == "verified"
            assert first.json()["receipt"]["author_id"] == "package-x-account-001"
            assert len(provider_calls) == 1

            replay = client.post(
                path,
                json=publication_body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "package-publication-compatible-replay-002",
                },
            )
            assert replay.status_code == 200, replay.text
            assert replay.headers["X-Command-Replayed"] == "true"
            assert replay.json()["replayed"] is True
            assert len(provider_calls) == 1

            publications = client.get(
                "/api/v1/runs/{}/social-publications".format(document["run_id"])
            )
            assert publications.status_code == 200, publications.text
            records = publications.json()["publications"]
            assert len(records) == 1
            assert records[0]["status"] == "succeeded"

            audit = client.get("/api/v1/audit-events").json()["events"]
            success_events = [
                event
                for event in audit
                if event["action"] == "social.publication_succeeded"
            ]
            assert len(success_events) == 1
            assert success_events[0]["payload"]["provider_post_id"] == (
                X_POST_ID
            )

            serialized = json.dumps(
                {"records": records, "audit": success_events}, sort_keys=True
            )
            for forbidden in (
                ADMIN_KEY,
                X_SECRET,
                X_ACCESS_TOKEN,
                X_ACCESS_SECRET,
                "package-publication-effect-001",
                "Packaged exact-once publication",
            ):
                assert forbidden not in serialized

    socket.socket.connect = original_connect
    socket.create_connection = original_create_connection
    assert attempted_sockets == []
    print("social_publication_mock_effect=pass")
    print("social_publication_mock_replay=pass")
    print("social_publication_mock_audit=pass")
    print("social_publication_socket_guard=pass")
    print("social_publication_real_provider_http=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
