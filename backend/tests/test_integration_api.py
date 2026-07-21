import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


VIEWER_ALPHA = "integration-viewer-alpha-key-material-2026"
VIEWER_BETA = "integration-viewer-beta-key-material-2026"


def identity(tenant_id, subject_id, key_id, api_key):
    return {
        "tenant_id": tenant_id,
        "subject_id": subject_id,
        "role": "viewer",
        "key_id": key_id,
        "api_key": api_key,
        "active": True,
    }


def auth(api_key, request_id="integration-review-request-0001"):
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-ID": request_id,
    }


class IntegrationApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "runtime.sqlite3"
        self.app = create_app(
            database_path=str(self.database),
            identity_credentials=[
                identity(
                    "tenant-alpha",
                    "viewer-alpha",
                    "viewer-alpha-v1",
                    VIEWER_ALPHA,
                ),
                identity(
                    "tenant-beta",
                    "viewer-beta",
                    "viewer-beta-v1",
                    VIEWER_BETA,
                ),
            ],
            session_cookie_secure=False,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_registry_requires_authentication_and_derives_tenant(self):
        with TestClient(self.app) as client:
            denied = client.get(
                "/api/v1/integrations",
                headers={"X-Request-ID": "integration-no-auth-0001"},
            )
            self.assertEqual(denied.status_code, 401)
            self.assertEqual(denied.json()["code"], "authentication_failed")

            alpha = client.get(
                "/api/v1/integrations", headers=auth(VIEWER_ALPHA)
            )
            beta = client.get(
                "/api/v1/integrations", headers=auth(VIEWER_BETA)
            )
            self.assertEqual(alpha.status_code, 200)
            self.assertEqual(beta.status_code, 200)
            self.assertEqual(alpha.json()["tenant_id"], "tenant-alpha")
            self.assertEqual(beta.json()["tenant_id"], "tenant-beta")
            self.assertEqual(len(alpha.json()["integrations"]), 1)
            self.assertEqual(
                alpha.json()["integrations"][0]["review_status"],
                "reviewed_disabled",
            )
            self.assertFalse(
                alpha.json()["integrations"][0]["external_effects_enabled"]
            )

    def test_detail_is_read_only_uniform_and_non_mutating(self):
        with TestClient(self.app) as client:
            before = client.get(
                "/api/v1/audit-events", headers=auth(VIEWER_ALPHA)
            ).json()["events"]
            response = client.get(
                "/api/v1/integrations/video-use", headers=auth(VIEWER_ALPHA)
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["tenant_id"], "tenant-alpha")
            self.assertEqual(
                response.json()["integration"]["upstream_commit"],
                "92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66",
            )
            self.assertFalse(response.json()["integration"]["activation_allowed"])

            missing = client.get(
                "/api/v1/integrations/unknown", headers=auth(VIEWER_ALPHA)
            )
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(
                missing.json(),
                {
                    "code": "resource_not_found",
                    "detail": "resource not found",
                    "request_id": "integration-review-request-0001",
                },
            )
            after = client.get(
                "/api/v1/audit-events", headers=auth(VIEWER_ALPHA)
            ).json()["events"]
            self.assertEqual(after, before)

    def test_no_execution_route_or_openapi_mutation_exists(self):
        with TestClient(self.app) as client:
            attempted = client.post(
                "/api/v1/integrations/video-use/execute",
                headers=auth(VIEWER_ALPHA, "integration-execute-denied-0001"),
                json={"operation": "render_video"},
            )
            self.assertIn(attempted.status_code, {404, 405})
            self.assertNotIn("ffmpeg", attempted.text.lower())
            openapi = client.get("/openapi.json").json()
            integration_paths = {
                path: methods
                for path, methods in openapi["paths"].items()
                if path.startswith("/api/v1/integrations")
            }
            self.assertEqual(
                set(integration_paths),
                {
                    "/api/v1/integrations",
                    "/api/v1/integrations/{integration_id}",
                },
            )
            self.assertTrue(
                all(set(methods) == {"get"} for methods in integration_paths.values())
            )


if __name__ == "__main__":
    unittest.main()
