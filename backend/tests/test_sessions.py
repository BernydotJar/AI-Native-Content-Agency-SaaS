import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


API_KEY = "tenant-browser-session-key-2026-secure"
BRIEF = {
    "title": "Browser session launch",
    "objective": "Verify cookie authentication without browser key persistence",
    "audience": "production operators",
    "platforms": ["x", "instagram"],
    "budget_cents": 0,
    "campaign_goal": "verification",
}


class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"
        self.static_dir = Path(self.temp.name) / "missing"
        self.keys = {"browser-tenant": API_KEY}

    def tearDown(self):
        self.temp.cleanup()

    def client(self, secure=False):
        return TestClient(
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys=self.keys,
                session_cookie_secure=secure,
                session_ttl_seconds=600,
            )
        )

    def test_http_only_session_requires_csrf_and_survives_restart(self):
        with self.client() as client:
            created = client.post(
                "/api/v1/sessions",
                json={"api_key": API_KEY},
                headers={"X-Request-ID": "session-create-0001"},
            )
            self.assertEqual(created.status_code, 201)
            session = created.json()
            csrf_token = session["csrf_token"]
            cookie_value = client.cookies.get("agency_session")
            self.assertIsNotNone(cookie_value)
            set_cookie = created.headers["set-cookie"].lower()
            self.assertIn("httponly", set_cookie)
            self.assertIn("samesite=strict", set_cookie)
            self.assertNotIn("secure", set_cookie)
            self.assertNotIn(API_KEY, created.text)
            self.assertNotIn(cookie_value, created.text)

            me = client.get("/api/v1/me")
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["tenant_id"], "browser-tenant")
            self.assertEqual(me.json()["subject_id"], "tenant:browser-tenant")
            self.assertEqual(me.json()["role"], "admin")
            self.assertEqual(me.json()["key_id"], "legacy:browser-tenant")
            self.assertEqual(me.json()["auth_method"], "session")
            self.assertIn("greenlight:decide", me.json()["permissions"])
            resumed = client.get("/api/v1/sessions/current")
            self.assertEqual(resumed.status_code, 200)
            rotated_csrf = resumed.json()["csrf_token"]
            self.assertNotEqual(rotated_csrf, csrf_token)

            no_csrf = client.post("/api/v1/runs", json=BRIEF)
            self.assertEqual(no_csrf.status_code, 403)
            wrong_csrf = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={"X-CSRF-Token": "wrong-csrf-token-value"},
            )
            self.assertEqual(wrong_csrf.status_code, 403)
            accepted = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={
                    "X-CSRF-Token": rotated_csrf,
                    "X-Request-ID": "session-run-0001",
                    "Idempotency-Key": "session-run-command-0001",
                },
            )
            self.assertEqual(accepted.status_code, 201)
            self.assertEqual(accepted.json()["tenant_id"], "browser-tenant")

            audit = client.get("/api/v1/audit-events")
            self.assertEqual(audit.status_code, 200)
            self.assertEqual(
                [item["action"] for item in audit.json()["events"]],
                [
                    "session.created",
                    "request.verification_denied",
                    "request.verification_denied",
                    "run.created",
                ],
            )

        database_bytes = self.database.read_bytes()
        self.assertNotIn(API_KEY.encode("utf-8"), database_bytes)
        self.assertNotIn(cookie_value.encode("utf-8"), database_bytes)
        self.assertNotIn(csrf_token.encode("utf-8"), database_bytes)

        with self.client() as restarted:
            restarted.cookies.set("agency_session", cookie_value)
            restored = restarted.get("/api/v1/me")
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()["auth_method"], "session")
            resumed_after_restart = restarted.get("/api/v1/sessions/current")
            self.assertEqual(resumed_after_restart.status_code, 200)
            restart_csrf = resumed_after_restart.json()["csrf_token"]

            revoked = restarted.delete(
                "/api/v1/sessions/current",
                headers={
                    "X-CSRF-Token": restart_csrf,
                    "X-Request-ID": "session-revoke-0001",
                },
            )
            self.assertEqual(revoked.status_code, 200)
            self.assertEqual(revoked.json(), {"status": "revoked"})
            self.assertEqual(restarted.get("/api/v1/me").status_code, 401)

            bearer_audit = restarted.get(
                "/api/v1/audit-events",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            )
            self.assertEqual(
                [item["action"] for item in bearer_audit.json()["events"]],
                [
                    "session.created",
                    "request.verification_denied",
                    "request.verification_denied",
                    "run.created",
                    "session.revoked",
                ],
            )
            metrics = restarted.get("/metrics").text
            self.assertIn(
                'agency_browser_sessions_total{action="revoked"} 1', metrics
            )

    def test_production_cookie_is_secure_and_bearer_cannot_revoke_browser_session(self):
        with self.client(secure=True) as client:
            created = client.post(
                "/api/v1/sessions", json={"api_key": API_KEY}
            )
            self.assertEqual(created.status_code, 201)
            self.assertIn("secure", created.headers["set-cookie"].lower())
            self.assertEqual(client.get("/api/v1/me").status_code, 401)

            bearer_revoke = client.delete(
                "/api/v1/sessions/current",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            )
            self.assertEqual(bearer_revoke.status_code, 400)


if __name__ == "__main__":
    unittest.main()
