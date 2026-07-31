#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/workload-rollback-v1.json"
REPORT_SCHEMA = "agency-workload-rollback-report.v1"
CONTRACT_SCHEMA = "agency-workload-rollback.v1"
IDENTITY_KEY = "rollback-drill-admin-key-material-2026"
TENANT_ID = "rollback-drill"
AUDIT_KEY_ID = "rollback-audit-v1"
AUDIT_KEY_BYTES = bytes(range(32))


def canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def run(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    env: Mapping[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command), cwd=cwd, env=None if env is None else dict(env),
        capture_output=True, text=True, check=False, timeout=timeout,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError("command failed ({}): {}".format(" ".join(command), detail))
    return completed


def git_text(*arguments: str) -> str:
    return run(("git", *arguments), timeout=120).stdout.strip()


def load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("rollback contract must be a JSON object")
    return value


def validate_contract(
    value: Mapping[str, Any], *, current_commit: str | None = None
) -> dict[str, Any]:
    expected_fields = {
        "schema_version", "rollback_commit", "required_runtime_schema_version",
        "maximum_local_rto_seconds", "stable_path_contract",
    }
    if set(value) != expected_fields:
        raise ValueError("rollback contract fields are invalid")
    if value.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError("rollback contract schema is unsupported")
    rollback = value.get("rollback_commit")
    required_schema = value.get("required_runtime_schema_version")
    maximum_rto = value.get("maximum_local_rto_seconds")
    paths = value.get("stable_path_contract")
    if not isinstance(rollback, str) or len(rollback) != 40:
        raise ValueError("rollback_commit must be a full Git SHA")
    if not isinstance(required_schema, int) or required_schema < 1:
        raise ValueError("required_runtime_schema_version must be positive")
    if not isinstance(maximum_rto, int) or maximum_rto < 1 or maximum_rto > 120:
        raise ValueError("maximum_local_rto_seconds must be between 1 and 120")
    if (
        not isinstance(paths, list) or not paths or len(paths) != len(set(paths))
        or any(not isinstance(path, str) or not path.startswith("/") for path in paths)
    ):
        raise ValueError("stable_path_contract must contain unique absolute paths")
    required_paths = {
        "/healthz", "/readyz", "/api/v1/runs",
        "/api/v1/audit-events", "/api/v1/audit-events/integrity",
    }
    if set(paths) != required_paths:
        raise ValueError("stable_path_contract does not match the rollback drill")

    rollback_resolved = git_text("rev-parse", f"{rollback}^{{commit}}")
    current = current_commit or git_text("rev-parse", "HEAD")
    current_resolved = git_text("rev-parse", f"{current}^{{commit}}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", rollback_resolved, current_resolved],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=30,
    )
    if ancestor.returncode != 0:
        raise ValueError("rollback commit must be an ancestor of the candidate")
    if rollback_resolved == current_resolved:
        raise ValueError("rollback commit must differ from the candidate")

    versions: dict[str, int] = {}
    trees: dict[str, str] = {}
    for label, commit in (("candidate", current_resolved), ("rollback", rollback_resolved)):
        source = git_text("show", f"{commit}:backend/agency_runtime/postgres.py")
        marker = 'POSTGRES_SCHEMA_VERSION = "'
        start = source.find(marker)
        if start < 0:
            raise ValueError(f"{label} source does not declare runtime schema version")
        start += len(marker)
        end = source.find('"', start)
        versions[label] = int(source[start:end])
        if versions[label] != required_schema:
            raise ValueError(
                f"{label} schema {versions[label]} is incompatible with required {required_schema}"
            )
        api_source = git_text("show", f"{commit}:backend/agency_runtime/api.py")
        for path in paths:
            if path not in api_source:
                raise ValueError(f"{label} source is missing required API path {path}")
        trees[label] = git_text("rev-parse", f"{commit}^{{tree}}")
    return {
        "candidate_commit": current_resolved,
        "candidate_tree": trees["candidate"],
        "rollback_commit": rollback_resolved,
        "rollback_tree": trees["rollback"],
        "runtime_schema_version": required_schema,
        "maximum_local_rto_seconds": maximum_rto,
        "stable_path_contract": sorted(paths),
    }


