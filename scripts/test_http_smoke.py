from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from scripts.http_smoke import request_json, verify_run


def completed_smoke_run() -> dict[str, object]:
    return {
        "status": "completed",
        "external_side_effects": False,
        "artifacts": [
            {
                "kind": "campaign_package",
                "payload": {"publication_performed": False},
            },
            *[{"kind": "draft", "payload": {}} for _ in range(7)],
        ],
        "evidence": [{"sandbox": True} for _ in range(8)],
    }


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class HttpSmokeTest(unittest.TestCase):
    def test_accepts_exactly_eight_artifacts_and_evidence(self) -> None:
        verify_run(completed_smoke_run())

    def test_rejects_inexact_workflow_counts(self) -> None:
        for field, message in (
            ("artifacts", "exactly eight artifacts"),
            ("evidence", "exactly eight evidence records"),
        ):
            with self.subTest(field=field):
                run = completed_smoke_run()
                values = run[field]
                self.assertIsInstance(values, list)
                assert isinstance(values, list)
                values.pop()
                with self.assertRaisesRegex(RuntimeError, message):
                    verify_run(run)

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
