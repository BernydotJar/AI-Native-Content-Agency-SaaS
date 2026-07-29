import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "publish-branch-via-git-data.py"
SPEC = importlib.util.spec_from_file_location("git_data_publisher", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Git Data publisher")
PUBLISHER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PUBLISHER
SPEC.loader.exec_module(PUBLISHER)


class GitDataPublisherTests(unittest.TestCase):
    def test_parse_git_tree_handles_binary_safe_paths(self):
        raw = (
            b"100644 blob aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\tREADME.md\0"
            b"100755 blob bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\tscripts/run.sh\0"
        )
        tree = PUBLISHER.parse_git_tree(raw)
        self.assertEqual(tree["README.md"].mode, "100644")
        self.assertEqual(tree["scripts/run.sh"].mode, "100755")
        self.assertEqual(tree["scripts/run.sh"].object_type, "blob")

    def test_changed_paths_detects_add_modify_delete_and_mode_change(self):
        entry = PUBLISHER.TreeEntry
        local = {
            "added.txt": entry("added.txt", "100644", "blob", "a" * 40),
            "modified.txt": entry("modified.txt", "100644", "blob", "b" * 40),
            "mode.sh": entry("mode.sh", "100755", "blob", "c" * 40),
            "same.txt": entry("same.txt", "100644", "blob", "d" * 40),
        }
        remote = {
            "deleted.txt": entry("deleted.txt", "100644", "blob", "e" * 40),
            "modified.txt": entry("modified.txt", "100644", "blob", "f" * 40),
            "mode.sh": entry("mode.sh", "100644", "blob", "c" * 40),
            "same.txt": entry("same.txt", "100644", "blob", "d" * 40),
        }
        self.assertEqual(
            PUBLISHER.changed_paths(local, remote),
            ("added.txt", "deleted.txt", "mode.sh", "modified.txt"),
        )

    def test_parse_remote_tree_rejects_truncation(self):
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            PUBLISHER.parse_remote_tree({"truncated": True, "tree": []})

    def test_parse_remote_tree_ignores_directory_nodes(self):
        tree = PUBLISHER.parse_remote_tree(
            {
                "truncated": False,
                "tree": [
                    {
                        "path": "scripts",
                        "mode": "040000",
                        "type": "tree",
                        "sha": "a" * 40,
                    },
                    {
                        "path": "scripts/run.sh",
                        "mode": "100755",
                        "type": "blob",
                        "sha": "b" * 40,
                    },
                ],
            }
        )
        self.assertEqual(tuple(tree), ("scripts/run.sh",))

    def test_parse_git_tree_rejects_duplicate_paths(self):
        raw = (
            b"100644 blob aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\tdup.txt\0"
            b"100644 blob bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\tdup.txt\0"
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            PUBLISHER.parse_git_tree(raw)


if __name__ == "__main__":
    unittest.main()
