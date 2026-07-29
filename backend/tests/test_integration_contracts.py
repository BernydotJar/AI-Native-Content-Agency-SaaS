import copy
import json
import unittest
from dataclasses import fields
from importlib.resources import files

from agency_runtime.integrations import (
    IntegrationContractError,
    IntegrationDisabledError,
    IntegrationExecutionReceipt,
    IntegrationInvocationPlan,
    IntegrationRegistry,
    IntegrationReviewManifest,
)


class IntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = IntegrationRegistry.default()

    def valid_plan(self, **overrides):
        values = {
            "integration_id": "video-use",
            "operation": "transcribe_media",
            "tenant_id": "tenant-alpha",
            "campaign_id": "campaign-alpha",
            "workspace_id": "workspace-alpha",
            "idempotency_key": "video-use:transcribe:command-0001",
            "greenlight_id": "greenlight-video-0001",
            "fencing_token": 7,
            "input_paths": ("inputs/interview.mp4",),
            "output_paths": ("outputs/interview.transcript.json",),
            "secret_refs": ("secret://elevenlabs/api-key",),
            "network_hosts": ("api.elevenlabs.io",),
            "untrusted_inputs": ("media", "transcript", "prompt"),
            "max_input_bytes": 50_000_000,
            "max_output_bytes": 5_000_000,
            "max_duration_seconds": 900,
            "max_attempts": 1,
            "max_cost_cents": 0,
        }
        values.update(overrides)
        return IntegrationInvocationPlan.review_only(**values)

    def test_manifest_is_exact_pinned_and_packaged(self):
        manifest = self.registry.get("video-use")
        self.assertEqual(manifest.schema, "agency-integration-review.v1")
        self.assertEqual(
            manifest.upstream_commit,
            "92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66",
        )
        self.assertEqual(manifest.license, "MIT")
        self.assertEqual(manifest.review_status, "reviewed_disabled")
        self.assertFalse(manifest.activation_allowed)
        self.assertFalse(manifest.execution_available)
        self.assertFalse(manifest.external_effects_enabled)
        self.assertIn("helpers/render.py", manifest.reviewed_files)
        self.assertIn(
            "VIDEO-USE-001", {item["id"] for item in manifest.known_findings}
        )
        packaged = files("agency_runtime").joinpath(
            "integration_reviews/video_use.json"
        )
        self.assertTrue(packaged.is_file())
        self.assertEqual(
            json.loads(packaged.read_text())["upstream_commit"],
            manifest.upstream_commit,
        )

    def test_manifest_mutation_and_malformed_collections_fail_closed(self):
        packaged = files("agency_runtime").joinpath(
            "integration_reviews/video_use.json"
        )
        source = json.loads(packaged.read_text())
        invalid = (
            {"activation_allowed": True},
            {"execution_available": True},
            {"external_effects_enabled": True},
            {"review_status": "enabled"},
            {"upstream_commit": "not-a-commit"},
            {"reviewed_at": "2026-07-21"},
            {"upstream_repository": "file:///tmp/repository"},
            {"capabilities": "video_rendering"},
            {"required_binaries": "ffmpeg"},
            {"optional_binaries": "yt-dlp"},
            {"external_services": "api.elevenlabs.io"},
            {"activation_requirements": "approve everything"},
            {"activation_requirements": []},
            {"known_findings": [{"id": "bad", "severity": "UNKNOWN", "code": "x", "state": "x", "evidence": "x"}]},
        )
        for override in invalid:
            candidate = copy.deepcopy(source)
            candidate.update(override)
            with self.subTest(override=override), self.assertRaises(
                IntegrationContractError
            ):
                IntegrationReviewManifest.from_mapping(candidate)

    def test_valid_review_plan_remains_non_executable(self):
        plan = self.valid_plan()
        self.assertFalse(plan.execution_permitted)
        self.assertEqual(plan.review_status, "review_only")
        self.assertEqual(plan.network_hosts, ("api.elevenlabs.io",))
        with self.assertRaises(IntegrationDisabledError):
            self.registry.execute(plan)
        with self.assertRaises(IntegrationDisabledError):
            self.registry.receipt_from_plan(
                plan,
                provider_request_id="provider-request-0001",
                output_sha256=("a" * 64,),
            )

    def test_approval_and_bounds_fail_closed(self):
        invalid = (
            {"idempotency_key": "short"},
            {"greenlight_id": ""},
            {"fencing_token": 0},
            {"max_input_bytes": 0},
            {"max_input_bytes": 500_000_001},
            {"max_output_bytes": 0},
            {"max_duration_seconds": 0},
            {"max_duration_seconds": 3601},
            {"max_attempts": 0},
            {"max_attempts": 4},
            {"max_cost_cents": 1},
            {"operation": "publish_video"},
            {"untrusted_inputs": ("media",)},
            {"untrusted_inputs": ("media", "transcript", "prompt", "trusted")},
        )
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(
                IntegrationContractError
            ):
                self.valid_plan(**override)

    def test_paths_secrets_and_egress_fail_closed(self):
        invalid = (
            {"input_paths": ("/etc/passwd",)},
            {"input_paths": ("inputs/../../etc/passwd",)},
            {"input_paths": ("inputs/%2e%2e/etc/passwd",)},
            {"input_paths": ("outputs/not-an-input.mp4",)},
            {"output_paths": ("/tmp/output.mp4",)},
            {"output_paths": ("outputs/../escape.mp4",)},
            {"output_paths": ("inputs/not-an-output.json",)},
            {"secret_refs": ("sk-live-secret-value",)},
            {"secret_refs": ("secret://unknown/key",)},
            {"network_hosts": ("evil.example",)},
            {"network_hosts": ("api.elevenlabs.io", "evil.example")},
        )
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(
                IntegrationContractError
            ):
                self.valid_plan(**override)

    def test_operation_specific_egress_and_secret_contract(self):
        with self.assertRaises(IntegrationContractError):
            self.valid_plan(
                operation="render_video",
                secret_refs=("secret://elevenlabs/api-key",),
                network_hosts=("api.elevenlabs.io",),
            )
        render = self.valid_plan(
            operation="render_video",
            input_paths=("inputs/timeline.json", "inputs/footage/clip.mp4"),
            output_paths=("outputs/final.mp4",),
            secret_refs=(),
            network_hosts=(),
        )
        self.assertFalse(render.execution_permitted)

    def test_future_receipt_shape_is_explicit_but_unconstructable(self):
        self.assertEqual(
            [field.name for field in fields(IntegrationExecutionReceipt)],
            [
                "schema",
                "integration_id",
                "operation",
                "tenant_id",
                "campaign_id",
                "workspace_id",
                "idempotency_key_digest",
                "greenlight_id",
                "fencing_token",
                "input_sha256",
                "output_sha256",
                "provider_request_id",
                "cost_cents",
                "completed_at",
            ],
        )
        with self.assertRaises(IntegrationDisabledError):
            self.registry.receipt_from_plan(
                self.valid_plan(),
                provider_request_id="provider-request-0001",
                output_sha256=("a" * 64,),
            )

    def test_unknown_manifest_is_not_enumerated(self):
        with self.assertRaises(KeyError):
            self.registry.get("unknown-integration")


if __name__ == "__main__":
    unittest.main()
