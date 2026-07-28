from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx


_TRENDS_URL = "https://trends.google.com/trending/rss"
_NEWS_URL = "https://news.google.com/rss/search"
_TRENDS_NAMESPACE = "https://trends.google.com/trending/rss"
_MAX_RESPONSE_BYTES = 512 * 1024
_ALLOWED_GEOS = frozenset({"GT"})
_TOPIC_QUERIES = {
    "ai": "inteligencia artificial Guatemala",
    "marketing": "marketing digital Guatemala",
    "business": "emprendimiento Guatemala",
}
_ALLOWED_TOPICS = frozenset({"general", *_TOPIC_QUERIES})


class TrendRadarUnavailable(RuntimeError):
    """Raised when an allowlisted research source cannot be verified."""


class TrendRadar:
    """Read-only Google RSS research client with fixed destinations and topics."""

    def __init__(self, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._transport = transport

    def read(
        self,
        *,
        geo: str = "GT",
        limit: int = 8,
        topic: str = "general",
    ) -> Dict[str, object]:
        normalized_geo = geo.strip().upper()
        normalized_topic = topic.strip().lower()
        if normalized_geo not in _ALLOWED_GEOS:
            raise ValueError("trend geography is not allowlisted")
        if normalized_topic not in _ALLOWED_TOPICS:
            raise ValueError("trend topic is not allowlisted")
        if limit < 1 or limit > 10:
            raise ValueError("trend limit must be between 1 and 10")

        if normalized_topic == "general":
            return self._read_trends(normalized_geo, limit)
        return self._read_news(normalized_geo, normalized_topic, limit)

    def _request(self, url: str, params: Dict[str, str]) -> httpx.Response:
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=httpx.Timeout(6.0),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.get(
                    url,
                    params=params,
                    headers={"Accept": "application/rss+xml, application/xml;q=0.9"},
                )
        except httpx.HTTPError as error:
            raise TrendRadarUnavailable("research source request failed") from error

        if response.status_code != 200:
            raise TrendRadarUnavailable("research source rejected the request")
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise TrendRadarUnavailable("research source response exceeded the size limit")
        upper = response.content.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise TrendRadarUnavailable(
                "research source document contains forbidden declarations"
            )
        return response

    @staticmethod
    def _rss_channel(response: httpx.Response) -> ElementTree.Element:
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            raise TrendRadarUnavailable(
                "research source returned invalid XML"
            ) from error
        if root.tag != "rss":
            raise TrendRadarUnavailable(
                "research source returned an unexpected document"
            )
        channel = root.find("channel")
        if channel is None:
            raise TrendRadarUnavailable(
                "research source did not include an RSS channel"
            )
        return channel

    def _read_trends(self, geo: str, limit: int) -> Dict[str, object]:
        response = self._request(_TRENDS_URL, {"geo": geo})
        channel = self._rss_channel(response)
        trends: List[Dict[str, object]] = []
        namespace = "{{{}}}".format(_TRENDS_NAMESPACE)

        for item in channel.findall("item"):
            title = self._text(item.find("title"), 200)
            published_at = self._text(item.find("pubDate"), 100)
            traffic = self._text(item.find(namespace + "approx_traffic"), 80)
            news_items: List[Dict[str, str]] = []
            for news_item in item.findall(namespace + "news_item"):
                headline = self._text(
                    news_item.find(namespace + "news_item_title"), 300
                )
                source = self._text(
                    news_item.find(namespace + "news_item_source"), 160
                )
                url = self._safe_https_url(
                    self._text(news_item.find(namespace + "news_item_url"), 2048)
                )
                if headline and source and url:
                    news_items.append(
                        {"title": headline, "source": source, "url": url}
                    )
                if len(news_items) >= 3:
                    break
            news_source = news_items[0]["source"] if news_items else self._text(
                item.find(namespace + "picture_source"), 160
            )
            if not title or not published_at:
                continue
            trends.append(
                {
                    "title": title,
                    "approx_traffic": traffic,
                    "published_at": published_at,
                    "news_source": news_source,
                    "news_items": news_items,
                    "signal_type": "search_trend",
                }
            )
            if len(trends) >= limit:
                break
        if not trends:
            raise TrendRadarUnavailable("research source returned no verifiable items")

        return {
            "geo": geo,
            "topic": "general",
            "source": "Google Trends RSS",
            "source_url": "{}?{}".format(_TRENDS_URL, urlencode({"geo": geo})),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "trends": trends,
        }

    def _read_news(self, geo: str, topic: str, limit: int) -> Dict[str, object]:
        query = _TOPIC_QUERIES[topic]
        params = {
            "q": query,
            "hl": "es-419",
            "gl": "US",
            "ceid": "US:es-419",
        }
        response = self._request(_NEWS_URL, params)
        channel = self._rss_channel(response)
        trends: List[Dict[str, object]] = []

        for item in channel.findall("item"):
            title = self._text(item.find("title"), 300)
            published_at = self._text(item.find("pubDate"), 100)
            source = self._text(item.find("source"), 160)
            url = self._safe_https_url(self._text(item.find("link"), 2048))
            if not title or not published_at or not source or not url:
                continue
            trends.append(
                {
                    "title": title,
                    "approx_traffic": "",
                    "published_at": published_at,
                    "news_source": source,
                    "news_items": [
                        {"title": title, "source": source, "url": url}
                    ],
                    "signal_type": "news_signal",
                }
            )
            if len(trends) >= limit:
                break
        if not trends:
            raise TrendRadarUnavailable("research source returned no verifiable items")

        return {
            "geo": geo,
            "topic": topic,
            "source": "Google News RSS",
            "source_url": "{}?{}".format(_NEWS_URL, urlencode(params)),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "trends": trends,
        }

    @staticmethod
    def _safe_https_url(value: str) -> str:
        if not value:
            return ""
        try:
            parsed = urlsplit(value)
        except ValueError:
            return ""
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return ""
        normalized = urlunsplit(
            ("https", parsed.netloc, parsed.path or "/", parsed.query, "")
        )
        return normalized if len(normalized) <= 2048 else ""

    @staticmethod
    def _text(element: Optional[ElementTree.Element], maximum: int) -> str:
        if element is None or element.text is None:
            return ""
        return " ".join(element.text.split())[:maximum]
