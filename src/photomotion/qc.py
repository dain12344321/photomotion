"""QC: I2V must remain the photograph — no fire, fans, or invented furniture."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from photomotion.constants import PUSH_ZOOM


def extract_frame(video: Path, dest: Path, *, last: bool = False, time_s: float | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y"]
    if time_s is not None:
        cmd += ["-ss", f"{max(0.0, time_s):.3f}"]
    elif last:
        cmd += ["-sseof", "-0.05"]
    cmd += ["-i", str(video), "-frames:v", "1", str(dest)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[-1000:])
    return dest


def _luma_16x9(path: Path, size: tuple[int, int] = (160, 90)) -> np.ndarray:
    im = Image.open(path).convert("L")
    w, h = im.size
    target = 16 / 9
    if w / h >= target:
        nw = int(round(h * target))
        x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    else:
        nh = int(round(w / target))
        y = (h - nh) // 2
        im = im.crop((0, y, w, y + nh))
    im = im.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255.0


def _luma_zoomed(path: Path, zoom: float, size: tuple[int, int] = (160, 90)) -> np.ndarray:
    """Center-crop the still by `zoom` so a dolly last-frame can match."""
    z = max(1.0, float(zoom))
    base = _luma_16x9(path, size=(320, 180))
    h, w = base.shape
    zh, zw = max(8, int(round(h / z))), max(8, int(round(w / z)))
    y = max(0, (h - zh) // 2)
    x = max(0, (w - zw) // 2)
    crop = base[y : y + zh, x : x + zw]
    im = Image.fromarray((crop * 255).astype(np.uint8), mode="L")
    im = im.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255.0


def frame_resemblance(
    still: Path,
    frame: Path,
    threshold: float = 0.72,
    zoom: float = 1.0,
) -> dict:
    """Mean absolute error on 16:9 luma, zoom-compensated."""
    aa = _luma_zoomed(still, zoom)
    bb = _luma_16x9(frame)
    mae = float(np.mean(np.abs(aa - bb)))
    score = max(0.0, 1.0 - mae * 3.0)
    tile = 16
    worst = 0.0
    h, w = aa.shape
    for y in range(0, h - tile + 1, tile):
        for x in range(0, w - tile + 1, tile):
            worst = max(
                worst,
                float(np.mean(np.abs(aa[y : y + tile, x : x + tile] - bb[y : y + tile, x : x + tile]))),
            )
    tile_ok = worst < 0.12
    return {
        "score": round(score, 4),
        "mae": round(mae, 4),
        "tile_mae": round(worst, 4),
        "pass": bool(score >= threshold and tile_ok),
        "threshold": threshold,
        "zoom": round(float(zoom), 4),
    }


def _probe_duration(video: Path) -> float:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video),
        ],
        capture_output=True,
        text=True,
    )
    err = proc.stderr or ""
    import re

    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
    if not m:
        return 2.5
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def flicker_score(frames: list[np.ndarray]) -> float:
    """95th percentile of per-pixel std across time. Fire/fans spike this."""
    if len(frames) < 2:
        return 0.0
    stack = np.stack(frames, axis=0)
    std = stack.std(axis=0)
    return float(np.percentile(std, 95))


def qc_i2v_against_still(still: Path, clip: Path, qc_dir: Path) -> dict:
    """First/mid/last must match the still; flicker must stay camera-like."""
    qc_dir.mkdir(parents=True, exist_ok=True)
    duration = max(0.4, _probe_duration(clip))
    samples = [
        ("first", 0.04, 1.0, 0.82),
        ("mid", duration * 0.45, 1.0 + (PUSH_ZOOM - 1.0) * 0.45, 0.74),
        ("last", max(0.0, duration - 0.06), PUSH_ZOOM, 0.72),
    ]
    checks = {}
    luma_frames: list[np.ndarray] = []
    for name, t, zoom, thresh in samples:
        dest = qc_dir / f"{clip.stem}_frame_{name}.jpg"
        extract_frame(clip, dest, time_s=t)
        rec = frame_resemblance(still, dest, threshold=thresh, zoom=zoom)
        rec["frame"] = str(dest)
        rec["t"] = round(t, 3)
        checks[name] = rec
        luma_frames.append(_luma_16x9(dest))

    flicker = round(flicker_score(luma_frames), 4)
    # Honest dolly on a still sits ~0.02–0.05. Fire / spinning fans jump above 0.07.
    flicker_pass = flicker <= 0.055
    passed = all(c["pass"] for c in checks.values()) and flicker_pass
    result = {
        "first": checks["first"],
        "mid": checks["mid"],
        "last": checks["last"],
        "score": checks["first"]["score"],
        "mae": checks["first"]["mae"],
        "flicker": flicker,
        "flicker_pass": flicker_pass,
        "pass": bool(passed),
        "threshold": checks["first"]["threshold"],
        "frame": checks["first"]["frame"],
        "frame_last": checks["last"]["frame"],
        "clip": str(clip),
        "still": str(still),
    }
    (qc_dir / (clip.stem + ".json")).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
