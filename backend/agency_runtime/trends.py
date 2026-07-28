from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from xml.etree import ElementTree

import httpx


_TRENDS_URL = "https://trends.google.com/trending/rss"
_TRENDS_NAMESPACE = "https://trends.google.com/trending/rss"
_MAX_RESPONSE_BYTES = 512 * 1024
_ALLOWED_GEOS = frozenset({"GT"})


class TrendRadarUnavailable(RuntimeError):
    """Raised when the allowlisted trend source cannot be verified."""


class TrendRadar:
    """Read-only Google Trends RSS client with a fixed destination allowlist."""

    def __init__(self, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._transport = transport

    def read(self, *, geo: str = "GT", limit: int = 8) -> Dict[str, object]:
        normalized_geo = geo.strip().upper()
        if normalized_geo not in _ALLOWED_GEOS:
            raise ValueError("trend geography is not allowlisted")
        if limit < 1 or limit > 10:
            raise ValueError("trend limit must be between 1 and 10")

        try:
            with httpx.Client(
                transport=self._transport,
                timeout=httpx.Timeout(6.0),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.get(
                    _TRENDS_URL,
                    params={"geo": normalized_geo},
                    headers={"Accept": "application/rss+xml, application/xml;q=0.9"},
                )
        except httpx.HTTPError as error:
            raise TrendRadarUnavailable("trend source request failed") from error

        if response.status_code != 200:
            raise TrendRadarUnavailable("trend source rejected the request")
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise TrendRadarUnavailable("trend source response exceeded the size limit")
        if b"<!DOCTYPE" in response.content.upper() or b"<!ENTITY" in response.content.upper():
            raise TrendRadarUnavailable("trend source document contains forbidden declarations")

        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            raise TrendRadarUnavailable("trend source returned invalid XML") from error
        if root.tag != "rss":
            raise TrendRadarUnavailable("trend source returned an unexpected document")
        channel = root.find("channel")
        if channel is None:
            raise TrendRadarUnavailable("trend source did not include an RSS channel")

        trends: List[Dict[str, str]] = []
        for item in channel.findall("item"):
            title = self._text(item.find("title"), 200)
            published_at = self._text(item.find("pubDate"), 100)
            traffic = self._text(
                item.find("{{{}}}approx_traffic".format(_TRENDS_NAMESPACE)),
                80,
            )
            news_source = self._text(
                item.find(".//{{{}}}news_item_source".format(_TRENDS_NAMESPACE)),
                160,
            )
            if not title or not published_at:
                continue
            trends.append(
                {
                    "title": title,
                    "approx_traffic": traffic,
                    "published_at": published_at,
                    "news_source": news_source,
                }
            )
            if len(trends) >= limit:
                break
        if not trends:
            raise TrendRadarUnavailable("trend source returned no verifiable items")

        return {
            "geo": normalized_geo,
            "source": "Google Trends RSS",
            "source_url": "{}?geo={}".format(_TRENDS_URL, normalized_geo),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "trends": trends,
        }

    @staticmethod
    def _text(element: Optional[ElementTree.Element], maximum: int) -> str:
        if element is None or element.text is None:
            return ""
        return " ".join(element.text.split())[:maximum]
