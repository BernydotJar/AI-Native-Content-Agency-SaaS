import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from agency_runtime.social_oauth import SocialTokenCipher
from agency_runtime.social_oauth_store import (
    SQLiteSocialOAuthStore,
    SocialConnectionRecord,
)
from agency_runtime.social_publication import (
    SocialPublicationAuthority,
    SocialPublicationBlockedError,
    SocialPublicationCommand,
    SocialPublicationProviderRejectedError,
    SocialPublicationUnavailableError,
    SocialPublicationUnknownError,
)
from agency_runtime.social_publication_store import (
    SQLiteSocialPublicationStore,
    SocialPublicationConflictError,
)


NOW = "2026-07-23T20:30:00+00:00"
X_CONSUMER_SECRET = "x-consumer-secret-must-not-leak"
X_ACCESS_TOKEN = "x-access-token-must-not-leak"
X_ACCESS_SECRET = "x-access-secret-must-not-leak"
IG_ACCESS_TOKEN = "instagram-access-token-must-not-leak"
MEDIA_URL = "https://cdn.example.test/governed-media.jpg"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def encryption_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def command(channel="x", **changes):
    values = {
        "tenant_id": "tenant-alpha",
        "channel_id": channel,
        "account_id": "account-x" if channel == "x" else "account-instagram",
        "run_id": "run-001",
        "artifact_id": "artifact-001",
        "artifact_hash": digest("approved-artifact"),
        "content": "Approved campaign copy",
        "media_url": None if channel == "x" else MEDIA_URL,
        "media_hash": None if channel == "x" else digest("governed-media"),
        "greenlight_id": "greenlight-001",
        "greenlight_fencing_token": 0,
        "budget_cents": 0,
        "idempotency_key": "publication-command-001",
    }
    values.update(changes)
    return SocialPublicationCommand(**values)


class FailingCompleteStore(SQLiteSocialPublicationStore):
    def complete(self, *args, **kwargs):
        raise OSError("simulated persistence failure after provider success")


class SocialPublicationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.connection_store = SQLiteSocialOAuthStore(self.path, clock=lambda: NOW)
        self.publication_store = SQLiteSocialPublicationStore(
            self.path, clock=lambda: NOW
        )
        self.cipher = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": encryption_key()}), "social-v1"
        )
        self._connect(
            "x",
            "account-x",
            "connected_x",
            {
                "access_token": X_ACCESS_TOKEN,
                "access_token_secret": X_ACCESS_SECRET,
            },
        )
        self._connect(
            "instagram",
            "account-instagram",
            "connected.instagram",
            {"access_token": IG_ACCESS_TOKEN},
        )
        self.authorities = []

    def tearDown(self):
        for authority in self.authorities:
            authority.close()
        self.publication_store.close()
        self.connection_store.close()
        self.temp.cleanup()

    def _connect(self, channel, account_id, username, tokens):
        encrypted = self.cipher.encrypt(
            tokens,
            associated_data="tenant-alpha:{}:connection".format(channel),
        )
        self.connection_store.upsert_connection(
            SocialConnectionRecord(
                tenant_id="tenant-alpha",
                channel_id=channel,
                account_id=account_id,
                account_username=username,
                encrypted_tokens=encrypted,
                scopes=("publish",),
                token_expires_at=None,
                connected_at=NOW,
                updated_at=NOW,
            )
        )

    def authority(self, handler, *, enabled=True, store=None, **options):
        authority = SocialPublicationAuthority(
            store=store or self.publication_store,
            connection_store=self.connection_store,
            cipher=self.cipher,
            x_consumer_key="x-consumer-key",
            x_consumer_secret=X_CONSUMER_SECRET,
            enabled=enabled,
            transport=httpx.MockTransport(handler),
            clock=lambda: NOW,
            nonce_factory=lambda: "publication-nonce-001",
            timestamp_factory=lambda: 1784838600,
            **options,
        )
        self.authorities.append(authority)
        return authority

    def test_disabled_authority_never_touches_store_or_transport(self):
        calls = []
        authority = self.authority(
            lambda request: calls.append(request), enabled=False
        )
        with self.assertRaises(SocialPublicationUnavailableError):
            authority.execute(command())
        self.assertEqual(calls, [])
        self.assertEqual(self.publication_store.list_for_run("tenant-alpha", "run-001"), ())

    def test_x_success_replays_receipt_without_second_post(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), "https://api.x.com/2/tweets")
            authorization = request.headers["Authorization"]
            self.assertTrue(authorization.startswith("OAuth "))
            self.assertNotIn(X_CONSUMER_SECRET, authorization)
            self.assertNotIn(X_ACCESS_SECRET, authorization)
            self.assertEqual(json.loads(request.content), {"text": "Approved campaign copy"})
            return httpx.Response(
                201,
                headers={"x-request-id": "x-request-001"},
                json={"data": {"id": "x-post-001", "text": "ignored"}},
            )

        authority = self.authority(handler)
        first = authority.execute(command())
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(first.provider_post_id, "x-post-001")
        self.assertFalse(first.replayed)
        second = authority.execute(command())
        self.assertTrue(second.replayed)
        self.assertEqual(second.provider_post_id, "x-post-001")
        self.assertEqual(len(calls), 1)
        serialized = json.dumps(second.public_dict(), sort_keys=True)
        for forbidden in (
            "Approved campaign copy",
            X_CONSUMER_SECRET,
            X_ACCESS_TOKEN,
            X_ACCESS_SECRET,
        ):
            self.assertNotIn(forbidden, serialized)

    def test_same_effect_with_different_idempotency_key_replays_without_second_post(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(201, json={"data": {"id": "x-post-binding-001"}})

        authority = self.authority(handler)
        first = authority.execute(command())
        second = authority.execute(
            command(idempotency_key="publication-command-different-key")
        )
        self.assertEqual(first.intent_id, second.intent_id)
        self.assertTrue(second.replayed)
        self.assertEqual(len(calls), 1)

    def test_same_idempotency_key_with_changed_content_conflicts_before_http(self):
        calls = []
        authority = self.authority(
            lambda request: calls.append(request)
            or httpx.Response(201, json={"data": {"id": "post-001"}})
        )
        authority.execute(command())
        with self.assertRaises(SocialPublicationConflictError):
            authority.execute(command(content="Changed approved copy"))
        self.assertEqual(len(calls), 1)

    def test_known_rejection_is_failed_and_never_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(
                400,
                text="provider leaked {} {}".format(
                    X_CONSUMER_SECRET, X_ACCESS_TOKEN
                ),
            )

        authority = self.authority(handler)
        with self.assertRaises(SocialPublicationProviderRejectedError) as rejected:
            authority.execute(command())
        self.assertEqual(rejected.exception.phase, "x_post_create")
        self.assertEqual(rejected.exception.status_code, 400)
        self.assertEqual(rejected.exception.provider_code, "")
        self.assertNotIn(X_CONSUMER_SECRET, str(rejected.exception))
        self.assertNotIn(X_ACCESS_TOKEN, str(rejected.exception))
        stored = self.publication_store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(stored.status, "failed")
        self.assertEqual(
            stored.failure_reason,
            "provider_rejected:x_post_create:400:none:none:none",
        )
        with self.assertRaises(SocialPublicationBlockedError) as blocked:
            authority.execute(command())
        self.assertEqual(blocked.exception.status, "failed")
        self.assertEqual(len(calls), 1)
        self.assertNotIn(X_CONSUMER_SECRET, str(blocked.exception))


    def test_instagram_rejection_exposes_only_safe_structured_diagnostics(self):
        leaked_message = "token={} media={}".format(IG_ACCESS_TOKEN, MEDIA_URL)

        def handler(request):
            self.assertTrue(request.url.path.endswith("/media"))
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": leaked_message,
                        "type": "OAuthException",
                        "code": 100,
                        "error_subcode": 2207052,
                        "fbtrace_id": "trace-must-not-be-copied",
                    }
                },
            )

        authority = self.authority(handler)
        with self.assertRaises(SocialPublicationProviderRejectedError) as rejected:
            authority.execute(command("instagram"))
        error = rejected.exception
        self.assertEqual(error.phase, "instagram_container_create")
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.provider_code, "100")
        self.assertEqual(error.provider_subcode, "2207052")
        self.assertEqual(error.error_type, "OAuthException")
        stored = self.publication_store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(
            stored.failure_reason,
            "provider_rejected:instagram_container_create:400:100:2207052:OAuthException",
        )
        serialized = repr(error.__dict__)
        self.assertNotIn(leaked_message, serialized)
        self.assertNotIn(IG_ACCESS_TOKEN, serialized)
        self.assertNotIn(MEDIA_URL, serialized)
        self.assertNotIn("trace-must-not-be-copied", serialized)

    def test_ambiguous_provider_failure_is_unknown_and_blocks_retry(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503, text="ambiguous upstream state")

        authority = self.authority(handler)
        with self.assertRaises(SocialPublicationUnknownError):
            authority.execute(command())
        stored = self.publication_store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(stored.status, "unknown")
        with self.assertRaises(SocialPublicationBlockedError) as blocked:
            authority.execute(command())
        self.assertEqual(blocked.exception.status, "unknown")
        self.assertEqual(len(calls), 1)

    def test_instagram_waits_for_container_and_verifies_published_media(self):
        calls = []
        sleeps = []
        status_reads = 0

        def handler(request):
            nonlocal status_reads
            calls.append(request)
            self.assertEqual(
                request.headers["Authorization"],
                "Bearer {}".format(IG_ACCESS_TOKEN),
            )
            self.assertTrue(request.url.path.startswith("/v24.0/"))
            if request.method == "POST" and request.url.path.endswith("/media"):
                body = request.content.decode("utf-8")
                self.assertIn('name="image_url"', body)
                self.assertIn(MEDIA_URL, body)
                self.assertIn('name="caption"', body)
                self.assertIn("Approved campaign copy", body)
                self.assertTrue(request.headers["Content-Type"].startswith("multipart/form-data;"))
                return httpx.Response(
                    200,
                    headers={"x-fb-trace-id": "ig-container-request"},
                    json={"id": "ig-container-001"},
                )
            if request.method == "GET" and request.url.path.endswith("/ig-container-001"):
                self.assertEqual(request.url.params["fields"], "status_code,status")
                status_reads += 1
                return httpx.Response(
                    200,
                    json={
                        "status_code": "IN_PROGRESS" if status_reads == 1 else "FINISHED",
                        "status": "processing" if status_reads == 1 else "published",
                    },
                )
            if request.method == "POST" and request.url.path.endswith("/media_publish"):
                self.assertEqual(request.url.params["creation_id"], "ig-container-001")
                self.assertEqual(request.content, b"")
                return httpx.Response(
                    200,
                    headers={"x-fb-trace-id": "ig-publish-request"},
                    json={"id": "ig-post-001"},
                )
            if request.method == "GET" and request.url.path.endswith("/ig-post-001"):
                self.assertEqual(
                    request.url.params["fields"],
                    "id,caption,media_type,permalink,timestamp,username",
                )
                return httpx.Response(
                    200,
                    json={
                        "id": "ig-post-001",
                        "caption": "Approved campaign copy",
                        "media_type": "IMAGE",
                        "permalink": "https://www.instagram.com/p/ig-post-001/",
                        "timestamp": "2026-07-23T20:31:00+00:00",
                        "username": "connected.instagram",
                    },
                )
            raise AssertionError("unexpected Instagram request {}".format(request.url))

        authority = self.authority(
            handler,
            instagram_container_poll_attempts=3,
            instagram_container_poll_interval_seconds=0.01,
            sleep=lambda seconds: sleeps.append(seconds),
        )
        result = authority.execute(command("instagram"))
        self.assertEqual(result.provider_container_id, "ig-container-001")
        self.assertEqual(result.provider_post_id, "ig-post-001")
        self.assertEqual(len(calls), 5)
        self.assertEqual(sleeps, [0.01])
        self.assertEqual(result.receipt["verification_status"], "verified")
        self.assertEqual(
            result.receipt["permalink"],
            "https://www.instagram.com/p/ig-post-001/",
        )
        self.assertEqual(result.receipt["username"], "connected.instagram")
        self.assertEqual(
            result.receipt["caption_sha256"], digest("Approved campaign copy")
        )
        self.assertEqual(result.receipt["media_sha256"], digest("governed-media"))
        serialized = json.dumps(result.public_dict(), sort_keys=True)
        self.assertNotIn("Approved campaign copy", serialized)
        raw = self.path.read_bytes()
        self.assertNotIn(MEDIA_URL.encode(), raw)
        self.assertNotIn(IG_ACCESS_TOKEN.encode(), raw)

    def test_instagram_container_terminal_error_fails_without_publish(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.method == "POST" and request.url.path.endswith("/media"):
                return httpx.Response(200, json={"id": "ig-container-error"})
            if request.method == "GET" and request.url.path.endswith("/ig-container-error"):
                return httpx.Response(
                    200, json={"status_code": "ERROR", "status": "invalid media"}
                )
            raise AssertionError("media_publish must not be called")

        authority = self.authority(handler, sleep=lambda seconds: None)
        with self.assertRaises(SocialPublicationProviderRejectedError) as rejected:
            authority.execute(command("instagram"))
        self.assertEqual(rejected.exception.phase, "instagram_container_status")
        self.assertEqual(rejected.exception.status_code, 200)
        self.assertEqual(rejected.exception.error_type, "container_error")
        self.assertEqual(len(calls), 2)
        stored = self.publication_store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(stored.status, "failed")

    def test_instagram_poll_exhaustion_is_unknown_and_blocks_retry(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.method == "POST" and request.url.path.endswith("/media"):
                return httpx.Response(200, json={"id": "ig-container-slow"})
            if request.method == "GET" and request.url.path.endswith("/ig-container-slow"):
                return httpx.Response(200, json={"status_code": "IN_PROGRESS"})
            raise AssertionError("media_publish must not be called")

        authority = self.authority(
            handler,
            instagram_container_poll_attempts=2,
            instagram_container_poll_interval_seconds=0,
            sleep=lambda seconds: None,
        )
        with self.assertRaises(SocialPublicationUnknownError):
            authority.execute(command("instagram"))
        self.assertEqual(len(calls), 3)
        stored = self.publication_store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(stored.status, "unknown")
        with self.assertRaises(SocialPublicationBlockedError):
            authority.execute(command("instagram"))
        self.assertEqual(len(calls), 3)

    def test_instagram_read_after_write_mismatch_is_unknown(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.method == "POST" and request.url.path.endswith("/media"):
                return httpx.Response(200, json={"id": "ig-container-mismatch"})
            if request.method == "GET" and request.url.path.endswith("/ig-container-mismatch"):
                return httpx.Response(200, json={"status_code": "FINISHED"})
            if request.method == "POST" and request.url.path.endswith("/media_publish"):
                return httpx.Response(200, json={"id": "ig-post-mismatch"})
            if request.method == "GET" and request.url.path.endswith("/ig-post-mismatch"):
                return httpx.Response(
                    200,
                    json={
                        "id": "ig-post-mismatch",
                        "caption": "Different provider caption",
                        "media_type": "IMAGE",
                        "permalink": "https://www.instagram.com/p/ig-post-mismatch/",
                        "timestamp": "2026-07-23T20:31:00+00:00",
                        "username": "connected.instagram",
                    },
                )
            raise AssertionError("unexpected request")

        authority = self.authority(handler, sleep=lambda seconds: None)
        with self.assertRaises(SocialPublicationUnknownError):
            authority.execute(command("instagram"))
        self.assertEqual(len(calls), 4)
        stored = self.publication_store.list_for_run("tenant-alpha", "run-001")[0]
        self.assertEqual(stored.status, "unknown")

    def test_persistence_failure_after_provider_success_blocks_replay_as_pending(self):
        failing_store = FailingCompleteStore(self.path, clock=lambda: NOW)
        self.addCleanup(failing_store.close)
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(201, json={"data": {"id": "x-post-uncertain"}})

        authority = self.authority(handler, store=failing_store)
        with self.assertRaises(SocialPublicationUnknownError):
            authority.execute(command())
        with self.assertRaises(SocialPublicationBlockedError) as blocked:
            authority.execute(command())
        self.assertIn(blocked.exception.status, {"pending", "unknown"})
        self.assertEqual(len(calls), 1)

    def test_instagram_graph_api_version_is_explicit_and_validated(self):
        calls = []

        def handler(request):
            calls.append(request)
            if request.method == "POST" and request.url.path.endswith("/media"):
                self.assertTrue(request.url.path.startswith("/v25.0/"))
                return httpx.Response(400, json={"error": {"code": 100}})
            raise AssertionError("unexpected request")

        authority = self.authority(
            handler,
            instagram_graph_api_version="v25.0",
        )
        with self.assertRaises(SocialPublicationProviderRejectedError):
            authority.execute(command("instagram"))
        self.assertEqual(len(calls), 1)

        with self.assertRaisesRegex(ValueError, "vN.N"):
            self.authority(
                lambda request: httpx.Response(200),
                instagram_graph_api_version="latest",
            )

    def test_wrong_connected_account_and_missing_x_app_credentials_fail_before_intent(self):
        authority = self.authority(
            lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
        )
        with self.assertRaises(SocialPublicationUnavailableError):
            authority.execute(command(account_id="other-account"))
        self.assertEqual(self.publication_store.list_for_run("tenant-alpha", "run-001"), ())

        missing = SocialPublicationAuthority(
            store=self.publication_store,
            connection_store=self.connection_store,
            cipher=self.cipher,
            x_consumer_key="",
            x_consumer_secret="",
            enabled=True,
            transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
            ),
        )
        self.authorities.append(missing)
        with self.assertRaises(SocialPublicationUnavailableError):
            missing.execute(command(idempotency_key="publication-command-002"))
        self.assertEqual(self.publication_store.list_for_run("tenant-alpha", "run-001"), ())


if __name__ == "__main__":
    unittest.main()
