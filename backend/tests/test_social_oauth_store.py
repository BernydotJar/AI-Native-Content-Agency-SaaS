import hashlib
import os
import uuid
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agency_runtime.social_oauth import EncryptedSocialValue
from agency_runtime.postgres import PostgresRuntimeDatabase
from agency_runtime.social_oauth_store import (
    PostgresSocialOAuthStore,
    SQLiteSocialOAuthStore,
    SocialConnectionRecord,
    SocialOAuthStateRecord,
    SocialOAuthStateUnavailableError,
)


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value.isoformat()

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SQLiteSocialOAuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "runtime.sqlite3"
        self.clock = MutableClock()
        self.store = SQLiteSocialOAuthStore(self.path, clock=self.clock)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def state(self, *, expires_in=600):
        now = self.clock.value
        return SocialOAuthStateRecord(
            state_id="social-state-001",
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            channel_id="x",
            state_digest=digest("raw-state-secret"),
            provider_token_digest=digest("request-token") ,
            encrypted_payload=EncryptedSocialValue(
                key_id="social-v1", ciphertext="opaque-encrypted-state-payload"
            ),
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=expires_in)).isoformat(),
            consumed_at=None,
        )

    def test_state_is_single_use_and_bound_to_tenant_session_channel_and_provider_token(self):
        self.store.create_state(self.state())
        consumed = self.store.consume_state(
            tenant_id="tenant-alpha",
            session_id="session-alpha",
            channel_id="x",
            state_digest=digest("raw-state-secret"),
            provider_token_digest=digest("request-token"),
        )
        self.assertIsNotNone(consumed.consumed_at)

        attempts = (
            ("tenant-alpha", "session-alpha", "x", "raw-state-secret", "request-token"),
            ("tenant-beta", "session-alpha", "x", "raw-state-secret", "request-token"),
            ("tenant-alpha", "session-beta", "x", "raw-state-secret", "request-token"),
            ("tenant-alpha", "session-alpha", "instagram", "raw-state-secret", "request-token"),
            ("tenant-alpha", "session-alpha", "x", "wrong-state", "request-token"),
            ("tenant-alpha", "session-alpha", "x", "raw-state-secret", "wrong-token"),
        )
        for tenant, session, channel, state, token in attempts:
            with self.subTest(tenant=tenant, session=session, channel=channel):
                with self.assertRaises(SocialOAuthStateUnavailableError):
                    self.store.consume_state(
                        tenant_id=tenant,
                        session_id=session,
                        channel_id=channel,
                        state_digest=digest(state),
                        provider_token_digest=digest(token),
                    )

    def test_expired_state_is_never_consumed(self):
        self.store.create_state(self.state(expires_in=10))
        self.clock.advance(11)
        with self.assertRaises(SocialOAuthStateUnavailableError):
            self.store.consume_state(
                tenant_id="tenant-alpha",
                session_id="session-alpha",
                channel_id="x",
                state_digest=digest("raw-state-secret"),
                provider_token_digest=digest("request-token"),
            )

    def test_connection_is_tenant_scoped_upserted_and_physically_deleted(self):
        record = SocialConnectionRecord(
            tenant_id="tenant-alpha",
            channel_id="instagram",
            account_id="ig-account-001",
            account_username="agency.account",
            encrypted_tokens=EncryptedSocialValue(
                key_id="social-v1", ciphertext="encrypted-instagram-token"
            ),
            scopes=("instagram_business_basic", "instagram_business_content_publish"),
            token_expires_at="2026-09-01T00:00:00+00:00",
            connected_at=self.clock(),
            updated_at=self.clock(),
        )
        self.store.upsert_connection(record)
        restored = self.store.get_connection("tenant-alpha", "instagram")
        self.assertEqual(restored.account_username, "agency.account")
        self.assertEqual(restored.scopes, record.scopes)
        self.assertIsNone(self.store.get_connection("tenant-beta", "instagram"))

        updated = SocialConnectionRecord(
            **{
                **record.__dict__,
                "account_username": "agency.updated",
                "updated_at": "2026-07-23T06:10:00+00:00",
            }
        )
        self.store.upsert_connection(updated)
        self.assertEqual(
            self.store.get_connection("tenant-alpha", "instagram").account_username,
            "agency.updated",
        )
        self.assertEqual(self.store.connection_count("tenant-alpha"), 1)

        self.assertTrue(self.store.delete_connection("tenant-alpha", "instagram"))
        self.assertFalse(self.store.delete_connection("tenant-alpha", "instagram"))
        self.assertIsNone(self.store.get_connection("tenant-alpha", "instagram"))
        raw = self.path.read_bytes()
        self.assertFalse(
            any(
                forbidden in raw
                for forbidden in (b"encrypted-instagram-token", b"agency.updated")
            )
        )

    def test_plaintext_tokens_and_raw_state_are_absent_from_database(self):
        self.store.create_state(self.state())
        self.store.upsert_connection(
            SocialConnectionRecord(
                tenant_id="tenant-alpha",
                channel_id="x",
                account_id="x-account-001",
                account_username="x_account",
                encrypted_tokens=EncryptedSocialValue(
                    key_id="social-v1", ciphertext="ciphertext-only-value"
                ),
                scopes=("read", "write"),
                token_expires_at=None,
                connected_at=self.clock(),
                updated_at=self.clock(),
            )
        )
        raw = self.path.read_bytes()
        for forbidden in (
            b"raw-state-secret",
            b"request-token",
            b"actual-access-token",
            b"actual-refresh-token",
        ):
            self.assertNotIn(forbidden, raw)


