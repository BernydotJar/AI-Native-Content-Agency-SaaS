from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app
from agency_runtime.persistence import (
    AuthenticatedRequestRateLimitError,
    SQLiteRunStore,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 30, 7, 0, tzinfo=timezone.utc)

    def __call__(self) -> str:
        return self.value.isoformat()

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class SQLiteAuthenticatedRequestQuotaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.clock = MutableClock()
        self.store = SQLiteRunStore(self.path, clock=self.clock)

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_fixed_window_rejects_after_limit_and_resets(self) -> None:
        buckets = (("a" * 64, 2), ("b" * 64, 20))
        self.store.consume_authenticated_request_quota(buckets, 60)
        self.store.consume_authenticated_request_quota(buckets, 60)
        with self.assertRaises(AuthenticatedRequestRateLimitError) as raised:
            self.store.consume_authenticated_request_quota(buckets, 60)
        self.assertGreaterEqual(raised.exception.retry_after_seconds, 1)
        self.assertEqual(self.store.authenticated_request_quota_count("a" * 64), 2)
        self.assertEqual(self.store.authenticated_request_quota_count("b" * 64), 2)

        self.clock.advance(61)
        self.store.consume_authenticated_request_quota(buckets, 60)
        self.assertEqual(self.store.authenticated_request_quota_count("a" * 64), 1)
        self.assertEqual(self.store.authenticated_request_quota_count("b" * 64), 1)

    def test_multi_bucket_rejection_is_atomic(self) -> None:
        principal = "c" * 64
        tenant = "d" * 64
        self.store.consume_authenticated_request_quota(
            ((principal, 10), (tenant, 1)), 60
        )
        with self.assertRaises(AuthenticatedRequestRateLimitError):
            self.store.consume_authenticated_request_quota(
                ((principal, 10), (tenant, 1)), 60
            )
        self.assertEqual(self.store.authenticated_request_quota_count(principal), 1)
        self.assertEqual(self.store.authenticated_request_quota_count(tenant), 1)

    def test_storage_contains_only_bucket_hashes(self) -> None:
        principal = "e" * 64
        tenant = "f" * 64
        self.store.consume_authenticated_request_quota(
            ((principal, 10), (tenant, 100)), 60
        )
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT bucket_hash, window_started_at, request_count "
                "FROM authenticated_request_rate_limits ORDER BY bucket_hash"
            ).fetchall()
        self.assertEqual([row[0] for row in rows], [principal, tenant])
        self.assertEqual([row[2] for row in rows], [1, 1])
        serialized = repr(rows)
        self.assertNotIn("tenant-alpha", serialized)
        self.assertNotIn("viewer@example.com", serialized)

    def test_invalid_bucket_contract_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.store.consume_authenticated_request_quota((), 60)
        with self.assertRaisesRegex(ValueError, "unique"):
            self.store.consume_authenticated_request_quota(
                (("a" * 64, 10), ("a" * 64, 20)), 60
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            self.store.consume_authenticated_request_quota((("a" * 64, 0),), 60)
        with self.assertRaisesRegex(ValueError, "window"):
            self.store.consume_authenticated_request_quota((("a" * 64, 1),), 0)


VIEWER_KEY = "quota-viewer-key-material-2026"
SECOND_VIEWER_KEY = "quota-second-viewer-key-material-2026"
IDENTITIES = [
    {
        "tenant_id": "tenant-alpha",
        "subject_id": "viewer@example.com",
        "role": "viewer",
        "key_id": "viewer-v1",
        "api_key": VIEWER_KEY,
        "active": True,
    },
    {
        "tenant_id": "tenant-alpha",
        "subject_id": "second@example.com",
        "role": "viewer",
        "key_id": "second-v1",
        "api_key": SECOND_VIEWER_KEY,
        "active": True,
    },
]
BRIEF = {
    "title": "Quota denial",
    "objective": "Bound denial audit amplification",
    "audience": "security reviewers",
    "platforms": ["x"],
    "budget_cents": 0,
    "campaign_goal": "quota_verification",
}


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


class AuthenticatedRequestQuotaApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "api.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def client(self, *, principal_limit: int = 10, tenant_limit: int = 20) -> TestClient:
        return TestClient(
            create_app(
                database_path=str(self.path),
                static_dir=Path(self.temp.name) / "missing",
                tenant_api_keys={},
                identity_credentials=IDENTITIES,
                session_cookie_secure=False,
                session_ttl_seconds=600,
                authenticated_request_max_per_principal=principal_limit,
                authenticated_request_max_per_tenant=tenant_limit,
                authenticated_request_window_seconds=60,
            )
        )

    def test_rate_limit_prevents_denial_audit_amplification(self) -> None:
        with self.client() as client:
            for index in range(10):
                response = client.post(
                    "/api/v1/runs",
                    json=dict(BRIEF, title=f"Denied {index}"),
                    headers=bearer(VIEWER_KEY),
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["code"], "authorization_denied")

            limited = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Must not audit"),
                headers=bearer(VIEWER_KEY),
            )
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(limited.json()["code"], "request_rate_limited")
            self.assertGreaterEqual(int(limited.headers["Retry-After"]), 1)

            metrics = client.get("/metrics").text
            self.assertIn(
                'agency_authenticated_request_quota_total{outcome="allowed"} 10',
                metrics,
            )
            self.assertIn(
                'agency_authenticated_request_quota_total{outcome="rate_limited"} 1',
                metrics,
            )

        with sqlite3.connect(self.path) as connection:
            denial_count = connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE action = 'authorization.denied'"
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT bucket_hash, request_count FROM authenticated_request_rate_limits"
            ).fetchall()
        self.assertEqual(denial_count, 10)
        self.assertEqual(sorted(row[1] for row in rows), [10, 10])
        self.assertNotIn("tenant-alpha", repr(rows))
        self.assertNotIn("viewer@example.com", repr(rows))

    def test_bearer_and_session_share_principal_quota(self) -> None:
        with self.client() as client:
            for _ in range(10):
                self.assertEqual(
                    client.get("/api/v1/me", headers=bearer(VIEWER_KEY)).status_code,
                    200,
                )
            login = client.post(
                "/api/v1/sessions",
                json={"api_key": VIEWER_KEY, "username": "viewer@example.com"},
            )
            self.assertEqual(login.status_code, 201)
            limited = client.get("/api/v1/me")
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(limited.json()["code"], "request_rate_limited")

    def test_tenant_bucket_limits_multiple_principals(self) -> None:
        with self.client(principal_limit=10, tenant_limit=10) as client:
            for _ in range(5):
                self.assertEqual(
                    client.get("/api/v1/me", headers=bearer(VIEWER_KEY)).status_code,
                    200,
                )
                self.assertEqual(
                    client.get(
                        "/api/v1/me", headers=bearer(SECOND_VIEWER_KEY)
                    ).status_code,
                    200,
                )
            limited = client.get("/api/v1/me", headers=bearer(VIEWER_KEY))
            self.assertEqual(limited.status_code, 429)

    def test_configuration_bounds_fail_closed(self) -> None:
        common = {
            "database_path": str(self.path),
            "static_dir": Path(self.temp.name) / "missing",
            "tenant_api_keys": {},
            "identity_credentials": IDENTITIES,
            "session_cookie_secure": False,
        }
        with self.assertRaisesRegex(ValueError, "principal limit"):
            create_app(**common, authenticated_request_max_per_principal=9)
        with self.assertRaisesRegex(ValueError, "tenant limit"):
            create_app(
                **common,
                authenticated_request_max_per_principal=20,
                authenticated_request_max_per_tenant=19,
            )
        with self.assertRaisesRegex(ValueError, "request window"):
            create_app(**common, authenticated_request_window_seconds=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
