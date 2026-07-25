import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app
from agency_runtime.social_publication_store import SocialPublicationIntent


ADMIN_KEY = "publication-admin-key-material-2026"
VIEWER_KEY = "publication-viewer-key-material-2026"
POLITICAL_APPROVER_KEY = "publication-political-approver-key-2026"
X_SECRET = "publication-x-consumer-secret-must-not-leak"
X_ACCESS_TOKEN = "publication-x-access-token-must-not-leak"
X_ACCESS_SECRET = "publication-x-access-secret-must-not-leak"


def encryption_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def identities():
    return [
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "publication-admin",
            "role": "admin",
            "key_id": "publication-admin-v1",
            "api_key": ADMIN_KEY,
            "active": True,
        },
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "publication-viewer",
            "role": "viewer",
            "key_id": "publication-viewer-v1",
            "api_key": VIEWER_KEY,
            "active": True,
        },
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "publication-political-approver",
            "role": "admin",
            "key_id": "publication-political-approver-v1",
            "api_key": POLITICAL_APPROVER_KEY,
            "active": True,
        },
    ]


def environment(*, enabled=True, political_enabled=False):
    return {
        "AGENCY_X_CONSUMER_KEY": "publication-x-consumer-key",
        "AGENCY_X_CONSUMER_SECRET": X_SECRET,
        "AGENCY_X_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback",
        "AGENCY_INSTAGRAM_APP_ID": "publication-instagram-app-id",
        "AGENCY_INSTAGRAM_APP_SECRET": "publication-instagram-secret",
        "AGENCY_INSTAGRAM_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/instagram/oauth/callback",
        "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps(
            {"social-v1": encryption_key()}
        ),
        "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "social-v1",
        "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true" if enabled else "false",
        "AGENCY_POLITICAL_PUBLICATION_ENABLED": (
            "true" if political_enabled else "false"
        ),
        "AGENCY_POLITICAL_CONTENT_ENABLED": "true",
        "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-alpha",
        "AGENCY_X_USER_ACCESS_TOKEN": X_ACCESS_TOKEN,
        "AGENCY_X_USER_ACCESS_TOKEN_SECRET": X_ACCESS_SECRET,
        "AGENCY_X_ACCOUNT_ID": "x-account-001",
        "AGENCY_X_ACCOUNT_USERNAME": "publication_x",
        "AGENCY_INSTAGRAM_ACCESS_TOKEN": "publication-instagram-token",
        "AGENCY_INSTAGRAM_ACCOUNT_ID": "instagram-account-001",
        "AGENCY_INSTAGRAM_ACCOUNT_USERNAME": "publication.instagram",
    }


def open_session(client: TestClient, api_key=ADMIN_KEY):
    response = client.post("/api/v1/sessions", json={"api_key": api_key})
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["csrf_token"]


BRIEF = {
    "title": "Exact-once social campaign",
    "objective": "Publish one approved artifact with a durable provider receipt",
    "audience": "campaign operators",
    "platforms": ["x", "instagram"],
    "budget_cents": 0,
    "campaign_goal": "verification",
}


class SocialPublicationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def app(self, handler, *, enabled=True, political_enabled=False):
        no_oauth_http = lambda request: (_ for _ in ()).throw(
            AssertionError("OAuth HTTP is not expected")
        )
        return create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            social_environment=environment(
                enabled=enabled, political_enabled=political_enabled
            ),
            social_oauth_transport=httpx.MockTransport(no_oauth_http),
            social_publication_transport=httpx.MockTransport(handler),
        )

    def approved_run(self, client: TestClient, csrf: str, suffix="001"):
        created = client.post(
            "/api/v1/runs",
            json=dict(BRIEF, title="{} {}".format(BRIEF["title"], suffix)),
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "publication-run-{}".format(suffix),
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        run = created.json()
        approved = client.post(
            "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
            json={"reviewer": "publication-admin", "note": "approved"},
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "publication-greenlight-{}".format(suffix),
            },
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        completed = approved.json()
        copy_deck = next(
            item for item in completed["artifacts"] if item["kind"] == "copy_deck"
        )
        return completed, copy_deck

    @staticmethod
    def publication_body(run, copy_deck):
        return {
            "artifact_id": copy_deck["artifact_id"],
            "greenlight_id": run["greenlight"]["greenlight_id"],
            "greenlight_fencing_token": run["greenlight"]["fencing_token"],
        }

    def test_general_publication_enablement_does_not_enable_political_effects(self):
        calls = []
        political_brief = {
            "title": "Political effect must remain separately gated",
            "objective": "Verify independent political publication authority",
            "audience": "citizens",
            "platforms": ["x"],
            "campaign_type": "political",
            "locale": "es-GT",
            "jurisdiction": "Guatemala",
            "office": "diputado",
            "candidate_name": "Candidatura de prueba",
            "locality": "Distrito de prueba",
            "problem": "Información legislativa dispersa",
            "proposal": "Publicar un informe mensual de iniciativas y votaciones",
            "desired_action": "Consulta el plan y envía tus preguntas",
            "disclosure": "Contenido orgánico de una candidatura de prueba; requiere aprobación humana",
            "legal_review_status": "approved",
            "evidence_claims": [
                {
                    "statement": "La propuesta incluye un informe mensual.",
                    "source": "Plan legislativo de prueba",
                    "locator": "sección 4",
                    "verification_status": "verified",
                }
            ],
        }
        app = self.app(
            lambda request: calls.append(request),
            enabled=True,
            political_enabled=False,
        )
        with TestClient(app) as client:
            csrf = open_session(client)
            created = client.post(
                "/api/v1/runs",
                json=political_brief,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "political-independent-run-001",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={"reviewer": "publication-admin", "note": "editorial approved"},
                headers={
                    "Authorization": "Bearer {}".format(POLITICAL_APPROVER_KEY),
                    "Idempotency-Key": "political-independent-greenlight-001",
                }
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(
                item for item in completed["artifacts"] if item["kind"] == "copy_deck"
            )
            response = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json=self.publication_body(completed, copy_deck),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "political-independent-effect-001",
                },
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "political_publication_disabled")
        self.assertEqual(calls, [])

    def test_x_publication_is_exact_once_and_server_derives_approved_copy(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertEqual(str(request.url), "https://api.x.com/2/tweets")
            payload = json.loads(request.content)
            self.assertIn("Exact-once social campaign 001", payload["text"])
            self.assertNotIn("client supplied", payload["text"])
            return httpx.Response(
                201,
                headers={"x-request-id": "provider-request-001"},
                json={"data": {"id": "x-post-001"}},
            )

        app = self.app(handler)
        with TestClient(app) as client:
            csrf = open_session(client)
            run, copy_deck = self.approved_run(client, csrf)
            body = self.publication_body(run, copy_deck)
            path = "/api/v1/runs/{}/social-publications/x".format(run["run_id"])
            first = client.post(
                path,
                json=body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-x-exact-once-001",
                },
            )
            self.assertEqual(first.status_code, 201, first.text)
            self.assertEqual(first.json()["provider_post_id"], "x-post-001")
            self.assertFalse(first.json()["replayed"])

            replay = client.post(
                path,
                json=body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-x-exact-once-001",
                },
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertTrue(replay.json()["replayed"])
            self.assertEqual(len(calls), 1)

            listed = client.get(
                "/api/v1/runs/{}/social-publications".format(run["run_id"])
            )
            self.assertEqual(listed.status_code, 200)
            publications = listed.json()["publications"]
            self.assertEqual(len(publications), 1)
            self.assertEqual(publications[0]["status"], "succeeded")
            serialized = json.dumps(publications, sort_keys=True)
            for forbidden in (
                X_SECRET,
                X_ACCESS_TOKEN,
                X_ACCESS_SECRET,
                "publish-x-exact-once-001",
                "Exact-once social campaign",
            ):
                self.assertNotIn(forbidden, serialized)

            audit = client.get("/api/v1/audit-events").json()["events"]
            success = [
                item
                for item in audit
                if item["action"] == "social.publication_succeeded"
            ]
            self.assertEqual(len(success), 1)
            self.assertEqual(success[0]["payload"]["provider_post_id"], "x-post-001")

    def test_replay_repairs_missing_success_audit_without_second_provider_call(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(
                201,
                headers={"x-request-id": "provider-request-audit-repair"},
                json={"data": {"id": "x-post-audit-repair"}},
            )

        app = self.app(handler)
        original_record = app.state.runtime_service.record_publication_event
        audit_attempts = []

        def fail_first_audit(**kwargs):
            audit_attempts.append(kwargs["intent_id"])
            if len(audit_attempts) == 1:
                raise RuntimeError("injected audit persistence failure")
            return original_record(**kwargs)

        app.state.runtime_service.record_publication_event = fail_first_audit
        with TestClient(app, raise_server_exceptions=False) as client:
            csrf = open_session(client)
            run, copy_deck = self.approved_run(client, csrf, suffix="audit-repair")
            body = self.publication_body(run, copy_deck)
            path = "/api/v1/runs/{}/social-publications/x".format(run["run_id"])
            headers = {
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "publish-audit-repair-001",
            }

            first = client.post(path, json=body, headers=headers)
            self.assertEqual(first.status_code, 500, first.text)
            self.assertEqual(len(calls), 1)

            replay = client.post(path, json=body, headers=headers)
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertTrue(replay.json()["replayed"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(audit_attempts), 2)

            audit = client.get("/api/v1/audit-events").json()["events"]
            success = [
                item
                for item in audit
                if item["action"] == "social.publication_succeeded"
                and item["resource_id"] == replay.json()["intent_id"]
            ]
            self.assertEqual(len(success), 1)
            self.assertEqual(
                success[0]["payload"]["provider_post_id"],
                "x-post-audit-repair",
            )

    def test_request_cannot_inject_copy_or_media_url(self):
        app = self.app(
            lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
        )
        with TestClient(app) as client:
            csrf = open_session(client)
            run, copy_deck = self.approved_run(client, csrf, suffix="inject")
            body = self.publication_body(run, copy_deck)
            body.update(
                {
                    "content": "client supplied copy",
                    "media_url": "https://evil.example/media.jpg",
                }
            )
            response = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json=body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-injection-001",
                },
            )
            self.assertEqual(response.status_code, 422)

    def test_disabled_route_and_non_admin_fail_before_provider_http(self):
        calls = []
        disabled = self.app(lambda request: calls.append(request), enabled=False)
        with TestClient(disabled) as client:
            csrf = open_session(client)
            run, copy_deck = self.approved_run(client, csrf, suffix="disabled")
            response = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json=self.publication_body(run, copy_deck),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-disabled-001",
                },
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "social_publication_unavailable")
        self.assertEqual(calls, [])

        enabled = self.app(lambda request: calls.append(request), enabled=True)
        with TestClient(enabled) as client:
            admin_csrf = open_session(client)
            run, copy_deck = self.approved_run(client, admin_csrf, suffix="viewer")
            client.delete(
                "/api/v1/sessions/current",
                headers={"X-CSRF-Token": admin_csrf},
            )
            viewer_csrf = open_session(client, VIEWER_KEY)
            denied = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json=self.publication_body(run, copy_deck),
                headers={
                    "X-CSRF-Token": viewer_csrf,
                    "Idempotency-Key": "publish-viewer-001",
                },
            )
            self.assertEqual(denied.status_code, 403)
        self.assertEqual(calls, [])

    def test_unknown_outcome_blocks_retry_until_manual_reconciliation(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503, text="ambiguous provider state")

        app = self.app(handler)
        with TestClient(app) as client:
            csrf = open_session(client)
            run, copy_deck = self.approved_run(client, csrf, suffix="unknown")
            body = self.publication_body(run, copy_deck)
            path = "/api/v1/runs/{}/social-publications/x".format(run["run_id"])
            unknown = client.post(
                path,
                json=body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-unknown-001",
                },
            )
            self.assertEqual(unknown.status_code, 503)
            self.assertEqual(unknown.json()["code"], "social_publication_unknown")
            listed = client.get(
                "/api/v1/runs/{}/social-publications".format(run["run_id"])
            ).json()["publications"]
            self.assertEqual(listed[0]["status"], "unknown")
            intent_id = listed[0]["intent_id"]

            blocked = client.post(
                path,
                json=body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-unknown-001",
                },
            )
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(blocked.json()["code"], "social_publication_blocked")
            self.assertEqual(len(calls), 1)

            reconciled = client.post(
                "/api/v1/social-publications/{}/reconcile".format(intent_id),
                json={
                    "provider_post_id": "x-reconciled-post-001",
                    "provider_request_id": "operator-evidence-001",
                    "note": "Verified in provider console by authorized operator",
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "reconcile-unknown-001",
                },
            )
            self.assertEqual(reconciled.status_code, 200, reconciled.text)
            self.assertEqual(reconciled.json()["status"], "succeeded")
            self.assertEqual(
                reconciled.json()["provider_post_id"], "x-reconciled-post-001"
            )

            replayed = client.post(
                "/api/v1/social-publications/{}/reconcile".format(intent_id),
                json={
                    "provider_post_id": "x-reconciled-post-001",
                    "provider_request_id": "operator-evidence-001",
                    "note": "Verified in provider console by authorized operator",
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "reconcile-unknown-compatible-002",
                },
            )
            self.assertEqual(replayed.status_code, 200, replayed.text)
            self.assertEqual(replayed.headers["X-Command-Replayed"], "true")

            conflict = client.post(
                "/api/v1/social-publications/{}/reconcile".format(intent_id),
                json={
                    "provider_post_id": "x-different-post-002",
                    "provider_request_id": "operator-evidence-002",
                    "note": "Conflicting provider evidence",
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "reconcile-unknown-001",
                },
            )
            self.assertEqual(conflict.status_code, 409, conflict.text)
            self.assertEqual(
                conflict.json()["code"],
                "social_publication_reconciliation_conflict",
            )

            metrics = client.get("/metrics").text
            self.assertIn(
                'agency_social_publications_total{outcome="unknown"} 1',
                metrics,
            )
            self.assertIn(
                'agency_social_publications_total{outcome="blocked"} 1',
                metrics,
            )
            self.assertIn(
                'agency_social_publications_total{outcome="reconciled"} 1',
                metrics,
            )
            self.assertIn(
                'agency_social_publications_total{outcome="replayed"} 1',
                metrics,
            )
            audit = client.get("/api/v1/audit-events").json()["events"]
            reconciliation_events = [
                item
                for item in audit
                if item["action"] == "social.publication_reconciled"
                and item["resource_id"] == intent_id
            ]
            self.assertEqual(len(reconciliation_events), 1)
            self.assertNotIn("tenant-alpha", metrics)
            self.assertNotIn("Approved campaign copy", metrics)
            self.assertNotIn(
                "Verified in provider console",
                json.dumps(reconciled.json(), sort_keys=True),
            )

    def pending_intent(self, run_id, intent_id, key, binding):
        now = "2026-07-23T20:30:00+00:00"
        return SocialPublicationIntent(
            intent_id=intent_id,
            tenant_id="tenant-alpha",
            channel_id="x",
            account_id="x-account-001",
            run_id=run_id,
            artifact_id="copy-artifact-001",
            artifact_hash=hashlib.sha256(b"artifact").hexdigest(),
            content_hash=hashlib.sha256(b"content").hexdigest(),
            media_url_hash=None,
            media_hash=None,
            confirmation_hash=None,
            greenlight_id="greenlight-test-001",
            greenlight_fencing_token=0,
            budget_cents=0,
            idempotency_digest=hashlib.sha256(key.encode()).hexdigest(),
            binding_digest=hashlib.sha256(binding.encode()).hexdigest(),
            status="pending",
            execution_fencing_token=1,
            provider_container_id=None,
            provider_post_id=None,
            receipt={},
            failure_reason="",
            created_at=now,
            updated_at=now,
            completed_at=None,
            revoked_at=None,
        )

    def test_disconnect_revokes_pending_but_preserves_unknown_for_reconciliation(self):
        app = self.app(
            lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
        )
        with TestClient(app) as client:
            csrf = open_session(client)
            run, _ = self.approved_run(client, csrf, suffix="disconnect")
            store = app.state.runtime_service.publication_store
            pending = self.pending_intent(
                run["run_id"],
                "publication-pending-disconnect",
                "disconnect-pending-key",
                "disconnect-pending-binding",
            )
            unknown = self.pending_intent(
                run["run_id"],
                "publication-unknown-disconnect",
                "disconnect-unknown-key",
                "disconnect-unknown-binding",
            )
            store.reserve(pending)
            store.reserve(unknown)
            store.mark_unknown(
                "tenant-alpha",
                unknown.intent_id,
                1,
                "provider_outcome_unknown",
            )

            disconnected = client.delete(
                "/api/v1/social-channels/x/connection",
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(disconnected.status_code, 200, disconnected.text)
            self.assertEqual(
                store.get("tenant-alpha", pending.intent_id).status, "revoked"
            )
            self.assertEqual(
                store.get("tenant-alpha", unknown.intent_id).status, "unknown"
            )
            audit = client.get("/api/v1/audit-events").json()["events"]
            disconnect_event = next(
                item for item in audit if item["action"] == "social.disconnected"
            )
            self.assertEqual(
                disconnect_event["payload"]["pending_publication_intents_revoked"],
                1,
            )

    def test_greenlight_revocation_revokes_pending_publication_intent(self):
        app = self.app(
            lambda request: (_ for _ in ()).throw(AssertionError("no HTTP"))
        )
        with TestClient(app) as client:
            csrf = open_session(client)
            run, _ = self.approved_run(client, csrf, suffix="revoke")
            store = app.state.runtime_service.publication_store
            pending = self.pending_intent(
                run["run_id"],
                "publication-pending-revoke",
                "revoke-pending-key",
                "revoke-pending-binding",
            )
            store.reserve(pending)

            revoked = client.post(
                "/api/v1/runs/{}/greenlight/revoke".format(run["run_id"]),
                json={
                    "reviewer": "publication-admin",
                    "reason": "Campaign authorization withdrawn",
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publication-greenlight-revoke-001",
                },
            )
            self.assertEqual(revoked.status_code, 200, revoked.text)
            self.assertEqual(revoked.json()["status"], "revoked")
            self.assertEqual(
                store.get("tenant-alpha", pending.intent_id).status, "revoked"
            )
            audit = client.get("/api/v1/audit-events").json()["events"]
            publication_revocation = next(
                item
                for item in audit
                if item["action"] == "social.publication_intents_revoked"
            )
            self.assertEqual(
                publication_revocation["payload"]["pending_intents_revoked"], 1
            )

    def test_instagram_without_approved_media_is_blocked_before_http(self):
        calls = []
        app = self.app(lambda request: calls.append(request))
        with TestClient(app) as client:
            csrf = open_session(client)
            run, copy_deck = self.approved_run(client, csrf, suffix="instagram")
            response = client.post(
                "/api/v1/runs/{}/social-publications/instagram".format(
                    run["run_id"]
                ),
                json=self.publication_body(run, copy_deck),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "publish-instagram-no-media-001",
                },
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "social_publication_unavailable")
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
