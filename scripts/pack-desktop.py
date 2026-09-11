#!/usr/bin/env python3
"""Build public/downloads/photomotion-desktop.zip — no listing photos."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "downloads" / "photomotion-desktop.zip"

FILES = [
    "README.md",
    "HERMES.md",
    "LICENSE",
    "pyproject.toml",
    "requirements.txt",
    "run-desktop.sh",
    "run-desktop.bat",
    "desktop/README.md",
    "skills/photomotion/SKILL.md",
    "assets/music/LICENSE",
    "assets/music/easy-lemon.mp3",
    "assets/music/wallpaper.mp3",
    "assets/music/carefree.mp3",
    "assets/music/funkorama.mp3",
    "assets/fonts/Montserrat-SemiBold.ttf",
    "assets/fonts/Montserrat-Medium.ttf",
    "assets/fonts/OFL.txt",
    "tests/test_photomotion.py",
    "tests/test_assemble_files.py",
]

GLOBS = [
    "src/photomotion/*.py",
]

EXEC = {"run-desktop.sh", "desktop/run-desktop.sh"}


def _add(zf: zipfile.ZipFile, src: Path, arc: str, executable: bool = False) -> None:
    if executable:
        info = zipfile.ZipInfo(arc)
        info.date_time = src.stat().st_mtime_ns and src.stat().st_mtime
        import time

        st = src.stat()
        info.date_time = time.localtime(st.st_mtime)[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o755 << 16
        zf.writestr(info, src.read_bytes())
        return
    zf.write(src, arc)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prefix = "photomotion-desktop"
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in FILES:
            src = ROOT / rel
            if not src.exists():
                raise SystemExit(f"missing {rel}")
            if rel == "desktop/README.md":
                arc = f"{prefix}/README.md"
            elif rel == "README.md":
                arc = f"{prefix}/REPO-README.md"
            else:
                arc = f"{prefix}/{rel}"
            _add(zf, src, arc, executable=rel in EXEC)
        for pattern in GLOBS:
            for src in sorted(ROOT.glob(pattern)):
                if src.name == "__pycache__":
                    continue
                zf.write(src, f"{prefix}/{src.relative_to(ROOT).as_posix()}")
        zf.writestr(f"{prefix}/src/photomotion/py.typed", "")
    os.chmod(OUT, 0o644)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
