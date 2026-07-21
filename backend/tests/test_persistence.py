import tempfile
import unittest
from pathlib import Path

from agency_runtime.memory import SQLiteMemory
from agency_runtime.models import MissionBrief, Platform, Provenance
from agency_runtime.orchestrator import AgencyOrchestrator
from agency_runtime.persistence import SQLiteRunStore
from agency_runtime.tools import build_sandbox_toolset


FIXED_TIME = "2026-07-21T12:00:00+00:00"


def fixed_clock():
    return FIXED_TIME


class TenantPersistenceTests(unittest.TestCase):
    def test_memory_namespaces_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            provenance = Provenance(
                source="test",
                locator="sandbox://tenant-isolation",
                observed_at=FIXED_TIME,
            )
            with SQLiteMemory(
                database, clock=fixed_clock, namespace="tenant-alpha"
            ) as alpha:
                alpha_record = alpha.store(
                    alpha.observe(
                        "Shared phrase",
                        provenance,
                        confidence=0.9,
                        tags=("shared",),
                    )
                )
            with SQLiteMemory(
                database, clock=fixed_clock, namespace="tenant-beta"
            ) as beta:
                beta_record = beta.store(
                    beta.observe(
                        "Shared phrase",
                        provenance,
                        confidence=0.9,
                        tags=("shared",),
                    )
                )
                self.assertNotEqual(alpha_record.memory_id, beta_record.memory_id)
                with self.assertRaises(KeyError):
                    beta.recall(alpha_record.memory_id)

    def test_run_store_round_trip_preserves_greenlight_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite3"
            memory = SQLiteMemory(
                database, clock=fixed_clock, namespace="tenant-alpha"
            )
            try:
                orchestrator = AgencyOrchestrator(
                    build_sandbox_toolset(), memory, clock=fixed_clock
                )
                run = orchestrator.start(
                    MissionBrief(
                        title="Persistence fixture",
                        objective="Verify durable run serialization",
                        audience="reviewers",
                        platforms=(Platform.X, Platform.INSTAGRAM),
                    )
                )
                store = SQLiteRunStore(database, clock=fixed_clock)
                try:
                    store.create("tenant-alpha", run)
                    restored = store.get("tenant-alpha", run.run_id)
                    orchestrator.restore_run(restored)
                    approved = orchestrator.approve(
                        run.run_id, "owner", "durable fixture"
                    )
                    store.save("tenant-alpha", approved)
                    final = store.get("tenant-alpha", run.run_id)
                    self.assertEqual(final.status.value, "completed")
                    self.assertEqual(final.greenlight.note, "durable fixture")
                    self.assertEqual(len(final.artifacts), 8)
                    self.assertFalse(
                        final.artifact("campaign_package").payload[
                            "publication_performed"
                        ]
                    )
                finally:
                    store.close()
            finally:
                memory.close()


if __name__ == "__main__":
    unittest.main()
