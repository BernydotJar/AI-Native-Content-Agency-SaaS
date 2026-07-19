"""Run the checked Alembic revisions through the passwordless Cloud SQL connector."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> None:
    connection_name = _required("AGENCY_CLOUD_SQL_CONNECTION_NAME")
    database_name = _required("AGENCY_CLOUD_SQL_DATABASE")
    database_user = _required("AGENCY_CLOUD_SQL_IAM_USER")
    alembic_ini = Path(os.environ.get("AGENCY_ALEMBIC_INI", "/app/backend/alembic.ini"))
    if not alembic_ini.is_file():
        raise SystemExit("Alembic configuration is unavailable")

    connector = Connector(refresh_strategy="LAZY")

    def connect() -> object:
        return connector.connect(
            connection_name,
            "pg8000",
            user=database_user,
            db=database_name,
            enable_iam_auth=True,
            ip_type=IPTypes.PUBLIC,
        )

    engine = create_engine(
        "postgresql+pg8000://",
        creator=connect,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(782347192345)")
            configuration = Config(str(alembic_ini))
            configuration.attributes["connection"] = connection
            command.upgrade(configuration, "head")
    finally:
        engine.dispose()
        connector.close()


if __name__ == "__main__":
    main()
