from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from scripts.dev_apply_gate import (
    ALLOW_DECISION,
    ATTESTATION_SCHEMA,
    GateError,
    build_metadata,
    parse_attestation,
    source_tree_sha256,
    verify_attestation,
)


IMAGE_REFERENCE = "us-central1-docker.pkg.dev/agency-dev/images/app@sha256:" + "b" * 64
WORKFLOW_REF = "owner/repository/.github/workflows/deploy-dev.yml@refs/heads/main"
WORKFLOW_ACTOR = "workflow-actor"
REVIEWER = "independent-reviewer"
RUN_ID = "123456789"


class DevApplyGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        self._git("init", "--quiet")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Dev Apply Gate Tests")
        (self.repository / "application.txt").write_text("version one\n", encoding="utf-8")
        nested = self.repository / "public"
        nested.mkdir()
        (nested / "asset.txt").write_text("tracked asset\n", encoding="utf-8")
        self._commit_all("initial source")
        self.source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(self.repository),
            text=True,
        ).strip()
        self.plan = self.repository / "tfplan"
        self.plan.write_bytes(b"saved terraform plan\x00v1")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=str(self.repository),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _commit_all(self, message: str) -> None:
        self._git("add", "--all")
        self._git("commit", "--quiet", "-m", message)

    def _payload(self) -> Dict[str, str]:
        metadata = build_metadata(
            self.plan,
            self.repository,
            self.source_commit,
            IMAGE_REFERENCE,
            WORKFLOW_REF,
        )
        return {
            "schema_version": ATTESTATION_SCHEMA,
            "decision": ALLOW_DECISION,
            "plan_sha256": metadata["plan_sha256"],
            "source_tree_sha256": metadata["source_tree_sha256"],
            "source_commit": self.source_commit,
            "image_reference": IMAGE_REFERENCE,
            "workflow_ref": WORKFLOW_REF,
            "workflow_actor": WORKFLOW_ACTOR,
            "reviewer": REVIEWER,
            "environment": "dev",
            "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "evidence_url": "https://github.com/owner/repository/actions/runs/{}".format(RUN_ID),
        }

    def _verify(self, payload: Dict[str, str]) -> Dict[str, str]:
        return verify_attestation(
            json.dumps(payload),
            self.plan,
            self.repository,
            self.source_commit,
            IMAGE_REFERENCE,
            WORKFLOW_REF,
            WORKFLOW_ACTOR,
            RUN_ID,
        )

    def test_full_tracked_tree_hash_is_deterministic_and_ignores_untracked_files(
        self,
    ) -> None:
        original = source_tree_sha256(self.repository)
        self.assertEqual(source_tree_sha256(self.repository), original)

        (self.repository / "untracked.txt").write_text("not part of source\n", encoding="utf-8")
        self.assertEqual(source_tree_sha256(self.repository), original)

        (self.repository / "public" / "asset.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "uncommitted changes"):
            source_tree_sha256(self.repository)
        self._commit_all("change formerly omitted path")
        self.assertNotEqual(source_tree_sha256(self.repository), original)

    def test_valid_exact_attestation_is_verified(self) -> None:
        result = self._verify(self._payload())
        self.assertEqual(result["result"], "VERIFIED")
        self.assertEqual(result["decision"], ALLOW_DECISION)
        self.assertEqual(result["reviewer"], REVIEWER)
        self.assertRegex(result["attestation_sha256"], r"^[0-9a-f]{64}$")

    def test_every_runtime_binding_is_fail_closed(self) -> None:
        mismatches = {
            "decision": "DENY_APPLY",
            "plan_sha256": "0" * 64,
            "source_tree_sha256": "1" * 64,
            "source_commit": "c" * 40,
            "image_reference": "us-central1-docker.pkg.dev/agency-dev/images/app@sha256:"
            + "d" * 64,
            "workflow_ref": "owner/repository/.github/workflows/other.yml@refs/heads/main",
            "workflow_actor": "another-actor",
            "environment": "stage",
            "evidence_url": "https://github.com/owner/repository/actions/runs/999",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                payload = self._payload()
                payload[field] = value
                with self.assertRaises(GateError):
                    self._verify(payload)

    def test_reviewer_must_be_distinct_from_actor(self) -> None:
        payload = self._payload()
        payload["reviewer"] = WORKFLOW_ACTOR.upper()
        with self.assertRaisesRegex(GateError, "reviewer must differ"):
            self._verify(payload)

    def test_locked_schema_rejects_missing_unknown_and_duplicate_fields(self) -> None:
        payload = self._payload()
        missing = dict(payload)
        missing.pop("reviewer")
        with self.assertRaisesRegex(GateError, "locked schema"):
            parse_attestation(json.dumps(missing))

        unknown = dict(payload)
        unknown["comment"] = "not permitted"
        with self.assertRaisesRegex(GateError, "locked schema"):
            parse_attestation(json.dumps(unknown))

        encoded = json.dumps(payload)
        duplicate = encoded[:-1] + ',"decision":"ALLOW_DEV_APPLY"}'
        with self.assertRaisesRegex(GateError, "duplicate key"):
            parse_attestation(duplicate)

    def test_plan_mutation_invalidates_attestation(self) -> None:
        payload = self._payload()
        self.plan.write_bytes(b"different saved plan")
        with self.assertRaisesRegex(GateError, "plan_sha256"):
            self._verify(payload)

    def test_source_commit_must_match_checked_out_head(self) -> None:
        with self.assertRaisesRegex(GateError, "checked-out HEAD"):
            build_metadata(
                self.plan,
                self.repository,
                "a" * 40,
                IMAGE_REFERENCE,
                WORKFLOW_REF,
            )


if __name__ == "__main__":
    unittest.main()
