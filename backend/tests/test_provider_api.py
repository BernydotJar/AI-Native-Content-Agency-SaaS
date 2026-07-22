import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app


API_KEY = "tenant-provider-verification-key-2026"


class ProviderApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "runtime.sqlite3")
        self.static_dir = Path(self.temp.name) / "missing"

    def tearDown(self):
        self.temp.cleanup()

    def client(self, provider_environment=None):
        return TestClient(
            create_app(
                database_path=self.database,
                static_dir=self.static_dir,
                tenant_api_keys={"tenant-alpha": API_KEY},
                provider_environment=provider_environment or {},
            )
        )

    def test_provider_catalog_requires_identity_and_returns_server_state_only(self):
        raw_key = "openai-provider-key-that-must-never-leave-the-server"
        with self.client(
            {
                "OPENAI_API_KEY": raw_key,
                "AGENCY_OPENAI_MODEL": "gpt-5.2",
            }
        ) as client:
            self.assertEqual(client.get("/api/v1/providers").status_code, 401)

            response = client.get(
                "/api/v1/providers",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["tenant_id"], "tenant-alpha")
            self.assertEqual(len(payload["providers"]), 5)
            openai = payload["providers"][0]
            self.assertEqual(openai["provider_id"], "openai")
            self.assertTrue(openai["configured"])
            self.assertEqual(openai["model"], "gpt-5.2")
            self.assertEqual(
                payload["gateway"],
                {
                    "execution_enabled": False,
                    "selected_provider": "",
                    "execution_available": False,
                    "durable_outbound_receipt": False,
                    "automatic_run_integration": False,
                },
            )
            self.assertNotIn(raw_key, response.text)
            self.assertNotIn("api_key", response.text.lower())

    def test_gateway_status_can_report_protocol_ready_without_execution_route(self):
        raw_key = "moonshot-provider-key-that-must-never-leave-the-server"
        with self.client(
            {
                "AGENCY_MODEL_EXECUTION_ENABLED": "true",
                "AGENCY_MODEL_PROVIDER": "moonshot",
                "AGENCY_MODEL_EGRESS_ALLOWED_HOSTS": "api.moonshot.ai",
                "MOONSHOT_API_KEY": raw_key,
                "AGENCY_MOONSHOT_MODEL": "kimi-k3",
            }
        ) as client:
            response = client.get(
                "/api/v1/providers",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(
                payload["gateway"],
                {
                    "execution_enabled": True,
                    "selected_provider": "moonshot",
                    "execution_available": True,
                    "durable_outbound_receipt": False,
                    "automatic_run_integration": False,
                },
            )
            moonshot = next(
                item for item in payload["providers"] if item["provider_id"] == "moonshot"
            )
            self.assertEqual(moonshot["model"], "kimi-k3")
            self.assertNotIn(raw_key, response.text)
            schema = client.get("/openapi.json").json()
            self.assertNotIn("/api/v1/model-completions", schema["paths"])
            self.assertNotIn("/api/v1/providers/execute", schema["paths"])

    def test_provider_catalog_is_read_only_in_openapi(self):
        with self.client() as client:
            schema = client.get("/openapi.json").json()
            self.assertEqual(set(schema["paths"]["/api/v1/providers"]), {"get"})
            self.assertEqual(
                client.post(
                    "/api/v1/providers",
                    headers={"Authorization": "Bearer {}".format(API_KEY)},
                    json={},
                ).status_code,
                405,
            )


if __name__ == "__main__":
    unittest.main()
