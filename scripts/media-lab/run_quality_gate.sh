#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [ -z "${PYTHON_BIN:-}" ]; then PYTHON_BIN=python3; fi
"$PYTHON_BIN" -c 'import PIL' || { echo 'Install Pillow 12.0.0 for render_storyboards.py' >&2; exit 1; }
python3 -m unittest discover -s scripts/media-lab -p test_check_video.py -v
"$PYTHON_BIN" scripts/media-lab/render_storyboards.py --outdir artifacts/media-lab/generated
for n in spaghetti campaignos; do
  python3 scripts/media-lab/check_video.py "artifacts/media-lab/generated/$n-illustrated-storyboard.mp4" \
    --tier preview --contact-sheet "artifacts/media-lab/generated/$n-illustrated-contact.png" \
    --json-out "artifacts/media-lab/generated/$n-illustrated-qa.json" >/dev/null
done
python3 - <<'PY'
import json
from pathlib import Path
for key in ('spaghetti', 'campaignos'):
    p=Path('artifacts/media-lab/generated')/(key+'-illustrated-qa.json')
    doc=json.loads(p.read_text())
    assert doc['status']=='pass' and doc['delivery_decode']=='pass'
    assert doc['max_freeze_seconds'] < 1.2 and doc['blackout_events']==0
    assert not doc['warnings']
    assert doc['marketing_release'] == 'blocked_pending_human_and_release_authority'
    print('qa_'+key+'=pass sha256='+doc['sha256'])
PY
printf 'media_quality_lab=pass\n'
