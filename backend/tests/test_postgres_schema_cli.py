import contextlib
import io
import json
import os
import unittest
from unittest import mock

from agency_runtime import postgres as postgres_module
from agency_runtime import postgres_schema
from agency_runtime.api import RuntimeService


class PostgreSQLConnectionSecurityTests(unittest.TestCase):
    def test_connection_fixes_search_path_before_use(self):
        connection = mock.Mock()
        cursor = mock.Mock()
        connection.cursor.return_value = cursor
        with mock.patch.object(
            postgres_module.dbapi, "connect", return_value=connection
        ) as connect:
            observed = postgres_module._connect_database_url(
                "postgresql://runtime@db.internal/agency?sslmode=disable",
                timeout_seconds=7,
            )

        self.assertIs(observed, connection)
        connect.assert_called_once()
        cursor.execute.assert_called_once_with(
            "SET search_path TO pg_catalog, public"
        )
        cursor.close.assert_called_once_with()
        connection.commit.assert_called_once_with()
        connection.close.assert_not_called()

    def test_connection_closes_when_search_path_setup_fails(self):
        connection = mock.Mock()
        cursor = mock.Mock()
        cursor.execute.side_effect = RuntimeError("search path setup failed")
        connection.cursor.return_value = cursor
        with mock.patch.object(
            postgres_module.dbapi, "connect", return_value=connection
        ):
            with self.assertRaisesRegex(RuntimeError, "search path setup failed"):
                postgres_module._connect_database_url(
                    "postgresql://runtime@db.internal/agency?sslmode=disable",
                    timeout_seconds=7,
                )

        cursor.close.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()

    def test_connection_rejects_url_control_of_search_path(self):
        with self.assertRaisesRegex(ValueError, "unsupported PostgreSQL connection"):
            postgres_module._connection_options(
                "postgresql://runtime@db.internal/agency"
                "?sslmode=disable&search_path=attacker",
                timeout_seconds=7,
            )


class PostgreSQLSchemaCommandTests(unittest.TestCase):
    def test_success_uses_named_environment_and_closes_database(self):
        database = mock.Mock()
        old = os.environ.get("AGENCY_MIGRATION_DATABASE_URL")
        os.environ["AGENCY_MIGRATION_DATABASE_URL"] = (
            "postgresql://migrator:secret@db.internal/agency"
        )
        try:
            stdout = io.StringIO()
            with mock.patch.object(
                postgres_schema, "PostgresRuntimeDatabase", return_value=database
            ) as constructor, contextlib.redirect_stdout(stdout):
                status = postgres_schema.main(
                    [
                        "initialize",
                        "--database-url-env",
                        "AGENCY_MIGRATION_DATABASE_URL",
                    ]
                )
        finally:
            if old is None:
                os.environ.pop("AGENCY_MIGRATION_DATABASE_URL", None)
            else:
                os.environ["AGENCY_MIGRATION_DATABASE_URL"] = old

        self.assertEqual(status, 0)
        constructor.assert_called_once_with(
            "postgresql://migrator:secret@db.internal/agency",
            min_size=1,
            max_size=1,
            schema_mode="initialize",
        )
        database.close.assert_called_once_with()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["mode"], "initialize")
        self.assertEqual(payload["schema_version"], "1")
        self.assertNotIn("secret", stdout.getvalue())
        self.assertNotIn("db.internal", stdout.getvalue())

    def test_application_runtime_rejects_initialize_before_connecting(self):
        with self.assertRaisesRegex(
            ValueError, "application runtime PostgreSQL schema mode must be validate"
        ):
            RuntimeService(
                ":memory:",
                database_url="postgresql://runtime@db.internal/agency",
                postgres_schema_mode="initialize",
            )

    def test_driver_failure_never_echoes_database_secret(self):
        old = os.environ.get("SENSITIVE_DATABASE_URL")
        os.environ["SENSITIVE_DATABASE_URL"] = (
            "postgresql://operator:do-not-print@localhost/agency"
        )
        try:
            stderr = io.StringIO()
            with mock.patch.object(
                postgres_schema,
                "PostgresRuntimeDatabase",
                side_effect=RuntimeError(
                    "driver failed for postgresql://operator:do-not-print@localhost/agency"
                ),
            ), contextlib.redirect_stderr(stderr):
                status = postgres_schema.main(
                    [
                        "validate",
                        "--database-url-env",
                        "SENSITIVE_DATABASE_URL",
                    ]
                )
        finally:
            if old is None:
                os.environ.pop("SENSITIVE_DATABASE_URL", None)
            else:
                os.environ["SENSITIVE_DATABASE_URL"] = old

        self.assertEqual(status, 1)
        self.assertIn("error_type=RuntimeError", stderr.getvalue())
        self.assertNotIn("do-not-print", stderr.getvalue())
        self.assertNotIn("postgresql://", stderr.getvalue())

    def test_invalid_or_missing_environment_name_fails_closed(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            invalid = postgres_schema.main(
                ["validate", "--database-url-env", "not-valid"]
            )
        self.assertEqual(invalid, 1)
        self.assertIn("variable name is invalid", stderr.getvalue())

        old = os.environ.pop("AGENCY_UNSET_DATABASE_URL", None)
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                missing = postgres_schema.main(
                    [
                        "validate",
                        "--database-url-env",
                        "AGENCY_UNSET_DATABASE_URL",
                    ]
                )
        finally:
            if old is not None:
                os.environ["AGENCY_UNSET_DATABASE_URL"] = old
        self.assertEqual(missing, 1)
        self.assertIn("is not configured", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
