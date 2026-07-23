import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


VIEWER_KEY = "social-viewer-key-material-2026"


def identity():
    return {
        "tenant_id": "tenant-alpha",
        "subject_id": "viewer-alpha",
        "role": "viewer",
        "key_id": "viewer-alpha-v1",
        "api_key": VIEWER_KEY,
        "active": True,
    }


def auth(request_id="social-channel-request-0001"):
    return {
        "Authorization": f"Bearer {VIEWER_KEY}",
        "X-Request-ID": request_id,
    }


class SocialChannelApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "runtime.sqlite3"

    def tearDown(self):
        self.temporary.cleanup()

    def app(self, social_environment=None):
        return create_app(
            database_path=str(self.database),
            identity_credentials=[identity()],
            session_cookie_secure=False,
            social_environment=social_environment or {},
        )

    def test_catalog_requires_authentication_and_returns_exact_disabled_channels(self):
        with TestClient(self.app()) as client:
            denied = client.get(
                "/api/v1/social-channels",
                headers={"X-Request-ID": "social-no-auth-0001"},
            )
            self.assertEqual(denied.status_code, 401)

            response = client.get("/api/v1/social-channels", headers=auth())
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["tenant_id"], "tenant-alpha")
            self.assertEqual(
                [channel["channel_id"] for channel in body["channels"]],
                ["x", "instagram"],
            )
            self.assertTrue(
                all(
                    channel["configuration_state"] == "missing_credentials"
                    for channel in body["channels"]
                )
            )
            self.assertTrue(
                all(channel["publishing_available"] is False for channel in body["channels"])
            )

    def test_ready_configuration_is_secret_free_and_honest_about_oauth(self):
        environment = {
            "AGENCY_X_CONSUMER_KEY": "x-consumer-key-value",
            "AGENCY_X_CONSUMER_SECRET": "x-consumer-secret-value",
            "AGENCY_X_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback",
            "AGENCY_INSTAGRAM_APP_ID": "instagram-app-id",
            "AGENCY_INSTAGRAM_APP_SECRET": "instagram-app-secret-value",
            "AGENCY_INSTAGRAM_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback",
        }
        with TestClient(self.app(environment)) as client:
            response = client.get("/api/v1/social-channels", headers=auth())
            self.assertEqual(response.status_code, 200)
            channels = response.json()["channels"]
            self.assertTrue(all(channel["configured"] for channel in channels))
            self.assertTrue(
                all(
                    channel["configuration_state"] == "ready_for_authentication"
                    for channel in channels
                )
            )
            self.assertTrue(all(channel["oauth_start_available"] is False for channel in channels))
            self.assertTrue(all(channel["connection_state"] == "not_connected" for channel in channels))
            serialized = json.dumps(response.json())
            for secret in (
                "x-consumer-key-value",
                "x-consumer-secret-value",
                "instagram-app-id",
                "instagram-app-secret-value",
            ):
                self.assertNotIn(secret, serialized)

    def test_detail_is_uniform_and_no_oauth_or_publish_mutation_exists(self):
        with TestClient(self.app()) as client:
            instagram = client.get(
                "/api/v1/social-channels/instagram", headers=auth()
            )
            self.assertEqual(instagram.status_code, 200)
            self.assertTrue(instagram.json()["channel"]["requires_media"])

            missing = client.get(
                "/api/v1/social-channels/unknown", headers=auth()
            )
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.json()["code"], "resource_not_found")

            for path in (
                "/api/v1/social-channels/x/oauth/start",
                "/api/v1/social-channels/instagram/oauth/start",
                "/api/v1/social-channels/x/publish",
                "/api/v1/social-channels/instagram/publish",
            ):
                attempted = client.post(path, headers=auth(), json={})
                self.assertIn(attempted.status_code, {404, 405})

            openapi = client.get("/openapi.json").json()
            social_paths = {
                path: methods
                for path, methods in openapi["paths"].items()
                if path.startswith("/api/v1/social-channels")
            }
            self.assertEqual(
                set(social_paths),
                {
                    "/api/v1/social-channels",
                    "/api/v1/social-channels/{channel_id}",
                },
            )
            self.assertTrue(
                all(set(methods) == {"get"} for methods in social_paths.values())
            )


if __name__ == "__main__":
    unittest.main()
