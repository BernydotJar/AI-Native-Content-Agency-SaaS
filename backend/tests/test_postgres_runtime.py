import os
import time
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from agency_runtime.api import create_app
from agency_runtime.models import Provenance
from agency_runtime.postgres import (
    PostgresMemory,
    PostgresRuntimeDatabase,
    _connect_database_url,
)


DATABASE_URL = os.environ.get("AGENCY_TEST_DATABASE_URL", "")
MIGRATION_DATABASE_URL = os.environ.get(
    "AGENCY_TEST_MIGRATION_DATABASE_URL", DATABASE_URL
)


@contextmanager
def raw_connection(database_url=DATABASE_URL):
    connection = _connect_database_url(database_url, timeout_seconds=10)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


BRIEF = {
    "title": "Shared PostgreSQL campaign",
    "objective": "Verify shared multi-replica runtime state",
    "audience": "platform engineers",
    "platforms": ["x", "instagram"],
    "budget_cents": 0,
    "campaign_goal": "verification",
}


def auth(api_key, idempotency_key=None):
    result = {"Authorization": "Bearer {}".format(api_key)}
    if idempotency_key is not None:
        result["Idempotency-Key"] = idempotency_key
    return result


def identity(tenant_id, subject_id, role, key_id, api_key, active=True):
    return {
        "tenant_id": tenant_id,
        "subject_id": subject_id,
        "role": role,
        "key_id": key_id,
        "api_key": api_key,
        "active": active,
    }


