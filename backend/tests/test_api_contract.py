from __future__ import annotations

import copy
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from agency_runtime.api import (
    PublicErrorResponse,
    ValidationErrorResponse,
    create_app,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify-api-contract.py"
ADMIN_KEY = "api-contract-admin-key-material-2026"
VIEWER_KEY = "api-contract-viewer-key-material-2026"
BRIEF = {
    "title": "Contract verification",
    "objective": "Prove the versioned API error envelope",
    "audience": "integration engineers",
    "platforms": ["x"],
    "budget_cents": 0,
    "campaign_goal": "verification",
}


def identities():
    return [
        {
            "tenant_id": "contract-tenant",
            "subject_id": "contract-admin",
            "role": "admin",
            "key_id": "admin-v1",
            "api_key": ADMIN_KEY,
            "active": True,
        },
        {
            "tenant_id": "contract-tenant",
            "subject_id": "contract-viewer",
            "role": "viewer",
            "key_id": "viewer-v1",
            "api_key": VIEWER_KEY,
            "active": True,
        },
    ]


def app(**overrides):
    arguments = {
        "database_path": ":memory:",
        "static_dir": Path("/definitely/missing"),
        "identity_credentials": identities(),
        "session_cookie_secure": False,
    }
    arguments.update(overrides)
    return create_app(**arguments)


def auth(key: str, request_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "X-Request-ID": request_id,
    }


class ApiContractSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("verify_api_contract", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load API contract verifier")
        cls.contract_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.contract_module)

    def test_committed_contract_matches_source_application(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            env={**os.environ, "API_CONTRACT_USE_INSTALLED": "0"},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("api_contract=pass", completed.stdout)
        self.assertIn("operations=31", completed.stdout)
        self.assertIn("standard_error_responses=310", completed.stdout)
        self.assertIn("external_effects=0", completed.stdout)

    def test_verifier_rejects_unversioned_paths_and_missing_error_contracts(self):
        document = self.contract_module.build_contract()
        for path in ("/admin", "/api/v10/admin", "/api/v1beta/admin"):
            with self.subTest(path=path):
                unversioned = copy.deepcopy(document)
                unversioned["paths"][path] = copy.deepcopy(
                    unversioned["paths"]["/healthz"]
                )
                with self.assertRaisesRegex(ValueError, "unversioned path set drift"):
                    self.contract_module.validate_contract(unversioned)

        missing_error = copy.deepcopy(document)
        del missing_error["paths"]["/api/v1/me"]["get"]["responses"]["503"]
        with self.assertRaisesRegex(ValueError, "response 503"):
            self.contract_module.validate_contract(missing_error)

        incomplete_422 = copy.deepcopy(document)
        incomplete_422["paths"]["/api/v1/me"]["get"]["responses"]["422"]["content"][
            "application/json"
        ]["schema"] = {"$ref": "#/components/schemas/ValidationErrorResponse"}
        with self.assertRaisesRegex(ValueError, "response 422 references"):
            self.contract_module.validate_contract(incomplete_422)

    def test_error_models_reject_extra_or_unsanitized_shapes(self):
        with self.assertRaises(ValidationError):
            PublicErrorResponse.model_validate(
                {
                    "code": "internal_error",
                    "detail": "internal service error",
                    "request_id": "contract-model-0001",
                    "exception": "RuntimeError",
                }
            )
        with self.assertRaises(ValidationError):
            ValidationErrorResponse.model_validate(
                {
                    "code": "request_validation_failed",
                    "detail": "request validation failed",
                    "request_id": "contract-model-0002",
                    "errors": [
                        {
                            "location": ["body"],
                            "type": "missing",
                            "input": "secret-value",
                        }
                    ],
                }
            )


class ApiContractRuntimeTests(unittest.TestCase):
    def assert_public_error(self, response, status_code: int, request_id: str):
        self.assertEqual(response.status_code, status_code, response.text)
        document = PublicErrorResponse.model_validate(response.json())
        self.assertEqual(document.request_id, request_id)
        self.assertEqual(response.headers.get("X-Request-ID"), request_id)
        self.assertNotIn("Traceback", response.text)
        self.assertNotIn("RuntimeError", response.text)
        return document

    def test_runtime_error_envelope_covers_safe_status_surface(self):
        runtime = app(max_request_body_bytes=1024)

        def internal_failure():
            raise RuntimeError("private contract failure detail")

        def domain_validation_failure():
            from agency_runtime.api import PublicApiError

            raise PublicApiError(
                status_code=422,
                code="domain_validation_failed",
                detail="domain validation failed",
            )

        runtime.add_api_route(
            "/api/v1/_contract/internal-error",
            internal_failure,
            methods=["GET"],
            include_in_schema=False,
        )
        runtime.add_api_route(
            "/api/v1/_contract/domain-validation-error",
            domain_validation_failure,
            methods=["GET"],
            include_in_schema=False,
        )
        with TestClient(runtime, raise_server_exceptions=False) as client:
            unauthorized = client.get(
                "/api/v1/me", headers={"X-Request-ID": "contract-401"}
            )
            self.assert_public_error(unauthorized, 401, "contract-401")

            bad_oauth = client.post(
                "/api/v1/social-channels/x/oauth/start",
                headers=auth(ADMIN_KEY, "contract-400"),
            )
            self.assertEqual(
                self.assert_public_error(bad_oauth, 400, "contract-400").code,
                "browser_session_required",
            )

            forbidden_headers = auth(VIEWER_KEY, "contract-403")
            forbidden_headers["Idempotency-Key"] = "contract-forbidden-0001"
            forbidden = client.post(
                "/api/v1/runs", json=BRIEF, headers=forbidden_headers
            )
            forbidden_error = self.assert_public_error(
                forbidden, 403, "contract-403"
            )
            self.assertNotIn("runs:create", forbidden.text)
            self.assertEqual(forbidden_error.detail, "request not permitted")

            missing = client.get(
                "/api/v1/runs/contract-missing",
                headers=auth(VIEWER_KEY, "contract-404"),
            )
            self.assert_public_error(missing, 404, "contract-404")

            conflict = client.get(
                "/api/v1/audit-events/integrity",
                headers=auth(VIEWER_KEY, "contract-409"),
            )
            self.assertEqual(
                self.assert_public_error(conflict, 409, "contract-409").code,
                "audit_checkpoint_signing_unavailable",
            )

            too_large_headers = auth(ADMIN_KEY, "contract-413")
            too_large_headers.update(
                {
                    "Idempotency-Key": "contract-too-large-0001",
                    "Content-Type": "application/json",
                }
            )
            too_large = client.post(
                "/api/v1/runs", content=b"x" * 2048, headers=too_large_headers
            )
            self.assert_public_error(too_large, 413, "contract-413")

            invalid_headers = auth(ADMIN_KEY, "contract-422")
            invalid_headers["Idempotency-Key"] = "contract-invalid-0001"
            invalid = client.post(
                "/api/v1/runs", json={}, headers=invalid_headers
            )
            self.assertEqual(invalid.status_code, 422, invalid.text)
            validation = ValidationErrorResponse.model_validate(invalid.json())
            self.assertEqual(validation.request_id, "contract-422")
            self.assertGreaterEqual(len(validation.errors), 1)
            self.assertLessEqual(len(validation.errors), 20)
            for item in invalid.json()["errors"]:
                self.assertEqual(set(item), {"location", "type"})
            self.assertEqual(invalid.headers.get("X-Request-ID"), "contract-422")

            domain_invalid = client.get(
                "/api/v1/_contract/domain-validation-error",
                headers={"X-Request-ID": "contract-domain-422"},
            )
            domain_error = self.assert_public_error(
                domain_invalid, 422, "contract-domain-422"
            )
            self.assertEqual(domain_error.code, "domain_validation_failed")
            self.assertNotIn("errors", domain_invalid.json())

            internal = client.get(
                "/api/v1/_contract/internal-error",
                headers={"X-Request-ID": "contract-500"},
            )
            internal_error = self.assert_public_error(
                internal, 500, "contract-500"
            )
            self.assertEqual(internal_error.code, "internal_error")
            self.assertEqual(internal_error.detail, "internal service error")

        unavailable = app(identity_credentials=[])
        with TestClient(unavailable) as client:
            response = client.get(
                "/readyz", headers={"X-Request-ID": "contract-503"}
            )
            self.assert_public_error(response, 503, "contract-503")

    def test_durable_quota_uses_the_same_429_contract(self):
        runtime = app(
            authenticated_request_max_per_principal=10,
            authenticated_request_max_per_tenant=100,
            authenticated_request_window_seconds=60,
        )
        with TestClient(runtime) as client:
            for index in range(10):
                response = client.get(
                    "/api/v1/me",
                    headers=auth(VIEWER_KEY, f"contract-quota-{index:02d}"),
                )
                self.assertEqual(response.status_code, 200)
            limited = client.get(
                "/api/v1/me", headers=auth(VIEWER_KEY, "contract-429")
            )
            error = self.assert_public_error(limited, 429, "contract-429")
            self.assertEqual(error.code, "request_rate_limited")
            self.assertGreaterEqual(int(limited.headers["Retry-After"]), 1)


if __name__ == "__main__":
    unittest.main()
