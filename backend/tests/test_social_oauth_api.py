import base64
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app


ADMIN_KEY = "social-admin-key-material-2026"
VIEWER_KEY = "social-viewer-key-material-2026"
OTHER_ADMIN_KEY = "social-other-admin-key-material-2026"
X_SECRET = "x-consumer-secret-api-test"
IG_SECRET = "instagram-app-secret-api-test"


def encryption_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def identities():
    return [
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "admin-alpha",
            "role": "admin",
            "key_id": "admin-alpha-v1",
            "api_key": ADMIN_KEY,
            "active": True,
        },
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "viewer-alpha",
            "role": "viewer",
            "key_id": "viewer-alpha-v1",
            "api_key": VIEWER_KEY,
            "active": True,
        },
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "admin-alpha-other",
            "role": "admin",
            "key_id": "admin-alpha-v2",
            "api_key": OTHER_ADMIN_KEY,
            "active": True,
        },
    ]


def environment():
    return {
        "AGENCY_X_CONSUMER_KEY": "x-consumer-key-api-test",
        "AGENCY_X_CONSUMER_SECRET": X_SECRET,
        "AGENCY_X_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback",
        "AGENCY_INSTAGRAM_APP_ID": "instagram-app-id-api-test",
        "AGENCY_INSTAGRAM_APP_SECRET": IG_SECRET,
        "AGENCY_INSTAGRAM_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback",
        "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps(
            {"social-v1": encryption_key()}
        ),
        "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "social-v1",
    }


