"""Hardened container entrypoint for the combined SPA and control plane."""

from __future__ import annotations

import os

import uvicorn


def _port() -> int:
    raw_port = os.environ.get("PORT", "8080")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise SystemExit("PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")
    return port


def main() -> None:
    os.environ.setdefault("AGENCY_WEB_DIST", "/app/static")
    if os.environ.get("AGENCY_RUN_MIGRATIONS_ON_START", "false").lower() == "true":
        from run_cloud_migrations import main as run_cloud_migrations

        run_cloud_migrations()
    uvicorn.run(
        "control_plane.api:create_app",
        factory=True,
        host="0.0.0.0",
        port=_port(),
        access_log=False,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
