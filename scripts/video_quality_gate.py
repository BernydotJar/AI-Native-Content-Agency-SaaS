#!/usr/bin/env python3
"""Local technical QA of a rendered video. This does NOT judge creative quality.

Requires ffmpeg + ffprobe; never calls a video generation provider or network.
The visual/semantic release decision always requires a human reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def _run(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def inspect_video(
    path: Path,
    *,
    min_width: int = 1280,
    min_height: int = 720,
    min_fps: float = 24.0,
    min_duration: float = 2.0,
    require_audio: bool = False,
) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("input must be a nonempty local video file")
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError("QA input exceeds 512 MiB limit")
    probe = _run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ], timeout=30)
    if probe.returncode:
        raise ValueError("ffprobe could not decode input metadata")
    data = json.loads(probe.stdout)
    streams = data.get("streams", [])
    visual = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not visual:
        raise ValueError("video stream is missing")
    rate = str(visual.get("avg_frame_rate") or visual.get("r_frame_rate") or "0/1")
    try:
        numerator, denominator = (rate.split("/") + ["1"])[:2]
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    duration = float(visual.get("duration") or data.get("format", {}).get("duration") or 0)
    width = int(visual.get("width", 0))
    height = int(visual.get("height", 0))
    failures = []
    if width < min_width or height < min_height:
        failures.append("resolution_below_required")
    if fps < min_fps:
        failures.append("frame_rate_below_required")
    if duration < min_duration:
        failures.append("duration_below_required")
    if require_audio and not audio:
        failures.append("missing_audio")
    if visual.get("codec_name") not in {"h264", "hevc", "vp9", "av1"}:
        failures.append("unsupported_delivery_codec")
    if visual.get("pix_fmt") not in {"yuv420p", "yuvj420p", "yuv420p10le"}:
        failures.append("delivery_pixel_format_requires_review")

    decoded = _run([
        "ffmpeg", "-nostdin", "-v", "error", "-xerror",
        "-i", str(path), "-f", "null", "-",
    ], timeout=120)
    if decoded.returncode:
        failures.append("video_decode_failure")
    analysis = _run([
        "ffmpeg", "-nostdin", "-hide_banner", "-nostats",
        "-i", str(path),
        "-vf", "blackdetect=d=0.25:pix_th=0.08,freezedetect=n=-60dB:d=0.5",
        "-an", "-f", "null", "-",
    ], timeout=120)
    warnings = []
    if analysis.returncode:
        warnings.append("visual_diagnostics_failed")
    black_events = len(re.findall(r"black_start:", analysis.stderr))
    frozen_events = len(re.findall(r"freeze_start:", analysis.stderr))
    if black_events:
        warnings.append("black_frames_or_creative_blackout_review")
    if frozen_events:
        warnings.append("freeze_or_intentional_static_shot_review")
    if audio and audio.get("codec_name") != "aac":
        warnings.append("audio_codec_compatibility_review")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "schema": "agency.video_quality.v1",
        "input_filename": path.name,
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
        "video": {
            "width": width, "height": height, "fps": round(fps, 3),
            "duration_seconds": round(duration, 3),
            "codec": visual.get("codec_name"),
            "pixel_format": visual.get("pix_fmt"),
        },
        "audio": {
            "present": bool(audio),
            "codec": audio.get("codec_name") if audio else None,
            "sample_rate_hz": int(audio.get("sample_rate") or 0) if audio else 0,
        },
        "diagnostics": {"black_events": black_events, "freeze_events": frozen_events},
        "technical_pass": not failures,
        "hard_failures": failures,
        "warnings": warnings,
        "creative_review": {
            "required": True,
            "status": "not_reviewed",
            "criteria": [
                "subject_and_identity_consistency",
                "hands_food_utensil_interaction_and_physics",
                "temporal_motion_coherence",
                "cinematography_lighting_and_composition",
                "audio_sync_and_storytelling",
                "rights_and_synthetic_media_disclosure",
            ],
        },
        "production_release_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Technical QA, not a cinematic quality score")
    parser.add_argument("video", type=Path)
    parser.add_argument("--min-width", type=int, default=1280)
    parser.add_argument("--min-height", type=int, default=720)
    parser.add_argument("--min-fps", type=float, default=24)
    parser.add_argument("--min-duration", type=float, default=2)
    parser.add_argument("--require-audio", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_video(
            args.video, min_width=args.min_width, min_height=args.min_height,
            min_fps=args.min_fps, min_duration=args.min_duration,
            require_audio=args.require_audio,
        )
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        result = {"schema": "agency.video_quality.v1", "technical_pass": False,
                  "hard_failures": [type(error).__name__], "production_release_approved": False}
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(serialized, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    return 0 if result["technical_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
