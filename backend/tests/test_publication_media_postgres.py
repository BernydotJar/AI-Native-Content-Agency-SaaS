import hashlib
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agency_runtime.postgres import PostgresRuntimeDatabase, _connect_database_url
from agency_runtime.publication_media_postgres import PostgresPublicationMediaStore
from agency_runtime.publication_media_store import PublicationMediaRecord


DATABASE_URL = os.environ.get("AGENCY_TEST_DATABASE_URL", "")
MIGRATION_DATABASE_URL = os.environ.get(
    "AGENCY_TEST_MIGRATION_DATABASE_URL", DATABASE_URL
)
NOW = "2026-07-25T08:00:00+00:00"
EXPIRES = "2026-07-26T08:00:00+00:00"
FIXTURE = Path(__file__).parent / "fixtures" / "publication-media-320x400.jpg"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@unittest.skipUnless(DATABASE_URL, "AGENCY_TEST_DATABASE_URL is not configured")
class PostgresPublicationMediaStoreTests(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.tenant = "media-tenant-{}".format(suffix)
        self.media_id = "publication-media-{}".format(suffix)
        self.raw = FIXTURE.read_bytes()
        self.database_a = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.database_b = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.store_a = PostgresPublicationMediaStore(
            self.database_a, clock=lambda: NOW
        )
        self.store_b = PostgresPublicationMediaStore(
            self.database_b, clock=lambda: NOW
        )

    def tearDown(self):
        self.database_a.close()
        self.database_b.close()
        connection = _connect_database_url(
            MIGRATION_DATABASE_URL, timeout_seconds=10
        )
        try:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM public.publication_media_objects WHERE tenant_id = %s",
                (self.tenant,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record(self, **changes):
        values = {
            "media_id": self.media_id,
            "tenant_id": self.tenant,
            "run_id": "run-001",
            "channel_id": "instagram",
            "content_type": "image/jpeg",
            "byte_size": len(self.raw),
            "sha256": hashlib.sha256(self.raw).hexdigest(),
            "width": 320,
            "height": 400,
            "alt_text": "Tarjeta de prueba con fondo azul oscuro.",
            "rights_attested_by": "media-admin",
            "public_token_digest": digest("{}:public-token".format(self.tenant)),
            "idempotency_digest": digest("{}:idempotency".format(self.tenant)),
            "binding_digest": digest("{}:binding".format(self.tenant)),
            "created_at": NOW,
            "expires_at": EXPIRES,
            "revoked_at": None,
        }
        values.update(changes)
        return PublicationMediaRecord(**values)

    def test_two_replicas_share_one_binding_and_exact_bytes(self):
        record = self.record()
        with ThreadPoolExecutor(max_workers=2) as executor:
            reservations = [
                future.result()
                for future in (
                    executor.submit(self.store_a.reserve, record, self.raw),
                    executor.submit(self.store_b.reserve, record, self.raw),
                )
            ]
        self.assertEqual(sorted(item.created for item in reservations), [False, True])
        self.assertEqual({item.record.media_id for item in reservations}, {self.media_id})
        loaded, content = self.store_b.get_public(record.public_token_digest)
        self.assertEqual(loaded.sha256, record.sha256)
        self.assertEqual(content, self.raw)
        self.assertIsNone(self.store_b.get("other-tenant", self.media_id))

    def test_revocation_is_visible_across_replicas(self):
        record = self.record()
        self.store_a.create(record, self.raw)
        self.store_b.revoke(self.tenant, self.media_id, "rights_revoked")
        with self.assertRaises(KeyError):
            self.store_a.get_public(record.public_token_digest)


if __name__ == "__main__":
    unittest.main()
