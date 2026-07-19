"""Exercise the real HTTP/repository path against a migrated PostgreSQL database."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from control_plane.api import create_app
from control_plane.settings import Settings


def main() -> None:
    database_url = os.environ.get("AGENCY_DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("AGENCY_DATABASE_URL must select the isolated PostgreSQL test database")
    application = create_app(
        Settings(
            environment="test",
            auth_mode="development_headers",
            database_url=database_url,
            auto_create_schema=False,
            cors_origins=("http://localhost:8080",),
        )
    )
    identity = {
        "X-Tenant-ID": "ci-tenant",
        "X-Principal-ID": "ci-principal",
        "X-Correlation-ID": "ci-postgres-integration",
    }
    payload = {
        "schema_version": "v1",
        "title": "PostgreSQL integration",
        "objective": "Verify durable control-plane transport and repository behavior",
        "audience": "CI verifier",
        "platforms": ["x"],
        "budget_cents": 0,
        "source_asset": "sandbox://fixtures/integration.png",
        "campaign_goal": "validation",
    }
    with TestClient(application) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        mission_response = client.post(
            "/api/v1/missions",
            json=payload,
            headers={**identity, "Idempotency-Key": "ci-postgres-mission"},
        )
        assert mission_response.status_code == 201, mission_response.text
        mission = mission_response.json()
        run_response = client.post(
            f"/api/v1/missions/{mission['mission_id']}/runs",
            json={"schema_version": "v1"},
            headers={**identity, "Idempotency-Key": "ci-postgres-run"},
        )
        assert run_response.status_code == 201, run_response.text
        run = run_response.json()
        assert run["status"] == "awaiting_greenlight"
        assert run["external_side_effects"] is False
        fetched = client.get(f"/api/v1/runs/{run['run_id']}", headers=identity)
        assert fetched.status_code == 200
        assert fetched.json()["artifact_manifest_hash"] == run["artifact_manifest_hash"]
    application.state.engine.dispose()
    print("postgres_integration=PASS")


if __name__ == "__main__":
    main()
