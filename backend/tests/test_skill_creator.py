import os
import tempfile
import unittest
from pathlib import Path

from agency_runtime import (
    DynamicSkillCreator,
    SkillAlreadyExistsError,
    SkillCreationError,
    UnsafeSkillPathError,
    load_flow_manifest,
)


class DynamicSkillCreatorTests(unittest.TestCase):
    def test_creates_deterministic_markdown_inside_explicit_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            creator = DynamicSkillCreator(root)
            result = creator.create(
                slug="brand-guard",
                title="Brand Guard",
                description="Review each draft against the local brand policy.",
                instructions=(
                    "Check tone and prohibited claims.",
                    "Return evidence with every flagged issue.",
                ),
            )
            self.assertEqual(result.path, root.resolve() / "brand-guard.md")
            self.assertTrue(result.path.is_file())
            content = result.path.read_text(encoding="utf-8")
            self.assertIn("generated_by: agency_runtime.DynamicSkillCreator", content)
            self.assertIn("1. Check tone and prohibited claims.", content)
            self.assertEqual(len(result.sha256), 64)
            self.assertFalse(result.overwritten)
            self.assertEqual(os.stat(result.path).st_mode & 0o777, 0o600)

    def test_blocks_path_traversal_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            creator = DynamicSkillCreator(Path(directory) / "skills")
            unsafe_slugs = (
                "../escape",
                "nested/escape",
                "/tmp/escape",
                ".",
                "..",
                "skill.md",
                "MixedCase",
            )
            for slug in unsafe_slugs:
                with self.subTest(slug=slug), self.assertRaises(UnsafeSkillPathError):
                    creator.create(slug, "Title", "Description", ("Instruction",))

    def test_overwrite_is_opt_in_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            creator = DynamicSkillCreator(Path(directory) / "skills")
            original = creator.create(
                "safe-skill", "Safe Skill", "First version", ("First step",)
            )
            with self.assertRaises(SkillAlreadyExistsError):
                creator.create(
                    "safe-skill", "Safe Skill", "Second version", ("Second step",)
                )
            replaced = creator.create(
                "safe-skill",
                "Safe Skill",
                "Second version",
                ("Second step",),
                overwrite=True,
            )
            self.assertTrue(replaced.overwritten)
            self.assertNotEqual(original.sha256, replaced.sha256)
            self.assertIn(
                "Second version", replaced.path.read_text(encoding="utf-8")
            )

    def test_symlink_escape_is_rejected_even_when_overwrite_is_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "skills"
            creator = DynamicSkillCreator(root)
            outside = base / "outside.md"
            outside.write_text("do not replace", encoding="utf-8")
            destination = root / "escape.md"
            try:
                destination.symlink_to(outside)
            except (NotImplementedError, OSError):
                self.skipTest("symlinks are unavailable on this platform")
            with self.assertRaises(UnsafeSkillPathError):
                creator.create(
                    "escape",
                    "Escape",
                    "Must remain contained",
                    ("Do not follow symlinks",),
                    overwrite=True,
                )
            self.assertEqual(outside.read_text(encoding="utf-8"), "do not replace")

    def test_rejects_invalid_content(self):
        with tempfile.TemporaryDirectory() as directory:
            creator = DynamicSkillCreator(Path(directory) / "skills")
            with self.assertRaises(SkillCreationError):
                creator.create("valid", "Title\x07", "Description", ("Step",))
            with self.assertRaises(SkillCreationError):
                creator.create("valid", "Title", "Description", ())

    def test_rejects_a_file_as_the_explicit_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root_file = Path(directory) / "not-a-directory"
            root_file.write_text("occupied", encoding="utf-8")
            with self.assertRaises(SkillCreationError):
                DynamicSkillCreator(root_file)


class FlowManifestTests(unittest.TestCase):
    def test_manifest_describes_eight_agent_sandbox_and_gate(self):
        manifest = load_flow_manifest()
        self.assertEqual(manifest["runtime_mode"], "deterministic_sandbox")
        self.assertFalse(manifest["external_framework_required"])
        self.assertFalse(manifest["external_side_effects_enabled"])
        self.assertEqual(len(manifest["agents"]), 8)
        self.assertEqual(manifest["approval_gate"]["before"], "publisher")


if __name__ == "__main__":
    unittest.main()
