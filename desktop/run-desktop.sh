#!/bin/sh
# Launcher lives at repo root; this copy is for the unzipped kit.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
exec "$ROOT/run-desktop.sh"
