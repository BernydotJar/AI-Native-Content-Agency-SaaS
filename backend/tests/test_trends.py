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
        <ht:news_item_title>Local teams adopt practical AI</ht:news_item_title>
        <ht:news_item_url>https://example.test/ai?ref=trend#tracking</ht:news_item_url>
        <ht:news_item_source>Example News</ht:news_item_source>
      </ht:news_item>
      <ht:news_item>
        <ht:news_item_title>Unsafe evidence is ignored</ht:news_item_title>
        <ht:news_item_url>http://example.test/insecure</ht:news_item_url>
        <ht:news_item_source>Unsafe News</ht:news_item_source>
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

NEWS_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Guatemala explores responsible artificial intelligence</title>
      <link>https://news.google.com/rss/articles/example?oc=5</link>
      <pubDate>Tue, 28 Jul 2026 14:00:00 GMT</pubDate>
      <source url="https://example.test">Example Technology</source>
    </item>
  </channel>
</rss>
"""


class TrendRadarTests(unittest.TestCase):
    def test_reads_google_trends_with_bounded_https_evidence(self):
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
        self.assertEqual(snapshot["topic"], "general")
        self.assertEqual(snapshot["source"], "Google Trends RSS")
        self.assertEqual(len(snapshot["trends"]), 1)
        trend = snapshot["trends"][0]
        self.assertEqual(trend["title"], "Guatemala innovation")
        self.assertEqual(trend["signal_type"], "search_trend")
        self.assertEqual(trend["news_source"], "Example News")
        self.assertEqual(
            trend["news_items"],
            [
                {
                    "title": "Local teams adopt practical AI",
                    "source": "Example News",
                    "url": "https://example.test/ai?ref=trend",
                }
            ],
        )

    def test_reads_allowlisted_topic_from_google_news_without_api_key(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.host, "news.google.com")
            self.assertEqual(request.url.params["q"], "inteligencia artificial Guatemala")
            self.assertEqual(request.url.params["hl"], "es-419")
            return httpx.Response(200, content=NEWS_RSS)

        radar = TrendRadar(transport=httpx.MockTransport(handler))
        snapshot = radar.read(geo="GT", topic="ai", limit=3)

        self.assertEqual(snapshot["topic"], "ai")
        self.assertEqual(snapshot["source"], "Google News RSS")
        self.assertEqual(snapshot["trends"][0]["signal_type"], "news_signal")
        self.assertEqual(
            snapshot["trends"][0]["news_items"][0]["source"],
            "Example Technology",
        )

    def test_rejects_unallowlisted_topics(self):
        radar = TrendRadar(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=RSS)
            )
        )
        with self.assertRaises(ValueError):
            radar.read(topic="arbitrary-user-query")

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
