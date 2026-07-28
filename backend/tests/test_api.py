import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


ALPHA_KEY = "tenant-alpha-verification-key-2026"
BETA_KEY = "tenant-beta-verification-key-2026"
POLITICAL_APPROVER_KEY = "tenant-alpha-political-approver-key-2026"
BRIEF = {
    "title": "Evidence-led launch",
    "objective": "Turn a campaign brief into a governed campaign package",
    "audience": "growth leaders",
    "platforms": ["x", "instagram"],
    "budget_cents": 50000,
    "campaign_goal": "qualified_demand",
}


def auth(api_key, idempotency_key=None):
    result = {"Authorization": "Bearer {}".format(api_key)}
    if idempotency_key is not None:
        result["Idempotency-Key"] = idempotency_key
    return result


class ApiVerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "runtime.sqlite3")
        self.static_dir = Path(self.temp.name) / "missing"
        self.keys = {"tenant-alpha": ALPHA_KEY, "tenant-beta": BETA_KEY}

    def tearDown(self):
        self.temp.cleanup()

    def client(self, keys=None):
        return TestClient(
            create_app(
                database_path=self.database,
                static_dir=self.static_dir,
                tenant_api_keys=self.keys if keys is None else keys,
                session_cookie_secure=False,
                social_environment={"AGENCY_POLITICAL_CONTENT_ENABLED": "true"},
            )
        )

    def test_health_readiness_and_authentication_contracts(self):
        with self.client() as client:
            health = client.get("/healthz")
            self.assertEqual(health.status_code, 200)
            self.assertFalse(health.json()["external_side_effects_enabled"])
            self.assertTrue(health.json()["auth_configured"])

            ready = client.get("/readyz")
            self.assertEqual(ready.status_code, 200)
            self.assertTrue(ready.json()["durable_run_store"])
            self.assertFalse(ready.json()["individual_identity_configured"])
            self.assertNotIn("credential_count", ready.json())

            self.assertEqual(client.get("/api/v1/me").status_code, 401)
            self.assertEqual(
                client.get(
                    "/api/v1/me", headers=auth("invalid-credential-value-2026")
                ).status_code,
                401,
            )
            principal = client.get("/api/v1/me", headers=auth(ALPHA_KEY))
            self.assertEqual(principal.status_code, 200)
            self.assertEqual(principal.json()["tenant_id"], "tenant-alpha")
            self.assertNotIn(ALPHA_KEY, principal.text)

            mismatched_login = client.post(
                "/api/v1/sessions",
                json={
                    "username": "someone-else@example.com",
                    "api_key": ALPHA_KEY,
                },
            )
            self.assertEqual(mismatched_login.status_code, 401)

            matched_login = client.post(
                "/api/v1/sessions",
                json={
                    "username": "tenant:tenant-alpha",
                    "api_key": ALPHA_KEY,
                },
            )
            self.assertEqual(matched_login.status_code, 201)
            self.assertEqual(
                matched_login.json()["subject_id"],
                "tenant:tenant-alpha",
            )

        with self.client(keys={}) as unconfigured:
            self.assertEqual(unconfigured.get("/healthz").status_code, 200)
            self.assertEqual(unconfigured.get("/readyz").status_code, 503)
            self.assertEqual(
                unconfigured.post("/api/v1/runs", json=BRIEF).status_code, 503
            )

    def test_brief_to_scholar_to_greenlight_to_campaign_package(self):
        with self.client() as client:
            created = client.post(
                "/api/v1/runs", json=BRIEF, headers=auth(ALPHA_KEY, "api-create-vertical-0001")
            )
            self.assertEqual(created.status_code, 201)
            run = created.json()
            self.assertEqual(run["tenant_id"], "tenant-alpha")
            self.assertEqual(run["status"], "awaiting_greenlight")
            self.assertEqual(len(run["artifacts"]), 7)
            research = next(
                item
                for item in run["artifacts"]
                if item["kind"] == "research_dossier"
            )
            self.assertEqual(
                set(research["payload"]["scholar"]),
                {
                    "reencuadre_cognitivo",
                    "tension_del_trade_off",
                    "resolucion_operativa",
                },
            )
            self.assertEqual(
                run["agent_states"]["publisher"]["status"],
                "waiting_greenlight",
            )

            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={
                    "reviewer": "commercial-owner",
                    "note": "Approved sandbox package",
                },
                headers=auth(ALPHA_KEY, "api-" + "approve-vertical-0001"),
            )
            self.assertEqual(approved.status_code, 200)
            completed = approved.json()
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(
                len(completed["greenlight"]["approved_artifact_ids"]), 7
            )
            self.assertEqual(
                len(completed["greenlight"]["approved_artifact_hashes"]), 7
            )
            self.assertEqual(
                completed["greenlight"]["authorized_channels"],
                ["x", "instagram"],
            )
            package = next(
                item
                for item in completed["artifacts"]
                if item["kind"] == "campaign_package"
            )
            self.assertFalse(package["payload"]["publication_performed"])

    def test_tenant_isolation_and_duplicate_scope(self):
        beta_brief = dict(BRIEF, title="Beta-only launch")
        with self.client() as client:
            alpha = client.post(
                "/api/v1/runs", json=BRIEF, headers=auth(ALPHA_KEY, "api-create-alpha-0001")
            )
            beta = client.post(
                "/api/v1/runs", json=beta_brief, headers=auth(BETA_KEY, "api-create-beta-0001")
            )
            self.assertEqual(alpha.status_code, 201)
            self.assertEqual(beta.status_code, 201)
            beta_run_id = beta.json()["run_id"]
            self.assertEqual(
                client.get(
                    "/api/v1/runs/{}".format(beta_run_id),
                    headers=auth(ALPHA_KEY),
                ).status_code,
                404,
            )
            self.assertEqual(
                client.get(
                    "/api/v1/runs/{}".format(beta_run_id),
                    headers=auth(BETA_KEY),
                ).status_code,
                200,
            )

            same_brief_beta = client.post(
                "/api/v1/runs", json=BRIEF, headers=auth(BETA_KEY, "api-create-beta-shared-0001")
            )
            self.assertEqual(same_brief_beta.status_code, 201)
            self.assertEqual(
                same_brief_beta.json()["run_id"], alpha.json()["run_id"]
            )
            alpha_replay = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers=auth(ALPHA_KEY, "api-create-alpha-duplicate-0001"),
            )
            self.assertEqual(alpha_replay.status_code, 200)
            self.assertEqual(alpha_replay.headers["X-Command-Replayed"], "true")
            self.assertEqual(alpha_replay.json(), alpha.json())

    def test_run_and_greenlight_survive_service_restart(self):
        with self.client() as first_client:
            created = first_client.post(
                "/api/v1/runs", json=BRIEF, headers=auth(ALPHA_KEY, "api-create-restart-0001")
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]

        with self.client() as second_client:
            restored = second_client.get(
                "/api/v1/runs/{}".format(run_id), headers=auth(ALPHA_KEY)
            )
            self.assertEqual(restored.status_code, 200)
            self.assertEqual(restored.json()["status"], "awaiting_greenlight")
            approved = second_client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={"reviewer": "owner", "note": "durable approval"},
                headers=auth(ALPHA_KEY, "api-approve-restart-0001"),
            )
            self.assertEqual(approved.status_code, 200)

        with self.client() as third_client:
            completed = third_client.get(
                "/api/v1/runs/{}".format(run_id), headers=auth(ALPHA_KEY)
            )
            self.assertEqual(completed.status_code, 200)
            self.assertEqual(completed.json()["status"], "completed")
            self.assertEqual(
                completed.json()["greenlight"]["note"], "durable approval"
            )

    def test_second_decision_is_a_conflict_after_restore(self):
        with self.client() as client:
            first = client.post(
                "/api/v1/runs", json=BRIEF, headers=auth(ALPHA_KEY, "api-create-second-decision-0001")
            )
            run_id = first.json()["run_id"]
            decision = {"reviewer": "owner", "note": "reject"}
            self.assertEqual(
                client.post(
                    "/api/v1/runs/{}/greenlight/reject".format(run_id),
                    json=decision,
                    headers=auth(ALPHA_KEY, "api-reject-first-decision-0001"),
                ).status_code,
                200,
            )

        with self.client() as restarted:
            self.assertEqual(
                restarted.post(
                    "/api/v1/runs/{}/greenlight/approve".format(run_id),
                    json=decision,
                    headers=auth(ALPHA_KEY, "api-" + "approve-second-decision-0001"),
                ).status_code,
                409,
            )


