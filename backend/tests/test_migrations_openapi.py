from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from control_plane.openapi import canonical_openapi


def alembic_config(database: Path) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", "sqlite+pysqlite:///{}".format(database))
    return config


@pytest.fixture
def engine_factory() -> Iterator[Callable[[str], Engine]]:
    engines = []

    def build(url: str) -> Engine:
        engine = create_engine(url)
        engines.append(engine)
        return engine

    yield build
    for engine in engines:
        engine.dispose()


def test_migration_upgrade_downgrade_and_reupgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_factory: Callable[[str], Engine],
) -> None:
    monkeypatch.delenv("AGENCY_DATABASE_URL", raising=False)
    database = tmp_path / "migration.sqlite3"
    config = alembic_config(database)
    command.upgrade(config, "head")
    engine = engine_factory("sqlite+pysqlite:///{}".format(database))
    expected = {
        "alembic_version",
        "tenants",
        "principals",
        "missions",
        "runs",
        "run_steps",
        "artifacts",
        "tool_evidence",
        "run_events",
        "approvals",
        "audit_events",
        "idempotency_records",
    }
    assert expected == set(inspect(engine).get_table_names())
    inspector = inspect(engine)
    assert ("mission_id", "tenant_id") in {
        tuple(item["constrained_columns"]) for item in inspector.get_foreign_keys("runs")
    }
    for table in (
        "run_steps",
        "artifacts",
        "tool_evidence",
        "run_events",
        "approvals",
        "audit_events",
    ):
        assert ("run_id", "tenant_id") in {
            tuple(item["constrained_columns"]) for item in inspector.get_foreign_keys(table)
        }
    assert ("tenant_id", "principal_id") in {
        tuple(item["constrained_columns"]) for item in inspector.get_foreign_keys("approvals")
    }
    approval_columns = {column["name"]: column for column in inspector.get_columns("approvals")}
    assert approval_columns["idempotency_key"]["nullable"] is False
    assert ("tenant_id", "idempotency_key") in {
        tuple(item["column_names"]) for item in inspector.get_unique_constraints("approvals")
    }
    assert ("tenant_id",) in {
        tuple(item["constrained_columns"])
        for item in inspector.get_foreign_keys("idempotency_records")
    }
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert expected == set(inspect(engine).get_table_names())


def test_migration_honors_injected_sqlalchemy_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_factory: Callable[[str], Engine],
) -> None:
    monkeypatch.delenv("AGENCY_DATABASE_URL", raising=False)
    database = tmp_path / "injected-connection.sqlite3"
    engine = engine_factory("sqlite+pysqlite:///{}".format(database))
    config = alembic_config(database)
    config.set_main_option("sqlalchemy.url", "invalid-dialect://must-not-be-used")

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    assert "runs" in inspect(engine).get_table_names()


def test_approval_idempotency_key_is_backfilled_from_revision_0002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_factory: Callable[[str], Engine],
) -> None:
    monkeypatch.delenv("AGENCY_DATABASE_URL", raising=False)
    database = tmp_path / "approval-idempotency-backfill.sqlite3"
    config = alembic_config(database)
    command.upgrade(config, "0002_tenant_integrity")
    engine = engine_factory("sqlite+pysqlite:///{}".format(database))
    metadata = sa.MetaData()
    metadata.reflect(bind=engine)
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tenants"].insert(),
            {"tenant_id": "tenant-legacy", "created_at": now},
        )
        connection.execute(
            metadata.tables["principals"].insert(),
            {
                "tenant_id": "tenant-legacy",
                "principal_id": "principal-legacy",
                "auth_mode": "development_headers",
                "created_at": now,
            },
        )
        connection.execute(
            metadata.tables["missions"].insert(),
            {
                "mission_id": "mission-legacy",
                "tenant_id": "tenant-legacy",
                "created_by": "principal-legacy",
                "schema_version": "v1",
                "title": "Legacy approval",
                "objective": "Prove a safe approval-key migration",
                "audience": "migration verifier",
                "platforms": ["x"],
                "budget_cents": 0,
                "source_asset": "sandbox://fixtures/legacy.png",
                "campaign_goal": "validation",
                "created_at": now,
                "version": 1,
            },
        )
        connection.execute(
            metadata.tables["runs"].insert(),
            {
                "run_id": "run-legacy",
                "mission_id": "mission-legacy",
                "tenant_id": "tenant-legacy",
                "schema_version": "v1",
                "status": "completed",
                "artifact_manifest_hash": "a" * 64,
                "policy_version": "greenlight.v1",
                "external_side_effects": False,
                "started_at": now,
                "completed_at": now,
                "version": 2,
            },
        )
        connection.execute(
            metadata.tables["approvals"].insert(),
            {
                "approval_id": "approval-legacy",
                "run_id": "run-legacy",
                "tenant_id": "tenant-legacy",
                "principal_id": "principal-legacy",
                "decision": "approved",
                "reviewer": "legacy reviewer",
                "note": "Migrated safely",
                "artifact_manifest_hash": "a" * 64,
                "policy_version": "greenlight.v1",
                "decided_at": now,
            },
        )
        connection.execute(
            metadata.tables["idempotency_records"].insert(),
            {
                "record_id": "idempotency-legacy",
                "tenant_id": "tenant-legacy",
                "idempotency_key": "legacy-approval-key",
                "operation": "run.approval",
                "request_hash": "b" * 64,
                "status_code": 200,
                "response_payload": {
                    "schema_version": "v1",
                    "run_id": "run-legacy",
                },
                "created_at": now,
            },
        )

    command.upgrade(config, "head")
    migrated = sa.MetaData()
    migrated.reflect(bind=engine)
    with engine.connect() as connection:
        approval = connection.execute(
            sa.select(migrated.tables["approvals"].c.idempotency_key)
        ).scalar_one()
    assert approval == "legacy-approval-key"