DATABASE_URL = os.environ.get("AGENCY_TEST_DATABASE_URL", "")


@unittest.skipUnless(DATABASE_URL, "AGENCY_TEST_DATABASE_URL is not configured")
class PostgresSocialOAuthStoreTests(unittest.TestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:12]
        self.tenant = "oauth-tenant-{}".format(suffix)
        self.session = "oauth-session-{}".format(suffix)
        self.clock = MutableClock()
        self.database_a = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.database_b = PostgresRuntimeDatabase(
            DATABASE_URL, min_size=1, max_size=2, schema_mode="validate"
        )
        self.store_a = PostgresSocialOAuthStore(self.database_a, clock=self.clock)
        self.store_b = PostgresSocialOAuthStore(self.database_b, clock=self.clock)
        self.store_a.clear_tenant(self.tenant)

    def tearDown(self):
        self.store_a.clear_tenant(self.tenant)
        self.database_a.close()
        self.database_b.close()

    def state(self):
        now = self.clock.value
        return SocialOAuthStateRecord(
            state_id="state-{}".format(uuid.uuid4().hex),
            tenant_id=self.tenant,
            session_id=self.session,
            channel_id="x",
            state_digest=digest("state-{}".format(self.tenant)),
            provider_token_digest=digest("provider-{}".format(self.tenant)),
            encrypted_payload=EncryptedSocialValue(
                key_id="social-v1", ciphertext="opaque-postgres-state"
            ),
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=10)).isoformat(),
            consumed_at=None,
        )

    def test_postgres_state_is_consumed_once_across_replicas(self):
        record = self.state()
        self.store_a.create_state(record)

        def consume(store):
            return store.consume_state(
                tenant_id=self.tenant,
                session_id=self.session,
                channel_id="x",
                state_digest=record.state_digest,
                provider_token_digest=record.provider_token_digest,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(consume, store) for store in (self.store_a, self.store_b)]
        successes = []
        failures = []
        for future in futures:
            try:
                successes.append(future.result())
            except SocialOAuthStateUnavailableError as error:
                failures.append(error)
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertIsNotNone(successes[0].consumed_at)

    def test_postgres_connection_is_shared_tenant_scoped_and_deleted(self):
        record = SocialConnectionRecord(
            tenant_id=self.tenant,
            channel_id="instagram",
            account_id="ig-{}".format(self.tenant),
            account_username="account.{}".format(self.tenant),
            encrypted_tokens=EncryptedSocialValue(
                key_id="social-v1", ciphertext="opaque-postgres-token"
            ),
            scopes=("instagram_business_basic", "instagram_business_content_publish"),
            token_expires_at="2026-09-01T00:00:00+00:00",
            connected_at=self.clock(),
            updated_at=self.clock(),
        )
        self.store_a.upsert_connection(record)
        restored = self.store_b.get_connection(self.tenant, "instagram")
        self.assertEqual(restored.account_id, record.account_id)
        self.assertEqual(restored.account_username, record.account_username)
        self.assertEqual(restored.scopes, record.scopes)
        self.assertIsNone(self.store_b.get_connection("different-tenant", "instagram"))
        self.assertEqual(self.store_b.connection_count(self.tenant), 1)
        self.assertTrue(self.store_b.delete_connection(self.tenant, "instagram"))
        self.assertIsNone(self.store_a.get_connection(self.tenant, "instagram"))


if __name__ == "__main__":
    unittest.main()
