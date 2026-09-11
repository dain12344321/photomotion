"""Rock-solid in-frame camera: Lanczos crop from a 4K plate. No zoompan warp."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image

from photomotion.constants import (
    FPS,
    FRAME_TRAVEL_X,
    FRAME_TRAVEL_X_1X1,
    FRAME_TRAVEL_X_9X16,
    FRAME_TRAVEL_Y,
    FRAME_TRAVEL_Y_1X1,
    FRAME_TRAVEL_Y_9X16,
    HOLD_IN,
    HOLD_OUT,
    KB_PLATE_H,
    KB_PLATE_W,
    KEN_BURNS_DRIFT_X,
    KEN_BURNS_DRIFT_Y,
    KEN_BURNS_ZOOM,
    MASTER_H,
    MASTER_W,
    ORBIT_ARC,
    ORBIT_TRAVEL,
    ORBIT_Z0,
    ORBIT_ZOOM,
    PUSH_DRIFT_X,
    PUSH_DRIFT_Y,
    PUSH_ZOOM,
    RAMP_ACCEL,
    RAMP_DECEL,
    STATIC_ZOOM,
)
from photomotion.motion import assert_allowed


def largest_aspect(width: int, height: int, ratio: float) -> tuple[float, float, float, float]:
    """Largest window of the given aspect (w/h) inside the image."""
    src_ratio = width / height if height else ratio
    if src_ratio >= ratio:
        h = float(height)
        w = h * ratio
        x = (width - w) / 2.0
        y = 0.0
    else:
        w = float(width)
        h = w / ratio
        x = 0.0
        y = (height - h) / 2.0
    return x, y, w, h


def largest_16x9(width: int, height: int) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) of the largest 16:9 window inside the still."""
    x, y, w, h = largest_aspect(width, height, 16 / 9)
    xi, yi = int(x), int(y)
    wi, hi = int(round(w)), int(round(h))
    wi -= wi % 2
    hi -= hi % 2
    return xi, yi, wi, hi


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


def _ramp_peak() -> float:
    cruise = 1.0 - RAMP_ACCEL - RAMP_DECEL
    return 1.0 / (RAMP_ACCEL / 2.0 + cruise + RAMP_DECEL / 2.0)


def speed_ramp(t: float) -> float:
    """Trapezoidal speed ramp: hold, accel, cruise, decel, hold. v=0 at both ends."""
    t = min(1.0, max(0.0, t))
    if t <= HOLD_IN:
        return 0.0
    if t >= 1.0 - HOLD_OUT:
        return 1.0
    span = 1.0 - HOLD_IN - HOLD_OUT
    u = (t - HOLD_IN) / span
    a, d = RAMP_ACCEL, RAMP_DECEL
    c = 1.0 - a - d
    v_peak = _ramp_peak()
    if u <= a:
        return v_peak * ((u * u) / (2.0 * a))
    if u <= a + c:
        return v_peak * (a / 2.0 + (u - a))
    s = u - a - c
    return v_peak * (a / 2.0 + c + s - (s * s) / (2.0 * d))


def ramp_velocity(t: float) -> float:
    """Normalized velocity of speed_ramp. Zero during holds and at both ends of the move."""
    t = min(1.0, max(0.0, t))
    if t <= HOLD_IN or t >= 1.0 - HOLD_OUT:
        return 0.0
    span = 1.0 - HOLD_IN - HOLD_OUT
    u = (t - HOLD_IN) / span
    a, d = RAMP_ACCEL, RAMP_DECEL
    c = 1.0 - a - d
    v_peak = _ramp_peak()
    if u <= a:
        dPdu = (v_peak * u) / a
    elif u <= a + c:
        dPdu = v_peak
    else:
        s = u - a - c
        dPdu = v_peak * (1.0 - s / d)
    return dPdu / span


def shaped_ease(t: float) -> float:
    """Public alias — same contract as the TS engine."""
    return speed_ramp(t)


def _motion_offset(motion: str, e: float, sign: int) -> tuple[float, float, float, float]:
    if motion == "orbit":
        theta = (e - 0.5) * 2.0
        return ORBIT_Z0, ORBIT_ZOOM, theta * ORBIT_TRAVEL * sign, math.sin(e * math.pi) * ORBIT_ARC * sign
    if motion == "push_in":
        return 1.0, PUSH_ZOOM, e * PUSH_DRIFT_X * sign, e * PUSH_DRIFT_Y * sign
    if motion == "pull_out":
        return PUSH_ZOOM, 1.0, (1.0 - e) * PUSH_DRIFT_X * sign, (1.0 - e) * PUSH_DRIFT_Y * sign
    if motion == "ken_burns":
        return 1.0, KEN_BURNS_ZOOM, e * KEN_BURNS_DRIFT_X * sign, e * KEN_BURNS_DRIFT_Y * sign
    return 1.0, STATIC_ZOOM, 0.0, 0.0


def _travel_for_ratio(ratio: float) -> tuple[float, float]:
    if ratio <= 9 / 16 + 0.02:
        return FRAME_TRAVEL_X_9X16, FRAME_TRAVEL_Y_9X16
    if ratio <= 1.05:
        return FRAME_TRAVEL_X_1X1, FRAME_TRAVEL_Y_1X1
    return FRAME_TRAVEL_X, FRAME_TRAVEL_Y


def _apply_window(
    z0: float,
    z1: float,
    ox: float,
    oy: float,
    e: float,
    focal: tuple[float, float],
    plate_w: float,
    plate_h: float,
    ratio: float,
) -> tuple[float, float, float, float]:
    fx, fy = focal
    z = z0 + (z1 - z0) * e
    _bx, _by, base_w, base_h = largest_aspect(int(plate_w), int(plate_h), ratio)
    w = base_w / z
    h = base_h / z
    max_x = max(0.0, plate_w - w)
    max_y = max(0.0, plate_h - h)
    tx, ty = _travel_for_ratio(ratio)
    home_x = max_x * min(max(fx, 0.0), 1.0)
    home_y = max_y * min(max(fy, 0.0), 1.0)
    x = min(max(home_x + ox * w * tx, 0.0), max_x)
    y = min(max(home_y + oy * h * ty, 0.0), max_y)
    return x, y, w, h


def camera_window_at(
    motion: str,
    t01: float,
    yaw: int | None = None,
    focal: tuple[float, float] = (0.5, 0.46),
) -> tuple[float, float, float, float]:
    motion = assert_allowed(motion)
    sign = 1 if (yaw if yaw is not None else 1) >= 0 else -1
    e = speed_ramp(t01)
    z0, z1, ox, oy = _motion_offset(motion, e, sign)
    return _apply_window(z0, z1, ox, oy, e, focal, float(KB_PLATE_W), float(KB_PLATE_H), 16 / 9)


def camera_source_window(
    motion: str,
    t01: float,
    yaw: int | None,
    focal: tuple[float, float],
    img_w: int,
    img_h: int,
    aspect: str,
) -> tuple[float, float, float, float]:
    """Full-bleed crop in source pixels. 9:16 is a real vertical slice, not letterboxed 16:9."""
    motion = assert_allowed(motion)
    ratio = 9 / 16 if aspect == "9x16" else 1.0 if aspect == "1x1" else 16 / 9
    sign = 1 if (yaw if yaw is not None else 1) >= 0 else -1
    e = speed_ramp(t01)
    z0, z1, ox, oy = _motion_offset(motion, e, sign)
    return _apply_window(z0, z1, ox, oy, e, focal, float(img_w), float(img_h), ratio)


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
