from __future__ import annotations

import json
import subprocess
import unittest

from scripts.rollback_image_gate import RollbackGateError, inspect, protect


REPOSITORY = "us-central1-docker.pkg.dev/agency-dev/agency-images"
DESIRED = REPOSITORY + "/app@sha256:" + "a" * 64
ROLLBACK = REPOSITORY + "/app@sha256:" + "b" * 64
ROLLBACK_TAG = REPOSITORY + "/app:rollback-current"


def completed(stdout="{}", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class FakeRunner:
    def __init__(self, *, service_image=ROLLBACK, protected_digest="b" * 64):
        self.service_image = service_image
        self.protected_digest = protected_digest
        self.commands = []

    def __call__(self, command, **_kwargs):
        self.commands.append(command)
        joined = " ".join(command)
        if "run services describe" in joined:
            if self.service_image is None:
                return completed(returncode=1, stderr="NOT_FOUND: service not found")
            return completed(
                json.dumps(
                    {
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "application",
                                            "image": self.service_image,
                                        },
                                        {"name": "cloud-sql-proxy", "image": "ignored"},
                                    ]
                                }
                            }
                        }
                    }
                )
            )
        if "docker tags add" in joined:
            return completed()
        if ROLLBACK_TAG in command:
            return completed(json.dumps({"version": "sha256:" + self.protected_digest}))
        if DESIRED in command:
            return completed(json.dumps({"version": "sha256:" + "a" * 64}))
        if ROLLBACK in command:
            return completed(json.dumps({"version": "sha256:" + "b" * 64}))
        if self.service_image is not None and self.service_image in command:
            return completed(
                json.dumps({"version": self.service_image.rsplit("@", maxsplit=1)[-1]})
            )
        raise AssertionError(command)


class RollbackImageGateTest(unittest.TestCase):
    def inspect(self, runner, **overrides):
        arguments = {
            "artifact_repository": REPOSITORY,
            "desired_image": DESIRED,
            "project_id": "agency-dev",
            "region": "us-central1",
            "service_name": "agency-control-plane-dev",
            "require_protected_rollback": True,
            "runner": runner,
        }
        arguments.update(overrides)
        return inspect(**arguments)

    def test_existing_digest_and_protected_predecessor_pass(self):
        report = self.inspect(FakeRunner())
        self.assertEqual(report["rollback_image"], ROLLBACK)
        self.assertTrue(report["retention_verified"])
        self.assertEqual(report["rollback_depth"], 1)

    def test_wrong_application_registry_is_rejected(self):
        with self.assertRaisesRegex(RollbackGateError, "foundation repository"):
            self.inspect(
                FakeRunner(),
                desired_image="evil.invalid/app@sha256:" + "a" * 64,
            )

    def test_wrong_registry_on_deployed_predecessor_is_rejected(self):
        with self.assertRaisesRegex(RollbackGateError, "foundation repository"):
            self.inspect(FakeRunner(service_image="evil.invalid/app@sha256:" + "b" * 64))

    def test_missing_or_wrong_protected_tag_is_rejected(self):
        with self.assertRaisesRegex(RollbackGateError, "protected rollback tag"):
            self.inspect(FakeRunner(protected_digest="c" * 64))

    def test_first_deployment_has_explicit_single_depth_convention(self):
        report = self.inspect(FakeRunner(service_image=None))
        self.assertTrue(report["first_deployment"])
        self.assertIsNone(report["rollback_image"])
        self.assertFalse(report["retention_verified"])

    def test_plan_to_apply_candidate_change_is_rejected(self):
        baseline = self.inspect(FakeRunner())
        changed = REPOSITORY + "/app@sha256:" + "c" * 64
        with self.assertRaisesRegex(RollbackGateError, "candidate changed"):
            self.inspect(
                FakeRunner(service_image=changed),
                require_protected_rollback=False,
                baseline=baseline,
            )

    def test_protect_moves_one_reviewed_tag_and_verifies_it(self):
        runner = FakeRunner()
        baseline = self.inspect(runner, require_protected_rollback=False)
        report = protect(baseline, runner=runner)
        self.assertTrue(report["retention_verified"])
        self.assertTrue(any("docker tags add" in " ".join(c) for c in runner.commands))


if __name__ == "__main__":
    unittest.main()
