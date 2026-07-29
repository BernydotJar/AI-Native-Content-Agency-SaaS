from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "neutral_x_publication.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("neutral_x_publication", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class NeutralXPublicationScriptTests(unittest.TestCase):
    def test_neutral_text_is_bounded_and_non_persuasive(self):
        brief = module.build_neutral_x_brief()
        text = module.expected_x_text()
        self.assertEqual(brief["platforms"], ["x"])
        self.assertEqual(brief["budget_cents"], 0)
        self.assertEqual(brief["publication_mode"], "organic")
        self.assertLessEqual(len(text), 280)
        self.assertEqual(len(text), 276)
        self.assertEqual(
            module.common.sha256_text(text),
            "582e6e4137624526250a0feab6abf0a4a9b502e453f703f42dcc7a8956170f96",
        )
        self.assertIn("No corresponde a una campaña electoral", text)
        self.assertIn("No se requiere acción", text)
        self.assertNotIn("vota", text.lower())
        self.assertNotIn("apoya", text.lower())

    def test_prepare_and_execute_flags_fail_closed(self):
        base = {
            "AGENCY_POLITICAL_CONTENT_ENABLED": "true",
            "AGENCY_SOCIAL_PUBLICATION_ENABLED": "false",
            "AGENCY_POLITICAL_PUBLICATION_ENABLED": "false",
            "AGENCY_POLITICAL_PAID_MEDIA_ENABLED": "false",
        }
        module.validate_prepare_flags(base)
        with self.assertRaises(module.common.NeutralPublicationError):
            module.validate_execute_flags(base)
        enabled = {
            **base,
            "AGENCY_SOCIAL_PUBLICATION_ENABLED": "true",
            "AGENCY_POLITICAL_PUBLICATION_ENABLED": "true",
        }
        module.validate_execute_flags(enabled)
        with self.assertRaises(module.common.NeutralPublicationError):
            module.validate_prepare_flags(enabled)

    def test_parser_requires_explicit_external_effect_acknowledgement(self):
        args = module.parser().parse_args(
            [
                "execute",
                "--manifest",
                "manifest.json",
                "--confirmation",
                "PUBLICAR POLITICA run-example x",
            ]
        )
        self.assertFalse(args.acknowledge_external_effect)

    def test_safe_receipt_omits_credentials_and_raw_confirmation(self):
        source = SCRIPT.read_text(encoding="utf-8")
        block = source.split("safe_receipt = {", 1)[1].split(
            "receipt_path.write_text", 1
        )[0]
        for field in (
            "api_key",
            "access_token",
            "access_token_secret",
            "consumer_secret",
            "political_confirmation",
        ):
            self.assertNotIn('"{}"'.format(field), block)


if __name__ == "__main__":
    unittest.main()
