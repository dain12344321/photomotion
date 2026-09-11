#!/bin/sh
# PhotoMotion desktop — photos in, 1080p MP4s out.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required (3.10+)." >&2
  exit 1
fi

if ! python3 -c "import numpy, PIL" >/dev/null 2>&1; then
  echo "Installing numpy and pillow…"
  python3 -m pip install -r requirements.txt
fi

python3 -m photomotion check || true
echo
echo "Opening the local desk. Drop 5+ JPEGs. Ken Burns is offline."
echo "X / Imagine: python3 -m photomotion auth --login"
echo
exec python3 -m photomotion serve --host 127.0.0.1 --port 8765
