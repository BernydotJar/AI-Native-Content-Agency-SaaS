import base64
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app


LEGAL_KEY = "political-legal-admin-key-material-2026"
APPROVER_KEY = "political-greenlight-admin-key-material-2026"


def auth(key: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer {}".format(key)}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def identities() -> list[dict[str, object]]:
    return [
        {
            "tenant_id": "tenant-political",
            "subject_id": "legal.reviewer@example.test",
            "role": "admin",
            "key_id": "political-legal-v1",
            "api_key": LEGAL_KEY,
            "active": True,
        },
        {
            "tenant_id": "tenant-political",
            "subject_id": "greenlight.approver@example.test",
            "role": "admin",
            "key_id": "political-approver-v1",
            "api_key": APPROVER_KEY,
            "active": True,
        },
    ]


def social_environment(
    *,
    content_enabled: bool,
    publication_enabled: bool = True,
    political_publication_enabled: bool = True,
    paid_enabled: bool = False,
) -> dict[str, str]:
    key = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")
    return {
        "AGENCY_POLITICAL_CONTENT_ENABLED": "true" if content_enabled else "false",
        "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true" if publication_enabled else "false",
        "AGENCY_POLITICAL_PUBLICATION_ENABLED": (
            "true" if political_publication_enabled else "false"
        ),
        "AGENCY_POLITICAL_PAID_MEDIA_ENABLED": "true" if paid_enabled else "false",
        "AGENCY_X_CONSUMER_KEY": "political-x-consumer-key",
        "AGENCY_X_CONSUMER_SECRET": "political-x-consumer-secret",
        "AGENCY_X_REDIRECT_URI": "http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback",
        "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON": json.dumps({"social-v1": key}),
        "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID": "social-v1",
        "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID": "tenant-political",
        "AGENCY_X_USER_ACCESS_TOKEN": "political-x-access-token",
        "AGENCY_X_USER_ACCESS_TOKEN_SECRET": "political-x-access-secret",
        "AGENCY_X_ACCOUNT_ID": "political-x-account",
        "AGENCY_X_ACCOUNT_USERNAME": "political_sandbox",
    }


def political_brief(*, mode: str = "organic", title: str = "Political compliance run") -> dict[str, object]:
    return {
        "title": title,
        "objective": "Verify a governed political publication flow",
        "audience": "citizens in a technical sandbox",
        "platforms": ["x"],
        "budget_cents": 0,
        "campaign_goal": "technical_verification",
        "campaign_type": "political",
        "publication_mode": mode,
        "locale": "es-GT",
        "jurisdiction": "Guatemala",
        "office": "alcalde",
        "candidate_name": "Candidatura técnica de prueba",
        "locality": "Municipio de prueba",
        "problem": "La información pública está fragmentada",
        "proposal": "Publicar un tablero mensual verificable",
        "desired_action": "Consulta la metodología y envía observaciones",
        "disclosure": "Prueba técnica; no corresponde a una campaña electoral.",
        "legal_review_status": "approved",
        "legal_reviewed_by": "client-value-must-be-discarded",
        "evidence_claims": [
            {
                "statement": "La prueba propone un tablero mensual verificable.",
                "source": "Documento técnico de prueba",
                "locator": "sección 1",
                "verification_status": "verified",
                "reviewed_by": "client-value-must-be-discarded",
            }
        ],
    }


class PoliticalComplianceModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def app(self, handler, *, content_enabled: bool, paid_enabled: bool = False):
        return create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            social_environment=social_environment(
                content_enabled=content_enabled,
                paid_enabled=paid_enabled,
            ),
            social_oauth_transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(AssertionError("OAuth HTTP not expected"))
            ),
            social_publication_transport=httpx.MockTransport(handler),
        )

    def create_run(self, client: TestClient, *, mode: str = "organic", suffix: str = "001"):
        created = client.post(
            "/api/v1/runs",
            json=political_brief(mode=mode, title="Political compliance {}".format(suffix)),
            headers=auth(LEGAL_KEY, "political-create-{}".format(suffix)),
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()

    def approve(self, client: TestClient, run: dict[str, object], *, key: str, suffix: str):
        return client.post(
            "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
            json={"reviewer": "client-reviewer-ignored", "note": "Independent approval"},
            headers=auth(key, "political-approve-{}".format(suffix)),
        )

    @staticmethod
    def open_session(client: TestClient, key: str = APPROVER_KEY) -> str:
        response = client.post("/api/v1/sessions", json={"api_key": key})
        if response.status_code != 201:
            raise AssertionError(response.text)
        return str(response.json()["csrf_token"])

    def test_political_content_creation_is_disabled_by_default(self):
        calls: list[httpx.Request] = []
        with TestClient(self.app(calls.append, content_enabled=False)) as client:
            response = client.post(
                "/api/v1/runs",
                json=political_brief(),
                headers=auth(LEGAL_KEY, "political-content-disabled-001"),
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "political_content_disabled")
        self.assertEqual(calls, [])

    def test_paid_political_mode_is_disabled_independently(self):
        calls: list[httpx.Request] = []
        with TestClient(self.app(calls.append, content_enabled=True, paid_enabled=False)) as client:
            response = client.post(
                "/api/v1/runs",
                json=political_brief(mode="paid", title="Paid mode disabled"),
                headers=auth(LEGAL_KEY, "political-paid-disabled-001"),
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "political_paid_media_disabled")
        self.assertEqual(calls, [])

    def test_same_identity_cannot_attest_legal_review_and_greenlight(self):
        calls: list[httpx.Request] = []
        with TestClient(self.app(calls.append, content_enabled=True)) as client:
            run = self.create_run(client, suffix="same-reviewer")
            response = self.approve(client, run, key=LEGAL_KEY, suffix="same-reviewer")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            response.json()["code"], "political_reviewer_separation_required"
        )
        self.assertEqual(calls, [])

    def test_independent_greenlight_adds_compliance_record_to_approved_envelope(self):
        calls: list[httpx.Request] = []
        with TestClient(self.app(calls.append, content_enabled=True)) as client:
            run = self.create_run(client, suffix="independent")
            response = self.approve(
                client, run, key=APPROVER_KEY, suffix="independent"
            )
        self.assertEqual(response.status_code, 200, response.text)
        completed = response.json()
        record = next(
            item
            for item in completed["artifacts"]
            if item["kind"] == "political_compliance_record"
        )
        self.assertEqual(record["payload"]["publication_mode"], "organic")
        self.assertEqual(record["payload"]["jurisdiction"], "Guatemala")
        self.assertEqual(
            record["payload"]["legal_reviewer"], "legal.reviewer@example.test"
        )
        self.assertEqual(
            record["payload"]["greenlight_approver"],
            "greenlight.approver@example.test",
        )
        self.assertEqual(
            record["payload"]["retention_state"],
            "durable_until_governed_deletion",
        )
        self.assertRegex(record["payload"]["disclosure_sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(record["artifact_id"], completed["greenlight"]["approved_artifact_ids"])
        self.assertEqual(calls, [])

    def test_paid_political_mode_never_reaches_organic_transport(self):
        calls: list[httpx.Request] = []
        with TestClient(
            self.app(calls.append, content_enabled=True, paid_enabled=True)
        ) as client:
            run = self.create_run(client, mode="paid", suffix="paid")
            approved = self.approve(client, run, key=APPROVER_KEY, suffix="paid")
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(
                item for item in completed["artifacts"] if item["kind"] == "copy_deck"
            )
            csrf = self.open_session(client)
            response = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json={
                    "artifact_id": copy_deck["artifact_id"],
                    "media_artifact_id": None,
                    "greenlight_id": completed["greenlight"]["greenlight_id"],
                    "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
                    "political_confirmation": "PUBLICAR POLITICA {} x".format(run["run_id"]),
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "political-paid-effect-001",
                },
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "paid_publication_requires_ads_authority")
        self.assertEqual(calls, [])

    def test_wrong_confirmation_blocks_before_intent_and_provider_http(self):
        calls: list[httpx.Request] = []
        app = self.app(calls.append, content_enabled=True)
        with TestClient(app) as client:
            run = self.create_run(client, suffix="wrong-confirmation")
            approved = self.approve(
                client, run, key=APPROVER_KEY, suffix="wrong-confirmation"
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(
                item for item in completed["artifacts"] if item["kind"] == "copy_deck"
            )
            csrf = self.open_session(client)
            response = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json={
                    "artifact_id": copy_deck["artifact_id"],
                    "media_artifact_id": None,
                    "greenlight_id": completed["greenlight"]["greenlight_id"],
                    "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
                    "political_confirmation": "PUBLICAR POLITICA otro-run x",
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "political-wrong-confirmation-effect-001",
                },
            )
            count = len(
                app.state.runtime_service.publication_store.list_for_run(
                    "tenant-political", run["run_id"]
                )
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "political_confirmation_invalid")
        self.assertEqual(count, 0)
        self.assertEqual(calls, [])

    def test_correct_confirmation_is_persisted_only_as_sha256(self):
        calls: list[httpx.Request] = []
        created_text: dict[str, str] = {}
        post_id = "1800000000000000201"

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.method == "POST":
                created_text["value"] = json.loads(request.content)["text"]
                return httpx.Response(201, json={"data": {"id": post_id}})
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": post_id,
                        "text": created_text["value"],
                        "author_id": "political-x-account",
                        "created_at": "2026-07-23T20:30:01Z",
                    }
                },
            )

        app = self.app(handler, content_enabled=True)
        with TestClient(app) as client:
            run = self.create_run(client, suffix="correct-confirmation")
            approved = self.approve(
                client, run, key=APPROVER_KEY, suffix="correct-confirmation"
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_deck = next(
                item for item in completed["artifacts"] if item["kind"] == "copy_deck"
            )
            phrase = "PUBLICAR POLITICA {} x".format(run["run_id"])
            csrf = self.open_session(client)
            response = client.post(
                "/api/v1/runs/{}/social-publications/x".format(run["run_id"]),
                json={
                    "artifact_id": copy_deck["artifact_id"],
                    "media_artifact_id": None,
                    "greenlight_id": completed["greenlight"]["greenlight_id"],
                    "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
                    "political_confirmation": phrase,
                },
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "political-correct-confirmation-effect-001",
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            intent = app.state.runtime_service.publication_store.list_for_run(
                "tenant-political", run["run_id"]
            )[0]
            database_text = self.database.read_bytes()
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            response.json()["receipt"]["verification_status"], "verified"
        )
        self.assertEqual(
            intent.confirmation_hash,
            hashlib.sha256(phrase.encode("utf-8")).hexdigest(),
        )
        self.assertNotIn(phrase.encode("utf-8"), database_text)
        self.assertNotIn("political_confirmation", response.text)

    def test_commercial_default_remains_backward_compatible(self):
        calls: list[httpx.Request] = []
        with TestClient(self.app(calls.append, content_enabled=False)) as client:
            response = client.post(
                "/api/v1/runs",
                json={
                    "title": "Commercial compatibility",
                    "objective": "Preserve existing commercial creation",
                    "audience": "operators",
                    "platforms": ["x"],
                    "budget_cents": 0,
                },
                headers=auth(LEGAL_KEY, "commercial-compatible-create-001"),
            )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["brief"]["publication_mode"], "organic")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
