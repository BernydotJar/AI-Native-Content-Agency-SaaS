import asyncio
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import PublicApiError, create_app


VIEWER_KEY = "security-viewer-tenant-alpha-key-2026"
ADMIN_KEY = "security-admin-tenant-alpha-key-2026"
BETA_KEY = "security-admin-tenant-beta-key-2026"
INVALID_KEY = "security-invalid-credential-key-2026"
BRIEF = {
    "title": "Security-governed campaign",
    "objective": "Verify safe public errors and durable denial evidence",
    "audience": "tenant security reviewers",
    "platforms": ["x", "instagram"],
    "budget_cents": 0,
    "campaign_goal": "security_verification",
}


def identity(tenant_id, subject_id, role, key_id, api_key):
    return {
        "tenant_id": tenant_id,
        "subject_id": subject_id,
        "role": role,
        "key_id": key_id,
        "api_key": api_key,
        "active": True,
    }


def auth(api_key, request_id=None, idempotency_key=None):
    headers = {"Authorization": "Bearer {}".format(api_key)}
    if request_id:
        headers["X-Request-ID"] = request_id
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def expected_error(code, detail, request_id):
    return {"code": code, "detail": detail, "request_id": request_id}


class SecurityPrivacyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"
        self.static_dir = Path(self.temp.name) / "missing"
        self.identities = [
            identity(
                "tenant-alpha",
                "viewer@example.com",
                "viewer",
                "viewer-v1",
                VIEWER_KEY,
            ),
            identity(
                "tenant-alpha",
                "admin@example.com",
                "admin",
                "admin-v1",
                ADMIN_KEY,
            ),
            identity(
                "tenant-beta",
                "beta-admin@example.com",
                "admin",
                "beta-admin-v1",
                BETA_KEY,
            ),
        ]

    def tearDown(self):
        self.temp.cleanup()

    def client(
        self, *, raise_server_exceptions=True, max_request_body_bytes=None
    ):
        return TestClient(
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys={},
                identity_credentials=self.identities,
                session_cookie_secure=False,
                session_ttl_seconds=600,
                max_request_body_bytes=max_request_body_bytes,
            ),
            raise_server_exceptions=raise_server_exceptions,
        )

    def test_public_errors_are_uniform_and_do_not_enumerate_security_state(self):
        with self.client() as client:
            invalid = client.get(
                "/api/v1/me",
                headers=auth(INVALID_KEY, "security-auth-invalid-0001"),
            )
            self.assertEqual(invalid.status_code, 401)
            self.assertEqual(
                invalid.json(),
                expected_error(
                    "authentication_failed",
                    "authentication failed",
                    "security-auth-invalid-0001",
                ),
            )
            self.assertEqual(invalid.headers["WWW-Authenticate"], "Bearer")

            missing_cookie = client.get(
                "/api/v1/me", headers={"X-Request-ID": "security-cookie-missing-0001"}
            )
            self.assertEqual(missing_cookie.status_code, 401)
            self.assertEqual(
                missing_cookie.json(),
                expected_error(
                    "authentication_failed",
                    "authentication failed",
                    "security-cookie-missing-0001",
                ),
            )

            opened = client.post(
                "/api/v1/sessions",
                json={"api_key": ADMIN_KEY},
                headers={"X-Request-ID": "security-session-open-0001"},
            )
            self.assertEqual(opened.status_code, 201)
            cookie = client.cookies.get("agency_session")
            csrf = opened.json()["csrf_token"]
            self.assertTrue(cookie)
            revoked = client.delete(
                "/api/v1/sessions/current",
                headers={
                    "X-CSRF-Token": csrf,
                    "X-Request-ID": "security-session-revoke-0001",
                },
            )
            self.assertEqual(revoked.status_code, 200)
            client.cookies.set("agency_session", cookie)
            revoked_session = client.get(
                "/api/v1/me", headers={"X-Request-ID": "security-cookie-state-0001"}
            )
            self.assertEqual(revoked_session.status_code, 401)
            self.assertEqual(revoked_session.json(), missing_cookie.json() | {
                "request_id": "security-cookie-state-0001"
            })
            self.assertNotIn("revoked", revoked_session.json()["detail"].lower())
            self.assertNotIn("active", revoked_session.json()["detail"].lower())

            denied = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=auth(VIEWER_KEY, "security-rbac-denied-0001"),
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(
                denied.json(),
                expected_error(
                    "authorization_denied",
                    "request not permitted",
                    "security-rbac-denied-0001",
                ),
            )
            for forbidden in ("viewer", "runs:create", "permission", "role"):
                self.assertNotIn(forbidden, denied.text)

            beta_command = "security-beta-create-0001"
            beta = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Beta private campaign"),
                headers=auth(BETA_KEY, idempotency_key=beta_command),
            )
            self.assertEqual(beta.status_code, 201)
            foreign_id = beta.json()["run_id"]
            foreign = client.get(
                "/api/v1/runs/{}".format(foreign_id),
                headers=auth(ADMIN_KEY, "security-resource-hidden-0001"),
            )
            missing = client.get(
                "/api/v1/runs/run-does-not-exist",
                headers=auth(ADMIN_KEY, "security-resource-hidden-0001"),
            )
            self.assertEqual(foreign.status_code, 404)
            self.assertEqual(foreign.json(), missing.json())
            self.assertEqual(
                foreign.json(),
                expected_error(
                    "resource_not_found",
                    "resource not found",
                    "security-resource-hidden-0001",
                ),
            )
            self.assertNotIn(foreign_id, foreign.text)
            self.assertNotIn("run-does-not-exist", missing.text)

            alpha_command = "security-alpha-create-0001"
            created = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=auth(ADMIN_KEY, idempotency_key=alpha_command),
            )
            self.assertEqual(created.status_code, 201)
            duplicate = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Changed hidden campaign"),
                headers=auth(ADMIN_KEY, "security-conflict-hidden-0001", alpha_command),
            )
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(
                duplicate.json(),
                expected_error(
                    "idempotency_conflict",
                    "idempotency key conflicts with a prior request",
                    "security-conflict-hidden-0001",
                ),
            )
            self.assertNotIn(created.json()["run_id"], duplicate.text)
            self.assertNotIn("already exists", duplicate.text)

    def test_validation_errors_never_reflect_credentials_or_campaign_input(self):
        with self.client() as client:
            submitted_secret = "short-secret-value"
            invalid_session = client.post(
                "/api/v1/sessions",
                json={"api_key": submitted_secret},
                headers={"X-Request-ID": "security-validation-key-0001"},
            )
            self.assertEqual(invalid_session.status_code, 422)
            self.assertEqual(invalid_session.json()["code"], "request_validation_failed")
            self.assertEqual(
                invalid_session.json()["detail"], "request validation failed"
            )
            self.assertEqual(
                invalid_session.json()["request_id"], "security-validation-key-0001"
            )
            serialized = json.dumps(invalid_session.json(), sort_keys=True)
            self.assertNotIn(submitted_secret, serialized)
            self.assertNotIn('"input"', serialized)
            self.assertEqual(
                invalid_session.json()["errors"],
                [{"location": ["body", "api_key"], "type": "string_too_short"}],
            )

            campaign_secret = "private-political-strategy-" * 300
            invalid_brief = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, objective=campaign_secret),
                headers=auth(ADMIN_KEY, "security-validation-brief-0001", "security-invalid-brief-0001"),
            )
            self.assertEqual(invalid_brief.status_code, 422)
            serialized = json.dumps(invalid_brief.json(), sort_keys=True)
            self.assertNotIn(campaign_secret[:100], serialized)
            self.assertNotIn('"input"', serialized)
            self.assertEqual(
                invalid_brief.json()["errors"],
                [{"location": ["body", "objective"], "type": "string_too_long"}],
            )

    def test_authorization_and_csrf_denials_are_durable_and_tenant_scoped(self):
        with self.client() as client:
            invalid = client.get(
                "/api/v1/me",
                headers=auth(INVALID_KEY, "security-unauthenticated-0001"),
            )
            self.assertEqual(invalid.status_code, 401)

            denied = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=auth(VIEWER_KEY, "security-audit-authz-0001"),
            )
            self.assertEqual(denied.status_code, 403)

            opened = client.post(
                "/api/v1/sessions",
                json={"api_key": ADMIN_KEY},
                headers={"X-Request-ID": "security-audit-session-0001"},
            )
            self.assertEqual(opened.status_code, 201)
            csrf = opened.json()["csrf_token"]
            wrong_csrf = "wrong-{}".format(csrf)
            verification_denied = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="CSRF denied campaign"),
                headers={
                    "X-CSRF-Token": wrong_csrf,
                    "X-Request-ID": "security-audit-csrf-0001",
                },
            )
            self.assertEqual(verification_denied.status_code, 403)
            self.assertEqual(
                verification_denied.json(),
                expected_error(
                    "request_verification_failed",
                    "request verification failed",
                    "security-audit-csrf-0001",
                ),
            )

            audit_response = client.get(
                "/api/v1/audit-events", headers=auth(ADMIN_KEY)
            )
            self.assertEqual(audit_response.status_code, 200)
            events = audit_response.json()["events"]
            security_events = [
                event
                for event in events
                if event["action"]
                in {"authorization.denied", "request.verification_denied"}
            ]
            self.assertEqual(
                [event["action"] for event in security_events],
                ["authorization.denied", "request.verification_denied"],
            )
            self.assertEqual(
                [event["request_id"] for event in security_events],
                ["security-audit-authz-0001", "security-audit-csrf-0001"],
            )
            self.assertEqual(
                [event["actor"] for event in security_events],
                [
                    "api-key:viewer@example.com",
                    "browser-session:admin@example.com",
                ],
            )
            self.assertTrue(
                all(event["tenant_id"] == "tenant-alpha" for event in security_events)
            )
            self.assertEqual(
                security_events[0]["payload"],
                {
                    "auth_method": "bearer",
                    "reason": "authorization",
                    "role": "viewer",
                },
            )
            self.assertEqual(
                security_events[1]["payload"],
                {
                    "auth_method": "session",
                    "reason": "csrf",
                    "role": "admin",
                },
            )
            audit_text = audit_response.text
            for secret in (VIEWER_KEY, ADMIN_KEY, csrf, wrong_csrf, INVALID_KEY):
                self.assertNotIn(secret, audit_text)
            self.assertNotIn("security-unauthenticated-0001", audit_text)

            beta_audit = client.get(
                "/api/v1/audit-events", headers=auth(BETA_KEY)
            )
            self.assertEqual(beta_audit.status_code, 200)
            self.assertEqual(beta_audit.json()["events"], [])

            metrics = client.get("/metrics").text
            self.assertIn(
                'agency_security_denials_total{reason="authorization"} 1', metrics
            )
            self.assertIn('agency_security_denials_total{reason="csrf"} 1', metrics)
            self.assertNotIn("tenant-alpha", metrics)
            self.assertNotIn("runs:create", metrics)
            self.assertNotIn("viewer@example.com", metrics)

        with self.client() as restarted:
            durable = restarted.get(
                "/api/v1/audit-events", headers=auth(ADMIN_KEY)
            )
            self.assertEqual(durable.status_code, 200)
            self.assertEqual(
                [
                    event["action"]
                    for event in durable.json()["events"]
                    if event["action"].endswith("denied")
                ],
                ["authorization.denied", "request.verification_denied"],
            )

    def test_declared_and_streamed_oversized_bodies_fail_before_dispatch(self):
        request_id = "security-body-limit-0001"
        oversized = json.dumps(
            dict(BRIEF, objective="x" * 3000), separators=(",", ":")
        ).encode("utf-8")
        with self.client(max_request_body_bytes=1024) as client:
            declared = client.post(
                "/api/v1/runs",
                content=oversized,
                headers={
                    **auth(ADMIN_KEY, request_id),
                    "Content-Type": "application/json",
                },
            )
            self.assertEqual(declared.status_code, 413)
            self.assertEqual(
                declared.json(),
                expected_error(
                    "request_too_large", "request too large", request_id
                ),
            )
            self.assertEqual(declared.headers["Cache-Control"], "no-store")

            async def streamed_request():
                pending = []
                for index in range(0, len(oversized), 128):
                    end = min(index + 128, len(oversized))
                    pending.append(
                        {
                            "type": "http.request",
                            "body": oversized[index:end],
                            "more_body": end < len(oversized),
                        }
                    )
                sent = []

                async def receive():
                    if pending:
                        return pending.pop(0)
                    return {"type": "http.disconnect"}

                async def send(message):
                    sent.append(message)

                scope = {
                    "type": "http",
                    "asgi": {"version": "3.0", "spec_version": "2.3"},
                    "http_version": "1.1",
                    "method": "POST",
                    "scheme": "http",
                    "path": "/api/v1/runs",
                    "raw_path": b"/api/v1/runs",
                    "query_string": b"",
                    "root_path": "",
                    "headers": [
                        (b"host", b"testserver"),
                        (b"authorization", "Bearer {}".format(ADMIN_KEY).encode()),
                        (b"x-request-id", b"security-body-limit-0002"),
                        (b"content-type", b"application/json"),
                        (b"transfer-encoding", b"chunked"),
                    ],
                    "client": ("127.0.0.1", 4242),
                    "server": ("testserver", 80),
                    "state": {},
                }
                await client.app(scope, receive, send)
                return sent

            streamed_messages = asyncio.run(streamed_request())
            start = next(
                message
                for message in streamed_messages
                if message["type"] == "http.response.start"
            )
            body = b"".join(
                message.get("body", b"")
                for message in streamed_messages
                if message["type"] == "http.response.body"
            )
            self.assertEqual(start["status"], 413)
            streamed_payload = json.loads(body)
            self.assertEqual(streamed_payload["code"], "request_too_large")
            self.assertEqual(
                streamed_payload["request_id"], "security-body-limit-0002"
            )

            async def ambiguous_framing_request():
                pending = [
                    {
                        "type": "http.request",
                        "body": json.dumps(BRIEF).encode("utf-8"),
                        "more_body": False,
                    }
                ]
                sent = []

                async def receive():
                    if pending:
                        return pending.pop(0)
                    return {"type": "http.disconnect"}

                async def send(message):
                    sent.append(message)

                scope = {
                    "type": "http",
                    "asgi": {"version": "3.0", "spec_version": "2.3"},
                    "http_version": "1.1",
                    "method": "POST",
                    "scheme": "http",
                    "path": "/api/v1/runs",
                    "raw_path": b"/api/v1/runs",
                    "query_string": b"",
                    "root_path": "",
                    "headers": [
                        (b"host", b"testserver"),
                        (b"authorization", "Bearer {}".format(ADMIN_KEY).encode()),
                        (b"x-request-id", b"security-framing-invalid-0001"),
                        (b"content-type", b"application/json"),
                        (b"content-length", b"512"),
                        (b"content-length", b"513"),
                    ],
                    "client": ("127.0.0.1", 4242),
                    "server": ("testserver", 80),
                    "state": {},
                }
                await client.app(scope, receive, send)
                return sent

            framing_messages = asyncio.run(ambiguous_framing_request())
            framing_start = next(
                message
                for message in framing_messages
                if message["type"] == "http.response.start"
            )
            framing_body = b"".join(
                message.get("body", b"")
                for message in framing_messages
                if message["type"] == "http.response.body"
            )
            self.assertEqual(framing_start["status"], 400)
            self.assertEqual(json.loads(framing_body)["code"], "invalid_request")

            audit = client.get(
                "/api/v1/audit-events", headers=auth(ADMIN_KEY)
            )
            self.assertEqual(audit.status_code, 200)
            self.assertEqual(audit.json()["events"], [])

    def test_request_body_limit_configuration_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "request body limit"):
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys={},
                identity_credentials=self.identities,
                max_request_body_bytes=1023,
            )
        with self.assertRaisesRegex(ValueError, "request body limit"):
            create_app(
                database_path=str(self.database),
                static_dir=self.static_dir,
                tenant_api_keys={},
                identity_credentials=self.identities,
                max_request_body_bytes=10 * 1024 * 1024 + 1,
            )

    def test_internal_failures_do_not_reflect_exception_content(self):
        secret = "database-password-and-private-campaign-content"
        with self.client(raise_server_exceptions=False) as client:
            with mock.patch.object(
                client.app.state.runtime_service,
                "start",
                side_effect=RuntimeError(secret),
            ):
                with self.assertLogs("agency_runtime.api", level="ERROR") as captured:
                    response = client.post(
                        "/api/v1/runs",
                        json=BRIEF,
                        headers=auth(ADMIN_KEY, "security-internal-error-0001", "security-internal-command-0001"),
                    )
            self.assertEqual(response.status_code, 500)
            self.assertEqual(
                response.json(),
                expected_error(
                    "internal_error",
                    "internal service error",
                    "security-internal-error-0001",
                ),
            )
            self.assertNotIn(secret, response.text)
            self.assertNotIn(secret, "\n".join(captured.output))
            self.assertIn("RuntimeError", "\n".join(captured.output))

    def test_public_error_constructor_rejects_unsafe_contract_values(self):
        with self.assertRaisesRegex(ValueError, "code is invalid"):
            PublicApiError(status_code=403, code="Role viewer denied", detail="safe")
        with self.assertRaisesRegex(ValueError, "detail is invalid"):
            PublicApiError(
                status_code=403,
                code="authorization_denied",
                detail="unsafe\nheader-like detail",
            )
        with self.assertRaisesRegex(ValueError, "4xx or 5xx"):
            PublicApiError(status_code=200, code="request_failed", detail="safe")

    def test_api_responses_include_no_store_and_baseline_security_headers(self):
        with self.client() as client:
            success = client.get(
                "/api/v1/me",
                headers=auth(ADMIN_KEY, "security-headers-success-0001"),
            )
            failure = client.get(
                "/api/v1/me",
                headers=auth(INVALID_KEY, "security-headers-failure-0001"),
            )
            for response in (success, failure):
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                self.assertEqual(
                    response.headers["Permissions-Policy"],
                    "camera=(), microphone=(), geolocation=()",
                )
                self.assertEqual(
                    response.headers["Cross-Origin-Resource-Policy"], "same-origin"
                )
                self.assertTrue(response.headers["X-Request-ID"].startswith("security-"))


if __name__ == "__main__":
    unittest.main()