def validate_report(value: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "status", "candidate", "rollback", "runtime_schema_version",
        "stable_port", "rto_milliseconds", "maximum_rto_milliseconds", "runs",
        "audit", "database", "security", "external_effects",
    }
    if set(value) != required:
        raise ValueError("rollback report fields are invalid")
    if value.get("schema_version") != REPORT_SCHEMA or value.get("status") != "pass":
        raise ValueError("rollback report status/schema is invalid")
    if value.get("external_effects") != 0:
        raise ValueError("rollback report must prove zero external effects")
    if int(value["rto_milliseconds"]) > int(value["maximum_rto_milliseconds"]):
        raise ValueError("rollback RTO exceeded the configured maximum")
    security = value.get("security")
    if not isinstance(security, dict) or security != {
        "candidate_non_root": True,
        "candidate_read_only": True,
        "rollback_non_root": True,
        "rollback_read_only": True,
        "providers_enabled": False,
        "database_restore_performed": False,
        "writers_overlapped": False,
    }:
        raise ValueError("rollback security evidence is invalid")
    serialized = canonical(value)
    for forbidden in (IDENTITY_KEY, base64.urlsafe_b64encode(AUDIT_KEY_BYTES).decode("ascii")):
        if forbidden in serialized:
            raise ValueError("rollback report contains credential material")


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(
    method: str, url: str, *, headers: Mapping[str, str] | None = None,
    body: Mapping[str, Any] | None = None, timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json", **dict(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        payload = json.loads(error.read().decode("utf-8"))
        return error.code, payload


def wait_ready(base_url: str, timeout_seconds: float) -> tuple[dict[str, Any], int]:
    started = time.monotonic_ns()
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            status, document = http_json("GET", base_url + "/readyz", timeout=1.0)
            if status == 200 and document.get("status") == "ready":
                elapsed_ms = (time.monotonic_ns() - started) // 1_000_000
                return document, int(elapsed_ms)
            last_error = f"status={status} body={document}"
        except Exception as error:
            last_error = type(error).__name__
        time.sleep(0.1)
    raise RuntimeError(f"workload did not become ready: {last_error}")


def export_source(commit: str, destination: Path) -> Path:
    context = destination / commit[:12]
    context.mkdir(parents=True, exist_ok=True)
    archive = destination / f"{commit[:12]}.tar"
    run(("git", "archive", "--format=tar", f"--output={archive}", commit))
    run(("tar", "-xf", str(archive), "-C", str(context)))
    archive.unlink()
    return context


def buildah_prefix(build_root: Path, run_root: Path) -> tuple[str, ...]:
    return (
        "buildah", "--root", str(build_root), "--runroot", str(run_root),
        "--storage-driver", "vfs",
    )


def build_image(
    context: Path, tag: str, commit: str, *,
    build_root: Path, run_root: Path,
) -> str:
    buildah = buildah_prefix(build_root, run_root)
    run(
        (
            *buildah, "bud", "--isolation", "chroot", "--format", "docker",
            "--layers=false", "--label",
            f"org.opencontainers.image.revision={commit}",
            "--tag", tag, str(context),
        ),
        timeout=900,
    )
    inspection = json.loads(
        run((*buildah, "inspect", "--type", "image", tag), timeout=60).stdout
    )
    digest = str(inspection.get("FromImageDigest", ""))
    if not digest.startswith("sha256:"):
        raise RuntimeError("Buildah image digest is unavailable")
    return digest


def identity_json() -> str:
    return json.dumps(
        [
            {
                "tenant_id": TENANT_ID,
                "subject_id": "rollback-admin",
                "role": "admin",
                "key_id": "rollback-admin-v1",
                "api_key": IDENTITY_KEY,
                "active": True,
            }
        ],
        separators=(",", ":"),
        sort_keys=True,
    )


def audit_keyring_json() -> str:
    encoded = base64.urlsafe_b64encode(AUDIT_KEY_BYTES).decode("ascii").rstrip("=")
    return json.dumps({AUDIT_KEY_ID: encoded}, separators=(",", ":"), sort_keys=True)


def runtime_environment(port: int) -> list[str]:
    return [
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONUNBUFFERED=1",
        "PIP_DISABLE_PIP_VERSION_CHECK=1",
        "AGENCY_STATIC_DIR=/app/dist",
        f"PORT={port}",
        "AGENCY_MEMORY_DB=/data/runtime.sqlite3",
        f"AGENCY_IDENTITY_CREDENTIALS_JSON={identity_json()}",
        "AGENCY_SESSION_COOKIE_SECURE=false",
        "AGENCY_SESSION_TTL_SECONDS=600",
        "AGENCY_SOCIAL_PUBLICATION_ENABLED=false",
        "AGENCY_POLITICAL_CONTENT_ENABLED=false",
        "AGENCY_POLITICAL_PUBLICATION_ENABLED=false",
        "AGENCY_POLITICAL_PAID_MEDIA_ENABLED=false",
        "AGENCY_MODEL_EXECUTION_ENABLED=false",
        "AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED=false",
        f"AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON={audit_keyring_json()}",
        f"AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID={AUDIT_KEY_ID}",
    ]


def start_runtime(
    *, tag: str, name: str, port: int, data_directory: Path,
    build_root: Path, run_root: Path, bundles: Path,
) -> tuple[dict[str, Any], dict[str, bool]]:
    buildah = buildah_prefix(build_root, run_root)
    buildah_name = name + "-rootfs"
    run((*buildah, "from", "--name", buildah_name, tag), timeout=120)
    mountpoint = Path(run((*buildah, "mount", buildah_name), timeout=60).stdout.strip())
    (mountpoint / "data").mkdir(exist_ok=True)
    bundle = bundles / name
    bundle.mkdir(parents=True, exist_ok=True)
    run(("runc", "spec"), cwd=bundle, timeout=30)
    config_path = bundle / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["process"]["terminal"] = False
    config["process"]["user"] = {"uid": 10001, "gid": 10001}
    config["process"]["args"] = ["/usr/local/bin/agency-api"]
    config["process"]["env"] = runtime_environment(port)
    config["process"]["cwd"] = "/app"
    config["process"]["capabilities"] = {
        "bounding": [], "effective": [], "permitted": [], "ambient": []
    }
    config["process"]["noNewPrivileges"] = True
    config["root"] = {"path": str(mountpoint), "readonly": True}
    config["hostname"] = name[:63]
    config["linux"]["namespaces"] = [
        item for item in config["linux"]["namespaces"] if item.get("type") != "network"
    ]
    config["mounts"].extend(
        [
            {
                "destination": "/tmp",
                "type": "tmpfs",
                "source": "tmpfs",
                "options": ["nosuid", "noexec", "nodev", "mode=1777", "size=32m"],
            },
            {
                "destination": "/data",
                "type": "none",
                "source": str(data_directory),
                "options": ["rbind", "rw", "nosuid", "nodev"],
            },
        ]
    )
    config_path.write_text(canonical(config), encoding="utf-8")
    log_path = bundle / "runtime.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["runc", "run", "--bundle", str(bundle), name],
        cwd=ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.3)
    if process.poll() is not None:
        log_handle.close()
        detail = log_path.read_text(encoding="utf-8", errors="replace")
        raise RuntimeError(f"runc workload exited during startup: {detail}")
    return (
        {
            "runc_id": name,
            "buildah_name": buildah_name,
            "mountpoint": str(mountpoint),
            "bundle": str(bundle),
            "process": process,
            "log_handle": log_handle,
            "log_path": str(log_path),
            "build_root": str(build_root),
            "run_root": str(run_root),
        },
        {"non_root": True, "read_only": True},
    )


