import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agency_runtime.api import create_app, run
from agency_runtime.auth import AuthConfigurationError, TenantAuthenticator


VIEWER_KEY = "viewer-tenant-alpha-key-material-2026"
OPERATOR_OLD_KEY = "operator-old-tenant-alpha-key-2026"
OPERATOR_NEW_KEY = "operator-new-tenant-alpha-key-2026"
APPROVER_KEY = "approver-tenant-alpha-key-2026"
ADMIN_KEY = "admin-tenant-alpha-key-material-2026"
INACTIVE_KEY = "inactive-tenant-alpha-key-2026"
INVALID_KEY = "invalid-authentication-key-material-2026"

BRIEF = {
    "title": "Role-governed campaign",
    "objective": "Verify individual identity and least-privilege execution",
    "audience": "governed operators",
    "platforms": ["x", "instagram"],
    "budget_cents": 0,
    "campaign_goal": "authorization_verification",
}


def identity(
    subject_id,
    role,
    key_id,
    api_key,
    *,
    active=True,
    tenant_id="tenant-alpha",
):
    return {
        "tenant_id": tenant_id,
        "subject_id": subject_id,
        "role": role,
        "key_id": key_id,
        "api_key": api_key,
        "active": active,
    }


def auth(api_key):
    return {"Authorization": "Bearer {}".format(api_key)}


IDENTITIES = [
    identity("viewer@example.com", "viewer", "viewer-v1", VIEWER_KEY),
    identity("operator@example.com", "operator", "operator-v1", OPERATOR_OLD_KEY),
    identity("operator@example.com", "operator", "operator-v2", OPERATOR_NEW_KEY),
    identity("approver@example.com", "approver", "approver-v1", APPROVER_KEY),
    identity("admin@example.com", "admin", "admin-v1", ADMIN_KEY),
    identity("inactive@example.com", "viewer", "inactive-v1", INACTIVE_KEY, active=False),
]


class IndividualIdentityAndRbacTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"
        self.static_dir = Path(self.temp.name) / "missing"

    def tearDown(self):
        self.temp.cleanup()

    def client(
        self,
        identities=None,
        *,
        max_failures=5,
        source_max_failures=50,
        window_seconds=300,
    ):
        return TestClient(
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys={},
                identity_credentials=IDENTITIES if identities is None else identities,
                session_cookie_secure=False,
                session_ttl_seconds=600,
                login_max_failures=max_failures,
                login_source_max_failures=source_max_failures,
                login_window_seconds=window_seconds,
            )
        )

    def test_roles_enforce_least_privilege_and_audit_subjects(self):
        with self.client() as client:
            viewer = client.get("/api/v1/me", headers=auth(VIEWER_KEY))
            self.assertEqual(viewer.status_code, 200)
            self.assertEqual(viewer.json()["subject_id"], "viewer@example.com")
            self.assertEqual(viewer.json()["role"], "viewer")
            self.assertEqual(viewer.json()["key_id"], "viewer-v1")
            self.assertNotIn("runs:create", viewer.json()["permissions"])
            self.assertEqual(
                client.post("/api/v1/runs", json=BRIEF, headers=auth(VIEWER_KEY)).status_code,
                403,
            )
            self.assertEqual(
                client.get("/api/v1/audit-events", headers=auth(VIEWER_KEY)).status_code,
                200,
            )

            created = client.post(
                "/api/v1/runs", json=BRIEF, headers=auth(OPERATOR_OLD_KEY)
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]
            self.assertEqual(
                client.post(
                    "/api/v1/runs/{}/greenlight/approve".format(run_id),
                    json={"reviewer": "operator", "note": "must not approve"},
                    headers=auth(OPERATOR_OLD_KEY),
                ).status_code,
                403,
            )

            self.assertEqual(
                client.post("/api/v1/runs", json=dict(BRIEF, title="approver"), headers=auth(APPROVER_KEY)).status_code,
                403,
            )
            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={"reviewer": "approver@example.com", "note": "least privilege"},
                headers=auth(APPROVER_KEY),
            )
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.json()["status"], "completed")

            audit = client.get("/api/v1/audit-events", headers=auth(VIEWER_KEY))
            self.assertEqual(audit.status_code, 200)
            actors = [item["actor"] for item in audit.json()["events"]]
            self.assertEqual(
                actors,
                ["api-key:operator@example.com", "api-key:approver@example.com"],
            )
            self.assertNotIn(OPERATOR_OLD_KEY, audit.text)
            self.assertNotIn(APPROVER_KEY, audit.text)

    def test_browser_session_inherits_role_and_enforces_permissions(self):
        with self.client() as client:
            opened = client.post("/api/v1/sessions", json={"api_key": VIEWER_KEY})
            self.assertEqual(opened.status_code, 201)
            self.assertEqual(opened.json()["subject_id"], "viewer@example.com")
            self.assertEqual(opened.json()["role"], "viewer")
            self.assertEqual(opened.json()["key_id"], "viewer-v1")
            csrf = opened.json()["csrf_token"]

            me = client.get("/api/v1/me")
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["auth_method"], "session")
            self.assertEqual(me.json()["role"], "viewer")
            denied = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertIn("runs:create", denied.json()["detail"])
            self.assertEqual(client.get("/api/v1/audit-events").status_code, 200)

    def test_overlapping_rotation_and_inactive_key_revoke_existing_session(self):
        with self.client() as client:
            old_identity = client.get("/api/v1/me", headers=auth(OPERATOR_OLD_KEY))
            new_identity = client.get("/api/v1/me", headers=auth(OPERATOR_NEW_KEY))
            self.assertEqual(old_identity.status_code, 200)
            self.assertEqual(new_identity.status_code, 200)
            self.assertEqual(
                old_identity.json()["subject_id"], new_identity.json()["subject_id"]
            )
            self.assertNotEqual(old_identity.json()["key_id"], new_identity.json()["key_id"])
            self.assertEqual(
                client.get("/api/v1/me", headers=auth(INACTIVE_KEY)).status_code, 401
            )

            opened = client.post(
                "/api/v1/sessions", json={"api_key": OPERATOR_OLD_KEY}
            )
            self.assertEqual(opened.status_code, 201)
            session_cookie = client.cookies.get("agency_session")
            self.assertIsNotNone(session_cookie)

        rotated = [
            identity(
                "operator@example.com",
                "operator",
                "operator-v1",
                OPERATOR_OLD_KEY,
                active=False,
            ),
            identity(
                "operator@example.com",
                "operator",
                "operator-v2",
                OPERATOR_NEW_KEY,
            ),
        ]
        with self.client(rotated) as restarted:
            restarted.cookies.set("agency_session", session_cookie)
            revoked = restarted.get("/api/v1/me")
            self.assertEqual(revoked.status_code, 401)
            self.assertEqual(
                revoked.json()["detail"], "session credential is no longer active"
            )
            current = restarted.get("/api/v1/me", headers=auth(OPERATOR_NEW_KEY))
            self.assertEqual(current.status_code, 200)
            self.assertEqual(current.json()["key_id"], "operator-v2")

    def test_role_downgrade_applies_to_an_existing_session(self):
        with self.client(
            [
                identity(
                    "admin@example.com",
                    "admin",
                    "admin-v1",
                    ADMIN_KEY,
                )
            ]
        ) as client:
            opened = client.post(
                "/api/v1/sessions", json={"api_key": ADMIN_KEY}
            )
            self.assertEqual(opened.status_code, 201)
            session_cookie = client.cookies.get("agency_session")
            csrf = opened.json()["csrf_token"]

        with self.client(
            [
                identity(
                    "admin@example.com",
                    "viewer",
                    "admin-v1",
                    ADMIN_KEY,
                )
            ]
        ) as restarted:
            restarted.cookies.set("agency_session", session_cookie)
            current = restarted.get("/api/v1/me")
            self.assertEqual(current.status_code, 200)
            self.assertEqual(current.json()["role"], "viewer")
            denied = restarted.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(denied.status_code, 403)

    def test_legacy_truncated_session_fingerprint_survives_schema_migration(self):
        legacy_keys = {"tenant-alpha": ADMIN_KEY}
        with TestClient(
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys=legacy_keys,
                session_cookie_secure=False,
                session_ttl_seconds=600,
            )
        ) as client:
            opened = client.post(
                "/api/v1/sessions", json={"api_key": ADMIN_KEY}
            )
            self.assertEqual(opened.status_code, 201)
            session_cookie = client.cookies.get("agency_session")

        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                UPDATE runtime_sessions
                SET credential_fingerprint = substr(credential_fingerprint, 1, 16),
                    subject_id = '',
                    key_id = ''
                """
            )

        with TestClient(
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys=legacy_keys,
                session_cookie_secure=False,
                session_ttl_seconds=600,
            )
        ) as restarted:
            restarted.cookies.set("agency_session", session_cookie)
            current = restarted.get("/api/v1/me")
            self.assertEqual(current.status_code, 200)
            self.assertEqual(current.json()["tenant_id"], "tenant-alpha")
            self.assertEqual(current.json()["subject_id"], "tenant:tenant-alpha")
            self.assertEqual(current.json()["role"], "admin")
            self.assertEqual(current.json()["key_id"], "legacy:tenant-alpha")

    def test_rate_limit_is_hashed_durable_and_visible_in_metrics(self):
        with self.client(max_failures=2, window_seconds=60) as client:
            first = client.post("/api/v1/sessions", json={"api_key": INVALID_KEY})
            second = client.post("/api/v1/sessions", json={"api_key": INVALID_KEY})
            limited = client.post("/api/v1/sessions", json={"api_key": INVALID_KEY})
            self.assertEqual(first.status_code, 401)
            self.assertEqual(second.status_code, 401)
            self.assertEqual(limited.status_code, 429)
            self.assertGreaterEqual(int(limited.headers["Retry-After"]), 1)
            metrics = client.get("/metrics").text
            self.assertIn(
                'agency_authentication_attempts_total{outcome="failed"} 2', metrics
            )
            self.assertIn(
                'agency_authentication_attempts_total{outcome="rate_limited"} 1',
                metrics,
            )

        raw = self.database.read_bytes()
        self.assertNotIn(INVALID_KEY.encode("utf-8"), raw)
        self.assertNotIn(b"testclient", raw)
        with self.client(max_failures=2, window_seconds=60) as restarted:
            still_limited = restarted.post(
                "/api/v1/sessions", json={"api_key": INVALID_KEY}
            )
            self.assertEqual(still_limited.status_code, 429)
            valid_same_source = restarted.get(
                "/api/v1/me", headers=auth(ADMIN_KEY)
            )
            self.assertEqual(valid_same_source.status_code, 200)

        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(
                "SELECT bucket_hash FROM authentication_failures"
            ).fetchall()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(len(item[0]) == 64 for item in rows))

    def test_source_bucket_limits_password_spray_across_distinct_keys(self):
        with self.client(
            max_failures=2, source_max_failures=3, window_seconds=60
        ) as client:
            for index in range(3):
                response = client.post(
                    "/api/v1/sessions",
                    json={"api_key": "distinct-invalid-key-material-2026-{}".format(index)},
                )
                self.assertEqual(response.status_code, 401)
            limited = client.post(
                "/api/v1/sessions",
                json={"api_key": "distinct-invalid-key-material-2026-final"},
            )
            self.assertEqual(limited.status_code, 429)

    def test_server_trusts_only_configured_forwarding_proxies(self):
        with patch.dict(
            os.environ,
            {
                "AGENCY_HOST": "127.0.0.1",
                "PORT": "19090",
                "FORWARDED_ALLOW_IPS": "10.0.0.0/8,192.0.2.10",
            },
            clear=False,
        ), patch("uvicorn.run") as uvicorn_run:
            run()
        uvicorn_run.assert_called_once_with(
            "agency_runtime.api:app",
            host="127.0.0.1",
            port=19090,
            proxy_headers=True,
            forwarded_allow_ips="10.0.0.0/8,192.0.2.10",
        )

    def test_identity_configuration_rejects_unsafe_or_ambiguous_records(self):
        with self.assertRaises(AuthConfigurationError):
            TenantAuthenticator(
                identity_credentials=[
                    identity("bad role", "owner", "key-v1", VIEWER_KEY)
                ]
            )
        with self.assertRaises(AuthConfigurationError):
            TenantAuthenticator(
                identity_credentials=[
                    identity("one@example.com", "viewer", "shared", VIEWER_KEY),
                    identity("two@example.com", "viewer", "shared", OPERATOR_OLD_KEY),
                ]
            )
        with self.assertRaises(AuthConfigurationError):
            TenantAuthenticator(
                identity_credentials=[
                    identity("one@example.com", "viewer", "one", VIEWER_KEY),
                    identity("two@example.com", "viewer", "two", VIEWER_KEY),
                ]
            )


if __name__ == "__main__":
    unittest.main()
