import hashlib
import tempfile
import unittest
from pathlib import Path

from agency_runtime.publication_media import (
    PublicationMediaValidationError,
    validate_publication_media,
)
from agency_runtime.publication_media_store import (
    PublicationMediaRecord,
    SQLitePublicationMediaStore,
)

NOW = "2026-07-25T08:00:00+00:00"
EXPIRES = "2026-07-26T08:00:00+00:00"
FIXTURE = Path(__file__).parent / "fixtures" / "publication-media-320x400.jpg"


class PublicationMediaValidationTests(unittest.TestCase):
    def test_valid_jpeg_is_fully_decoded_and_hashed(self):
        raw = FIXTURE.read_bytes()
        validated = validate_publication_media(raw, "image/jpeg")
        self.assertEqual((validated.width, validated.height), (320, 400))
        self.assertEqual(validated.byte_size, len(raw))
        self.assertEqual(validated.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(validated.content_type, "image/jpeg")

    def test_invalid_and_wrong_ratio_images_fail_closed(self):
        with self.assertRaises(PublicationMediaValidationError):
            validate_publication_media(b"not-a-jpeg", "image/jpeg")
        with self.assertRaises(PublicationMediaValidationError):
            validate_publication_media(FIXTURE.read_bytes(), "image/png")


class SQLitePublicationMediaStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.store = SQLitePublicationMediaStore(self.path, clock=lambda: NOW)
        self.raw = FIXTURE.read_bytes()
        self.record = PublicationMediaRecord(
            media_id="publication-media-001",
            tenant_id="tenant-alpha",
            run_id="run-001",
            channel_id="instagram",
            content_type="image/jpeg",
            byte_size=len(self.raw),
            sha256=hashlib.sha256(self.raw).hexdigest(),
            width=320,
            height=400,
            alt_text="Tarjeta de prueba con fondo azul oscuro.",
            rights_attested_by="media-admin",
            public_token_digest=hashlib.sha256(b"opaque-public-token").hexdigest(),
            created_at=NOW,
            expires_at=EXPIRES,
            revoked_at=None,
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_bytes_are_durable_and_public_lookup_is_digest_only(self):
        created = self.store.create(self.record, self.raw)
        self.assertEqual(created.sha256, self.record.sha256)
        self.store.close()
        self.store = SQLitePublicationMediaStore(self.path, clock=lambda: NOW)
        loaded, content = self.store.get_public(self.record.public_token_digest)
        self.assertEqual(loaded.media_id, self.record.media_id)
        self.assertEqual(content, self.raw)
        self.assertNotIn(b"opaque-public-token", self.path.read_bytes())

    def test_random_and_expired_public_capabilities_fail_closed(self):
        self.store.create(self.record, self.raw)
        with self.assertRaises(KeyError):
            self.store.get_public(hashlib.sha256(b"random-token").hexdigest())
        self.store.close()
        self.store = SQLitePublicationMediaStore(
            self.path, clock=lambda: "2026-07-27T08:00:00+00:00"
        )
        with self.assertRaises(KeyError):
            self.store.get_public(self.record.public_token_digest)

    def test_tenant_binding_and_revocation_fail_closed(self):
        self.store.create(self.record, self.raw)
        self.assertIsNone(self.store.get("tenant-other", self.record.media_id))
        self.store.revoke("tenant-alpha", self.record.media_id, "rights_revoked")
        with self.assertRaises(KeyError):
            self.store.get_public(self.record.public_token_digest)


if __name__ == "__main__":
    unittest.main()
