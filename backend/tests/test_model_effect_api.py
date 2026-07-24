import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app


ADMIN_KEY = "model-effect-admin-key-material-2026"
VIEWER_KEY = "model-effect-viewer-key-material-2026"
MODEL_SECRET = "model-effect-openai-secret-must-not-leak"


def identities():
    return [
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "model-effect-admin",
            "role": "admin",
            "key_id": "model-effect-admin-v1",
            "api_key": ADMIN_KEY,
            "active": True,
        },
        {
            "tenant_id": "tenant-alpha",
            "subject_id": "model-effect-viewer",
            "role": "viewer",
            "key_id": "model-effect-viewer-v1",
            "api_key": VIEWER_KEY,
            "active": True,
        },
    ]


def environment(*, authority_enabled=True, gateway_enabled=True):
    return {
        "AGENCY_MODEL_EXECUTION_ENABLED": "true" if gateway_enabled else "false",
        "AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED": (
            "true" if authority_enabled else "false"
        ),
        "AGENCY_MODEL_PROVIDER": "openai" if gateway_enabled else "",
        "OPENAI_API_KEY": MODEL_SECRET,
        "AGENCY_OPENAI_MODEL": "gpt-5.2",
        "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": (
            "api.openai.com" if gateway_enabled else ""
        ),
        "AGENCY_MODEL_MAX_OUTPUT_TOKENS": "128",
    }


def open_session(client: TestClient, api_key=ADMIN_KEY):
    response = client.post("/api/v1/sessions", json={"api_key": api_key})
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["csrf_token"]


BRIEF = {
    "title": "Governed model effect campaign",
    "objective": "Refine one governed artifact with exact-once model authority",
    "audience": "campaign operators",
    "platforms": ["x"],
    "budget_cents": 0,
    "campaign_goal": "verification",
}


class ModelEffectApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "runtime.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def app(self, handler, *, authority_enabled=True, gateway_enabled=True):
        return create_app(
            database_path=str(self.database),
            identity_credentials=identities(),
            session_cookie_secure=False,
            provider_environment=environment(
                authority_enabled=authority_enabled,
                gateway_enabled=gateway_enabled,
            ),
            model_transport=httpx.MockTransport(handler),
        )

    def awaiting_run(self, client: TestClient, csrf: str, suffix="001"):
        response = client.post(
            "/api/v1/runs",
            json=dict(BRIEF, title="{} {}".format(BRIEF["title"], suffix)),
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "model-effect-run-{}".format(suffix),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        self.assertEqual(run["status"], "awaiting_greenlight")
        source = next(
            artifact
            for artifact in run["artifacts"]
            if artifact["created_by"] == "writer"
        )
        return run, source

    @staticmethod
    def body(source, *, instruction="Improve this governed draft without inventing evidence."):
        return {
            "source_artifact_id": source["artifact_id"],
            "instruction": instruction,
            "max_cost_micros": 500_000,
        }

    @staticmethod
    def provider_success(text="A governed model-assisted refinement."):
        return httpx.Response(
            200,
            headers={"x-request-id": "model-provider-request-001"},
            json={
                "id": "model-response-001",
                "model": "gpt-5.2",
                "output_text": text,
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 7,
                    "total_tokens": 27,
                },
            },
        )

    def test_exact_once_execution_attaches_one_artifact_and_repairs_audit(self):
        calls = []

        def handler(request):
            calls.append(request)
            payload = json.loads(request.content)
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            self.assertEqual(payload["model"], "gpt-5.2")
            self.assertIn("governed artifact", payload["input"])
            self.assertNotIn("model-effect-command-001", request.content.decode())
            return self.provider_success()

        app = self.app(handler)
        service = app.state.runtime_service
        original_attach = service.attach_model_effect_result
        attachment_attempts = []

        def fail_first_attachment(**kwargs):
            attachment_attempts.append(kwargs["result"].effect_id)
            if len(attachment_attempts) == 1:
                raise RuntimeError("injected run attachment failure")
            return original_attach(**kwargs)

        service.attach_model_effect_result = fail_first_attachment
        with TestClient(app, raise_server_exceptions=False) as client:
            csrf = open_session(client)
            run, source = self.awaiting_run(client, csrf)
            path = "/api/v1/runs/{}/model-effects/writer".format(run["run_id"])
            headers = {
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "model-effect-command-001",
            }

            first = client.post(path, json=self.body(source), headers=headers)
            self.assertEqual(first.status_code, 500, first.text)
            self.assertEqual(len(calls), 1)

            replay = client.post(path, json=self.body(source), headers=headers)
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")
            self.assertTrue(replay.json()["effect"]["replayed"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(attachment_attempts), 2)

            current = client.get("/api/v1/runs/{}".format(run["run_id"])).json()
            model_artifacts = [
                artifact
                for artifact in current["artifacts"]
                if artifact["kind"] == "model_completion"
            ]
            self.assertEqual(len(model_artifacts), 1)
            self.assertEqual(
                model_artifacts[0]["payload"]["output_text"],
                "A governed model-assisted refinement.",
            )

            listed = client.get(
                "/api/v1/runs/{}/model-effects".format(run["run_id"])
            )
            self.assertEqual(listed.status_code, 200, listed.text)
            serialized = json.dumps(listed.json(), sort_keys=True)
            for forbidden in (
                MODEL_SECRET,
                "model-effect-command-001",
                "Improve this governed draft",
                "A governed model-assisted refinement.",
            ):
                self.assertNotIn(forbidden, serialized)

            audit = client.get("/api/v1/audit-events").json()["events"]
            events = [
                item
                for item in audit
                if item["action"] == "model.effect_succeeded"
            ]
            self.assertEqual(len(events), 1)
            audit_serialized = json.dumps(events, sort_keys=True)
            self.assertNotIn(MODEL_SECRET, audit_serialized)
            self.assertNotIn("Improve this governed draft", audit_serialized)
            self.assertNotIn("A governed model-assisted refinement.", audit_serialized)

    def test_disabled_non_admin_and_bearer_requests_never_call_provider(self):
        calls = []
        disabled = self.app(
            lambda request: calls.append(request), authority_enabled=False
        )
        with TestClient(disabled) as client:
            csrf = open_session(client)
            run, source = self.awaiting_run(client, csrf, suffix="disabled")
            response = client.post(
                "/api/v1/runs/{}/model-effects/writer".format(run["run_id"]),
                json=self.body(source),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "model-effect-disabled-001",
                },
            )
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()["code"], "model_effect_unavailable")
        self.assertEqual(calls, [])

        enabled = self.app(lambda request: calls.append(request))
        with TestClient(enabled) as client:
            admin_csrf = open_session(client)
            run, source = self.awaiting_run(client, admin_csrf, suffix="authority")
            client.delete(
                "/api/v1/sessions/current",
                headers={"X-CSRF-Token": admin_csrf},
            )
            viewer_csrf = open_session(client, VIEWER_KEY)
            denied = client.post(
                "/api/v1/runs/{}/model-effects/writer".format(run["run_id"]),
                json=self.body(source),
                headers={
                    "X-CSRF-Token": viewer_csrf,
                    "Idempotency-Key": "model-effect-viewer-001",
                },
            )
            self.assertEqual(denied.status_code, 403, denied.text)
            client.delete(
                "/api/v1/sessions/current",
                headers={"X-CSRF-Token": viewer_csrf},
            )
            bearer = client.post(
                "/api/v1/runs/{}/model-effects/writer".format(run["run_id"]),
                json=self.body(source),
                headers={
                    "Authorization": "Bearer {}".format(ADMIN_KEY),
                    "X-CSRF-Token": "not-a-session-token",
                    "Idempotency-Key": "model-effect-bearer-001",
                },
            )
            self.assertEqual(bearer.status_code, 400, bearer.text)
            self.assertEqual(bearer.json()["code"], "browser_session_required")
        self.assertEqual(calls, [])

    def test_unknown_blocks_approval_until_idempotent_reconciliation(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503, text="ambiguous provider state")

        app = self.app(handler)
        with TestClient(app) as client:
            csrf = open_session(client)
            run, source = self.awaiting_run(client, csrf, suffix="unknown")
            path = "/api/v1/runs/{}/model-effects/writer".format(run["run_id"])
            headers = {
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "model-effect-unknown-001",
            }
            unknown = client.post(path, json=self.body(source), headers=headers)
            self.assertEqual(unknown.status_code, 503, unknown.text)
            self.assertEqual(unknown.json()["code"], "model_effect_unknown")

            blocked = client.post(path, json=self.body(source), headers=headers)
            self.assertEqual(blocked.status_code, 409, blocked.text)
            self.assertEqual(blocked.json()["code"], "model_effect_blocked")
            self.assertEqual(len(calls), 1)

            effects = client.get(
                "/api/v1/runs/{}/model-effects".format(run["run_id"])
            ).json()["effects"]
            self.assertEqual(effects[0]["status"], "unknown")
            effect_id = effects[0]["effect_id"]

            approval = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={"reviewer": "model-effect-admin", "note": "approve"},
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "model-effect-approve-blocked-001",
                },
            )
            self.assertEqual(approval.status_code, 409, approval.text)

            reconciliation_body = {
                "output_text": "Recovered governed provider output.",
                "provider_request_id": "provider-console-evidence-001",
                "note": "Verified by an authorized operator in the provider console.",
            }
            reconciliation_headers = {
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "model-effect-reconcile-001",
            }
            reconciled = client.post(
                "/api/v1/model-effects/{}/reconcile".format(effect_id),
                json=reconciliation_body,
                headers=reconciliation_headers,
            )
            self.assertEqual(reconciled.status_code, 200, reconciled.text)
            self.assertEqual(reconciled.json()["effect"]["status"], "succeeded")

            replay = client.post(
                "/api/v1/model-effects/{}/reconcile".format(effect_id),
                json=reconciliation_body,
                headers=reconciliation_headers,
            )
            self.assertEqual(replay.status_code, 200, replay.text)
            self.assertEqual(replay.headers["X-Command-Replayed"], "true")

            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={"reviewer": "model-effect-admin", "note": "approve"},
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": "model-effect-approve-after-reconcile",
                },
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            self.assertEqual(approved.json()["status"], "completed")

    def test_same_key_changed_binding_conflicts_before_second_http(self):
        calls = []

        def handler(request):
            calls.append(request)
            return self.provider_success()

        app = self.app(handler)
        with TestClient(app) as client:
            csrf = open_session(client)
            run, source = self.awaiting_run(client, csrf, suffix="conflict")
            path = "/api/v1/runs/{}/model-effects/writer".format(run["run_id"])
            headers = {
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "model-effect-conflict-001",
            }
            first = client.post(path, json=self.body(source), headers=headers)
            self.assertEqual(first.status_code, 201, first.text)
            conflict = client.post(
                path,
                json=self.body(source, instruction="A changed operator instruction."),
                headers=headers,
            )
            self.assertEqual(conflict.status_code, 409, conflict.text)
            self.assertEqual(conflict.json()["code"], "idempotency_conflict")
            self.assertEqual(len(calls), 1)

    def test_provider_status_and_openapi_are_truthful(self):
        app = self.app(lambda request: self.provider_success())
        with TestClient(app) as client:
            csrf = open_session(client)
            status_response = client.get("/api/v1/providers")
            self.assertEqual(status_response.status_code, 200)
            gateway = status_response.json()["gateway"]
            self.assertTrue(gateway["execution_enabled"])
            self.assertTrue(gateway["execution_available"])
            self.assertTrue(gateway["durable_outbound_receipt"])
            self.assertFalse(gateway["automatic_run_integration"])

            schema = client.get("/openapi.json").json()
            self.assertIn(
                "/api/v1/runs/{run_id}/model-effects/{station}",
                schema["paths"],
            )
            self.assertIn(
                "/api/v1/model-effects/{effect_id}/reconcile",
                schema["paths"],
            )
            self.assertNotIn(MODEL_SECRET, json.dumps(schema))
            self.assertTrue(csrf)


if __name__ == "__main__":
    unittest.main()
