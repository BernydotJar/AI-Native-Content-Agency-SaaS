#!/usr/bin/env python3
"""Machine-verifiable delivery QA; creative/likeness QA always needs human review."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


class VideoQAError(Exception):
    pass


def run(*command: str) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=120)
    if result.returncode:
        raise VideoQAError(f"{command[0]} failed: {result.stderr[-1200:]}")
    return result.stdout


def probe(path: Path) -> dict:
    return json.loads(run(
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-print_format", "json", str(path)
    ))


def evaluate_metadata(data: dict, *, orientation: str = "vertical", tier: str = "preview") -> dict:
    streams = data.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    errors = []
    if len(videos) != 1:
        raise VideoQAError("expected exactly one video stream")
    v = videos[0]
    width, height = int(v.get("width", 0)), int(v.get("height", 0))
    duration = float(data.get("format", {}).get("duration", 0))
    fps = Fraction(v.get("avg_frame_rate", "0/1"))
    if v.get("codec_name") != "h264":
        errors.append("video codec must be H.264")
    if v.get("pix_fmt") != "yuv420p":
        errors.append("pixel format must be yuv420p for social compatibility")
    if not 4 <= duration <= 30:
        errors.append("clip duration outside 4..30 seconds")
    if fps < 24 or fps > 60:
        errors.append("frame rate outside 24..60 fps")
    minimum = 1080 if tier == "final" else 720
    if min(width, height) < minimum:
        errors.append(f"short edge is below {minimum}px for {tier}")
    if orientation == "vertical" and width >= height:
        errors.append("expected vertical 9:16 orientation")
    if orientation == "horizontal" and width <= height:
        errors.append("expected horizontal 16:9 orientation")
    if orientation == "vertical" and abs(width / max(height, 1) - 9 / 16) > .02:
        errors.append("vertical output must use approximately 9:16 aspect")
    if orientation == "horizontal" and abs(width / max(height, 1) - 16 / 9) > .02:
        errors.append("horizontal output must use approximately 16:9 aspect")
    if len(audio) != 1 or audio[0].get("codec_name") != "aac":
        errors.append("deliverable must include one AAC audio track (quiet bed or narration)")
    return {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "video": {"codec": v.get("codec_name"), "width": width, "height": height,
                  "fps": float(fps), "pixel_format": v.get("pix_fmt"),
                  "frames": int(v.get("nb_frames", "0") or "0")},
        "audio": {"codec": audio[0].get("codec_name")} if audio else None,
        "duration_seconds": round(duration, 3),
    }


def verify(path: Path, orientation: str, contact_sheet: Path | None, tier: str = "preview") -> dict:
    if not path.is_file() or path.stat().st_size < 4096:
        raise VideoQAError("input video is missing or too small")
    document = evaluate_metadata(probe(path), orientation=orientation, tier=tier)
    if document["status"] == "fail":
        return document
    # Actual decoding catches many corrupt frames that ffprobe metadata misses.
    run("ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-i", str(path), "-map", "0:v:0", "-f", "null", "-")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    document["sha256"] = sha
    document["size_bytes"] = path.stat().st_size
    run("ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-i", str(path), "-map", "0:a:0", "-f", "null", "-")
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-i",
         str(path), "-vf", "blackdetect=d=0.8:pix_th=0.025,freezedetect=n=-50dB:d=1.2",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        raise VideoQAError("video diagnostics failed")
    duration = document["duration_seconds"]
    frozen = []
    opened = None
    for match in re.finditer(r"lavfi.freezedetect.freeze_(start|end): (\d+(?:\.\d+)?)", result.stderr):
        if match.group(1) == "start":
            opened = float(match.group(2))
        elif opened is not None:
            frozen.append(round(float(match.group(2)) - opened, 3))
            opened = None
    if opened is not None:
        frozen.append(round(max(0, duration - opened), 3))
    document["max_freeze_seconds"] = max(frozen, default=0)
    document["blackout_events"] = len(re.findall(r"black_start:\s*[\d.]+", result.stderr))
    audio_scan = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-i", str(path),
         "-af", "volumedetect", "-vn", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    if audio_scan.returncode:
        raise VideoQAError("audio diagnostics failed")
    mean_match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", audio_scan.stderr)
    peak_match = re.search(r"max_volume:\s*(-?[\d.]+) dB", audio_scan.stderr)
    if not mean_match or not peak_match:
        raise VideoQAError("audio loudness data is missing")
    mean_db, peak_db = float(mean_match.group(1)), float(peak_match.group(1))
    document["audio_levels_dbfs"] = {"mean": mean_db, "peak": peak_db}
    warnings = []
    if document["max_freeze_seconds"] >= 1.2:
        warnings.append("Long apparent static hold; visually verify intentional pacing")
    if mean_db < -24 or mean_db > -12:
        warnings.append("Audio level outside approximate preview listening target (-24..-12 dBFS mean)")
    if peak_db > -1:
        document["errors"].append("Audio peak too close to clipping")
        document["status"] = "fail"
    document["warnings"] = warnings
    document["delivery_decode"] = "pass"
    document["prompt_adherence"] = "human_review_required"
    document["temporal_anatomy_and_object_consistency"] = "human_review_required"
    document["creative_quality"] = "human_review_required"
    document["marketing_release"] = "blocked_pending_human_and_release_authority"
    if contact_sheet:
        contact_sheet.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error", "-i",
            str(path), "-vf", "fps=1,scale=240:-2,tile=3x2",
            "-frames:v", "1", str(contact_sheet),
        ], capture_output=True, text=True, timeout=90)
        if result.returncode or not contact_sheet.is_file():
            raise VideoQAError("could not create contact sheet: " + result.stderr[-600:])
        document["contact_sheet"] = str(contact_sheet)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--orientation", choices=("vertical", "horizontal"), default="vertical")
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--tier", choices=("preview", "final"), default="preview")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.video, args.orientation, args.contact_sheet, tier=args.tier)
    except (VideoQAError, subprocess.TimeoutExpired, ValueError, OSError) as error:
        result = {"status": "fail", "errors": [str(error)]}
    print(json.dumps(result, sort_keys=True, indent=2))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