def test_approval_idempotency_migration_fails_closed_without_durable_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    engine_factory: Callable[[str], Engine],
) -> None:
    monkeypatch.delenv("AGENCY_DATABASE_URL", raising=False)
    database = tmp_path / "approval-idempotency-orphan.sqlite3"
    config = alembic_config(database)
    command.upgrade(config, "0002_tenant_integrity")
    engine = engine_factory("sqlite+pysqlite:///{}".format(database))
    metadata = sa.MetaData()
    metadata.reflect(bind=engine)
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        connection.execute(
            metadata.tables["tenants"].insert(),
            {"tenant_id": "tenant-orphan", "created_at": now},
        )
        connection.execute(
            metadata.tables["principals"].insert(),
            {
                "tenant_id": "tenant-orphan",
                "principal_id": "principal-orphan",
                "auth_mode": "development_headers",
                "created_at": now,
            },
        )
        connection.execute(
            metadata.tables["missions"].insert(),
            {
                "mission_id": "mission-orphan",
                "tenant_id": "tenant-orphan",
                "created_by": "principal-orphan",
                "schema_version": "v1",
                "title": "Orphan approval",
                "objective": "Prove the migration fails closed",
                "audience": "migration verifier",
                "platforms": ["x"],
                "budget_cents": 0,
                "source_asset": "sandbox://fixtures/orphan.png",
                "campaign_goal": "validation",
                "created_at": now,
                "version": 1,
            },
        )
        connection.execute(
            metadata.tables["runs"].insert(),
            {
                "run_id": "run-orphan",
                "mission_id": "mission-orphan",
                "tenant_id": "tenant-orphan",
                "schema_version": "v1",
                "status": "completed",
                "artifact_manifest_hash": "c" * 64,
                "policy_version": "greenlight.v1",
                "external_side_effects": False,
                "started_at": now,
                "completed_at": now,
                "version": 2,
            },
        )
        connection.execute(
            metadata.tables["approvals"].insert(),
            {
                "approval_id": "approval-orphan",
                "run_id": "run-orphan",
                "tenant_id": "tenant-orphan",
                "principal_id": "principal-orphan",
                "decision": "approved",
                "reviewer": "orphan reviewer",
                "note": "No matching idempotency record",
                "artifact_manifest_hash": "c" * 64,
                "policy_version": "greenlight.v1",
                "decided_at": now,
            },
        )

    with pytest.raises(RuntimeError, match="no durable idempotency record"):
        command.upgrade(config, "head")


def test_openapi_document_is_deterministic_and_versioned() -> None:
    first = canonical_openapi()
    second = canonical_openapi()
    assert first == second
    document = json.loads(first)
    assert document["info"]["version"] == "1.0.0"
    assert document["components"]["schemas"]["MissionCreate"]["additionalProperties"] is False
    assert set(document["paths"]) >= {
        "/healthz",
        "/readyz",
        "/api/v1/identity",
        "/api/v1/missions",
        "/api/v1/missions/{mission_id}/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/approvals",
    }
    assert document["components"]["schemas"]["IdentityResponse"]["additionalProperties"] is False
    assert (
        document["components"]["schemas"]["TenantIdentityResponse"]["properties"]["schema_version"][
            "const"
        ]
        == "v1"
    )
    assert (
        document["components"]["schemas"]["PrincipalIdentityResponse"]["properties"][
            "schema_version"
        ]["const"]
        == "v1"
    )
    assert "idempotency_key" in document["components"]["schemas"]["ApprovalResponse"]["required"]
    snapshot = Path(__file__).resolve().parents[1] / "openapi.json"
    assert snapshot.read_text(encoding="utf-8") == first
