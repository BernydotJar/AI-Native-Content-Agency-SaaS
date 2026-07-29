from __future__ import annotations

import json
import socket
import tempfile
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app


ADMIN_KEY = "package-model-admin-key-material-2026"
MODEL_SECRET = "package-model-secret-must-not-leak"


def environment() -> dict[str, str]:
    return {
        "AGENCY_MODEL_EXECUTION_ENABLED": "true",
        "AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED": "true",
        "AGENCY_MODEL_PROVIDER": "openai",
        "OPENAI_API_KEY": MODEL_SECRET,
        "AGENCY_OPENAI_MODEL": "gpt-5.2",
        "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.openai.com",
        "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "128",
    }


def identity() -> list[dict[str, object]]:
    return [
        {
            "tenant_id": "package-model-tenant",
            "subject_id": "package-model-admin",
            "role": "admin",
            "key_id": "package-model-admin-v1",
            "api_key": ADMIN_KEY,
            "active": True,
        }
    ]


def main() -> int:
    provider_calls: list[httpx.Request] = []
    attempted_sockets: list[object] = []

    def deny_socket_connect(_socket: socket.socket, address: object) -> None:
        attempted_sockets.append(address)
        raise AssertionError("real network sockets are disabled in the model package fixture")

    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    socket.socket.connect = deny_socket_connect
    socket.create_connection = lambda *args, **kwargs: deny_socket_connect(  # type: ignore[assignment]
        socket.socket(), args[0] if args else None
    )

    def provider(request: httpx.Request) -> httpx.Response:
        provider_calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer {}".format(MODEL_SECRET)
        body = json.loads(request.content)
        assert body["model"] == "gpt-5.2"
        assert body["max_output_tokens"] == 128
        assert "governed artifact" in body["input"]
        return httpx.Response(
            200,
            headers={"x-request-id": "package-model-provider-request-001"},
            json={
                "id": "package-model-response-001",
                "model": "gpt-5.2",
                "output_text": "Package-verified governed model refinement.",
                "usage": {
                    "input_tokens": 24,
                    "output_tokens": 6,
                    "total_tokens": 30,
                },
            },
        )

    try:
        with tempfile.TemporaryDirectory(prefix="agency-package-model-effect-") as directory:
            root = Path(directory)
            app = create_app(
                database_path=str(root / "runtime.sqlite3"),
                static_dir=root / "missing-static",
                identity_credentials=identity(),
                session_cookie_secure=False,
                provider_environment=environment(),
                model_transport=httpx.MockTransport(provider),
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
                        "title": "Packaged exact-once model effect",
                        "objective": "Prove installed-image model authority",
                        "audience": "production reviewers",
                        "platforms": ["x"],
                        "budget_cents": 0,
                        "campaign_goal": "verification",
                    },
                    headers={
                        "X-CSRF-Token": csrf,
                        "Idempotency-Key": "package-model-run-001",
                    },
                )
                assert run.status_code == 201, run.text
                document = run.json()
                source = next(
                    artifact
                    for artifact in document["artifacts"]
                    if artifact["created_by"] == "writer"
                )
                path = "/api/v1/runs/{}/model-effects/writer".format(
                    document["run_id"]
                )
                body = {
                    "source_artifact_id": source["artifact_id"],
                    "instruction": "Improve the governed artifact without inventing evidence.",
                    "max_cost_micros": 500_000,
                }
                first = client.post(
                    path,
                    json=body,
                    headers={
                        "X-CSRF-Token": csrf,
                        "Idempotency-Key": "package-model-effect-001",
                    },
                )
                assert first.status_code == 201, first.text
                assert first.json()["effect"]["replayed"] is False
                assert first.json()["effect"]["output_text"] == (
                    "Package-verified governed model refinement."
                )
                assert len(provider_calls) == 1

                replay = client.post(
                    path,
                    json=body,
                    headers={
                        "X-CSRF-Token": csrf,
                        "Idempotency-Key": "package-model-compatible-replay-002",
                    },
                )
                assert replay.status_code == 200, replay.text
                assert replay.headers["X-Command-Replayed"] == "true"
                assert replay.json()["effect"]["replayed"] is True
                assert len(provider_calls) == 1

                current = replay.json()["run"]
                artifacts = [
                    artifact
                    for artifact in current["artifacts"]
                    if artifact["kind"] == "model_completion"
                ]
                assert len(artifacts) == 1
                assert artifacts[0]["payload"]["output_text"] == (
                    "Package-verified governed model refinement."
                )

                listing = client.get(
                    "/api/v1/runs/{}/model-effects".format(document["run_id"])
                )
                assert listing.status_code == 200, listing.text
                records = listing.json()["effects"]
                assert len(records) == 1
                assert records[0]["status"] == "succeeded"
                serialized_records = json.dumps(records, sort_keys=True)
                assert "output_text" not in serialized_records
                assert "Improve the governed artifact" not in serialized_records

                audit = client.get("/api/v1/audit-events").json()["events"]
                success_events = [
                    event
                    for event in audit
                    if event["action"] == "model.effect_succeeded"
                ]
                assert len(success_events) == 1
                serialized = json.dumps(
                    {"records": records, "audit": success_events}, sort_keys=True
                )
                for forbidden in (
                    ADMIN_KEY,
                    MODEL_SECRET,
                    "package-model-effect-001",
                    "Improve the governed artifact",
                    "Package-verified governed model refinement.",
                ):
                    assert forbidden not in serialized
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create_connection

    assert attempted_sockets == []
    print("model_effect_mock_effect=pass")
    print("model_effect_mock_replay=pass")
    print("model_effect_mock_audit=pass")
    print("model_effect_socket_guard=pass")
    print("model_effect_real_provider_http=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
