import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app
from agency_runtime.observability import RuntimeMetrics


ALPHA_KEY = "tenant-alpha-observability-key-2026"
BETA_KEY = "tenant-beta-observability-key-2026"
BRIEF = {
    "title": "Observable launch",
    "objective": "Verify request correlation and durable audit evidence",
    "audience": "production operators",
    "platforms": ["x", "instagram"],
    "budget_cents": 12500,
    "campaign_goal": "verification",
}


def auth(api_key, idempotency_key=None):
    result = {"Authorization": "Bearer {}".format(api_key)}
    if idempotency_key is not None:
        result["Idempotency-Key"] = idempotency_key
    return result


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "runtime.sqlite3")
        self.static_dir = Path(self.temp.name) / "missing"
        self.keys = {"tenant-alpha": ALPHA_KEY, "tenant-beta": BETA_KEY}

    def tearDown(self):
        self.temp.cleanup()

    def client(self):
        return TestClient(
            create_app(
                database_path=self.database,
                static_dir=self.static_dir,
                tenant_api_keys=self.keys,
            )
        )

    def test_request_correlation_structured_logs_and_metrics_are_sanitized(self):
        with self.client() as client:
            request_id = "request-observe-0001"
            with self.assertLogs("agency_runtime.http", level="INFO") as captured:
                response = client.get(
                    "/api/v1/me?secret=query-secret-must-not-log",
                    headers={
                        **auth(ALPHA_KEY),
                        "X-Request-ID": request_id,
                    },
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["X-Request-ID"], request_id)
            log_output = "\n".join(captured.output)
            self.assertIn('"route":"/api/v1/me"', log_output)
            self.assertIn('"tenant_id":"tenant-alpha"', log_output)
            self.assertIn(request_id, log_output)
            self.assertNotIn(ALPHA_KEY, log_output)
            self.assertNotIn("query-secret-must-not-log", log_output)

            generated = client.get(
                "/healthz", headers={"X-Request-ID": "invalid request id"}
            ).headers["X-Request-ID"]
            self.assertNotEqual(generated, "invalid request id")
            self.assertRegex(generated, r"^req-[0-9a-f]{32}$")

            metrics = client.get("/metrics")
            self.assertEqual(metrics.status_code, 200)
            body = metrics.text
            self.assertIn(
                'agency_http_requests_total{method="GET",route="/api/v1/me",status="200"} 1',
                body,
            )
            self.assertIn("agency_runs_started_total 0", body)
            self.assertNotIn("tenant-alpha", body)
            self.assertNotIn(ALPHA_KEY, body)
            self.assertNotRegex(body, re.escape("query-secret-must-not-log"))

    def test_request_duration_histogram_is_cumulative_and_has_infinity_bucket(self):
        metrics = RuntimeMetrics()
        metrics.record_http("GET", "/api/v1/runs/{run_id}", 200, 0.004)
        metrics.record_http("GET", "/api/v1/runs/{run_id}", 200, 0.8)
        metrics.record_http("GET", "/api/v1/runs/{run_id}", 500, 12.0)

        rendered = metrics.render()
        self.assertIn(
            "# TYPE agency_http_request_duration_seconds histogram", rendered
        )
        self.assertIn(
            'agency_http_request_duration_seconds_bucket{le="0.005",method="GET",'
            'route="/api/v1/runs/{run_id}"} 1',
            rendered,
        )
        self.assertIn(
            'agency_http_request_duration_seconds_bucket{le="1",method="GET",'
            'route="/api/v1/runs/{run_id}"} 2',
            rendered,
        )
        self.assertIn(
            'agency_http_request_duration_seconds_bucket{le="+Inf",method="GET",'
            'route="/api/v1/runs/{run_id}"} 3',
            rendered,
        )
        self.assertIn(
            'agency_http_request_duration_seconds_count{method="GET",route="/api/v1/runs/{run_id}"} 3',
            rendered,
        )
        self.assertNotIn("tenant", rendered)

    def test_security_denial_metric_rejects_unbounded_reasons(self):
        metrics = RuntimeMetrics()
        metrics.security_denial("authorization")
        metrics.security_denial("csrf")
        with self.assertRaisesRegex(ValueError, "unsupported security denial"):
            metrics.security_denial("tenant-alpha:runs:create")

        rendered = metrics.render()
        self.assertIn(
            'agency_security_denials_total{reason="authorization"} 1', rendered
        )
        self.assertIn('agency_security_denials_total{reason="csrf"} 1', rendered)
        self.assertNotIn("tenant-alpha", rendered)
        self.assertNotIn("runs:create", rendered)

    def test_social_publication_metrics_are_bounded_and_content_free(self):
        metrics = RuntimeMetrics()
        for outcome in (
            "succeeded",
            "replayed",
            "blocked",
            "rejected",
            "unknown",
            "reconciled",
        ):
            metrics.social_publication(outcome)
        with self.assertRaisesRegex(
            ValueError, "unsupported social publication outcome"
        ):
            metrics.social_publication("tenant-alpha:Approved campaign copy")

        rendered = metrics.render()
        for outcome in (
            "succeeded",
            "replayed",
            "blocked",
            "rejected",
            "unknown",
            "reconciled",
        ):
            self.assertIn(
                'agency_social_publications_total{{outcome="{}"}} 1'.format(
                    outcome
                ),
                rendered,
            )
        self.assertNotIn("tenant-alpha", rendered)
        self.assertNotIn("Approved campaign copy", rendered)

    def test_audit_ledger_is_transactional_tenant_scoped_and_durable(self):
        with self.client() as client:
            created = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={
                    **auth(ALPHA_KEY, "audit-create-command-0001"),
                    "X-Request-ID": "audit-create-0001",
                },
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]

            duplicate = client.post(
                "/api/v1/runs",
                json=BRIEF,
                headers={
                    **auth(ALPHA_KEY, "audit-duplicate-command-0001"),
                    "X-Request-ID": "audit-duplicate-0001",
                },
            )
            self.assertEqual(duplicate.status_code, 200)
            self.assertEqual(duplicate.headers["X-Command-Replayed"], "true")

            approved = client.post(
                "/api/v1/runs/{}/greenlight/approve".format(run_id),
                json={
                    "reviewer": "commercial-owner",
                    "note": "Approved with durable audit evidence",
                },
                headers={
                    **auth(ALPHA_KEY, "audit-approve-command-0001"),
                    "X-Request-ID": "audit-approve-0001",
                },
            )
            self.assertEqual(approved.status_code, 200)

            first_page = client.get(
                "/api/v1/audit-events?limit=1", headers=auth(ALPHA_KEY)
            )
            self.assertEqual(first_page.status_code, 200)
            self.assertEqual(len(first_page.json()["events"]), 1)
            self.assertTrue(first_page.json()["has_more"])

            audit = client.get(
                "/api/v1/audit-events", headers=auth(ALPHA_KEY)
            )
            self.assertEqual(audit.status_code, 200)
            payload = audit.json()
            events = payload["events"]
            self.assertEqual(
                [item["action"] for item in events],
                ["run.created", "run.reused", "greenlight.approved"],
            )
            self.assertEqual(
                [item["request_id"] for item in events],
                ["audit-create-0001", "audit-duplicate-0001", "audit-approve-0001"],
            )
            self.assertEqual({item["tenant_id"] for item in events}, {"tenant-alpha"})
            self.assertTrue(
                all(item["actor"] == "api-key:tenant:tenant-alpha" for item in events)
            )
            self.assertNotIn(ALPHA_KEY, audit.text)
            self.assertIn("audit-duplicate-0001", audit.text)

            beta_audit = client.get(
                "/api/v1/audit-events", headers=auth(BETA_KEY)
            )
            self.assertEqual(beta_audit.status_code, 200)
            self.assertEqual(beta_audit.json()["events"], [])

            metrics = client.get("/metrics").text
            self.assertIn("agency_runs_started_total 1", metrics)
            self.assertIn(
                'agency_greenlight_decisions_total{decision="approved"} 1',
                metrics,
            )

        with self.client() as restarted:
            durable = restarted.get(
                "/api/v1/audit-events", headers=auth(ALPHA_KEY)
            )
            self.assertEqual(durable.status_code, 200)
            self.assertEqual(
                [item["action"] for item in durable.json()["events"]],
                ["run.created", "run.reused", "greenlight.approved"],
            )
            self.assertEqual(
                durable.json()["events"][2]["payload"]["note"],
                "Approved with durable audit evidence",
            )


if __name__ == "__main__":
    unittest.main()