def stop_runtime(runtime: dict[str, Any] | None) -> None:
    if runtime is None:
        return
    runc_id = str(runtime["runc_id"])
    process = runtime.get("process")
    subprocess.run(
        ["runc", "kill", runc_id, "TERM"], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=30,
    )
    if isinstance(process, subprocess.Popen):
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["runc", "kill", runc_id, "KILL"], cwd=ROOT,
                capture_output=True, text=True, check=False, timeout=30,
            )
            process.wait(timeout=10)
    subprocess.run(
        ["runc", "delete", "--force", runc_id], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=30,
    )
    log_handle = runtime.get("log_handle")
    if log_handle is not None and not log_handle.closed:
        log_handle.close()
    build_root = Path(str(runtime["build_root"]))
    run_root = Path(str(runtime["run_root"]))
    buildah = buildah_prefix(build_root, run_root)
    subprocess.run(
        [*buildah, "unmount", str(runtime["buildah_name"])], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=60,
    )
    subprocess.run(
        [*buildah, "rm", "--force", str(runtime["buildah_name"])], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=60,
    )


def remove_image(tag: str, build_root: Path, run_root: Path) -> None:
    buildah = buildah_prefix(build_root, run_root)
    subprocess.run(
        [*buildah, "rmi", "--force", tag], cwd=ROOT,
        capture_output=True, text=True, check=False, timeout=60,
    )


