"""Rock-solid in-frame camera: Lanczos crop from a 4K plate. No zoompan warp."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image

from photomotion.constants import (
    FPS,
    HOLD_IN,
    HOLD_OUT,
    KB_PLATE_H,
    KB_PLATE_W,
    MASTER_H,
    MASTER_W,
    ORBIT_TRAVEL,
    ORBIT_Z0,
    ORBIT_ZOOM,
    PUSH_ZOOM,
    STATIC_ZOOM,
)
from photomotion.motion import assert_allowed


def largest_16x9(width: int, height: int) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) of the largest 16:9 window inside the still."""
    target_ratio = 16 / 9
    src_ratio = width / height
    if src_ratio >= target_ratio:
        h = height
        w = int(round(h * target_ratio))
        x = (width - w) // 2
        y = 0
    else:
        w = width
        h = int(round(w / target_ratio))
        x = 0
        y = (height - h) // 2
    w -= w % 2
    h -= h % 2
    return x, y, w, h


def crop_16x9_jpeg(src: Path, dest: Path, focal: tuple[float, float] = (0.5, 0.46)) -> Path:
    """16:9 crop at 3840×2160 so the camera has subpixel headroom."""
    with Image.open(src) as im:
        im = im.convert("RGB")
        W, H = im.size
        x, y, w, h = largest_16x9(W, H)
        fx, fy = focal
        if W > w:
            x = int(round(fx * (W - w)))
            x = max(0, min(W - w, x))
        if H > h:
            y = int(round(fy * (H - h)))
            y = max(0, min(H - h, y))
        crop = im.crop((x, y, x + w, y + h))
        crop = crop.resize((KB_PLATE_W, KB_PLATE_H), Image.Resampling.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        crop.save(dest, "JPEG", quality=94, optimize=True)
    return dest


def _ease_cosine(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return (1.0 - math.cos(math.pi * t)) / 2.0


def shaped_ease(t: float) -> float:
    """Hold the still, cosine-ease, hold the landing — same contract as the TS engine."""
    t = min(1.0, max(0.0, t))
    if t <= HOLD_IN:
        return 0.0
    if t >= 1.0 - HOLD_OUT:
        return 1.0
    u = (t - HOLD_IN) / (1.0 - HOLD_IN - HOLD_OUT)
    return _ease_cosine(u)


def camera_window_at(
    motion: str,
    t01: float,
    yaw: int | None = None,
    focal: tuple[float, float] = (0.5, 0.46),
) -> tuple[float, float, float, float]:
    motion = assert_allowed(motion)
    fx, fy = focal
    sign = 1 if (yaw if yaw is not None else 1) >= 0 else -1
    if motion == "orbit":
        z0, z1, travel = ORBIT_Z0, ORBIT_ZOOM, ORBIT_TRAVEL
    elif motion == "push_in":
        z0, z1, travel = 1.0, PUSH_ZOOM, 0.0
    else:
        z0, z1, travel = 1.0, STATIC_ZOOM, 0.0
    e = shaped_ease(t01)
    z = z0 + (z1 - z0) * e
    w = KB_PLATE_W / z
    h = KB_PLATE_H / z
    max_x = KB_PLATE_W - w
    max_y = KB_PLATE_H - h
    ox = (e - 0.5) * 2.0 * travel * sign
    oy = math.sin(e * math.pi) * travel * 0.14 * sign
    x = max_x * (fx + ox * 0.5)
    y = max_y * (fy + oy * 0.5)
    x = min(max(x, 0.0), max(0.0, max_x))
    y = min(max(y, 0.0), max(0.0, max_y))
    if x + w > KB_PLATE_W:
        x = KB_PLATE_W - w
    if y + h > KB_PLATE_H:
        y = KB_PLATE_H - h
    return x, y, w, h


def camera_path(
    motion: str,
    frames: int,
    yaw: int | None = None,
    focal: tuple[float, float] = (0.5, 0.46),
) -> list[tuple[float, float, float, float]]:
    """Crop windows (x, y, w, h) on the 4K plate. Always in-frame."""
    motion = assert_allowed(motion)
    n = max(2, int(frames))
    return [camera_window_at(motion, i / (n - 1), yaw=yaw, focal=focal) for i in range(n)]


def render_clip(
    still: Path,
    dest: Path,
    motion: str,
    duration_s: float,
    focal: tuple[float, float] = (0.5, 0.46),
    yaw: int | None = None,
) -> Path:
    motion = assert_allowed(motion)
    dest.parent.mkdir(parents=True, exist_ok=True)
    crop_path = dest.with_suffix(".crop.jpg")
    crop_16x9_jpeg(still, crop_path, focal=focal)

    frames_out = max(2, int(round(float(duration_s) * FPS)))
    windows = camera_path(motion, frames_out, yaw=yaw, focal=focal)
    plate = Image.open(crop_path).convert("RGB")

    log_path = dest.with_suffix(".ffmpeg.log")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{MASTER_W}x{MASTER_H}",
        "-r",
        str(FPS),
        "-i",
        "pipe:0",
        "-frames:v",
        str(frames_out),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    with log_path.open("wb") as errf:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=errf,
        )
        assert proc.stdin is not None
        try:
            for x, y, w, h in windows:
                frame = plate.resize(
                    (MASTER_W, MASTER_H),
                    Image.Resampling.LANCZOS,
                    box=(x, y, x + w, y + h),
                )
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            code = proc.wait()
        except BrokenPipeError:
            proc.wait()
            code = proc.returncode or 1
    plate.close()
    crop_path.unlink(missing_ok=True)
    if code != 0:
        err = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        log_path.unlink(missing_ok=True)
        raise RuntimeError(err or f"ffmpeg exited {code}")
    log_path.unlink(missing_ok=True)
    return dest
