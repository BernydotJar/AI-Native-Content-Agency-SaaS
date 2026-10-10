# Video Production Engine — provider evaluation and evidence (2026-10-10)

Status: **READ-ONLY PROVIDER DISCOVERY + TECHNICAL VIDEO QA IMPLEMENTED**.
No live API generation, desktop-app control, tenant BYOK import, or media-worker execution is enabled.

## Product decision

A production SaaS needs a provider-agnostic video job contract, not an unreviewed
desktop automation command or a hardcoded paid vendor. Keep model-language
providers separate from video generators.

| Provider | Evaluation | Best-fit workflow | Preconditions |
| --- | --- | --- | --- |
| HeyGen | API optional, configurable in server secrets only | presenters, avatars, localization, explainers | PAYG budget, encrypted per-tenant credentials, durable effect worker |
| FreeVideo + ComfyUI | Local GPU worker candidate, not installed | image-to-video and reference-guided cinematic clips | compatible GPU, sufficient RAM/VRAM, model license review, network isolation |
| LTX-2.5 + ComfyUI | Local GPU cinematic worker candidate, not installed | cinematic controlled shots, start/end frames and synchronous audio | worker with CUDA GPU, pinned model revision/license, controlled generation budget |
| H3ddle | Apple Silicon desktop worker candidate, not installed | local editing, image/video/audio experimental generation | app bridge, model download, Apple Silicon Mac, model license review |
| Cloud Sandbox Computer Use | Native bridge connected; browser-tab approval workflow only | assisted review of supported web-based generators | allowlisted origin, per-action approval, session/tenant boundaries |

HEYGEN API documentation: https://developers.heygen.com/reference/create-video-agent-session
FreeVideo: https://github.com/FlashML-org/FreeVideo
LTX-2.5 official ComfyUI template: https://docs.ltx.io/open-source-model/integration-tools/comfy-ui/
H3ddle: https://github.com/AlexanderIstomin/h3ddle

## Proposed reference architecture

```text
Authenticated tenant Campaign Brief
  -> Creative Director: concept + script + shotlist + references
  -> Storyboard reviewer (content and rights)
  -> Generation Job: tenant + job_id + provider capability + aspect ratio
     -> policy: consent + spend quote + approved max amount + data residency
     -> job authority: durable idempotency / fence / retry / revocation
     -> provider router (one of):
        A. HeyGen v3 API (X-Api-Key from encrypted tenant vault)
        B. FreeVideo or LTX-2.5 / ComfyUI isolated GPU worker
        C. H3ddle scoped Apple-Silicon worker (future app bridge)
        D. Browser-assisted generator (per-action approval)
     -> webhook/poll receipt + status reconciliation
  -> governed media asset store: hash + provenance + license + expiry
  -> Video Quality Gate:
       - ffprobe / full ffmpeg decode / fps / resolution / audio
       - black or frozen segment flags (human can accept deliberate effects)
       - independent visual editorial QA and identity/rights review
  -> Studio timeline / approve creative
  -> independent human Greenlight for publication and campaign budget
```

Do not reuse `browser-use/video-use`'s reviewed-disabled execution path.
Its security findings and absent outbox/tenant authority remain binding.
The new endpoints `GET /api/v1/video/providers[/{provider_id}]`
are authenticated read-only discovery, not generation.

## Session execution: source content and hardware gates

At test time the connected Cloud Sandbox workstation was Linux aarch64 with
no NVIDIA GPU and no `/dev/dri` GPU device. No ComfyUI worker or HeyGen key
was detected. The connected OpenArt Free workspace had 40 credits; the least
expensive offered video generation cost 50 credits. Do not attempt a paid job
without the user's explicit authorization and a budget.

The official FreeVideo project publishes generated video examples at
https://freevideo-community.pages.dev/#gallery. Two **existing public examples**
were downloaded to a **temporary QA directory** and analyzed using the
repository-owned `scripts/video_quality_gate.py`. These are NOT fresh AI
generations by our SaaS; their original source is the upstream FreeVideo gallery.

