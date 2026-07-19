from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

if "uvicorn" not in sys.modules:
    try:
        __import__("uvicorn")
    except ModuleNotFoundError:
        uvicorn_stub = types.ModuleType("uvicorn")
        uvicorn_stub.run = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
        sys.modules["uvicorn"] = uvicorn_stub

from scripts.start_container import main


class StartContainerTest(unittest.TestCase):
    def test_cloud_migration_finishes_before_server_starts(self) -> None:
        calls: list[str] = []
        migration_module = types.ModuleType("run_cloud_migrations")
        migration_module.main = lambda: calls.append("migration")  # type: ignore[attr-defined]

        with (
            patch.dict(os.environ, {"AGENCY_RUN_MIGRATIONS_ON_START": "true", "PORT": "8080"}),
            patch.dict(sys.modules, {"run_cloud_migrations": migration_module}),
            patch(
                "scripts.start_container.uvicorn.run",
                side_effect=lambda *_args, **_kwargs: calls.append("server"),
            ),
        ):
            main()

        self.assertEqual(calls, ["migration", "server"])

    def test_local_container_skips_cloud_migration(self) -> None:
        calls: list[str] = []
        with (
            patch.dict(os.environ, {"AGENCY_RUN_MIGRATIONS_ON_START": "false", "PORT": "8080"}),
            patch(
                "scripts.start_container.uvicorn.run",
                side_effect=lambda *_args, **_kwargs: calls.append("server"),
            ),
        ):
            main()

        self.assertEqual(calls, ["server"])

    def test_failed_cloud_migration_prevents_server_start(self) -> None:
        migration_module = types.ModuleType("run_cloud_migrations")

        def migration_failure() -> None:
            raise RuntimeError("migration failed")

        migration_module.main = migration_failure  # type: ignore[attr-defined]
        with (
            patch.dict(
                os.environ,
                {"AGENCY_RUN_MIGRATIONS_ON_START": "true", "PORT": "8080"},
            ),
            patch.dict(sys.modules, {"run_cloud_migrations": migration_module}),
            patch("scripts.start_container.uvicorn.run") as server,
        ):
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                main()

        server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
