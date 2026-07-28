import unittest

import httpx

from agency_runtime.trends import TrendRadar, TrendRadarUnavailable


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item>
      <title>Guatemala innovation</title>
      <ht:approx_traffic>2,000+</ht:approx_traffic>
      <pubDate>Tue, 28 Jul 2026 12:00:00 +0000</pubDate>
      <ht:news_item>
        <ht:news_item_source>Example News</ht:news_item_source>
      </ht:news_item>
    </item>
    <item>
      <title>Regional football</title>
      <ht:approx_traffic>1,000+</ht:approx_traffic>
      <pubDate>Tue, 28 Jul 2026 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


class TrendRadarTests(unittest.TestCase):
    def test_reads_allowlisted_google_trends_rss_without_inventing_items(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.host, "trends.google.com")
            self.assertEqual(request.url.params["geo"], "GT")
            return httpx.Response(
                200,
                headers={"Content-Type": "application/xml"},
                content=RSS,
            )

        radar = TrendRadar(transport=httpx.MockTransport(handler))
        snapshot = radar.read(geo="GT", limit=1)

        self.assertEqual(snapshot["geo"], "GT")
        self.assertEqual(snapshot["source"], "Google Trends RSS")
        self.assertEqual(len(snapshot["trends"]), 1)
        self.assertEqual(snapshot["trends"][0]["title"], "Guatemala innovation")
        self.assertEqual(snapshot["trends"][0]["news_source"], "Example News")

    def test_fails_closed_for_provider_errors_and_invalid_documents(self):
        for response in (
            httpx.Response(503, content=b"provider unavailable"),
            httpx.Response(200, content=b"<html>not rss</html>"),
        ):
            radar = TrendRadar(
                transport=httpx.MockTransport(lambda _request, item=response: item)
            )
            with self.assertRaises(TrendRadarUnavailable):
                radar.read(geo="GT", limit=5)


if __name__ == "__main__":
    unittest.main()
