from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "neutral_instagram_publication.py"
SPEC = importlib.util.spec_from_file_location("neutral_instagram_publication", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class NeutralInstagramPublicationScriptTests(unittest.TestCase):
    def test_neutral_brief_and_caption_are_non_persuasive(self):
        brief = module.build_neutral_brief()
        caption = module.expected_caption()
        self.assertEqual(brief["platforms"], ["instagram"])
        self.assertEqual(brief["budget_cents"], 0)
        self.assertEqual(brief["publication_mode"], "organic")
        self.assertIn("No corresponde a una campaña electoral", caption)
        self.assertIn("No se requiere ninguna acción", caption)
        self.assertNotIn("vota", caption.lower())
        self.assertNotIn("apoya", caption.lower())


    def test_repeatability_variant_has_distinct_neutral_copy_and_media(self):
        baseline_caption = module.expected_caption(content_variant="baseline-v1")
        repeat_caption = module.expected_caption(content_variant="repeatability-v2")
        self.assertNotEqual(repeat_caption, baseline_caption)
        self.assertIn("segunda verificación técnica no electoral", repeat_caption)
        self.assertIn("No corresponde a una campaña electoral", repeat_caption)
        self.assertIn("No se requiere ninguna acción", repeat_caption)
        self.assertNotIn("vota", repeat_caption.lower())
        self.assertNotIn("apoya", repeat_caption.lower())
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.jpg"
            repeat = Path(directory) / "repeat.jpg"
            baseline_result = module.generate_neutral_media(baseline, "baseline-v1")
            repeat_result = module.generate_neutral_media(repeat, "repeatability-v2")
            self.assertNotEqual(repeat_result["sha256"], baseline_result["sha256"])
            self.assertEqual(repeat_result["width"], 1080)
            self.assertEqual(repeat_result["height"], 1350)

    def test_prepare_and_execute_flags_fail_closed(self):
        base = {
            "AGENCY_POLITICAL_CONTENT_ENABLED": "true",
            "AGENCY_SOCIAL_PUBLICATION_ENABLED": "false",
            "AGENCY_POLITICAL_PUBLICATION_ENABLED": "false",
            "AGENCY_POLITICAL_PAID_MEDIA_ENABLED": "false",
            "AGENCY_PUBLIC_MEDIA_BASE_URL": "https://media.example.test",
            "AGENCY_PUBLIC_MEDIA_SIGNING_KEY": "test-signing-key",
        }
        module.validate_prepare_flags(base)
        keyring = {
            **base,
            "AGENCY_PUBLIC_MEDIA_SIGNING_KEY": "",
            "AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON": "{\"media-v1\":\"opaque\"}",
            "AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID": "media-v1",
        }
        module.validate_prepare_flags(keyring)
        with self.assertRaises(module.NeutralPublicationError):
            module.validate_prepare_flags({**keyring, "AGENCY_PUBLIC_MEDIA_SIGNING_KEY": "legacy"})
        with self.assertRaises(module.NeutralPublicationError):
            module.validate_execute_flags(base)
        enabled = {
            **base,
            "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true",
            "AGENCY_POLITICAL_PUBLICATION_ENABLED": "true",
        }
        module.validate_execute_flags(enabled)
        with self.assertRaises(module.NeutralPublicationError):
            module.validate_prepare_flags(enabled)
        with self.assertRaises(module.NeutralPublicationError):
            module.validate_execute_flags(
                {**enabled, "AGENCY_POLITICAL_PAID_MEDIA_ENABLED": "true"}
            )

    def test_generated_media_is_exact_bounded_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "neutral.jpg"
            result = module.generate_neutral_media(target)
            self.assertEqual(result["width"], 1080)
            self.assertEqual(result["height"], 1350)
            self.assertEqual(result["content_type"], "image/jpeg")
            self.assertEqual(
                result["sha256"],
                module.sha256_bytes(target.read_bytes()),
            )
            self.assertLess(result["byte_size"], 8 * 1024 * 1024)

    def test_safe_receipt_block_omits_sensitive_fields(self):
        forbidden = {
            "api_key",
            "access_token",
            "client_secret",
            "media_url",
            "political_confirmation",
        }
        source = SCRIPT.read_text(encoding="utf-8")
        block = source.split("safe_receipt = {", 1)[1].split(
            "receipt_path.write_text", 1
        )[0]
        for field in forbidden:
            self.assertNotIn(f'"{field}"', block)

    def test_parser_requires_explicit_execution_acknowledgement(self):
        args = module.parser().parse_args(
            [
                "execute",
                "--manifest",
                "manifest.json",
                "--confirmation",
                "PUBLICAR POLITICA run-example instagram",
            ]
        )
        self.assertFalse(args.acknowledge_external_effect)


if __name__ == "__main__":
    unittest.main()
