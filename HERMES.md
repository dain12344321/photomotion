# PhotoMotion™ — Hermes seed

Teach this to a local Grok/Hermes agent. The web desk is optional. The product is the Python CLI.

## What it is

Finished listing JPEGs → ~30s music-synced tour in 16:9, 9:16, and 1:1.

Ken Burns (in-frame Lanczos crop) is the product. Grok Imagine I2V (`grok-imagine-video-1.5`) is optional, fail-closed.

Clone the **Reel-E deliverable**, not their stack: photos in, per-still camera inside the photograph, beat-synced cuts, unbranded master, optional address card.

## Hard rules

- Never mutate originals. Hash them. Work on `SOURCE/` copies.
- Automatic motions: `push_in`, in-frame `orbit`, in-frame `pull_out`, `ken_burns`, `static`.
- Banned: pan, I2V orbit, I2V pull-out (invents edges). In-frame pull-out is allowed.
- Baths / laundry / garage / mirrors → `static`.
- No AI disclosure watermark. Ever.
- Address overlay is a checkbox / `--address-card`. Default **off** (unbranded).
- SpaceXAI only. No Vertex, Veo, fal, Kling, Runway.
- Dry-run default. Live I2V needs `--live --confirm-live` and a dollar cap.
- Fail closed to Ken Burns. That is a passing job.

## CLI

```bash
export PYTHONPATH=src
python3 -m photomotion auth --login
python3 -m photomotion auth --status
./run-desktop.sh

python3 -m photomotion run \
  --input ./data/INBOX/<property> \
  --job-dir ./data/jobs/<property> \
  --address "14465 Garden Wy" \
  --city "Cedar Lake, IN" \
  --dry-run \
  --music easy-lemon

# Local photos-in / videos-out desk (ffmpeg on this machine)
python3 -m photomotion serve --port 8765

# Optional address card (Reel-E branded)
python3 -m photomotion remux --job-dir ./data/jobs/<property> --music easy-lemon --address-card

# Strip the card
python3 -m photomotion remux --job-dir ./data/jobs/<property> --music easy-lemon --no-address-card

# Optional Imagine on push-ins only
python3 -m photomotion run ... --live --confirm-live --spend-cap 15 --i2v-heroes 10
```

Beds: `easy-lemon` (default), `wallpaper`, `carefree`, `funkorama`. Kevin MacLeod CC BY 3.0.

Auth: `python3 -m photomotion auth --login` opens [console.x.ai](https://console.x.ai). Sign in with the same X account, create an API key, paste at the hidden prompt. Stored at `~/.photomotion/credentials.json` (mode 600). The CLI never prints the bearer. Ken Burns does not need a key. `python3 -m photomotion check` reports ffmpeg + numpy + pillow.

## Layout

```
INBOX/<property>/*.jpg
jobs/<property>/
  SOURCE/          read-only copies
  PROXIES/         ~1920 long side
  CLIPS/           per-still mp4
  DELIVER/         master_16x9_clean.mp4
                   vertical_9x16_clean.mp4
                   square_1x1_clean.mp4
                   plan.json  cut_list.json
```

## Motion + QC

- Push-in / pull-out / orbit use a sine ease-in-out (no cruise, no hold-in). Orbit is a frame-relative truck around the focal — no vertical crane. Ken Burns is a slow zoom plus lateral drift.
- Soft mix (~90ms) centered on the beat. Incoming shot is already rolling. No ffmpeg xfade.
- Render: 4K plate → Lanczos crop per frame → 1920×1080 @ 30fps. No ffmpeg `zoompan`.
- I2V: still is frame 1, `generate_audio: false`, do not set `aspect_ratio`.
- QC vs still (zoom-compensated luma, 16×16 tile MAE, flicker). Fire, spinning fans, extra furniture fail. Fallback Ken Burns.

## xAI

- Base `https://api.x.ai/v1`
- Auth: `XAI_API_KEY` or `~/.photomotion/credentials.json`. Never log the bearer.
- Model: `grok-imagine-video-1.5`
- ~$0.25/s 1080p + $0.01 image → ~$1.01 per 4s clip

## Tests

```bash
PYTHONPATH=src python3 -m unittest tests.test_photomotion -v
```
