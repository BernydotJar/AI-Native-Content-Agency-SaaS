"""Deterministic FFmpeg test: a compliant clip and intentionally failing constraints."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/video_quality_gate.py"
SPEC = importlib.util.spec_from_file_location("video_quality_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VideoQualityGateTests(unittest.TestCase):
    def test_decode_and_delivery_gate_are_distinct_from_editorial_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            movie = Path(temporary) / "synthetic-technical-fixture.mp4"
            command = [
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=384x216:rate=24",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=32000",
                "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", str(movie),
            ]
            subprocess.run(command, check=True, capture_output=True, timeout=35)

            passed = MODULE.inspect_video(
                movie, min_width=320, min_height=180,
                min_fps=24, min_duration=1.5, require_audio=True,
            )
            self.assertTrue(passed["technical_pass"])
            self.assertTrue(passed["audio"]["present"])
            self.assertTrue(passed["creative_review"]["required"])
            self.assertEqual(passed["creative_review"]["status"], "not_reviewed")
            self.assertFalse(passed["production_release_approved"])
            self.assertEqual(len(passed["sha256"]), 64)

            too_small = MODULE.inspect_video(movie)
            self.assertFalse(too_small["technical_pass"])
            self.assertIn("resolution_below_required", too_small["hard_failures"])
            self.assertFalse(too_small["production_release_approved"])

    def test_invalid_video_is_rejected_before_subprocess(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                MODULE.inspect_video(Path(temporary) / "missing.mp4")
            empty = Path(temporary) / "empty.mp4"
            empty.touch()
            with self.assertRaises(ValueError):
                MODULE.inspect_video(empty)


if __name__ == "__main__":
    unittest.main()
