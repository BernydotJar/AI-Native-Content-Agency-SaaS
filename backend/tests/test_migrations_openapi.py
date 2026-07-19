from __future__ import annotations

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from control_plane.openapi import canonical_openapi


def alembic_config(database: Path) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", "sqlite+pysqlite:///{}".format(database))
    return config


def test_migration_upgrade_downgrade_and_reupgrade(tmp_path: Path) -> None:
    database = tmp_path / "migration.sqlite3"
    config = alembic_config(database)
    command.upgrade(config, "head")
    engine = create_engine("sqlite+pysqlite:///{}".format(database))
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
        tuple(item["constrained_columns"])
        for item in inspector.get_foreign_keys("runs")
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
            tuple(item["constrained_columns"])
            for item in inspector.get_foreign_keys(table)
        }
    assert ("tenant_id", "principal_id") in {
        tuple(item["constrained_columns"])
        for item in inspector.get_foreign_keys("approvals")
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


def test_migration_honors_injected_sqlalchemy_connection(tmp_path: Path) -> None:
    database = tmp_path / "injected-connection.sqlite3"
    engine = create_engine("sqlite+pysqlite:///{}".format(database))
    config = alembic_config(database)
    config.set_main_option("sqlalchemy.url", "invalid-dialect://must-not-be-used")

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    assert "runs" in inspect(engine).get_table_names()


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
        "/api/v1/missions",
        "/api/v1/missions/{mission_id}/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/approvals",
    }
    snapshot = Path(__file__).resolve().parents[1] / "openapi.json"
    assert snapshot.read_text(encoding="utf-8") == first