| Upstream sample | Profile | Resolution | FPS | Length | Audio | Decode | Black/freeze | Technical result |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| `freevideo-harbor-rain-hongkong-high.mp4` | High | 1344 × 768 | 24 | 20.05 s | AAC 32 kHz | PASS | 0 / 0 | PASS |
| `freevideo-neon-gravity-arena-max.mp4` | Max | 1344 × 768 | 24 | 20.05 s | AAC 32 kHz | PASS | 0 / 0 | PASS |

Source URLs:
- https://freevideo-community.pages.dev/gallery/freevideo-harbor-rain-hongkong-high.mp4
- https://freevideo-community.pages.dev/gallery/freevideo-neon-gravity-arena-max.mp4

Provenance SHA-256:
- Hong Kong: `0a1d856753478019ad8ba5dd8d81bf2da23d5589278fa61e02453f33a374c4a4`
- Neon arena: `4df0649208f3d2be1397dce442a999139a581b77cddae6bc81247ce33e0cc84f`

Editorial sample review **limited to four sampled frames per video**:
- Harbor fight: consistent industrial dock set and fighters in sampled frames;
  visible rapid movement and cinematic night lighting, but independent full-playback
  review is still needed for exact temporal continuity, physics and prompt adherence.
- Neon arena: consistent stylized robot bodies, neon geometry and arena
  from the sampled frames; still needs full-playback review for limb morphs,
  object permanence, audio synchronization and storytelling.

`technical_pass=true` NEVER implies `production_release_approved=true`.
The script deliberately requires an additional human creative review.

## Reproducible QA command

```sh
python3 scripts/video_quality_gate.py /path/to/clip.mp4 \
  --min-width 1280 --min-height 720 --min-fps 24 --min-duration 5 \
  --require-audio --output /tmp/clip.quality.json
```

A film may deliberately have black frames, freeze frames or no audio;
these are warnings/review triggers, not automatic rejection unless audio
was explicitly required.

## Next safe delivery increments

1. Per-tenant encrypted HeyGen API credential import (admin-only; never sent in GET,
   logs or browser-side persistence). Connect, test using a **free nonbillable
   authentication probe if the provider documents one**, rotate, revoke, and audit.
2. Spend quote + tenant limit + human approval + durable effect/outbox with
   reconciliation. No retries of an ambiguous provider submission without receipts.
3. Worker bindings for GPU/Apple Silicon or a native-mac app bridge with
   explicit origin/app permissions and model-license review.
4. Production Media Vault for generated video (not the existing JPEG-only
   Instagram media path), immutability, expiry, signed URLs, and provenance.
5. Per-shot evaluation: temporal identity/object/physics checks, lip-sync,
   motion/scene consistency, creative human scoring, metadata, export standard.

## Cinematic adversarial benchmark: 'spaghetti' meme

A recognizable film star eating spaghetti is a useful stress test for hands,
utensils, strand continuity, face stability and mouth interaction. Such a result
should always be clearly labeled AI-generated, never marketed as genuine
footage or an endorsement. For transferable SaaS commercial evals, prefer a
consenting performer or wholly fictional adult. The prompt below requires
no external celebrity likeness:

> A single uninterrupted 6-second cinematic close-medium shot of a fictional
> adult man with expressive eyes eating spaghetti in a sunlit Italian trattoria.
> One right hand holds a real silver fork, winds exactly three spaghetti strands,
> lifts them from a white ceramic plate to the mouth, bites naturally, then
> lowers the fork. The left hand rests on the table. Stable face identity,
> five visible fingers on each hand, physically consistent strands and sauce.
> 35mm lens, photoreal live action, soft window light, shallow depth of field,
> natural food movement, 24 fps, 16:9, no jump cuts, no text, no watermark.
> Explicitly synthetic / AI-generated test footage.

Store seed, model/revision, generation parameters, negative prompt, rights and
consent alongside each output; compare subjective visual quality blind between
model/profile variants.
