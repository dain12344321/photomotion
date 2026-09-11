---
name: photomotion
description: >
  Lakeshore Listing Media PhotoMotion™ reels. Finished listing stills to a
  ~30s music-synced tour (16:9 / 9:16 / 1:1). Ken Burns default; optional
  Grok Imagine I2V fail-closed. Use when building, rendering, or remuxing
  listing videos, beat-sync, address overlays, or talking to grok-imagine-video-1.5.
---

# PhotoMotion

Read `/workspace/HERMES.md` for the full contract. Do not skip it.

## Defaults

- Motion: in-frame `push_in` / `orbit` / `pull_out` / `ken_burns` / `static`. Never pan. Never I2V orbit or I2V pull-out.
- Baths static. I2V only on `push_in`.
- Unbranded master. `--address-card` is opt-in. No AI watermark.
- Music: Easy Lemon. Cuts on 4-beat bars.
- Auth: `python3 -m photomotion auth --login` (X at console.x.ai). Model: `grok-imagine-video-1.5`. `generate_audio: false`.
- Fail closed to Ken Burns.

## Commands

```bash
PYTHONPATH=src python3 -m photomotion auth --login
PYTHONPATH=src python3 -m photomotion run --input INBOX/<p> --job-dir jobs/<p> --dry-run
PYTHONPATH=src python3 -m photomotion serve --port 8765
./run-desktop.sh
PYTHONPATH=src python3 -m photomotion remux --job-dir jobs/<p> --music easy-lemon --address-card
PYTHONPATH=src python3 -m unittest tests.test_photomotion -v
```
