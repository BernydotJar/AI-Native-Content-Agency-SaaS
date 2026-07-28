#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BACKUP_TOOL = ROOT / "scripts" / "manage-runtime-backup.py"


def _atomic_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".{}.tmp-{}".format(path.name, os.getpid()))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def social_connection_digest(database: Path) -> str:
    if not database.is_file() or database.is_symlink():
        raise FileNotFoundError("runtime database is unavailable")
    connection = sqlite3.connect(
        "file:{}?mode=ro".format(database.resolve()), uri=True, timeout=10
    )
    try:
        columns = [
            item[1]
            for item in connection.execute("PRAGMA table_info(social_connections)")
        ]
        if not columns:
            raise RuntimeError("social_connections table is unavailable")
        rows = connection.execute(
            "SELECT {} FROM social_connections ORDER BY tenant_id, channel_id".format(
                ", ".join('"{}"'.format(column) for column in columns)
            )
        ).fetchall()
    finally:
        connection.close()
    document = {"columns": columns, "rows": [list(row) for row in rows]}
    encoded = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _create_backup(database: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(output_dir, 0o700)
    completed = subprocess.run(
        [
            sys.executable,
            str(BACKUP_TOOL),
            "sqlite-backup",
            "--database",
            str(database),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError("social connection backup failed")
    try:
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        manifest = Path(result["manifest"])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("social connection backup returned invalid evidence") from error
    if result.get("status") != "created" or not manifest.is_file():
        raise RuntimeError("social connection backup evidence is unavailable")
    return manifest


def snapshot_if_changed(
    database: Path,
    output_dir: Path,
    state_file: Path,
    manifest_file: Path,
) -> str:
    digest = social_connection_digest(database)
    previous = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else ""
    if previous == digest:
        return "unchanged"
    manifest = _create_backup(database, output_dir)
    _atomic_private_text(manifest_file, str(manifest.resolve()) + "\n")
    _atomic_private_text(state_file, digest + "\n")
    return "created"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Back up SQLite only when encrypted social connection state changes."
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--manifest-file", required=True, type=Path)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.poll_seconds < 1 or arguments.poll_seconds > 3600:
        raise SystemExit("poll seconds must be between 1 and 3600")
    while True:
        try:
            result = snapshot_if_changed(
                arguments.database,
                arguments.output_dir,
                arguments.state_file,
                arguments.manifest_file,
            )
            print("social_connection_backup={}".format(result), flush=True)
        except (FileNotFoundError, RuntimeError, sqlite3.Error) as error:
            print(
                "social_connection_backup=failed reason={}".format(type(error).__name__),
                file=sys.stderr,
                flush=True,
            )
            if arguments.once:
                return 1
        if arguments.once:
            return 0
        time.sleep(arguments.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