@unittest.skipUnless(DATABASE_URL, "AGENCY_TEST_DATABASE_URL is not configured")
class PostgresSharedRuntimeTests(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.tenant = "pg-tenant-{}".format(suffix)
        self.viewer_key = "pg-viewer-key-material-{}-2026".format(suffix)
        self.operator_key = "pg-operator-key-material-{}-2026".format(suffix)
        self.approver_key = "pg-approver-key-material-{}-2026".format(suffix)
        self.rotated_key = "pg-rotated-key-material-{}-2026".format(suffix)
        self.invalid_key = "pg-invalid-key-material-{}-2026".format(suffix)
        self.identities = [
            identity(
                self.tenant,
                "viewer-{}".format(suffix),
                "viewer",
                "viewer-v1",
                self.viewer_key,
            ),
            identity(
                self.tenant,
                "operator-{}".format(suffix),
                "operator",
                "operator-v1",
                self.operator_key,
            ),
            identity(
                self.tenant,
                "approver-{}".format(suffix),
                "approver",
                "approver-v1",
                self.approver_key,
            ),
        ]

    def app(
        self, identities=None, *, max_failures=5, source_max_failures=50,
        worker_poll_interval=0.35,
    ):
        return create_app(
            database_path=":memory:",
            database_url=DATABASE_URL,
            static_dir=Path("/definitely/missing"),
            identity_credentials=self.identities if identities is None else identities,
            session_cookie_secure=False,
            session_ttl_seconds=600,
            login_max_failures=max_failures,
            login_source_max_failures=source_max_failures,
            login_window_seconds=60,
            postgres_pool_min_size=1,
            postgres_pool_max_size=3,
            postgres_connect_timeout_seconds=10,
            run_worker_poll_interval_seconds=worker_poll_interval,
        )

    def test_connection_settings_and_schema_version_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "connect timeout"):
            PostgresRuntimeDatabase(
                DATABASE_URL,
                min_size=1,
                max_size=2,
                connect_timeout_seconds=0,
            )

        separator = "&" if "?" in DATABASE_URL else "?"
        with self.assertRaisesRegex(ValueError, "unsupported PostgreSQL connection"):
            PostgresRuntimeDatabase(
                DATABASE_URL + separator + "target_session_attrs=read-write",
                min_size=1,
                max_size=2,
            )

        pool_database = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=1, connect_timeout_seconds=1
        )
        try:
            with pool_database.pool.connection():
                started = time.monotonic()
                with self.assertRaisesRegex(TimeoutError, "checkout timed out"):
                    with pool_database.pool.connection():
                        pass
                self.assertGreaterEqual(time.monotonic() - started, 0.8)
        finally:
            pool_database.close()

        validated = PostgresRuntimeDatabase(
            DATABASE_URL,
            min_size=1,
            max_size=2,
            schema_mode="validate",
        )
        validated.close()
        with raw_connection(MIGRATION_DATABASE_URL) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE runtime_schema_meta SET value = '999' WHERE key = 'schema_version'"
            )
        try:
            with self.assertRaisesRegex(
                RuntimeError, "unsupported PostgreSQL runtime schema version: 999"
            ):
                PostgresRuntimeDatabase(DATABASE_URL, min_size=1, max_size=2)
            with raw_connection(MIGRATION_DATABASE_URL) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT value FROM runtime_schema_meta WHERE key = 'schema_version'"
                )
                row = cursor.fetchone()
            self.assertEqual(row[0], "999")
        finally:
            with raw_connection(MIGRATION_DATABASE_URL) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "UPDATE runtime_schema_meta SET value = '6' WHERE key = 'schema_version'"
                )

    def test_two_instances_share_run_audit_and_greenlight_state(self):
        with TestClient(self.app()) as first, TestClient(self.app()) as second:
            ready = first.get("/readyz")
            self.assertEqual(ready.status_code, 200)
            self.assertEqual(ready.json()["storage_backend"], "postgresql")
            self.assertTrue(ready.json()["shared_state"])
            self.assertTrue(ready.json()["durable_run_store"])

            created = first.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=auth(self.operator_key, "postgres-create-shared-0001"),
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]

            restored = second.get(
                "/api/v1/runs/{}".format(run_id), headers=auth(self.viewer_key)
            )
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()["status"], "awaiting_greenlight")

            approved = second.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={"reviewer": "approver", "note": "shared state verified"},
                headers=auth(self.approver_key, "postgres-approve-shared-0001"),
            )
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.json()["status"], "completed")

            observed = first.get(
                "/api/v1/runs/{}".format(run_id), headers=auth(self.viewer_key)
            )
            self.assertEqual(observed.status_code, 200)
            self.assertEqual(observed.json()["status"], "completed")

            events = first.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            self.assertEqual(
                [event["action"] for event in events],
                ["run.created", "greenlight.approved"],
            )

    def test_compatible_create_replay_is_serialized_across_replicas(self):
        first = TestClient(self.app())
        second = TestClient(self.app())
        key = "postgres-compatible-create-{}".format(self.tenant)
        with first, second:
            def create(client):
                return client.post(
                    "/api/v1/runs",
                    json=dict(BRIEF, title="Compatible {}".format(self.tenant)),
                    headers=auth(self.operator_key, key),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = [
                    future.result()
                    for future in (
                        executor.submit(create, first),
                        executor.submit(create, second),
                    )
                ]
            self.assertEqual(sorted(response.status_code for response in responses), [200, 201])
            replay = next(response for response in responses if response.status_code == 200)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertEqual(responses[0].json(), responses[1].json())
            run_id = responses[0].json()["run_id"]
            events = first.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            created = [
                event
                for event in events
                if event["action"] == "run.created" and event["resource_id"] == run_id
            ]
            self.assertEqual(len(created), 1)
            self.assertNotIn(key, repr(created))

        with raw_connection(MIGRATION_DATABASE_URL) as connection:
            rows = connection.cursor()
            rows.execute(
                "SELECT event_id, payload_json::text FROM audit_events WHERE tenant_id = %s",
                (self.tenant,),
            )
            serialized = repr(rows.fetchall())
        self.assertNotIn(key, serialized)

    def test_same_resource_with_distinct_keys_creates_once_and_reuses_across_replicas(self):
        first = TestClient(self.app())
        second = TestClient(self.app())
        brief = dict(BRIEF, title="Resource replay {}".format(self.tenant))
        with first, second:
            def create(client, key):
                return client.post(
                    "/api/v1/runs",
                    json=brief,
                    headers=auth(self.operator_key, key),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = [
                    future.result()
                    for future in (
                        executor.submit(create, first, "postgres-resource-a-{}".format(self.tenant)),
                        executor.submit(create, second, "postgres-resource-b-{}".format(self.tenant)),
                    )
                ]
            self.assertEqual(sorted(response.status_code for response in responses), [200, 201])
            self.assertEqual(responses[0].json(), responses[1].json())
            replay = next(response for response in responses if response.status_code == 200)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            run_id = responses[0].json()["run_id"]
            events = first.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            actions = [
                event["action"]
                for event in events
                if event["resource_id"] == run_id
            ]
            self.assertEqual(sorted(actions), ["run.created", "run.reused"])

    def test_incompatible_create_reuse_yields_one_uniform_conflict(self):
        first = TestClient(self.app())
        second = TestClient(self.app())
        key = "postgres-incompatible-create-{}".format(self.tenant)
        with first, second:
            briefs = [
                dict(BRIEF, title="Incompatible A {}".format(self.tenant)),
                dict(BRIEF, title="Incompatible B {}".format(self.tenant)),
            ]

            def create(client, brief):
                return client.post(
                    "/api/v1/runs",
                    json=brief,
                    headers=auth(self.operator_key, key),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = [
                    future.result()
                    for future in (
                        executor.submit(create, first, briefs[0]),
                        executor.submit(create, second, briefs[1]),
                    )
                ]
            self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
            conflict = next(response for response in responses if response.status_code == 409)
            self.assertEqual(conflict.json()["code"], "idempotency_conflict")
            self.assertNotIn(key, conflict.text)

    def test_compatible_greenlight_replay_packages_once_across_replicas(self):
        first = TestClient(self.app())
        second = TestClient(self.app())
        with first, second:
            created = first.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Compatible decision {}".format(self.tenant)),
                headers=auth(self.operator_key, "postgres-compatible-run-{}".format(self.tenant)),
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]
            decision = {"reviewer": "approver", "note": "same decision"}
            key = "postgres-compatible-approve-{}".format(self.tenant)

            def approve(client):
                return client.post(
                    "/api/v1/runs/{}/greenlight/approve".format(run_id),
                    json=decision,
                    headers=auth(self.approver_key, key),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = [
                    future.result()
                    for future in (
                        executor.submit(approve, first),
                        executor.submit(approve, second),
                    )
                ]
            self.assertEqual([response.status_code for response in responses], [200, 200])
            self.assertEqual(responses[0].json(), responses[1].json())
            packages = [
                artifact
                for artifact in responses[0].json()["artifacts"]
                if artifact["kind"] == "campaign_package"
            ]
            self.assertEqual(len(packages), 1)
            events = first.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            decisions = [
                event
                for event in events
                if event["action"] == "greenlight.approved"
                and event["resource_id"] == run_id
            ]
            self.assertEqual(len(decisions), 1)

    def test_authorization_denial_is_shared_and_public_error_is_uniform(self):
        with TestClient(self.app()) as first, TestClient(self.app()) as second:
            request_id = "postgres-authz-denial-{}".format(self.tenant)
            denied = first.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Denied {}".format(self.tenant)),
                headers={
                    **auth(self.viewer_key),
                    "X-Request-ID": request_id,
                },
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(
                denied.json(),
                {
                    "code": "authorization_denied",
                    "detail": "request not permitted",
                    "request_id": request_id,
                },
            )
            self.assertNotIn("viewer", denied.text)
            self.assertNotIn("runs:create", denied.text)

            events = second.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            denial = next(
                event for event in events if event["request_id"] == request_id
            )
            self.assertEqual(denial["action"], "authorization.denied")
            self.assertEqual(denial["tenant_id"], self.tenant)
            self.assertEqual(
                denial["payload"],
                {
                    "auth_method": "bearer",
                    "reason": "authorization",
                    "role": "viewer",
                },
            )
            serialized = repr(denial)
            self.assertNotIn(self.viewer_key, serialized)
            self.assertNotIn(self.operator_key, serialized)

    def test_second_replica_cannot_overwrite_greenlight_decision(self):
        first = TestClient(self.app())
        second = TestClient(self.app())
        with first, second:
            created = first.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Concurrent Greenlight {}".format(self.tenant)),
                headers=auth(self.operator_key, "postgres-create-concurrent-0001"),
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]

            def decide(client, action):
                return client.post(
                    "/api/v1/runs/{}/greenlight/{}".format(run_id, action),
                    json={"reviewer": action, "note": "concurrent decision"},
                    headers=auth(
                        self.approver_key,
                        "postgres-greenlight-{}-0001".format(action),
                    ),
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(decide, first, "approve"),
                    executor.submit(decide, second, "reject"),
                ]
                responses = [future.result() for future in futures]
            self.assertEqual(sorted(response.status_code for response in responses), [200, 409])

            final = first.get(
                "/api/v1/runs/{}".format(run_id), headers=auth(self.viewer_key)
            )
            self.assertIn(final.json()["status"], {"completed", "rejected"})
            events = first.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            decisions = [
                event for event in events if event["action"].startswith("greenlight.")
            ]
            self.assertEqual(len(decisions), 1)

    def test_two_workers_checkpoint_one_async_run_without_duplicate_artifacts(self):
        first_app = self.app(worker_poll_interval=60)
        second_app = self.app(worker_poll_interval=60)
        first = TestClient(first_app)
        second = TestClient(second_app)
        with first, second:
            created = first.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Async workers {}".format(self.tenant)),
                headers={
                    **auth(
                        self.operator_key,
                        "postgres-async-workers-{}".format(self.tenant),
                    ),
                    "Prefer": "respond-async",
                },
            )
            self.assertEqual(created.status_code, 202)
            run_id = created.json()["run_id"]

            def checkpoint(service, worker):
                return service.execute_one_queued_run(worker)

            with ThreadPoolExecutor(max_workers=2) as executor:
                progressed = [
                    future.result()
                    for future in (
                        executor.submit(
                            checkpoint, first_app.state.runtime_service, "pg-worker-a"
                        ),
                        executor.submit(
                            checkpoint, second_app.state.runtime_service, "pg-worker-b"
                        ),
                    )
                ]
            self.assertEqual(progressed, [True, True])
            current = first.get(
                "/api/v1/runs/{}".format(run_id), headers=auth(self.viewer_key)
            ).json()
            self.assertEqual(current["status"], "running")
            self.assertEqual(current["execution"]["fencing_token"], 2)
            self.assertEqual(current["agent_states"]["ceo"]["status"], "ready")
            self.assertEqual(
                [item["kind"] for item in current["artifacts"]],
                ["mission_charter"],
            )
            self.assertEqual(current["execution"]["lease_owner"], "")

            events = first.get(
                "/api/v1/audit-events", headers=auth(self.viewer_key)
            ).json()["events"]
            checkpoints = [
                event
                for event in events
                if event["resource_id"] == run_id
                and event["action"] == "run.checkpointed"
            ]
            self.assertEqual(
                sorted(item["payload"]["fencing_token"] for item in checkpoints),
                [1, 2],
            )

    def test_session_and_rate_limit_are_shared_between_instances(self):
        with TestClient(self.app(max_failures=2)) as first, TestClient(
            self.app(max_failures=2)
        ) as second:
            issued = first.post(
                "/api/v1/sessions", json={"api_key": self.operator_key}
            )
            self.assertEqual(issued.status_code, 201)
            session_cookie = first.cookies.get("agency_session")
            self.assertTrue(session_cookie)

            second.cookies.set("agency_session", session_cookie)
            recovered = second.get("/api/v1/sessions/current")
            self.assertEqual(recovered.status_code, 200)
            self.assertEqual(recovered.json()["tenant_id"], self.tenant)

            for _ in range(2):
                self.assertEqual(
                    first.get(
                        "/api/v1/me", headers=auth(self.invalid_key)
                    ).status_code,
                    401,
                )
            limited = second.get("/api/v1/me", headers=auth(self.invalid_key))
            self.assertEqual(limited.status_code, 429)
            self.assertGreaterEqual(int(limited.headers["Retry-After"]), 1)

    def test_concurrent_invalid_credential_is_atomically_limited(self):
        first = TestClient(self.app(max_failures=1))
        second = TestClient(self.app(max_failures=1))
        with first, second:
            def attempt(client):
                return client.get(
                    "/api/v1/me", headers=auth(self.invalid_key)
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = [
                    future.result()
                    for future in (
                        executor.submit(attempt, first),
                        executor.submit(attempt, second),
                    )
                ]
            self.assertEqual(
                sorted(response.status_code for response in responses),
                [401, 429],
            )
            limited = first.get(
                "/api/v1/me", headers=auth(self.invalid_key)
            )
            self.assertEqual(limited.status_code, 429)

    def test_key_deactivation_revokes_session_across_instances(self):
        old_identity = identity(
            self.tenant,
            "rotating-subject",
            "admin",
            "admin-v1",
            self.operator_key,
        )
        new_identity = identity(
            self.tenant,
            "rotating-subject",
            "admin",
            "admin-v2",
            self.rotated_key,
        )
        with TestClient(self.app([old_identity, new_identity])) as first:
            issued = first.post(
                "/api/v1/sessions", json={"api_key": self.operator_key}
            )
            self.assertEqual(issued.status_code, 201)
            old_cookie = first.cookies.get("agency_session")

        with TestClient(self.app([new_identity])) as rotated:
            rotated.cookies.set("agency_session", old_cookie)
            self.assertEqual(rotated.get("/api/v1/me").status_code, 401)
            self.assertEqual(
                rotated.get(
                    "/api/v1/me", headers=auth(self.operator_key)
                ).status_code,
                401,
            )
            self.assertEqual(
                rotated.get(
                    "/api/v1/me", headers=auth(self.rotated_key)
                ).status_code,
                200,
            )

        database = PostgresRuntimeDatabase(DATABASE_URL, min_size=1, max_size=2)
        try:
            with database.pool.connection() as connection:
                rows = connection.execute(
                    """
                    SELECT session_token_hash, csrf_token_hash, credential_fingerprint
                    FROM runtime_sessions WHERE tenant_id = %s
                    """,
                    (self.tenant,),
                ).fetchall()
            serialized = repr(rows)
            self.assertNotIn(self.operator_key, serialized)
            self.assertNotIn(self.rotated_key, serialized)
            self.assertNotIn(old_cookie, serialized)
        finally:
            database.close()

    def test_memory_is_shared_and_tenant_partitioned(self):
        first_database = PostgresRuntimeDatabase(DATABASE_URL, min_size=1, max_size=2)
        second_database = PostgresRuntimeDatabase(DATABASE_URL, min_size=1, max_size=2)
        other_tenant = "{}-other".format(self.tenant)
        try:
            first_memory = PostgresMemory(first_database, namespace=self.tenant)
            second_memory = PostgresMemory(second_database, namespace=self.tenant)
            isolated_memory = PostgresMemory(second_database, namespace=other_tenant)
            observation = first_memory.observe(
                "PostgreSQL shared memory observation",
                Provenance(
                    source="integration-test",
                    locator="postgres://shared-memory",
                    observed_at="2026-07-21T00:00:00+00:00",
                ),
                confidence=0.95,
                tags=("postgresql", "shared-state"),
            )
            stored = first_memory.store(observation)
            self.assertEqual(second_memory.recall(stored.memory_id).content, stored.content)
            self.assertEqual(len(second_memory.search("postgresql shared-state")), 1)
            self.assertEqual(isolated_memory.count(), 0)
        finally:
            first_database.close()
            second_database.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
