import base64
import json
import os
import unittest

from agency_runtime.social_oauth import (
    EncryptedSocialValue,
    SocialTokenCipher,
    SocialTokenCipherConfigurationError,
    SocialTokenDecryptionError,
)


def key(seed: int) -> str:
    raw = bytes(((seed + index) % 256 for index in range(32)))
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class SocialTokenCipherTests(unittest.TestCase):
    def test_encrypts_authenticated_payload_and_hides_keys_from_repr(self):
        cipher = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": key(1)}), "social-v1"
        )
        value = cipher.encrypt(
            {"access_token": "secret-access", "refresh_token": "secret-refresh"},
            associated_data="tenant-alpha:x:connection",
        )

        self.assertEqual(value.key_id, "social-v1")
        self.assertNotIn("secret-access", value.ciphertext)
        self.assertNotIn("secret-refresh", value.ciphertext)
        self.assertEqual(
            cipher.decrypt(value, associated_data="tenant-alpha:x:connection"),
            {"access_token": "secret-access", "refresh_token": "secret-refresh"},
        )
        rendered = repr(cipher)
        self.assertIn("social-v1", rendered)
        self.assertNotIn(key(1), rendered)
        self.assertNotIn("secret", rendered)

    def test_wrong_tenant_or_tampering_fails_closed(self):
        cipher = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": key(7)}), "social-v1"
        )
        encrypted = cipher.encrypt(
            {"access_token": "tenant-bound-token"},
            associated_data="tenant-alpha:instagram:connection",
        )

        with self.assertRaises(SocialTokenDecryptionError):
            cipher.decrypt(
                encrypted,
                associated_data="tenant-beta:instagram:connection",
            )

        raw = bytearray(base64.urlsafe_b64decode(encrypted.ciphertext + "=="))
        raw[-1] ^= 1
        tampered = EncryptedSocialValue(
            key_id=encrypted.key_id,
            ciphertext=base64.urlsafe_b64encode(bytes(raw)).decode("ascii").rstrip("="),
        )
        with self.assertRaises(SocialTokenDecryptionError):
            cipher.decrypt(
                tampered,
                associated_data="tenant-alpha:instagram:connection",
            )

    def test_rotation_decrypts_old_key_and_encrypts_with_active_key(self):
        first = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": key(2)}), "social-v1"
        )
        old_value = first.encrypt(
            {"access_token": "old-token"}, associated_data="tenant-alpha:x:connection"
        )
        rotated = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": key(2), "social-v2": key(3)}), "social-v2"
        )

        self.assertEqual(
            rotated.decrypt(old_value, associated_data="tenant-alpha:x:connection"),
            {"access_token": "old-token"},
        )
        new_value = rotated.encrypt(
            {"access_token": "new-token"}, associated_data="tenant-alpha:x:connection"
        )
        self.assertEqual(new_value.key_id, "social-v2")

    def test_configuration_is_strict_and_requires_32_byte_keys(self):
        invalid_values = (
            (None, None),
            ("{}", "social-v1"),
            (json.dumps({"social-v1": "short"}), "social-v1"),
            (json.dumps({"social-v1": key(4)}), "missing"),
            (json.dumps({"bad key id": key(4)}), "bad key id"),
            (json.dumps([key(4)]), "social-v1"),
        )
        for raw_keys, active in invalid_values:
            with self.subTest(raw_keys=raw_keys, active=active):
                with self.assertRaises(SocialTokenCipherConfigurationError):
                    SocialTokenCipher.from_environment(raw_keys, active)

    def test_plaintext_shape_and_size_are_bounded(self):
        cipher = SocialTokenCipher.from_environment(
            json.dumps({"social-v1": key(5)}), "social-v1"
        )
        for payload in ({}, {"nested": {"not": "allowed"}}, {"huge": "x" * 20000}):
            with self.subTest(payload=list(payload)):
                with self.assertRaises(ValueError):
                    cipher.encrypt(payload, associated_data="tenant-alpha:x:connection")


if __name__ == "__main__":
    unittest.main()