def open_session(client: TestClient, api_key: str):
    response = client.post(
        "/api/v1/sessions",
        json={"api_key": api_key},
        headers={"X-Request-ID": "social-session-{}".format(api_key[-5:])},
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["csrf_token"]


class SocialOAuthApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "runtime.sqlite3"

    def tearDown(self):
        self.temporary.cleanup()

    def app(self, handler, social_environment=None):
        return create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            social_environment=social_environment or environment(),
            social_oauth_transport=httpx.MockTransport(handler),
        )

    def test_admin_connects_and_disconnects_x_without_token_disclosure(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path == "/oauth/request_token":
                return httpx.Response(
                    200,
                    text=(
                        "oauth_token=x-request-token&oauth_token_secret=x-request-secret"
                        "&oauth_callback_confirmed=true"
                    ),
                )
            if request.url.path == "/oauth/access_token":
                return httpx.Response(
                    200,
                    text=(
                        "oauth_token=x-user-token&oauth_token_secret=x-user-secret"
                        "&user_id=778899&screen_name=connected_x"
                    ),
                )
            raise AssertionError("unexpected request {}".format(request.url))

        app = self.app(handler)
        with TestClient(app, follow_redirects=False) as client:
            csrf = open_session(client, ADMIN_KEY)
            before = client.get("/api/v1/social-channels").json()["channels"]
            x_before = next(item for item in before if item["channel_id"] == "x")
            self.assertTrue(x_before["oauth_start_available"])
            self.assertIsNone(x_before["connected_account"])

            missing_csrf = client.post("/api/v1/social-channels/x/oauth/start")
            self.assertEqual(missing_csrf.status_code, 403)

            start = client.post(
                "/api/v1/social-channels/x/oauth/start",
                headers={"X-CSRF-Token": csrf, "X-Request-ID": "x-oauth-start-001"},
            )
            self.assertEqual(start.status_code, 201)
            authorization_url = start.json()["authorization_url"]
            self.assertEqual(
                parse_qs(urlsplit(authorization_url).query)["oauth_token"],
                ["x-request-token"],
            )

            callback = client.get(
                "/api/v1/social-channels/x/oauth/callback",
                params={"oauth_token": "x-request-token", "oauth_verifier": "verifier"},
                headers={"X-Request-ID": "x-oauth-callback-001"},
            )
            self.assertEqual(callback.status_code, 303)
            self.assertEqual(
                callback.headers["location"], "/?social_channel=x&status=connected"
            )

            catalog = client.get("/api/v1/social-channels").json()["channels"]
            connected = next(item for item in catalog if item["channel_id"] == "x")
            self.assertEqual(connected["connection_state"], "connected")
            self.assertEqual(
                connected["connected_account"]["account_username"], "connected_x"
            )
            self.assertEqual(
                connected["connected_account"]["token_storage"],
                "encrypted_server_side",
            )
            self.assertFalse(connected["oauth_start_available"])
            self.assertFalse(connected["publishing_available"])

            replay = client.get(
                "/api/v1/social-channels/x/oauth/callback",
                params={"oauth_token": "x-request-token", "oauth_verifier": "verifier"},
            )
            self.assertEqual(replay.status_code, 400)
            self.assertEqual(len(requests), 2)

            disconnected = client.delete(
                "/api/v1/social-channels/x/connection",
                headers={"X-CSRF-Token": csrf, "X-Request-ID": "x-disconnect-001"},
            )
            self.assertEqual(disconnected.status_code, 200)
            self.assertTrue(disconnected.json()["disconnected"])
            after = client.get("/api/v1/social-channels/x").json()["channel"]
            self.assertEqual(after["connection_state"], "not_connected")
            self.assertIsNone(after["connected_account"])

            audit = client.get("/api/v1/audit-events").json()["events"]
            actions = [item["action"] for item in audit]
            self.assertIn("social.oauth_started", actions)
            self.assertIn("social.connected", actions)
            self.assertIn("social.disconnected", actions)

            serialized = json.dumps(catalog) + json.dumps(audit)
            for secret in (
                X_SECRET,
                IG_SECRET,
                "x-request-secret",
                "x-user-token",
                "x-user-secret",
                encryption_key(),
            ):
                self.assertNotIn(secret, serialized)
            raw = self.database.read_bytes()
            self.assertNotIn(b"x-user-token", raw)
            self.assertNotIn(b"x-user-secret", raw)

    def test_instagram_connects_professional_account_and_wrong_session_is_rejected(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.url.host == "api.instagram.com":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "instagram-user-token",
                        "user_id": 123,
                        "expires_in": 3600,
                    },
                )
            if request.url.host == "graph.instagram.com":
                return httpx.Response(
                    200,
                    json={
                        "id": "123",
                        "username": "connected.instagram",
                        "account_type": "MEDIA_CREATOR",
                    },
                )
            raise AssertionError("unexpected request {}".format(request.url))

        app = self.app(handler)
        with TestClient(app, follow_redirects=False) as owner:
            csrf = open_session(owner, ADMIN_KEY)
            start = owner.post(
                "/api/v1/social-channels/instagram/oauth/start",
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(start.status_code, 201)
            state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]

            other_app = self.app(handler)
            with TestClient(other_app, follow_redirects=False) as other:
                open_session(other, OTHER_ADMIN_KEY)
                wrong = other.get(
                    "/api/v1/social-channels/instagram/oauth/callback",
                    params={"state": state, "code": "instagram-code"},
                )
                self.assertEqual(wrong.status_code, 400)
                self.assertEqual(len(calls), 0)

            connected = owner.get(
                "/api/v1/social-channels/instagram/oauth/callback",
                params={"state": state, "code": "instagram-code"},
            )
            self.assertEqual(connected.status_code, 303)
            channel = owner.get(
                "/api/v1/social-channels/instagram"
            ).json()["channel"]
            self.assertEqual(channel["connection_state"], "connected")
            self.assertEqual(
                channel["connected_account"]["account_username"],
                "connected.instagram",
            )
            self.assertEqual(len(calls), 2)

    def test_viewer_and_bearer_admin_cannot_start_browser_oauth(self):
        no_http = lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
        with TestClient(self.app(no_http)) as viewer:
            csrf = open_session(viewer, VIEWER_KEY)
            denied = viewer.post(
                "/api/v1/social-channels/x/oauth/start",
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(denied.status_code, 403)

        with TestClient(self.app(no_http)) as bearer:
            denied = bearer.post(
                "/api/v1/social-channels/x/oauth/start",
                headers={"Authorization": "Bearer {}".format(ADMIN_KEY)},
            )
            self.assertEqual(denied.status_code, 400)
            self.assertEqual(denied.json()["code"], "browser_session_required")


    def test_server_side_token_bootstrap_connects_both_channels_without_http(self):
        bootstrap = environment()
        bootstrap.update(
            {
                "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-alpha",
                "AGENCY_X_USER_ACCESS_TOKEN": "bootstrap-x-access-token",
                "AGENCY_X_USER_ACCESS_TOKEN_SECRET": "bootstrap-x-access-secret",
                "AGENCY_X_ACCOUNT_ID": "x-bootstrap-001",
                "AGENCY_X_ACCOUNT_USERNAME": "bootstrap_x",
                "AGENCY_INSTAGRAM_ACCESS_TOKEN": "bootstrap-instagram-token",
                "AGENCY_INSTAGRAM_ACCOUNT_ID": "ig-bootstrap-001",
                "AGENCY_INSTAGRAM_ACCOUNT_USERNAME": "bootstrap.instagram",
                "AGENCY_INSTAGRAM_TOKEN_EXPIRES_AT": "2026-09-01T00:00:00+00:00",
            }
        )
        no_http = lambda request: (_ for _ in ()).throw(AssertionError("no provider HTTP"))
        for restart in range(2):
            with TestClient(self.app(no_http, bootstrap)) as client:
                open_session(client, ADMIN_KEY)
                channels = client.get("/api/v1/social-channels").json()["channels"]
                self.assertEqual(
                    {item["channel_id"]: item["connection_state"] for item in channels},
                    {"x": "connected", "instagram": "connected"},
                )
                usernames = {
                    item["channel_id"]: item["connected_account"]["account_username"]
                    for item in channels
                }
                self.assertEqual(
                    usernames,
                    {"x": "bootstrap_x", "instagram": "bootstrap.instagram"},
                )
                audit = client.get("/api/v1/audit-events").json()["events"]
                bootstrap_events = [
                    item for item in audit if item["action"] == "social.bootstrapped"
                ]
                self.assertEqual(len(bootstrap_events), 2)
                serialized = json.dumps(channels) + json.dumps(audit)
                for forbidden in (
                    "bootstrap-x-access-token",
                    "bootstrap-x-access-secret",
                    "bootstrap-instagram-token",
                    encryption_key(),
                ):
                    self.assertNotIn(forbidden, serialized)
        raw = self.database.read_bytes()
        for forbidden in (
            b"bootstrap-x-access-token",
            b"bootstrap-x-access-secret",
            b"bootstrap-instagram-token",
        ):
            self.assertNotIn(forbidden, raw)

    def test_partial_or_unencrypted_token_bootstrap_fails_closed(self):
        partial = environment()
        partial.update(
            {
                "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-alpha",
                "AGENCY_X_USER_ACCESS_TOKEN": "partial-token",
                "AGENCY_X_ACCOUNT_ID": "x-partial",
                "AGENCY_X_ACCOUNT_USERNAME": "partial",
            }
        )
        with self.assertRaises(ValueError):
            self.app(lambda request: None, partial)

        unencrypted = environment()
        unencrypted.pop("AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON")
        unencrypted.pop("AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID")
        unencrypted.update(
            {
                "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-alpha",
                "AGENCY_INSTAGRAM_ACCESS_TOKEN": "unencrypted-token",
                "AGENCY_INSTAGRAM_ACCOUNT_ID": "ig-unencrypted",
                "AGENCY_INSTAGRAM_ACCOUNT_USERNAME": "unencrypted.account",
            }
        )
        with self.assertRaises(ValueError):
            self.app(lambda request: None, unencrypted)

    def test_partial_encryption_configuration_fails_application_startup(self):
        broken = environment()
        broken.pop("AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID")
        with self.assertRaises(ValueError):
            create_app(
                database_path=str(self.database),
                identity_credentials=identities(),
                session_cookie_secure=False,
                social_environment=broken,
            )


if __name__ == "__main__":
    unittest.main()
