"""Exercise the real HTTP/repository path against a migrated PostgreSQL database."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from control_plane.api import create_app
from control_plane.settings import Settings
from control_plane.storage import AuditEventRow, IdempotencyRow, RunRow, ToolEvidenceRow


def main() -> None:
    database_url = os.environ.get("AGENCY_DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit(
            "AGENCY_DATABASE_URL must select the isolated PostgreSQL test database"
        )
    settings = Settings(
        environment="test",
        auth_mode="development_headers",
        database_url=database_url,
        auto_create_schema=False,
        cors_origins=("http://localhost:8080",),
    )
    application = create_app(settings)
    namespace = uuid4().hex
    tenant_id = f"ci-tenant-{namespace}"
    principal_id = f"ci-principal-{namespace}"
    other_tenant_id = f"ci-tenant-other-{namespace}"
    other_principal_id = f"ci-principal-other-{namespace}"
    identity = {
        "X-Tenant-ID": tenant_id,
        "X-Principal-ID": principal_id,
        "X-Correlation-ID": f"ci-postgres-integration-{namespace}",
    }
    other_identity = {
        "X-Tenant-ID": other_tenant_id,
        "X-Principal-ID": other_principal_id,
        "X-Correlation-ID": f"ci-postgres-cross-tenant-{namespace}",
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
        identity_response = client.get("/api/v1/identity", headers=identity)
        assert identity_response.status_code == 200, identity_response.text
        assert identity_response.json()["tenant"]["tenant_id"] == tenant_id
        assert identity_response.json()["principal"]["principal_id"] == principal_id
        mission_response = client.post(
            "/api/v1/missions",
            json=payload,
            headers={
                **identity,
                "Idempotency-Key": f"ci-postgres-mission-{namespace}",
            },
        )
        assert mission_response.status_code == 201, mission_response.text
        mission = mission_response.json()
        start_barrier = Barrier(2)

        def start_run() -> tuple[int, dict]:
            start_barrier.wait(timeout=10)
            response = client.post(
                f"/api/v1/missions/{mission['mission_id']}/runs",
                json={"schema_version": "v1"},
                headers={
                    **identity,
                    "Idempotency-Key": f"ci-postgres-run-{namespace}",
                },
            )
            return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            run_results = list(executor.map(lambda _: start_run(), range(2)))
        assert [status for status, _ in run_results] == [201, 201], run_results
        assert run_results[0][1] == run_results[1][1]
        run = run_results[0][1]
        assert run["status"] == "awaiting_greenlight"
        assert run["external_side_effects"] is False
        with application.state.session_factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(RunRow)
                    .where(
                        RunRow.tenant_id == tenant_id,
                        RunRow.mission_id == mission["mission_id"],
                    )
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(IdempotencyRow)
                    .where(
                        IdempotencyRow.tenant_id == tenant_id,
                        IdempotencyRow.idempotency_key
                        == f"ci-postgres-run-{namespace}",
                    )
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEventRow)
                    .where(
                        AuditEventRow.tenant_id == tenant_id,
                        AuditEventRow.run_id == run["run_id"],
                        AuditEventRow.action == "run.started",
                    )
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ToolEvidenceRow)
                    .where(
                        ToolEvidenceRow.tenant_id == tenant_id,
                        ToolEvidenceRow.run_id == run["run_id"],
                    )
                )
                == 7
            )
        fetched = client.get(f"/api/v1/runs/{run['run_id']}", headers=identity)
        assert fetched.status_code == 200
        assert fetched.json()["artifact_manifest_hash"] == run["artifact_manifest_hash"]
        cross_tenant_read = client.get(
            f"/api/v1/runs/{run['run_id']}",
            headers=other_identity,
        )
        assert cross_tenant_read.status_code == 404, cross_tenant_read.text
        assert cross_tenant_read.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        cross_tenant_approval = client.post(
            f"/api/v1/runs/{run['run_id']}/approvals",
            json={
                "schema_version": "v1",
                "decision": "approved",
                "reviewer": other_principal_id,
                "note": "This tenant must not reach the target run.",
                "artifact_manifest_hash": run["artifact_manifest_hash"],
                "policy_version": "greenlight.v1",
            },
            headers={
                **other_identity,
                "Idempotency-Key": f"ci-postgres-cross-tenant-approval-{namespace}",
            },
        )
        assert cross_tenant_approval.status_code == 404, cross_tenant_approval.text
        assert cross_tenant_approval.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        approval_response = client.post(
            f"/api/v1/runs/{run['run_id']}/approvals",
            json={
                "schema_version": "v1",
                "decision": "approved",
                "reviewer": principal_id,
                "note": "PostgreSQL integration sandbox package.",
                "artifact_manifest_hash": run["artifact_manifest_hash"],
                "policy_version": "greenlight.v1",
            },
            headers={
                **identity,
                "Idempotency-Key": f"ci-postgres-approval-{namespace}",
            },
        )
        assert approval_response.status_code == 200, approval_response.text
        completed = approval_response.json()
        assert completed["status"] == "completed"
        assert (
            completed["approval"]["idempotency_key"]
            == f"ci-postgres-approval-{namespace}"
        )
        assert len(completed["artifacts"]) == 8
        assert len(completed["evidence"]) == 8
        assert completed["external_side_effects"] is False
    application.state.engine.dispose()

    # Rebuild the application and connection pool to prove that the response is
    # reconstructed from PostgreSQL rather than retained process state.
    restarted_application = create_app(settings)
    with TestClient(restarted_application) as restarted_client:
        restarted = restarted_client.get(
            f"/api/v1/runs/{run['run_id']}", headers=identity
        )
        assert restarted.status_code == 200, restarted.text
        assert restarted.json() == completed
        restarted_cross_tenant = restarted_client.get(
            f"/api/v1/runs/{run['run_id']}", headers=other_identity
        )
        assert restarted_cross_tenant.status_code == 404, restarted_cross_tenant.text
    restarted_application.state.engine.dispose()
    print("postgres_integration=PASS")


if __name__ == "__main__":
    main()
