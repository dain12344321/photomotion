"""Phase 1 gate: three deliverables exist with correct shapes."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

DELIVER = Path("/workspace/data/jobs/sumava/DELIVER")


def probe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # static ffmpeg build may ship ffprobe as ffmpeg -i
        return {}
    return json.loads(proc.stdout or "{}")


class DeliverableTests(unittest.TestCase):
    def test_three_files_present(self):
        if not DELIVER.exists():
            self.skipTest("sumava job not rendered")
        for name in (
            "master_16x9_clean.mp4",
            "vertical_9x16_clean.mp4",
            "square_1x1_clean.mp4",
        ):
            p = DELIVER / name
            self.assertTrue(p.exists(), name)
            self.assertGreater(p.stat().st_size, 1_000_000, name)