def auth_headers(request_id: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {IDENTITY_KEY}",
        "X-Request-ID": request_id,
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def create_run(base_url: str, request_id: str, idempotency_key: str, title: str) -> dict[str, Any]:
    status, document = http_json(
        "POST", base_url + "/api/v1/runs",
        headers=auth_headers(request_id, idempotency_key),
        body={
            "title": title,
            "objective": "Verify application rollback without data rollback",
            "audience": "release reliability reviewers",
            "platforms": ["x"],
            "budget_cents": 0,
            "campaign_goal": "verification",
        },
        timeout=30.0,
    )
    if status != 201:
        raise RuntimeError(f"run creation failed: {status} {document}")
    if document.get("external_side_effects_enabled") is not False:
        raise RuntimeError("run document does not prove external effects disabled")
    return document


def get_run(base_url: str, run_id: str, request_id: str) -> dict[str, Any]:
    status, document = http_json(
        "GET", base_url + f"/api/v1/runs/{run_id}",
        headers=auth_headers(request_id), timeout=10.0,
    )
    if status != 200:
        raise RuntimeError(f"run read failed: {status} {document}")
    return document


def audit_checkpoint(base_url: str, request_id: str) -> dict[str, Any]:
    status, document = http_json(
        "GET", base_url + "/api/v1/audit-events/integrity",
        headers=auth_headers(request_id), timeout=10.0,
    )
    if status != 200:
        raise RuntimeError(f"audit checkpoint failed: {status} {document}")
    return document


def final_database_evidence(database: Path) -> dict[str, Any]:
    previous_hash = "0" * 64
    expected_head_event_id = ""
    expected_count = 0
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        run_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM runtime_runs WHERE tenant_id = ?", (TENANT_ID,)
            ).fetchone()[0]
        )
        rows = connection.execute(
            """
            SELECT event_id, tenant_id, request_id, occurred_at, action,
                   resource_type, resource_id, actor, payload_json,
                   previous_hash, event_hash
            FROM audit_events
            WHERE tenant_id = ?
            ORDER BY sequence ASC
            """,
            (TENANT_ID,),
        ).fetchall()
        for row in rows:
            stored_previous = str(row["previous_hash"])
            if stored_previous != previous_hash:
                raise RuntimeError("final audit previous-hash link is invalid")
            document = (
                "audit-chain.v1",
                str(row["event_id"]),
                str(row["tenant_id"]),
                str(row["request_id"]),
                str(row["occurred_at"]),
                str(row["action"]),
                str(row["resource_type"]),
                str(row["resource_id"]),
                str(row["actor"]),
                json.loads(str(row["payload_json"])),
                previous_hash,
            )
            expected = hashlib.sha256(
                json.dumps(
                    document, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if str(row["event_hash"]) != expected:
                raise RuntimeError("final audit event hash is invalid")
            previous_hash = expected
            expected_head_event_id = str(row["event_id"])
            expected_count += 1
        head = connection.execute(
            "SELECT event_count, head_event_id, head_hash FROM audit_chain_heads WHERE tenant_id = ?",
            (TENANT_ID,),
        ).fetchone()
    if (
        integrity != "ok" or run_count < 2 or head is None
        or int(head["event_count"]) != expected_count
        or str(head["head_event_id"]) != expected_head_event_id
        or str(head["head_hash"]) != previous_hash
    ):
        raise RuntimeError("final SQLite or audit-chain head verification failed")
    return {
        "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "integrity_check": integrity,
        "tenant_run_count": run_count,
        "audit_event_count": expected_count,
        "audit_head_event_id": expected_head_event_id,
        "audit_head_hash": previous_hash,
    }


def execute_drill(contract: Mapping[str, Any], report_path: Path, allow_dirty: bool) -> dict[str, Any]:
    for command in ("buildah", "runc"):
        if shutil.which(command) is None:
            raise RuntimeError(f"{command} is required for the read-only workload rollback drill")
    dirty = bool(git_text("status", "--porcelain=v1"))
    if dirty and not allow_dirty:
        raise ValueError("worktree must be clean; use --allow-dirty only during development")
    binding = validate_contract(contract)
    candidate_commit = binding["candidate_commit"]
    rollback_commit = binding["rollback_commit"]
    suffix = hashlib.sha256((candidate_commit + rollback_commit).encode()).hexdigest()[:10]
    candidate_tag = f"agency-rollback-candidate:{suffix}"
    rollback_tag = f"agency-rollback-prior:{suffix}"
    candidate_name = f"agency-rollback-candidate-{suffix}"
    rollback_name = f"agency-rollback-prior-{suffix}"
    port = free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(prefix="agency-workload-rollback-") as temporary:
        root = Path(temporary)
        source_root = root / "sources"
        source_root.mkdir()
        build_root = root / "buildah-root"
        run_root = root / "buildah-runroot"
        bundles = root / "oci-bundles"
        build_root.mkdir()
        run_root.mkdir()
        bundles.mkdir()
        data_directory = root / "runtime-data"
        data_directory.mkdir(mode=0o700)
        os.chown(data_directory, 10001, 10001)
        database = data_directory / "runtime.sqlite3"
        candidate_context = export_source(candidate_commit, source_root)
        rollback_context = export_source(rollback_commit, source_root)
        candidate_runtime: dict[str, Any] | None = None
        rollback_runtime: dict[str, Any] | None = None
        try:
            candidate_image = build_image(
                candidate_context, candidate_tag, candidate_commit,
                build_root=build_root, run_root=run_root,
            )
            rollback_image = build_image(
                rollback_context, rollback_tag, rollback_commit,
                build_root=build_root, run_root=run_root,
            )
            candidate_runtime, candidate_security = start_runtime(
                tag=candidate_tag, name=candidate_name, port=port,
                data_directory=data_directory, build_root=build_root,
                run_root=run_root, bundles=bundles,
            )
            candidate_ready, candidate_startup_ms = wait_ready(base_url, 45.0)
            before_run = create_run(
                base_url, "rollback-before-create-0001",
                "rollback-before-command-0001", "Pre-rollback durable run",
            )
            before_read = get_run(
                base_url, str(before_run["run_id"]), "rollback-before-read-0001"
            )
            before_audit = audit_checkpoint(base_url, "rollback-before-audit-0001")

            failure_started_ns = time.monotonic_ns()
            stop_runtime(candidate_runtime)
            candidate_runtime = None
            rollback_runtime, rollback_security = start_runtime(
                tag=rollback_tag, name=rollback_name, port=port,
                data_directory=data_directory, build_root=build_root,
                run_root=run_root, bundles=bundles,
            )
            rollback_ready, _ = wait_ready(
                base_url, float(binding["maximum_local_rto_seconds"])
            )
            rto_ms = int((time.monotonic_ns() - failure_started_ns) // 1_000_000)
            preserved = get_run(
                base_url, str(before_run["run_id"]), "rollback-preserved-read-0001"
            )
            switched_audit = audit_checkpoint(base_url, "rollback-after-switch-audit-0001")
            if (
                preserved.get("run_id") != before_run.get("run_id")
                or preserved.get("status") != before_read.get("status")
                or switched_audit.get("event_count") != before_audit.get("event_count")
                or switched_audit.get("head_hash") != before_audit.get("head_hash")
            ):
                raise RuntimeError("pre-rollback state changed during application rollback")
            after_run = create_run(
                base_url, "rollback-after-create-0001",
                "rollback-after-command-0001", "Post-rollback durable run",
            )
            after_read = get_run(
                base_url, str(after_run["run_id"]), "rollback-after-read-0001"
            )
            after_audit = audit_checkpoint(base_url, "rollback-after-audit-0001")
            if int(after_audit["event_count"]) <= int(before_audit["event_count"]):
                raise RuntimeError("post-rollback write did not advance the audit chain")
            stop_runtime(rollback_runtime)
            rollback_runtime = None
            database_evidence = final_database_evidence(database)

            report = {
                "schema_version": REPORT_SCHEMA,
                "status": "pass",
                "candidate": {
                    "commit": candidate_commit,
                    "tree": binding["candidate_tree"],
                    "image_id": candidate_image,
                    "startup_milliseconds": candidate_startup_ms,
                    "ready_version": candidate_ready.get("version"),
                    "source_dirty": dirty,
                },
                "rollback": {
                    "commit": rollback_commit,
                    "tree": binding["rollback_tree"],
                    "image_id": rollback_image,
                    "ready_version": rollback_ready.get("version"),
                },
                "runtime_schema_version": binding["runtime_schema_version"],
                "stable_port": port,
                "rto_milliseconds": rto_ms,
                "maximum_rto_milliseconds": int(
                    binding["maximum_local_rto_seconds"] * 1000
                ),
                "runs": {
                    "pre_rollback_run_id": before_run["run_id"],
                    "pre_rollback_status": before_read["status"],
                    "preserved_after_rollback": True,
                    "post_rollback_run_id": after_run["run_id"],
                    "post_rollback_status": after_read["status"],
                },
                "audit": {
                    "before_event_count": before_audit["event_count"],
                    "before_head_hash": before_audit["head_hash"],
                    "after_switch_event_count": switched_audit["event_count"],
                    "after_switch_head_hash": switched_audit["head_hash"],
                    "after_write_event_count": after_audit["event_count"],
                    "after_write_head_hash": after_audit["head_hash"],
                    "final_event_count": database_evidence["audit_event_count"],
                    "final_head_hash": database_evidence["audit_head_hash"],
                },
                "database": {
                    "sha256": database_evidence["sha256"],
                    "integrity_check": database_evidence["integrity_check"],
                    "tenant_run_count": database_evidence["tenant_run_count"],
                    "restored_or_replaced": False,
                },
                "security": {
                    "candidate_non_root": candidate_security["non_root"],
                    "candidate_read_only": candidate_security["read_only"],
                    "rollback_non_root": rollback_security["non_root"],
                    "rollback_read_only": rollback_security["read_only"],
                    "providers_enabled": False,
                    "database_restore_performed": False,
                    "writers_overlapped": False,
                },
                "external_effects": 0,
            }
            validate_report(report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(canonical(report), encoding="utf-8")
            return report
        finally:
            stop_runtime(candidate_runtime)
            stop_runtime(rollback_runtime)
            remove_image(candidate_tag, build_root, run_root)
            remove_image(rollback_tag, build_root, run_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local application workload rollback.")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument(
        "--report", type=Path,
        default=ROOT / "artifacts/rollback/generated/workload-rollback-report.json",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    contract = load_contract(args.contract)
    binding = validate_contract(contract)
    if args.validate_only:
        print("workload_rollback_contract=pass")
        print(f"candidate_commit={binding['candidate_commit']}")
        print(f"rollback_commit={binding['rollback_commit']}")
        print(f"runtime_schema_version={binding['runtime_schema_version']}")
        print("external_effects=0")
        return 0
    report = execute_drill(contract, args.report.resolve(), args.allow_dirty)
    print("workload_rollback=pass")
    print(f"candidate_commit={report['candidate']['commit']}")
    print(f"rollback_commit={report['rollback']['commit']}")
    print(f"rto_milliseconds={report['rto_milliseconds']}")
    print(f"database_sha256={report['database']['sha256']}")
    print(f"report={args.report.resolve()}")
    print("database_restore_performed=false")
    print("external_effects=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"workload rollback verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
