from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agency_runtime.api import create_app
from agency_runtime.audit_integrity import (
    GENESIS_AUDIT_HASH,
    AuditChainCheckpoint,
    AuditCheckpointSigningConfigurationError,
    AuditCheckpointSigningKeyUnavailableError,
    AuditCheckpointSigningKeyring,
    AuditIntegrityError,
    SignedAuditChainCheckpoint,
    audit_event_hash,
)
from agency_runtime.persistence import AuditWrite, SQLiteRunStore


def encoded(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).rstrip(b"=").decode("ascii")


class AuditIntegrityPrimitiveTests(unittest.TestCase):
    def test_event_hash_is_deterministic_and_binds_every_field(self) -> None:
        values = {
            "event_id": "audit-1",
            "tenant_id": "tenant-alpha",
            "request_id": "request-1",
            "occurred_at": "2026-07-30T08:00:00+00:00",
            "action": "run.created",
            "resource_type": "execution_run",
            "resource_id": "run-1",
            "actor": "subject:admin@example.com",
            "payload": {"a": 1, "b": [2, 3]},
            "previous_hash": GENESIS_AUDIT_HASH,
        }
        first = audit_event_hash(**values)
        second = audit_event_hash(**values)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        for field in (
            "event_id",
            "tenant_id",
            "request_id",
            "occurred_at",
            "action",
            "resource_type",
            "resource_id",
            "actor",
            "payload",
            "previous_hash",
        ):
            changed = dict(values)
            if field == "payload":
                changed[field] = {"a": 2}
            elif field == "previous_hash":
                changed[field] = "1" * 64
            else:
                changed[field] = str(values[field]) + "-changed"
            self.assertNotEqual(first, audit_event_hash(**changed), field)

    def test_keyring_is_strict_rotatable_and_secret_free(self) -> None:
        keys = json.dumps({"audit-v1": encoded(1), "audit-v2": encoded(2)})
        keyring = AuditCheckpointSigningKeyring.from_environment(keys, "audit-v2")
        assert keyring is not None
        checkpoint = AuditChainCheckpoint(
            tenant_id="tenant-alpha",
            event_count=2,
            head_event_id="audit-2",
            head_hash="a" * 64,
            verified_at="2026-07-30T08:01:00+00:00",
        )
        signed = keyring.sign(checkpoint)
        self.assertEqual(signed.key_id, "audit-v2")
        self.assertTrue(keyring.verify(signed))
        self.assertNotIn(encoded(1), repr(keyring))
        self.assertNotIn(encoded(2), repr(keyring))

        old_only = AuditCheckpointSigningKeyring.from_environment(
            json.dumps({"audit-v1": encoded(1)}), "audit-v1"
        )
        assert old_only is not None
        with self.assertRaises(AuditCheckpointSigningKeyUnavailableError):
            old_only.verify(signed)

        tampered = SignedAuditChainCheckpoint(
            checkpoint=AuditChainCheckpoint(
                tenant_id=checkpoint.tenant_id,
                event_count=3,
                head_event_id=checkpoint.head_event_id,
                head_hash=checkpoint.head_hash,
                verified_at=checkpoint.verified_at,
            ),
            key_id=signed.key_id,
            signature=signed.signature,
        )
        self.assertFalse(keyring.verify(tampered))

    def test_keyring_partial_weak_duplicate_and_noncanonical_config_fail(self) -> None:
        self.assertIsNone(AuditCheckpointSigningKeyring.from_environment("", ""))
        for raw, active in ((json.dumps({"a": encoded(1)}), ""), ("", "a")):
            with self.assertRaises(AuditCheckpointSigningConfigurationError):
                AuditCheckpointSigningKeyring.from_environment(raw, active)
        with self.assertRaises(AuditCheckpointSigningConfigurationError):
            AuditCheckpointSigningKeyring.from_environment(
                json.dumps({"a": base64.urlsafe_b64encode(b"weak").decode("ascii")}),
                "a",
            )
        with self.assertRaises(AuditCheckpointSigningConfigurationError):
            AuditCheckpointSigningKeyring.from_environment(
                '{"a":"%s","a":"%s"}' % (encoded(1), encoded(2)), "a"
            )
        with self.assertRaises(AuditCheckpointSigningConfigurationError):
            AuditCheckpointSigningKeyring.from_environment(
                json.dumps({"a": encoded(1) + "="}), "a"
            )

    def test_empty_checkpoint_uses_genesis(self) -> None:
        checkpoint = AuditChainCheckpoint(
            tenant_id="tenant-empty",
            event_count=0,
            head_event_id="",
            head_hash=GENESIS_AUDIT_HASH,
            verified_at="2026-07-30T08:02:00+00:00",
        )
        self.assertEqual(checkpoint.document()["head_hash"], GENESIS_AUDIT_HASH)


class SQLiteAuditIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "audit.sqlite3"
        self.store = SQLiteRunStore(self.path)

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    @staticmethod
    def write(index: int, *, tenant: str = "tenant-alpha") -> tuple[str, AuditWrite]:
        return tenant, AuditWrite(
            request_id=f"request-{index}",
            action="run.updated",
            resource_type="execution_run",
            resource_id=f"run-{index}",
            actor="subject:admin@example.com",
            payload={"index": index, "approved": index % 2 == 0},
            event_id=f"audit-{tenant}-{index}",
        )

    def append(self, index: int, *, tenant: str = "tenant-alpha") -> None:
        tenant_id, audit = self.write(index, tenant=tenant)
        self.store.append_audit(tenant_id, audit)

    def test_append_builds_independent_tenant_chains_and_checkpoint(self) -> None:
        self.append(1)
        self.append(2)
        self.append(1, tenant="tenant-beta")
        alpha = self.store.audit_events("tenant-alpha")
        beta = self.store.audit_events("tenant-beta")
        self.assertEqual(alpha[0].previous_hash, GENESIS_AUDIT_HASH)
        self.assertEqual(alpha[1].previous_hash, alpha[0].event_hash)
        self.assertEqual(beta[0].previous_hash, GENESIS_AUDIT_HASH)
        self.assertNotEqual(alpha[0].event_hash, beta[0].event_hash)
        checkpoint = self.store.verify_audit_chain("tenant-alpha")
        self.assertEqual(checkpoint.event_count, 2)
        self.assertEqual(checkpoint.head_event_id, alpha[-1].event_id)
        self.assertEqual(checkpoint.head_hash, alpha[-1].event_hash)

    def test_mutation_deletion_and_reordering_fail_closed(self) -> None:
        for index in range(1, 4):
            self.append(index)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE audit_events SET action = 'tampered' WHERE event_id = 'audit-tenant-alpha-2'"
            )
        with self.assertRaises(AuditIntegrityError):
            self.store.verify_audit_chain("tenant-alpha")

        self.store.close()
        self.path.unlink()
        self.store = SQLiteRunStore(self.path)
        for index in range(1, 4):
            self.append(index)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "DELETE FROM audit_events WHERE event_id = 'audit-tenant-alpha-3'"
            )
        with self.assertRaisesRegex(AuditIntegrityError, "head"):
            self.store.verify_audit_chain("tenant-alpha")

        self.store.close()
        self.path.unlink()
        self.store = SQLiteRunStore(self.path)
        for index in range(1, 4):
            self.append(index)
        with sqlite3.connect(self.path) as connection:
            first = connection.execute(
                "SELECT sequence FROM audit_events WHERE event_id = 'audit-tenant-alpha-1'"
            ).fetchone()[0]
            second = connection.execute(
                "SELECT sequence FROM audit_events WHERE event_id = 'audit-tenant-alpha-2'"
            ).fetchone()[0]
            connection.execute("UPDATE audit_events SET sequence = -1 WHERE sequence = ?", (first,))
            connection.execute("UPDATE audit_events SET sequence = ? WHERE sequence = ?", (first, second))
            connection.execute("UPDATE audit_events SET sequence = ? WHERE sequence = -1", (second,))
        with self.assertRaises(AuditIntegrityError):
            self.store.verify_audit_chain("tenant-alpha")

    def test_legacy_rows_backfill_deterministically_and_reopen_verified(self) -> None:
        self.store.close()
        self.path.unlink()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            for index in range(1, 3):
                connection.execute(
                    """
                    INSERT INTO audit_events(
                        event_id, tenant_id, request_id, occurred_at, action,
                        resource_type, resource_id, actor, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"legacy-{index}",
                        "tenant-alpha",
                        f"request-{index}",
                        f"2026-07-30T08:0{index}:00+00:00",
                        "legacy.event",
                        "legacy",
                        str(index),
                        "migration",
                        json.dumps({"index": index}),
                    ),
                )
        self.store = SQLiteRunStore(self.path)
        first = self.store.verify_audit_chain("tenant-alpha")
        self.store.close()
        self.store = SQLiteRunStore(self.path)
        second = self.store.verify_audit_chain("tenant-alpha")
        self.assertEqual(first.event_count, 2)
        self.assertEqual(first.head_hash, second.head_hash)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT previous_hash, event_hash FROM audit_events ORDER BY sequence"
            ).fetchall()
            head = connection.execute(
                "SELECT event_count, head_hash FROM audit_chain_heads"
            ).fetchone()
        self.assertEqual(rows[0][0], GENESIS_AUDIT_HASH)
        self.assertEqual(rows[1][0], rows[0][1])
        self.assertEqual(head, (2, rows[1][1]))



AUDIT_ADMIN_KEY = "audit-integrity-admin-key-material-2026"
AUDIT_OTHER_KEY = "audit-integrity-other-key-material-2026"
AUDIT_IDENTITIES = [
    {
        "tenant_id": "tenant-alpha",
        "subject_id": "admin@example.com",
        "role": "admin",
        "key_id": "admin-v1",
        "api_key": AUDIT_ADMIN_KEY,
        "active": True,
    },
    {
        "tenant_id": "tenant-beta",
        "subject_id": "other@example.com",
        "role": "admin",
        "key_id": "other-v1",
        "api_key": AUDIT_OTHER_KEY,
        "active": True,
    },
]


def authorization(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def create_audited_run(client: TestClient, key: str, suffix: str) -> None:
    response = client.post(
        "/api/v1/runs",
        headers={
            **authorization(key),
            "Idempotency-Key": "audit-integrity-{}-0001".format(suffix),
            "X-Request-ID": "audit-integrity-{}-0001".format(suffix),
        },
        json={
            "title": "Audit integrity {}".format(suffix),
            "objective": "Produce a tenant-scoped audit event",
            "audience": "security reviewers",
            "platforms": ["x"],
            "budget_cents": 0,
            "campaign_goal": "audit_integrity",
        },
    )
    if response.status_code not in {201, 202}:
        raise AssertionError(response.text)


class AuditIntegrityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "api.sqlite3"
        self.keys = json.dumps(
            {"audit-v1": encoded(1), "audit-v2": encoded(2)}
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def app(self, *, configured: bool = True):
        options = {}
        if configured:
            options = {
                "audit_checkpoint_signing_keys_json": self.keys,
                "audit_checkpoint_active_key_id": "audit-v2",
            }
        return create_app(
            database_path=str(self.path),
            static_dir=Path(self.temp.name) / "missing",
            tenant_api_keys={},
            identity_credentials=AUDIT_IDENTITIES,
            session_cookie_secure=False,
            session_ttl_seconds=600,
            **options,
        )

    def test_checkpoint_is_tenant_scoped_signed_and_secret_free(self) -> None:
        with TestClient(self.app()) as client:
            create_audited_run(client, AUDIT_ADMIN_KEY, "alpha")
            create_audited_run(client, AUDIT_OTHER_KEY, "beta")
            alpha_checkpoint = client.get(
                "/api/v1/audit-events/integrity",
                headers=authorization(AUDIT_ADMIN_KEY),
            )
            beta_checkpoint = client.get(
                "/api/v1/audit-events/integrity",
                headers=authorization(AUDIT_OTHER_KEY),
            )
            self.assertEqual(alpha_checkpoint.status_code, 200)
            self.assertEqual(beta_checkpoint.status_code, 200)
            alpha_document = alpha_checkpoint.json()
            beta_document = beta_checkpoint.json()
            self.assertEqual(alpha_document["tenant_id"], "tenant-alpha")
            self.assertEqual(beta_document["tenant_id"], "tenant-beta")
            self.assertEqual(alpha_document["key_id"], "audit-v2")
            self.assertNotEqual(alpha_document["head_hash"], beta_document["head_hash"])
            health = client.get("/healthz").json()
            ready = client.get("/readyz").json()
            self.assertTrue(health["audit_integrity_chain_enabled"])
            self.assertTrue(health["audit_checkpoint_signing_configured"])
            self.assertEqual(
                ready["audit_integrity"],
                {
                    "chain_enabled": True,
                    "checkpoint_signing_configured": True,
                    "active_key_id": "audit-v2",
                },
            )
            serialized = json.dumps(
                {"health": health, "ready": ready, "checkpoint": alpha_document}
            )
            self.assertNotIn(encoded(1), serialized)
            self.assertNotIn(encoded(2), serialized)

        checkpoint = AuditChainCheckpoint(
            tenant_id=alpha_document["tenant_id"],
            event_count=alpha_document["event_count"],
            head_event_id=alpha_document["head_event_id"],
            head_hash=alpha_document["head_hash"],
            verified_at=alpha_document["verified_at"],
        )
        signed = SignedAuditChainCheckpoint(
            checkpoint=checkpoint,
            key_id=alpha_document["key_id"],
            signature=alpha_document["signature"],
        )
        keyring = AuditCheckpointSigningKeyring.from_environment(
            self.keys, "audit-v2"
        )
        assert keyring is not None
        self.assertTrue(keyring.verify(signed))

    def test_unconfigured_checkpoint_returns_safe_conflict(self) -> None:
        with TestClient(self.app(configured=False)) as client:
            response = client.get(
                "/api/v1/audit-events/integrity",
                headers=authorization(AUDIT_ADMIN_KEY),
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(
                response.json()["code"], "audit_checkpoint_signing_unavailable"
            )
            self.assertFalse(client.get("/healthz").json()["audit_checkpoint_signing_configured"])

    def test_partial_or_weak_checkpoint_configuration_fails_startup(self) -> None:
        common = {
            "database_path": str(self.path),
            "static_dir": Path(self.temp.name) / "missing",
            "tenant_api_keys": {},
            "identity_credentials": AUDIT_IDENTITIES,
            "session_cookie_secure": False,
        }
        with self.assertRaisesRegex(ValueError, "audit checkpoint signing"):
            create_app(
                **common,
                audit_checkpoint_signing_keys_json=self.keys,
                audit_checkpoint_active_key_id="",
            )
        with self.assertRaisesRegex(ValueError, "audit checkpoint signing"):
            create_app(
                **common,
                audit_checkpoint_signing_keys_json=json.dumps(
                    {"weak": base64.urlsafe_b64encode(b"weak").decode("ascii")}
                ),
                audit_checkpoint_active_key_id="weak",
            )

    def test_tampered_ledger_returns_safe_service_failure(self) -> None:
        with TestClient(self.app()) as client:
            create_audited_run(client, AUDIT_ADMIN_KEY, "tamper")
            with sqlite3.connect(self.path) as connection:
                connection.execute(
                    "UPDATE audit_events SET actor = 'tampered' WHERE tenant_id = 'tenant-alpha'"
                )
            response = client.get(
                "/api/v1/audit-events/integrity",
                headers=authorization(AUDIT_ADMIN_KEY),
            )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                response.json()["code"], "audit_integrity_verification_failed"
            )
            self.assertNotIn("tampered", json.dumps(response.json()))



if __name__ == "__main__":
    unittest.main(verbosity=2)
