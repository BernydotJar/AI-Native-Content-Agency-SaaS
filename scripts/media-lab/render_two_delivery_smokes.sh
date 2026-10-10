#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/artifacts/media-lab/generated"
if [ "$#" -gt 0 ]; then OUT="$1"; fi
mkdir -p "$OUT"
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
test -f "$FONT"
command -v ffmpeg >/dev/null || { echo 'ffmpeg is required' >&2; exit 1; }
command -v ffprobe >/dev/null || { echo 'ffprobe is required' >&2; exit 1; }

render() {
  local filename="$1" theme0="$2" theme1="$3" kicker="$4" headline="$5" subline="$6" bottom="$7"
  ffmpeg -hide_banner -nostdin -loglevel error -y \
    -f lavfi -i "gradients=s=720x1280:r=24:d=6:c0=$theme0:c1=$theme1:type=radial:speed=0.08:x0=180:y0=390:x1=600:y1=1180" \
    -f lavfi -i "sine=frequency=165:sample_rate=48000:duration=6" \
    -filter_complex "\
[0:v]\
drawgrid=width=120:height=120:thickness=1:color=white@0.055,\
drawbox=x=52:y=88:w=616:h=3:color=0xF3B96D@0.8:t=fill,\
drawbox=x=52:y=1010:w=616:h=2:color=0xF3B96D@0.34:t=fill,\
drawbox=x=52:y=1105:w=616:h=1:color=white@0.15:t=fill,\
drawtext=fontfile=$FONT:text='CAMPAIGNOS / MEDIA LAB':fontcolor=0xF3B96D:fontsize=23:x=52:y=130,\
drawtext=fontfile=$FONT:text='$kicker':fontcolor=0xD7D9E3:fontsize=28:x=52:y=330,\
drawtext=fontfile=$FONT:text='$headline':fontcolor=white:fontsize=47:x='52+8*sin(t*1.5)':y=450,\
drawtext=fontfile=$FONT:text='$subline':fontcolor=0xE6C9B4:fontsize=32:x=52:y=565,\
drawtext=fontfile=$FONT:text='$bottom':fontcolor=white:fontsize=23:x=52:y=1060,\
drawtext=fontfile=$FONT:text='PROCEDURAL PREVIEW / NOT AI FOOTAGE':fontcolor=0xAAB6C6:fontsize=19:x=52:y=1170,\
noise=alls=2:allf=t,\
fade=t=in:st=0:d=0.25,fade=t=out:st=5.70:d=0.3,format=yuv420p[v];\
[1:a]volume=0.06,afade=t=in:st=0:d=0.4,afade=t=out:st=5.4:d=0.6[a]" \
    -map '[v]' -map '[a]' -t 6 \
    -c:v libx264 -preset veryfast -crf 18 -r 24 \
    -c:a aac -b:a 160k -ar 48000 -pix_fmt yuv420p \
    -movflags +faststart "$OUT/$filename"
}
render 'spaghetti-motion-export-smoke.mp4' 0x060F24 0x6A2B31 \
  'CHALLENGE / HUMAN MOTION' 'THE SPAGHETTI' 'FORK  HAND  MOUTH' \
  'Benchmark concept  /  no actor impersonation'
render 'campaignos-premium-export-smoke.mp4' 0x061A24 0x713156 \
  'CAMPAIGN / AI NATIVE' 'ONE BRIEF' 'EIGHT AGENTS' \
  'Plan  Create  Review  Approve'
python3 "$ROOT/scripts/media-lab/check_video.py" "$OUT/spaghetti-motion-export-smoke.mp4" \
  --contact-sheet "$OUT/spaghetti-contact-sheet.png" --json-out "$OUT/spaghetti-qa.json" >/dev/null
python3 "$ROOT/scripts/media-lab/check_video.py" "$OUT/campaignos-premium-export-smoke.mp4" \
  --contact-sheet "$OUT/campaignos-contact-sheet.png" --json-out "$OUT/campaignos-qa.json" >/dev/null
python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
out=Path(sys.argv[1])
for name in ('spaghetti', 'campaignos'):
 d=json.loads((out/f'{name}-qa.json').read_text())
 print(json.dumps({'name':name,'delivery_status':d['status'],'dimensions':[d['video']['width'],d['video']['height']],'fps':d['video']['fps'],'duration':d['duration_seconds'],'size_bytes':d['size_bytes'],'creative_review':d['creative_quality']}))
PY
