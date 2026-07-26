import base64
import json
from datetime import datetime
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
                        "access_token": "instagram-short-token",
                        "user_id": 123,
                    },
                )
            if request.url.path == "/access_token":
                self.assertEqual(request.method, "GET")
                self.assertEqual(request.content, b"")
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer instagram-short-token",
                )
                query = parse_qs(request.url.query.decode("utf-8"))
                self.assertEqual(query["grant_type"], ["ig_exchange_token"])
                self.assertEqual(query["client_secret"], [IG_SECRET])
                self.assertNotIn("access_token", query)
                return httpx.Response(
                    200,
                    json={
                        "access_token": "instagram-long-token",
                        "token_type": "bearer",
                        "expires_in": 5_184_000,
                    },
                )
            if request.url.path == "/v24.0/me":
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer instagram-long-token",
                )
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
                self.assertEqual(wrong.status_code, 303)
                self.assertEqual(
                    wrong.headers["location"],
                    "/?social_channel=instagram&status=error&error=social_oauth_callback_invalid",
                )
                self.assertEqual(len(calls), 0)

            missing_state = owner.get(
                "/api/v1/social-channels/instagram/oauth/callback",
                params={"code": "instagram-code"},
            )
            self.assertEqual(missing_state.status_code, 422)
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
            connected_at = datetime.fromisoformat(
                channel["connected_account"]["connected_at"]
            )
            expires_at = datetime.fromisoformat(
                channel["connected_account"]["token_expires_at"]
            )
            self.assertGreater((expires_at - connected_at).total_seconds(), 5_000_000)
            self.assertLessEqual((expires_at - connected_at).total_seconds(), 5_184_000)
            self.assertEqual(len(calls), 3)
            raw = self.database.read_bytes()
            self.assertNotIn(b"instagram-short-token", raw)
            self.assertNotIn(b"instagram-long-token", raw)

    def test_instagram_unsupported_long_lived_exchange_connects_with_bounded_token(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.url.host == "api.instagram.com":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "bounded-short-token",
                        "user_id": 321,
                    },
                )
            if request.url.path == "/access_token":
                self.assertEqual(request.method, "GET")
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer bounded-short-token",
                )
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "type": "IGApiException",
                            "code": 100,
                            "message": "must never reach the browser",
                        }
                    },
                )
            if request.url.path == "/v24.0/me":
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer bounded-short-token",
                )
                return httpx.Response(
                    200,
                    json={
                        "id": "321",
                        "username": "bounded.instagram",
                        "account_type": "BUSINESS",
                    },
                )
            raise AssertionError("unexpected request {}".format(request.url))

        app = self.app(handler)
        with TestClient(app, follow_redirects=False) as client:
            csrf = open_session(client, ADMIN_KEY)
            start = client.post(
                "/api/v1/social-channels/instagram/oauth/start",
                headers={"X-CSRF-Token": csrf},
            )
            state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
            callback = client.get(
                "/api/v1/social-channels/instagram/oauth/callback",
                params={"state": state, "code": "instagram-code"},
            )
            self.assertEqual(callback.status_code, 303)
            self.assertEqual(
                callback.headers["location"],
                "/?social_channel=instagram&status=connected",
            )
            channel = client.get(
                "/api/v1/social-channels/instagram"
            ).json()["channel"]
            self.assertEqual(channel["connection_state"], "connected")
            self.assertEqual(
                channel["connected_account"]["account_username"],
                "bounded.instagram",
            )
            connected_at = datetime.fromisoformat(
                channel["connected_account"]["connected_at"]
            )
            expires_at = datetime.fromisoformat(
                channel["connected_account"]["token_expires_at"]
            )
            self.assertEqual((expires_at - connected_at).total_seconds(), 3300)
            self.assertEqual(len(calls), 3)
            raw = self.database.read_bytes()
            self.assertNotIn(b"bounded-short-token", raw)
            self.assertNotIn(b"must never reach the browser", raw)

    def test_instagram_long_lived_rejection_returns_phase_specific_redirect(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.url.host == "api.instagram.com":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "instagram-short-token",
                        "user_id": 123,
                    },
                )
            if request.url.path == "/access_token":
                self.assertEqual(request.method, "GET")
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer instagram-short-token",
                )
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "type": "OAuthException",
                            "code": 190,
                            "message": "must never reach the browser",
                        }
                    },
                )
            raise AssertionError("profile must not be called")

        app = self.app(handler)
        with TestClient(app, follow_redirects=False) as client:
            csrf = open_session(client, ADMIN_KEY)
            start = client.post(
                "/api/v1/social-channels/instagram/oauth/start",
                headers={"X-CSRF-Token": csrf},
            )
            state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
            callback = client.get(
                "/api/v1/social-channels/instagram/oauth/callback",
                params={"state": state, "code": "instagram-code"},
            )
            self.assertEqual(callback.status_code, 303)
            self.assertEqual(
                callback.headers["location"],
                "/?social_channel=instagram&status=error&error=instagram_long_lived_exchange_rejected",
            )
            channel = client.get(
                "/api/v1/social-channels/instagram"
            ).json()["channel"]
            self.assertEqual(channel["connection_state"], "not_connected")
            self.assertIsNone(channel["connected_account"])
            self.assertEqual(len(calls), 2)
            serialized = json.dumps(channel)
            self.assertNotIn("must never reach the browser", serialized)
            self.assertNotIn("instagram-short-token", self.database.read_text(errors="ignore"))

    def test_x_rejection_returns_actionable_sanitized_phase(self):
        def rejected(request):
            return httpx.Response(
                403,
                text="callback rejected {} {}".format(X_SECRET, IG_SECRET),
            )

        with TestClient(self.app(rejected)) as client:
            csrf = open_session(client, ADMIN_KEY)
            response = client.post(
                "/api/v1/social-channels/x/oauth/start",
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()["code"], "social_provider_rejected")
            self.assertIn("callback exacta", response.json()["detail"])
            serialized = json.dumps(response.json())
            self.assertNotIn(X_SECRET, serialized)
            self.assertNotIn(IG_SECRET, serialized)

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


    def test_expired_instagram_bootstrap_is_present_but_requires_new_oauth(self):
        bootstrap = environment()
        bootstrap.update(
            {
                "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-alpha",
                "AGENCY_INSTAGRAM_ACCESS_TOKEN": "expired-instagram-token",
                "AGENCY_INSTAGRAM_ACCOUNT_ID": "ig-expired-001",
                "AGENCY_INSTAGRAM_ACCOUNT_USERNAME": "expired.instagram",
                "AGENCY_INSTAGRAM_TOKEN_EXPIRES_AT": "2020-01-01T00:00:00+00:00",
            }
        )
        no_http = lambda request: (_ for _ in ()).throw(
            AssertionError("no provider HTTP")
        )
        with TestClient(self.app(no_http, bootstrap)) as client:
            open_session(client, ADMIN_KEY)
            channel = client.get(
                "/api/v1/social-channels/instagram"
            ).json()["channel"]
            self.assertEqual(channel["connection_state"], "not_connected")
            self.assertIsNone(channel["connected_account"])
            self.assertTrue(channel["oauth_start_available"])
            self.assertFalse(channel["publishing_available"])
            self.assertFalse(channel["external_effects_enabled"])
        self.assertNotIn(b"expired-instagram-token", self.database.read_bytes())

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

    def test_social_oauth_requires_lax_session_cookie_for_cross_site_callback(self):
        with self.assertRaisesRegex(ValueError, "COOKIE_SAMESITE=lax"):
            create_app(
                database_path=str(self.database),
                identity_credentials=identities(),
                session_cookie_secure=True,
                session_cookie_samesite="strict",
                social_environment=environment(),
                social_oauth_transport=httpx.MockTransport(
                    lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
                ),
            )

    def test_social_session_cookie_is_secure_lax_for_oauth_return(self):
        no_http = lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
        with TestClient(
            create_app(
                database_path=str(self.database),
                identity_credentials=identities(),
                session_cookie_secure=True,
                session_cookie_samesite="lax",
                social_environment=environment(),
                social_oauth_transport=httpx.MockTransport(no_http),
            ),
            base_url="https://agency.example",
        ) as client:
            opened = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY})
            self.assertEqual(opened.status_code, 201)
            cookie = opened.headers["set-cookie"].lower()
            self.assertIn("secure", cookie)
            self.assertIn("httponly", cookie)
            self.assertIn("samesite=lax", cookie)

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