class PoliticalCampaignApiTests(ApiVerticalSliceTests):
    POLITICAL_BRIEF = {
        "title": "Transparencia municipal verificable",
        "objective": "Explicar una propuesta de rendición de cuentas",
        "audience": "vecinas y vecinos del municipio",
        "platforms": ["instagram", "x"],
        "campaign_type": "political",
        "locale": "es-GT",
        "jurisdiction": "Guatemala",
        "office": "alcalde",
        "candidate_name": "Candidatura de prueba",
        "locality": "Municipio de prueba",
        "problem": "La ciudadanía no encuentra la información presupuestaria en un solo lugar",
        "proposal": "Publicar mensualmente avances, contratos y ejecución presupuestaria",
        "desired_action": "Consulta el plan completo y envía tus preguntas",
        "disclosure": "Contenido orgánico de una candidatura de prueba; requiere aprobación humana",
        "legal_review_status": "approved",
        "legal_reviewed_by": "claimed-legal-reviewer",
        "evidence_claims": [
            {
                "statement": "La propuesta contempla publicación mensual de avances y ejecución presupuestaria.",
                "source": "Plan municipal de prueba 2027-2031",
                "locator": "páginas 12-14",
                "verification_status": "verified",
                "reviewed_by": "human-fact-reviewer",
            }
        ],
    }

    def test_political_brief_without_evidence_is_rejected(self):
        with self.client() as client:
            response = client.post(
                "/api/v1/runs",
                json={**self.POLITICAL_BRIEF, "evidence_claims": []},
                headers=auth(ALPHA_KEY, "political-missing-evidence-0001"),
            )
        self.assertEqual(response.status_code, 422)

    def test_political_brief_round_trip_and_artifacts(self):
        with self.client() as client:
            response = client.post(
                "/api/v1/runs",
                json=self.POLITICAL_BRIEF,
                headers=auth(ALPHA_KEY, "political-grounded-run-0001"),
            )
            self.assertEqual(response.status_code, 201, response.text)
            run = response.json()
            self.assertEqual(run["brief"]["campaign_type"], "political")
            server_reviewer = run["brief"]["evidence_claims"][0]["reviewed_by"]
            self.assertTrue(server_reviewer)
            self.assertNotEqual(server_reviewer, "human-fact-reviewer")
            self.assertEqual(run["brief"]["legal_review_status"], "approved")
            self.assertEqual(run["brief"]["legal_reviewed_by"], server_reviewer)
            self.assertNotEqual(run["brief"]["legal_reviewed_by"], "claimed-legal-reviewer")
            writer = next(item for item in run["artifacts"] if item["kind"] == "copy_deck")
            risk = next(item for item in run["artifacts"] if item["kind"] == "risk_report")
            self.assertNotIn("made clear", str(writer).lower())
            self.assertTrue(risk["payload"]["publication_eligible"])
            restored = client.get(
                "/api/v1/runs/{}".format(run["run_id"]), headers=auth(ALPHA_KEY)
            )
            self.assertEqual(restored.json()["brief"]["candidate_name"], "Candidatura de prueba")


    def test_pending_legal_review_is_reviewable_but_not_greenlight_eligible(self):
        pending = {
            **self.POLITICAL_BRIEF,
            "title": "Campaña pendiente de revisión legal",
            "legal_review_status": "pending",
            "legal_reviewed_by": "untrusted-client-value",
        }
        with self.client() as client:
            created = client.post(
                "/api/v1/runs",
                json=pending,
                headers=auth(ALPHA_KEY, "political-legal-pending-0001"),
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            self.assertEqual(run["brief"]["legal_reviewed_by"], "")
            risk = next(item for item in run["artifacts"] if item["kind"] == "risk_report")
            self.assertFalse(risk["payload"]["publication_eligible"])
            approval = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={"reviewer": "approver", "note": "legal review missing"},
                headers=auth(ALPHA_KEY, "political-legal-pending-approve-0001"),
            )
        self.assertEqual(approval.status_code, 409)

    def test_political_publication_has_a_separate_disabled_by_default_gate(self):
        approver_identity = [
            {
                "tenant_id": "tenant-alpha",
                "subject_id": "political.approver@example.test",
                "role": "admin",
                "key_id": "political-approver-v1",
                "api_key": POLITICAL_APPROVER_KEY,
                "active": True,
            }
        ]
        with TestClient(
            create_app(
                database_path=self.database,
                static_dir=self.static_dir,
                tenant_api_keys=self.keys,
                identity_credentials=approver_identity,
                session_cookie_secure=False,
                social_environment={"AGENCY_POLITICAL_CONTENT_ENABLED": "true"},
            )
        ) as client:
            created = client.post(
                "/api/v1/runs",
                json={**self.POLITICAL_BRIEF, "title": "Publicación política bloqueada por default"},
                headers=auth(ALPHA_KEY, "political-publish-create-0001"),
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={"reviewer": "approver", "note": "editorial approval only"},
                headers=auth(POLITICAL_APPROVER_KEY, "political-publish-approve-0001"),
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            completed = approved.json()
            copy_artifact = next(
                item for item in completed["artifacts"] if item["kind"] == "copy_deck"
            )
            session = client.post(
                "/api/v1/sessions", json={"api_key": ALPHA_KEY}
            )
            self.assertEqual(session.status_code, 201, session.text)
            response = client.post(
                "/api/v1/runs/{}/social-publications/instagram".format(run["run_id"]),
                json={
                    "artifact_id": copy_artifact["artifact_id"],
                    "media_artifact_id": None,
                    "greenlight_id": completed["greenlight"]["greenlight_id"],
                    "greenlight_fencing_token": completed["greenlight"]["fencing_token"],
                },
                headers={
                    "X-CSRF-Token": session.json()["csrf_token"],
                    "Idempotency-Key": "political-publish-effect-0001",
                },
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "political_publication_disabled")

    def test_operator_cannot_self_attest_verified_evidence(self):
        operator_key = "political-operator-key-material-2026"
        identities = [
            {
                "tenant_id": "tenant-alpha",
                "subject_id": "operator@example.com",
                "role": "operator",
                "key_id": "operator-v1",
                "api_key": operator_key,
                "active": True,
            }
        ]
        with TestClient(
            create_app(
                database_path=str(Path(self.temp.name) / "operator-runtime.sqlite3"),
                static_dir=self.static_dir,
                tenant_api_keys={},
                identity_credentials=identities,
                session_cookie_secure=False,
                social_environment={"AGENCY_POLITICAL_CONTENT_ENABLED": "true"},
            )
        ) as client:
            response = client.post(
                "/api/v1/runs",
                json=self.POLITICAL_BRIEF,
                headers=auth(operator_key, "political-operator-attest-0001"),
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "authorization_denied")

    def test_unverified_claim_is_reviewable_but_cannot_receive_greenlight(self):
        unverified = {
            **self.POLITICAL_BRIEF,
            "title": "Campaña política pendiente de verificación",
            "evidence_claims": [
                {
                    **self.POLITICAL_BRIEF["evidence_claims"][0],
                    "verification_status": "unverified",
                    "reviewed_by": "",
                }
            ],
        }
        with self.client() as client:
            created = client.post(
                "/api/v1/runs",
                json=unverified,
                headers=auth(ALPHA_KEY, "political-unverified-run-0001"),
            )
            self.assertEqual(created.status_code, 201, created.text)
            run = created.json()
            risk = next(item for item in run["artifacts"] if item["kind"] == "risk_report")
            self.assertFalse(risk["payload"]["publication_eligible"])
            self.assertEqual(risk["payload"]["decision"], "revise")
            approval = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run["run_id"]),
                json={"reviewer": "approver", "note": "must remain blocked"},
                headers=auth(ALPHA_KEY, "political-unverified-approve-0001"),
            )
            self.assertEqual(approval.status_code, 409)


if __name__ == "__main__":
    unittest.main()
