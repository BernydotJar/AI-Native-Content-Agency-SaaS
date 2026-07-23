import base64
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from agency_runtime.social_channels import SocialChannelRegistry
from agency_runtime.social_oauth import SocialTokenCipher
from agency_runtime.social_oauth_service import (
    SocialOAuthCallbackError,
    SocialOAuthProviderError,
    SocialOAuthService,
)
from agency_runtime.social_oauth_store import SQLiteSocialOAuthStore


X_KEY = "x-consumer-key"
X_SECRET = "x-consumer-secret-must-not-leak"
IG_ID = "instagram-app-id"
IG_SECRET = "instagram-app-secret-must-not-leak"


def encryption_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def environment():
    return {
        "AGENCY_X_CONSUMER_KEY": X_KEY,
        "AGENCY_X_CONSUMER_SECRET": X_SECRET,
        "AGENCY_X_REDIRECT_URI": "https://agency.example/api/v1/social-channels/x/oauth/callback",
        "AGENCY_INSTAGRAM_APP_ID": IG_ID,
        "AGENCY_INSTAGRAM_APP_SECRET": IG_SECRET,
        "AGENCY_INSTAGRAM_REDIRECT_URI": "https://agency.example/api/v1/social-channels/instagram/oauth/callback",
    }


class SequenceFactory:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        if not self.values:
            raise AssertionError("deterministic sequence exhausted")
        return self.values.pop(0)


class SocialOAuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.store = SQLiteSocialOAuthStore(self.path)
        self.registry = SocialChannelRegistry.from_environment(environment())
        self.cipher = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": encryption_key()}), "social-v1"
        )
        self.services = []

    def tearDown(self):
        for service in self.services:
            service.close()
        self.store.close()
        self.temp.cleanup()

    def service(self, handler, *, states=("S" * 43,), nonces=("nonce-001", "nonce-002")):
        service = SocialOAuthService(
            registry=self.registry,
            store=self.store,
            cipher=self.cipher,
            transport=httpx.MockTransport(handler),
            clock=lambda: "2026-07-23T07:00:00+00:00",
            token_factory=SequenceFactory(*states),
            oauth_nonce_factory=SequenceFactory(*nonces),
            timestamp_factory=lambda: 1784790000,
        )
        self.services.append(service)
        return service

    def test_x_three_legged_oauth_connects_once_without_exposing_secrets(self):
        requests = []

        def handler(request):
            requests.append(request)
            authorization = request.headers["Authorization"]
            self.assertTrue(authorization.startswith("OAuth "))
            self.assertNotIn(X_SECRET, authorization)
            self.assertNotIn("request-token-secret", authorization)
            if request.url.path == "/oauth/request_token":
                self.assertIn("oauth_callback", authorization)
                return httpx.Response(
                    200,
                    text=(
                        "oauth_token=request-token&oauth_token_secret=request-token-secret"
                        "&oauth_callback_confirmed=true"
                    ),
                )
            if request.url.path == "/oauth/access_token":
                self.assertIn("oauth_verifier", authorization)
                return httpx.Response(
                    200,
                    text=(
                        "oauth_token=user-access-token&oauth_token_secret=user-access-secret"
                        "&user_id=123456&screen_name=agency_account"
                    ),
                )
            raise AssertionError("unexpected request {}".format(request.url))

        service = self.service(handler)
        started = service.start(
            tenant_id="tenant-alpha", session_id="session-alpha", channel_id="x"
        )
        self.assertEqual(started.channel_id, "x")
        self.assertEqual(
            parse_qs(urlsplit(started.authorization_url).query)["oauth_token"],
            ["request-token"],
        )
        connected = service.complete_x(
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            oauth_token="request-token",
            oauth_verifier="verifier-001",
        )
        self.assertEqual(connected.account_id, "123456")
        self.assertEqual(connected.account_username, "agency_account")
        self.assertEqual(len(requests), 2)

        with self.assertRaises(SocialOAuthCallbackError):
            service.complete_x(
                tenant_id="tenant-alpha",
                session_id="session-alpha",
                oauth_token="request-token",
                oauth_verifier="verifier-001",
            )
        self.assertEqual(len(requests), 2)
        raw = self.path.read_bytes()
        for forbidden in (
            X_SECRET.encode(),
            b"request-token-secret",
            b"user-access-token",
            b"user-access-secret",
        ):
            self.assertNotIn(forbidden, raw)

    def test_instagram_authorization_code_connects_professional_account(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.host == "api.instagram.com":
                body = request.content.decode("utf-8")
                self.assertIn("grant_type=authorization_code", body)
                self.assertIn("code=instagram-code-001", body)
                return httpx.Response(
                    200,
                    json={
                        "access_token": "instagram-access-token",
                        "user_id": 987654,
                        "expires_in": 3600,
                    },
                )
            if request.url.host == "graph.instagram.com":
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer instagram-access-token",
                )
                return httpx.Response(
                    200,
                    json={
                        "id": "987654",
                        "username": "professional.account",
                        "account_type": "BUSINESS",
                    },
                )
            raise AssertionError("unexpected request {}".format(request.url))

        state = "instagram-state-value-000000000000000000000001"
        service = self.service(handler, states=(state,))
        started = service.start(
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            channel_id="instagram",
        )
        query = parse_qs(urlsplit(started.authorization_url).query)
        self.assertEqual(query["state"], [state])
        self.assertEqual(query["response_type"], ["code"])
        self.assertIn("instagram_business_content_publish", query["scope"][0])

        connected = service.complete_instagram(
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            state_value=state,
            code="instagram-code-001",
        )
        self.assertEqual(connected.account_id, "987654")
        self.assertEqual(connected.account_username, "professional.account")
        self.assertEqual(connected.token_expires_at, "2026-07-23T08:00:00+00:00")
        self.assertEqual(len(requests), 2)
        stored = service.connection("tenant-alpha", "instagram")
        self.assertEqual(stored.account_username, "professional.account")
        self.assertIsNone(service.connection("tenant-beta", "instagram"))

    def test_instagram_consumer_account_is_rejected_and_callback_cannot_replay(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.url.host == "api.instagram.com":
                return httpx.Response(200, json={"access_token": "ig-token", "user_id": 42})
            return httpx.Response(
                200,
                json={"id": "42", "username": "personal", "account_type": "PERSONAL"},
            )

        state = "instagram-state-value-000000000000000000000002"
        service = self.service(handler, states=(state,))
        service.start(
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            channel_id="instagram",
        )
        with self.assertRaisesRegex(SocialOAuthCallbackError, "Professional"):
            service.complete_instagram(
                tenant_id="tenant-alpha",
                session_id="session-alpha",
                state_value=state,
                code="code-personal",
            )
        self.assertIsNone(service.connection("tenant-alpha", "instagram"))
        with self.assertRaises(SocialOAuthCallbackError):
            service.complete_instagram(
                tenant_id="tenant-alpha",
                session_id="session-alpha",
                state_value=state,
                code="code-personal",
            )
        self.assertEqual(len(calls), 2)

    def test_provider_failure_is_sanitized_and_never_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(
                500,
                text="upstream leaked {} {}".format(X_SECRET, IG_SECRET),
            )

        service = self.service(handler)
        with self.assertRaisesRegex(
            SocialOAuthProviderError, "social provider rejected the request"
        ) as captured:
            service.start(
                tenant_id="tenant-alpha", session_id="session-alpha", channel_id="x"
            )
        rendered = str(captured.exception)
        self.assertNotIn(X_SECRET, rendered)
        self.assertNotIn(IG_SECRET, rendered)
        self.assertEqual(len(calls), 1)

    def test_disconnect_is_tenant_scoped(self):
        def handler(request):
            if request.url.path == "/oauth/request_token":
                return httpx.Response(
                    200,
                    text="oauth_token=t&oauth_token_secret=s&oauth_callback_confirmed=true",
                )
            return httpx.Response(
                200,
                text="oauth_token=a&oauth_token_secret=b&user_id=1&screen_name=user",
            )

        service = self.service(handler)
        service.start(tenant_id="tenant-alpha", session_id="session-alpha", channel_id="x")
        service.complete_x(
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            oauth_token="t",
            oauth_verifier="v",
        )
        self.assertFalse(service.disconnect("tenant-beta", "x"))
        self.assertIsNotNone(service.connection("tenant-alpha", "x"))
        self.assertTrue(service.disconnect("tenant-alpha", "x"))
        self.assertIsNone(service.connection("tenant-alpha", "x"))


if __name__ == "__main__":
    unittest.main()
