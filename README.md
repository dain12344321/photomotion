# PhotoMotion™

Lakeshore Listing Media. Finished listing stills → a ~30s music-synced tour in 16:9, 9:16, and 1:1.

Ken Burns (in-frame Lanczos crop) is the product. Grok Imagine I2V is optional and fail-closed. Originals are never mutated.

This repo is two surfaces that share one camera / beat / classify engine:

| Surface | What it writes | Needs |
| --- | --- | --- |
| Operator desk (this web app) | Live tour + WebM | Browser. Sign in with X is optional. |
| Desktop CLI (`python3 -m photomotion`) | 1080p MP4 masters | Python 3.10+, numpy, pillow, ffmpeg |

## Motion law

- Allowed automatic: `push_in`, in-frame `orbit`, in-frame `pull_out`, `ken_burns`, `static`
- Banned: pan, I2V orbit, I2V pull-out (those invent edges)
- Baths / laundry / garage / mirrors stay `static`
- Trapezoid speed ramp (hold → accel → cruise → decel → hold). Soft dissolve inside the holds.
- Cuts snap to 4-beat bars on a dual-band onset grid

Address card is opt-in. No AI watermark.

## Operator desk

Sign in with X to mark yourself as the operator. Ken Burns plays without an account. Imagine is desktop-only, dry-run by default, and spends an xAI key from [console.x.ai](https://console.x.ai) (same X login).

Demo listings: **405 N Main St, Wanatah IN** and **11477 N 250 W, Sumava Resorts**. Drop 5+ of your own JPEGs on the desk.

## Desktop — photos in, videos out

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src

# One-command local desk (opens a drop page, ffmpeg writes MP4s here)
./run-desktop.sh          # macOS / Linux
run-desktop.bat           # Windows

python3 -m photomotion auth --login    # opens console.x.ai (X account), hidden paste
python3 -m photomotion auth --status   # never prints the bearer
python3 -m photomotion check           # ffmpeg + numpy + pillow

python3 -m photomotion run \
  --input ./data/INBOX/wanatah \
  --job-dir ./data/jobs/wanatah \
  --address "405 N Main St" \
  --city "Wanatah, IN 46390" \
  --dry-run --music wallpaper
```

Deliverables in `jobs/<property>/DELIVER/`:

- `master_16x9_clean.mp4`
- `vertical_9x16_clean.mp4` (blur-fill from 16:9)
- `square_1x1_clean.mp4`
- `plan.json` / `cut_list.json`

Live Imagine (push-ins only, dollar cap, confirm required):

```bash
python3 -m photomotion run ... --live --confirm-live --spend-cap 15 --i2v-heroes 2
```

A ready zip lives on the Desktop page of the operator desk — code, music, tests, `run-desktop.sh`. No listing photos.

Beds (Kevin MacLeod, CC BY 3.0): Easy Lemon, Wallpaper, Carefree, Funkorama.

## Tests

```bash
PYTHONPATH=src python3 -m unittest tests.test_photomotion -v
npm test
```

## Cloudflare

The desk is a browser engine (camera, beats, tour plan). Connect this GitHub repo to Cloudflare Pages for the operator UI. Workers cannot encode Lanczos 1080p — keep the Python CLI on the desktop. `wrangler.toml` is a stub, not a full Pages build.

## Hermes

See [HERMES.md](HERMES.md) and [skills/photomotion/SKILL.md](skills/photomotion/SKILL.md).
