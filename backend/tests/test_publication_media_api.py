import base64
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from agency_runtime.api import create_app

ADMIN_KEY = "media-admin-key-material-2026"
FIXTURE = Path(__file__).parent / "fixtures" / "publication-media-320x400.jpg"
def alt_header(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def signing_keys(**keys: int) -> str:
    return json.dumps({
        key_id: base64.urlsafe_b64encode(bytes([value]) * 32).rstrip(b"=").decode("ascii")
        for key_id, value in keys.items()
    })


BRIEF = {
    "title": "Governed media upload",
    "objective": "Attach exact image bytes before Greenlight",
    "audience": "campaign operators",
    "platforms": ["instagram"],
}


def identities():
    return [{
        "tenant_id": "tenant-alpha",
        "subject_id": "media-admin",
        "role": "admin",
        "key_id": "media-admin-v1",
        "api_key": ADMIN_KEY,
        "active": True,
    }]


class PublicationMediaApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"
        self.app = create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            public_media_base_url="https://media.example.test",
            public_media_signing_key="test-public-media-signing-key-32-bytes-minimum",
            social_environment={},
        )

    def tearDown(self):
        self.temp.cleanup()

    def publication_app(self, handler):
        encryption_key = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")
        environment = {
            "AGENCY_INSTAGRAM_APP_ID": "publication-instagram-app-id",
            "AGENCY_INSTAGRAM_APP_SECRET": "publication-instagram-secret",
            "AGENCY_INSTAGRAM_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback",
            "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps({"social-v1": encryption_key}),
            "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "social-v1",
            "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true",
            "AGENCY_POLITICAL_PUBLICATION_ENABLED": "false",
            "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-alpha",
            "AGENCY_INSTAGRAM_ACCESS_TOKEN": "publication-instagram-token",
            "AGENCY_INSTAGRAM_ACCOUNT_ID": "instagram-account-001",
            "AGENCY_INSTAGRAM_ACCOUNT_USERNAME": "publication.instagram",
        }
        no_oauth_http = lambda request: (_ for _ in ()).throw(
            AssertionError("OAuth HTTP is not expected")
        )
        return create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            public_media_base_url="https://media.example.test",
            public_media_signing_key="test-public-media-signing-key-32-bytes-minimum",
            social_environment=environment,
            social_oauth_transport=httpx.MockTransport(no_oauth_http),
            social_publication_transport=httpx.MockTransport(handler),
        )

    def test_public_media_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            create_app(
                database_path=str(Path(self.temp.name) / "missing-key.sqlite3"),
                identity_credentials=identities(),
                session_cookie_secure=False,
                public_media_base_url="https://media.example.test",
                public_media_signing_key="",
                social_environment={},
            )
        with self.assertRaises(ValueError):
            create_app(
                database_path=str(Path(self.temp.name) / "weak-key.sqlite3"),
                identity_credentials=identities(),
                session_cookie_secure=False,
                public_media_base_url="https://media.example.test",
                public_media_signing_key="too-short",
                social_environment={},
            )
        with self.assertRaises(ValueError):
            create_app(
                database_path=str(Path(self.temp.name) / "partial-keyring.sqlite3"),
                identity_credentials=identities(),
                session_cookie_secure=False,
                public_media_base_url="https://media.example.test",
                public_media_signing_keys_json=signing_keys(**{"media-v1": 1}),
                public_media_active_signing_key_id="",
                social_environment={},
            )
        with self.assertRaises(ValueError):
            create_app(
                database_path=str(Path(self.temp.name) / "ambiguous-keyring.sqlite3"),
                identity_credentials=identities(),
                session_cookie_secure=False,
                public_media_base_url="https://media.example.test",
                public_media_signing_key="test-public-media-signing-key-32-bytes-minimum",
                public_media_signing_keys_json=signing_keys(**{"media-v1": 1}),
                public_media_active_signing_key_id="media-v1",
                social_environment={},
            )
        with self.assertRaises(ValueError):
            create_app(
                database_path=str(Path(self.temp.name) / "insecure-url.sqlite3"),
                identity_credentials=identities(),
                session_cookie_secure=False,
                public_media_base_url="http://media.example.test",
                public_media_signing_key="test-public-media-signing-key-32-bytes-minimum",
                social_environment={},
            )

    def test_upload_attaches_immutable_artifact_and_public_route_returns_exact_bytes(self):
        raw = FIXTURE.read_bytes()
        with TestClient(self.app) as client:
            session = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY})
            csrf = session.json()["csrf_token"]
            created = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "media-run-0001"},
            )
            run = created.json()
            uploaded = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "media-upload-0001",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta de prueba con fondo azul oscuro."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            updated = uploaded.json()
            media = next(item for item in updated["artifacts"] if item["kind"] == "publication_media")
            self.assertEqual(media["payload"]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(media["payload"]["width"], 320)
            self.assertEqual(media["payload"]["height"], 400)
            self.assertEqual(media["payload"]["rights_attested_by"], "media-admin")
            public_path = urlsplit(media["payload"]["media_url"]).path
            fetched = client.get(public_path)
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.content, raw)
            self.assertEqual(fetched.headers["content-type"], "image/jpeg")
            self.assertEqual(fetched.headers["cache-control"], "public, max-age=300")
            self.assertNotIn("immutable", fetched.headers["cache-control"])
            self.assertEqual(
                fetched.headers["etag"],
                '"{}"'.format(hashlib.sha256(raw).hexdigest()),
            )
            replay = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "media-upload-0001",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta de prueba con fondo azul oscuro."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(
                len([item for item in replay.json()["artifacts"] if item["kind"] == "publication_media"]),
                1,
            )

    def test_signing_key_rotation_preserves_old_binding_and_uses_new_active_key(self):
        raw = FIXTURE.read_bytes()
        app_v1 = create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            public_media_base_url="https://media.example.test",
            public_media_signing_keys_json=signing_keys(**{"media-v1": 1}),
            public_media_active_signing_key_id="media-v1",
            social_environment={},
        )
        with TestClient(app_v1) as client:
            csrf = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY}).json()["csrf_token"]
            created = client.post(
                "/api/v1/runs", json=dict(BRIEF, title="Rotating media key v1"),
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rotation-run-v1"},
            )
            run = created.json()
            first = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram", content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "rotation-upload-v1",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta para rotación v1."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(first.status_code, 201, first.text)
            first_media = next(x for x in first.json()["artifacts"] if x["kind"] == "publication_media")
            first_url = first_media["payload"]["media_url"]

        app_v2 = create_app(
            database_path=str(self.database),
            identity_credentials=identities(), session_cookie_secure=False,
            public_media_base_url="https://media.example.test",
            public_media_signing_keys_json=signing_keys(**{"media-v1": 1, "media-v2": 2}),
            public_media_active_signing_key_id="media-v2", social_environment={},
        )
        with TestClient(app_v2) as client:
            csrf = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY}).json()["csrf_token"]
            replay = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram", content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "rotation-upload-v1-second-command",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta para rotación v1."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            replay_media = next(x for x in replay.json()["artifacts"] if x["kind"] == "publication_media")
            self.assertEqual(replay_media["payload"]["media_url"], first_url)
            row = app_v2.state.runtime_service.media_store.get("tenant-alpha", replay_media["payload"]["media_id"])
            assert row is not None
            self.assertEqual(row.public_signing_key_id, "media-v1")

            second_run = client.post(
                "/api/v1/runs", json=dict(BRIEF, title="Rotating media key v2"),
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rotation-run-v2"},
            ).json()
            second = client.post(
                f"/api/v1/runs/{second_run['run_id']}/publication-media/instagram", content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "rotation-upload-v2",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta para rotación v2."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(second.status_code, 201, second.text)
            second_media = next(x for x in second.json()["artifacts"] if x["kind"] == "publication_media")
            second_row = app_v2.state.runtime_service.media_store.get("tenant-alpha", second_media["payload"]["media_id"])
            assert second_row is not None
            self.assertEqual(second_row.public_signing_key_id, "media-v2")

        app_without_old = create_app(
            database_path=str(self.database), identity_credentials=identities(),
            session_cookie_secure=False, public_media_base_url="https://media.example.test",
            public_media_signing_keys_json=signing_keys(**{"media-v2": 2}),
            public_media_active_signing_key_id="media-v2", social_environment={},
        )
        with TestClient(app_without_old) as client:
            csrf = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY}).json()["csrf_token"]
            blocked = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram", content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "rotation-upload-v1-missing-key",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta para rotación v1."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(blocked.status_code, 503, blocked.text)
            self.assertEqual(blocked.json()["code"], "publication_media_unavailable")
            self.assertNotIn("media-v1", blocked.text)

    def test_upload_greenlight_publish_verify_and_replay(self):
        calls = []
        published_caption = ""

        def handler(request):
            nonlocal published_caption
            calls.append(request)
            self.assertEqual(
                request.headers["Authorization"],
                "Bearer publication-instagram-token",
            )
            if request.method == "POST" and request.url.path.endswith("/media"):
                self.assertTrue(request.url.path.startswith("/v24.0/"))
                body = request.content.decode("utf-8")
                self.assertTrue(request.headers["Content-Type"].startswith("multipart/form-data;"))
                published_caption = body.split('name="caption"\r\n\r\n', 1)[1].split("\r\n--", 1)[0]
                image_url = body.split('name="image_url"\r\n\r\n', 1)[1].split("\r\n--", 1)[0]
                self.assertTrue(image_url.startswith("https://media.example.test/"))
                return httpx.Response(200, json={"id": "ig-container-verified-api"})
            if request.method == "GET" and request.url.path.endswith("/ig-container-verified-api"):
                return httpx.Response(200, json={"status_code": "FINISHED", "status": "ready"})
            if request.method == "POST" and request.url.path.endswith("/media_publish"):
                return httpx.Response(200, json={"id": "ig-post-verified-api"})
            if request.method == "GET" and request.url.path.endswith("/ig-post-verified-api"):
                return httpx.Response(
                    200,
                    headers={"x-fb-trace-id": "verify-api-request"},
                    json={
                        "id": "ig-post-verified-api",
                        "caption": published_caption,
                        "media_type": "IMAGE",
                        "permalink": "https://www.instagram.com/p/ig-post-verified-api/",
                        "timestamp": "2026-07-25T08:20:00+00:00",
                        "username": "publication.instagram",
                    },
                )
            raise AssertionError("unexpected provider request {}".format(request.url))

        app = self.publication_app(handler)
        raw = FIXTURE.read_bytes()
        with TestClient(app) as client:
            csrf = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY}).json()["csrf_token"]
            created = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Verified Instagram publication"),
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "verified-media-run-0001"},
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            uploaded = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "verified-media-upload-0001",
                    "X-Media-Alt-Text-Base64": alt_header("Tarjeta azul de verificación de publicación."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            media_run = uploaded.json()
            approved = client.post(
                f"/api/v1/runs/{run['run_id']}/greenlight/approve",
                json={"reviewer": "media-admin", "note": "copy and media approved"},
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "verified-media-greenlight-0001"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(item for item in completed["artifacts"] if item["kind"] == "copy_deck")
            media = next(item for item in completed["artifacts"] if item["kind"] == "publication_media")
            body = {
                "artifact_id": copy_deck["artifact_id"],
                "media_artifact_id": media["artifact_id"],
                "greenlight_id": completed["greenlight"]["greenlight_id"],
                "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
            }
            path = f"/api/v1/runs/{run['run_id']}/social-publications/instagram"
            first = client.post(
                path,
                json=body,
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "verified-instagram-publish-0001"},
            )
            self.assertEqual(first.status_code, 201, first.text)
            receipt = first.json()["receipt"]
            self.assertEqual(receipt["verification_status"], "verified")
            self.assertEqual(receipt["username"], "publication.instagram")
            self.assertEqual(receipt["media_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(
                receipt["permalink"],
                "https://www.instagram.com/p/ig-post-verified-api/",
            )
            replay = client.post(
                path,
                json=body,
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "verified-instagram-publish-0001"},
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertEqual(replay.json()["provider_post_id"], "ig-post-verified-api")
        self.assertEqual(len(calls), 4)

    def test_instagram_code_190_invalidates_connection_and_requires_reauthorization(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertTrue(request.url.path.endswith("/media"))
            return httpx.Response(
                401,
                json={
                    "error": {
                        "message": "provider message must not be persisted",
                        "type": "OAuthException",
                        "code": 190,
                        "error_subcode": 0,
                    }
                },
            )

        app = self.publication_app(handler)
        raw = FIXTURE.read_bytes()
        with TestClient(app) as client:
            csrf = client.post(
                "/api/v1/sessions",
                json={"api_key": ADMIN_KEY},
            ).json()["csrf_token"]
            created = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Expired Instagram authorization"),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-authorization-run-0001",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            uploaded = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-authorization-media-0001",
                    "X-Media-Alt-Text-Base64": alt_header(
                        "Tarjeta para probar una autorización expirada."
                    ),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            approved = client.post(
                f"/api/v1/runs/{run['run_id']}/greenlight/approve",
                json={"reviewer": "media-admin", "note": "approved"},
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-authorization-greenlight-0001",
                },
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(
                item
                for item in completed["artifacts"]
                if item["kind"] == "copy_deck"
            )
            media = next(
                item
                for item in completed["artifacts"]
                if item["kind"] == "publication_media"
            )
            response = client.post(
                f"/api/v1/runs/{run['run_id']}/social-publications/instagram",
                json={
                    "artifact_id": copy_deck["artifact_id"],
                    "media_artifact_id": media["artifact_id"],
                    "greenlight_id": completed["greenlight"]["greenlight_id"],
                    "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-authorization-publish-0001",
                },
            )
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(
                response.json()["code"],
                "social_connection_reauthorization_required",
            )
            channel = client.get(
                "/api/v1/social-channels/instagram"
            ).json()["channel"]
            self.assertEqual(channel["connection_state"], "not_connected")
            self.assertIsNone(channel["connected_account"])
            self.assertTrue(channel["oauth_start_available"])
            publications = client.get(
                f"/api/v1/runs/{run['run_id']}/social-publications"
            ).json()["publications"]
            self.assertEqual(len(publications), 1)
            self.assertEqual(publications[0]["status"], "failed")
            self.assertEqual(
                publications[0]["failure_reason"],
                "provider_rejected:instagram_container_create:401:190:0:OAuthException",
            )
            audit = client.get("/api/v1/audit-events").json()["events"]
            self.assertIn(
                "social.reauthorization_required",
                [event["action"] for event in audit],
            )
        self.assertEqual(len(calls), 1)
        raw_database = self.database.read_bytes()
        self.assertNotIn(b"provider message must not be persisted", raw_database)
        self.assertNotIn(b"publication-instagram-token", raw_database)

    def test_media_route_allows_valid_body_over_global_limit_and_rejects_over_8_mib(self):
        image = Image.effect_noise((1080, 1350), 100).convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=95, subsampling=0)
        large_valid = output.getvalue()
        self.assertGreater(len(large_valid), 1024 * 1024)
        self.assertLess(len(large_valid), 8 * 1024 * 1024)

        with TestClient(self.app) as client:
            csrf = client.post(
                "/api/v1/sessions", json={"api_key": ADMIN_KEY}
            ).json()["csrf_token"]
            created = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="large governed media"),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "large-media-run-0001",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            accepted = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=large_valid,
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "large-media-upload-0001",
                    "X-Media-Alt-Text-Base64": alt_header("Imagen de ruido usada para validar el límite de carga."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(accepted.status_code, 201, accepted.text)
            oversized = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=b"x" * (8 * 1024 * 1024 + 1),
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "large-media-upload-oversized",
                    "X-Media-Alt-Text-Base64": alt_header("Debe ser rechazado por tamaño."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(oversized.status_code, 413, oversized.text)
            self.assertEqual(oversized.json()["code"], "request_too_large")

    def test_expired_approved_media_blocks_before_provider_http(self):
        provider_calls = []

        def handler(request):
            provider_calls.append(request)
            raise AssertionError("expired media must block before provider HTTP")

        app = self.publication_app(handler)
        raw = FIXTURE.read_bytes()
        with TestClient(app) as client:
            csrf = client.post(
                "/api/v1/sessions", json={"api_key": ADMIN_KEY}
            ).json()["csrf_token"]
            created = client.post(
                "/api/v1/runs",
                json=dict(BRIEF, title="Expired media preflight"),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-media-run-0001",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            uploaded = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg",
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-media-upload-0001",
                    "X-Media-Alt-Text-Base64": alt_header("Media que expirará antes del efecto."),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            approved = client.post(
                f"/api/v1/runs/{run['run_id']}/greenlight/approve",
                json={"reviewer": "media-admin", "note": "approved before expiry"},
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-media-greenlight-0001",
                },
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(
                item for item in completed["artifacts"] if item["kind"] == "copy_deck"
            )
            media = next(
                item for item in completed["artifacts"] if item["kind"] == "publication_media"
            )
            connection = sqlite3.connect(self.database)
            try:
                connection.execute(
                    "UPDATE publication_media_objects SET expires_at = ? WHERE media_id = ?",
                    ("2020-01-01T00:00:00+00:00", media["payload"]["media_id"]),
                )
                connection.commit()
            finally:
                connection.close()
            response = client.post(
                f"/api/v1/runs/{run['run_id']}/social-publications/instagram",
                json={
                    "artifact_id": copy_deck["artifact_id"],
                    "media_artifact_id": media["artifact_id"],
                    "greenlight_id": completed["greenlight"]["greenlight_id"],
                    "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "expired-media-publish-0001",
                },
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "social_publication_unavailable")
        self.assertEqual(provider_calls, [])

    def test_missing_rights_invalid_bytes_and_post_greenlight_upload_are_blocked(self):
        raw = FIXTURE.read_bytes()
        with TestClient(self.app) as client:
            session = client.post("/api/v1/sessions", json={"api_key": ADMIN_KEY})
            csrf = session.json()["csrf_token"]
            created = client.post(
                "/api/v1/runs", json=dict(BRIEF, title="blocked media"),
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "media-run-0002"},
            )
            run = created.json()
            missing = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "media-upload-missing-rights",
                    "X-Media-Alt-Text-Base64": alt_header("Accessible text"),
                },
            )
            self.assertEqual(missing.status_code, 422)
            invalid = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=b"invalid",
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "media-upload-invalid",
                    "X-Media-Alt-Text-Base64": alt_header("Accessible text"),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(invalid.status_code, 422)
            valid = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "media-upload-before-greenlight",
                    "X-Media-Alt-Text-Base64": alt_header("Accessible text"),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(valid.status_code, 201, valid.text)
            approved = client.post(
                f"/api/v1/runs/{run['run_id']}/greenlight/approve",
                json={"reviewer": "media-admin", "note": "approved"},
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "media-greenlight-0002"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            late = client.post(
                f"/api/v1/runs/{run['run_id']}/publication-media/instagram",
                content=raw,
                headers={
                    "Content-Type": "image/jpeg", "X-CSRF-Token": csrf,
                    "Idempotency-Key": "media-upload-after-greenlight",
                    "X-Media-Alt-Text-Base64": alt_header("Accessible text"),
                    "X-Media-Rights-Confirmed": "true",
                },
            )
            self.assertEqual(late.status_code, 409)


if __name__ == "__main__":
    unittest.main()
