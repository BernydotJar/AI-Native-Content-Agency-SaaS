"""Fail-closed video provider discovery and HeyGen draft contract."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app
from agency_runtime.video_providers import VideoProviderCatalog, heygen_video_agent_draft

API_KEY = "video-provider-viewer-test-key-material-2026"
HEYGEN_TEST_SECRET = "SAMPLE_SECRET_NEVER_SEND"


class VideoProviderTests(unittest.TestCase):
    def test_catalog_never_echoes_secrets_or_claims_generation(self):
        missing = VideoProviderCatalog({}).get("heygen")
        self.assertFalse(missing["configured"])
        self.assertEqual(missing["configuration_state"], "missing_credential")
        catalog = VideoProviderCatalog({"HEYGEN_API_KEY": HEYGEN_TEST_SECRET})
        content = catalog.list()
        self.assertEqual(len(content), 5)
        self.assertTrue(catalog.get("heygen")["configured"])
        self.assertTrue(all(p["execution_enabled"] is False for p in content))
        self.assertTrue(all(p["requires_human_authorization"] for p in content))
        self.assertNotIn(HEYGEN_TEST_SECRET, repr(content))
        with self.assertRaises(KeyError):
            catalog.get("other")

    def test_draft_matches_current_v3_video_agent_schema_and_validates(self):
        self.assertEqual(
            heygen_video_agent_draft("  An animated brand explainer  "),
            {"prompt": "An animated brand explainer", "mode": "generate"},
        )
        self.assertEqual(heygen_video_agent_draft("Hi", mode="chat")["mode"], "chat")
        for prompt in ("", "  ", "a" * 10001, None):
            with self.subTest(prompt=str(prompt)[:20]):
                with self.assertRaises(ValueError):
                    heygen_video_agent_draft(prompt)
        with self.assertRaises(ValueError):
            heygen_video_agent_draft("a", mode="billable_test")

    def test_catalog_endpoint_authenticated_tenant_scoped_get_only(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app(
                database_path=str(Path(temp) / "runtime.sqlite3"),
                provider_environment={"HEYGEN_API_KEY": HEYGEN_TEST_SECRET},
                identity_credentials=[{
                    "tenant_id": "video-tenant-alpha",
                    "subject_id": "video-viewer-alpha",
                    "role": "viewer",
                    "key_id": "video-key-alpha",
                    "api_key": API_KEY,
                    "active": True,
                }],
                session_cookie_secure=False,
            )
            with TestClient(app) as client:
                headers = {"Authorization": f"Bearer {API_KEY}", "X-Request-ID": "video-catalog-test-request"}
                self.assertEqual(client.get("/api/v1/video/providers").status_code, 401)
                response = client.get("/api/v1/video/providers", headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["tenant_id"], "video-tenant-alpha")
                self.assertEqual(len(response.json()["providers"]), 5)
                self.assertNotIn(HEYGEN_TEST_SECRET, response.text)
                single = client.get("/api/v1/video/providers/heygen", headers=headers)
                self.assertTrue(single.json()["provider"]["configured"])
                self.assertEqual(client.get("/api/v1/video/providers/nope", headers=headers).status_code, 404)
                self.assertIn(
                    client.post("/api/v1/video/providers/heygen", headers=headers, json={}).status_code,
                    (404, 405),
                )
                paths = {k: v for k, v in client.get("/openapi.json").json()["paths"].items()
                         if k.startswith("/api/v1/video")}
                self.assertEqual(
                    set(paths), {"/api/v1/video/providers", "/api/v1/video/providers/{provider_id}"}
                )
                self.assertTrue(all(set(methods) == {"get"} for methods in paths.values()))


if __name__ == "__main__":
    unittest.main()
