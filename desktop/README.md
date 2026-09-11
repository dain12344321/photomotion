# PhotoMotion™ desktop kit

Photos in, 1080p videos out. Unzip this folder, install numpy + pillow, point it at a property folder. ffmpeg must be on PATH.

## One command

```bash
# macOS / Linux
chmod +x run-desktop.sh
./run-desktop.sh

# Windows
run-desktop.bat
```

That opens a local desk. Drop 5+ listing JPEGs. This machine writes:

- `master_16x9_clean.mp4`
- `vertical_9x16_clean.mp4`
- `square_1x1_clean.mp4`

Originals are never mutated.

## Folder job

```bash
pip install -r requirements.txt
export PYTHONPATH=src

python3 -m photomotion run \
  --input /path/to/listing-stills \
  --job-dir ./jobs/listing \
  --address "405 N Main St" \
  --city "Wanatah, IN" \
  --dry-run --music wallpaper
```

## X account / Imagine

Ken Burns does not need a key. For optional Grok Imagine heroes:

1. Run `python3 -m photomotion auth --login`
2. Sign in at [console.x.ai](https://console.x.ai) with your **X account**
3. Create an API key and paste it at the hidden prompt
4. Stored at `~/.photomotion/credentials.json` (mode 600). The CLI never prints the bearer.

```bash
python3 -m photomotion auth --status
python3 -m photomotion check
python3 -m photomotion run ... --live --confirm-live --spend-cap 15 --i2v-heroes 2
```

See HERMES.md for the full contract.
