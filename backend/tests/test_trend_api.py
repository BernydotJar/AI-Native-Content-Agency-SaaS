import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from agency_runtime.api import create_app


API_KEY = "tenant-alpha-verification-key-2026"
RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item>
      <title>Guatemala innovation</title>
      <ht:approx_traffic>2,000+</ht:approx_traffic>
      <pubDate>Tue, 28 Jul 2026 12:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


class TrendApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "runtime.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def client(self, response: httpx.Response) -> TestClient:
        transport = httpx.MockTransport(lambda _request: response)
        return TestClient(
            create_app(
                database_path=self.database,
                static_dir=Path(self.temp.name) / "missing",
                tenant_api_keys={"tenant-alpha": API_KEY},
                session_cookie_secure=False,
                trends_transport=transport,
            )
        )

    def test_requires_identity_and_returns_tenant_scoped_snapshot(self):
        with self.client(httpx.Response(200, content=RSS)) as client:
            self.assertEqual(client.get("/api/v1/trends").status_code, 401)
            response = client.get(
                "/api/v1/trends?geo=GT&limit=1",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tenant_id"], "tenant-alpha")
        self.assertEqual(response.json()["source"], "Google Trends RSS")
        self.assertEqual(response.json()["trends"][0]["title"], "Guatemala innovation")
        self.assertNotIn(API_KEY, response.text)

    def test_maps_provider_failure_to_safe_public_error(self):
        with self.client(httpx.Response(503, content=b"upstream details")) as client:
            response = client.get(
                "/api/v1/trends",
                headers={"Authorization": "Bearer {}".format(API_KEY)},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "trend_radar_unavailable")
        self.assertNotIn("upstream details", response.text)


if __name__ == "__main__":
    unittest.main()
