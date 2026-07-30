import base64
import json
import unittest

from agency_runtime.publication_media_signing import (
    PublicMediaSigningConfigurationError,
    PublicMediaSigningKeyUnavailableError,
    PublicMediaSigningKeyring,
)


def encoded(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).rstrip(b"=").decode("ascii")


class PublicMediaSigningKeyringTests(unittest.TestCase):
    def test_keyring_signs_with_active_and_historical_keys_without_exposing_material(self):
        raw = json.dumps({"media-v1": encoded(1), "media-v2": encoded(2)})
        keyring = PublicMediaSigningKeyring.from_environment(raw, "media-v2", "")
        assert keyring is not None
        self.assertEqual(keyring.key_ids, ("media-v1", "media-v2"))
        key_id, active = keyring.sign_active("media-1", "2026-07-30T00:00:00+00:00")
        self.assertEqual(key_id, "media-v2")
        self.assertNotEqual(
            active,
            keyring.sign("media-v1", "media-1", "2026-07-30T00:00:00+00:00"),
        )
        rendered = repr(keyring)
        self.assertIn("media-v2", rendered)
        self.assertNotIn(encoded(1), rendered)
        self.assertNotIn(encoded(2), rendered)

    def test_legacy_key_preserves_historical_hmac_input(self):
        legacy = "legacy-public-media-signing-key-material-32-bytes"
        keyring = PublicMediaSigningKeyring.from_environment("", "", legacy)
        assert keyring is not None
        self.assertEqual(keyring.active_key_id, "legacy")
        # Regression value from the pre-keyring HMAC implementation.
        self.assertEqual(
            keyring.sign("legacy", "media-1", "2026-07-30T00:00:00+00:00"),
            "u8COUSpgoDeEJsRb9Pb859Dcg3KEuB8iXH2o7FST1jw",
        )

    def test_malformed_ambiguous_and_partial_configuration_fails_closed(self):
        invalid = (
            (json.dumps({"media-v1": encoded(1)}), "", ""),
            ("", "media-v1", ""),
            (json.dumps({"media-v1": "short"}), "media-v1", ""),
            (json.dumps({"bad key": encoded(1)}), "bad key", ""),
            ('{"media-v1":"%s","media-v1":"%s"}' % (encoded(1), encoded(2)), "media-v1", ""),
            (json.dumps({"media-v1": encoded(1)}), "missing", ""),
            (json.dumps({"media-v1": encoded(1)}), "media-v1", "legacy-key-material-that-is-long-enough-0001"),
            ("", "", "too-short"),
        )
        for raw, active, legacy in invalid:
            with self.subTest(raw=raw, active=active, legacy=bool(legacy)):
                with self.assertRaises(PublicMediaSigningConfigurationError):
                    PublicMediaSigningKeyring.from_environment(raw, active, legacy)

    def test_missing_historical_key_fails_closed(self):
        keyring = PublicMediaSigningKeyring.from_environment(
            json.dumps({"media-v2": encoded(2)}), "media-v2", ""
        )
        assert keyring is not None
        with self.assertRaises(PublicMediaSigningKeyUnavailableError):
            keyring.sign("media-v1", "media-1", "2026-07-30T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
