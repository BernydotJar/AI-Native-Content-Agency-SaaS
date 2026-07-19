from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from scripts.http_smoke import request_json


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class HttpSmokeTest(unittest.TestCase):
    def test_short_lived_identity_token_is_sent_as_bearer_header(self) -> None:
        captured_headers: dict[str, str] = {}

        def fake_urlopen(request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 10)
            captured_headers.update(dict(request.header_items()))  # type: ignore[attr-defined]
            return _Response(b'{"status":"ok"}')

        with patch("scripts.http_smoke.urlopen", fake_urlopen):
            result = request_json(
                "https://private-service.example",
                "/healthz",
                "tenant-a",
                "principal-a",
                identity_token="short-lived-token",
            )

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(captured_headers["Authorization"], "Bearer short-lived-token")

    def test_authorization_header_is_absent_for_local_smoke(self) -> None:
        captured_headers: dict[str, str] = {}

        def fake_urlopen(request: object, timeout: int) -> _Response:
            self.assertEqual(timeout, 10)
            captured_headers.update(dict(request.header_items()))  # type: ignore[attr-defined]
            return _Response(b'{"status":"ok"}')

        with patch("scripts.http_smoke.urlopen", fake_urlopen):
            request_json(
                "http://127.0.0.1:8080",
                "/healthz",
                "tenant-a",
                "principal-a",
            )

        self.assertNotIn("Authorization", captured_headers)


if __name__ == "__main__":
    unittest.main()
