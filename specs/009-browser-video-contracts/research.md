# Research — exact upstream review

## Source

- repository: `https://github.com/browser-use/video-use`
- exact commit: `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`
- commit verification: valid GitHub signature on the reviewed merge commit
- license: MIT
- releases/tags at review: none
- default branch protection: absent
- repository `SECURITY.md`: absent
- repository CI workflow: absent
- merged dependency lock: absent; upstream PR `#108` proposes `uv.lock`

## Direct execution surfaces

- `helpers/transcribe.py`: local media extraction plus HTTP upload to
  `https://api.elevenlabs.io/v1/speech-to-text` with `xi-api-key`.
- `helpers/transcribe_batch.py`: up to four concurrent transcription workers.
- `helpers/render.py`: caller-controlled EDL paths, ffmpeg filters, input/output
  files and rendered artifacts.
- `helpers/grade.py`: ffmpeg/ffprobe subprocesses and raw filter strings.
- `helpers/timeline_view.py`: frame/audio extraction and PNG generation.
- `install.md`: cloning, package installation, skill-directory symlinks,
  `.env` credential writes and credential validation request.
- `SKILL.md`: persistent `project.md`, optional downloads, shell-capable
  animation frameworks and parallel subagents.

## Reproducibility evidence

The review manifest stores SHA-256 for all 33 files in the exact tree. The
runtime packages the manifest only; no upstream source or dependencies are
vendored.

## Disposition

Useful product concepts were retained as a product-owned, review-only contract:
exact source identity, path roots, egress, secret references, approval/fence,
bounds and receipt fields. The implementation itself was rejected for runtime
adoption until its HIGH findings and product-specific authority gaps are closed.
