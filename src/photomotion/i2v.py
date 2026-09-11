"""Grok Imagine image-to-video adapter. Dry-run default. Fail → Ken Burns."""

from __future__ import annotations

import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

from photomotion.constants import (
    FPS,
    I2V_DURATION_S,
    I2V_MODEL,
    MASTER_H,
    MASTER_W,
    XAI_BASE,
)
from photomotion.spend import SpendBlocked, assert_live_allowed, estimate_clip_usd


class I2VResult:
    def __init__(self, **kwargs):
        self.ok = kwargs.get("ok", False)
        self.path = kwargs.get("path")
        self.fallback = kwargs.get("fallback", False)
        self.reason = kwargs.get("reason", "")
        self.sidecar = kwargs.get("sidecar") or {}


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def encode_still_jpeg(proxy: Path, long_side: int = 1920, quality: int = 85) -> bytes:
    """Re-encode the ~1920 proxy so the Imagine payload stays small."""
    with Image.open(proxy) as im:
        im = im.convert("RGB")
        w, h = im.size
        longest = max(w, h)
        if longest > long_side:
            scale = long_side / longest
            im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        buf = BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True)
        return buf.getvalue()


def still_to_data_url(proxy: Path) -> str:
    data = encode_still_jpeg(proxy)
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def upload_file(proxy: Path, api_key: str) -> str:
    """Files API fallback — never upload 6000px camera JPEGs."""
    boundary = "----photomotion"
    data = encode_still_jpeg(proxy)
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="purpose"\r\n\r\n'
            "assistants\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{proxy.stem}.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8")
        + data
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )
    req = urllib.request.Request(
        f"{XAI_BASE}/files",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["id"]


def _post_json(path: str, payload: dict, api_key: str, timeout: int = 60) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{XAI_BASE}{path}",
        data=body,
        headers=_auth_headers(api_key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_http_detail(exc)) from exc


def start_generation(
    image: dict,
    prompt: str,
    api_key: str,
    duration: int = I2V_DURATION_S,
) -> str:
    payload = {
        "model": I2V_MODEL,
        "prompt": prompt,
        "image": image,
        "duration": int(duration),
        "generate_audio": False,
        # Do NOT set aspect_ratio — it stretches 3:2 stills.
    }
    try:
        result = _post_json("/videos/generations", payload, api_key)
    except RuntimeError as exc:
        if "generate_audio" not in str(exc).lower():
            raise
        payload.pop("generate_audio", None)
        result = _post_json("/videos/generations", payload, api_key)
    return result.get("request_id") or result.get("id")


def poll(request_id: str, api_key: str, timeout_s: int = 300) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        req = urllib.request.Request(
            f"{XAI_BASE}/videos/{request_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        status = payload.get("status")
        if status == "done":
            return payload
        if status in {"failed", "expired"}:
            raise RuntimeError(f"I2V {status}: {payload}")
        time.sleep(5)
    raise TimeoutError(f"I2V poll timed out for {request_id}")


def download_video(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest


def conform_i2v(src: Path, dest: Path, duration_s: float) -> Path:
    """Crop-fill to 1920×1080 @ 30fps and trim from frame 1 to the beat length."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={MASTER_W}:{MASTER_H}:force_original_aspect_ratio=increase,"
        f"crop={MASTER_W}:{MASTER_H},fps={FPS},format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-t",
        f"{max(0.5, float(duration_s)):.4f}",
        "-an",
        "-vf",
        vf,
        "-r",
        str(FPS),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "conform failed: " + proc.stderr.decode("utf-8", errors="replace")[-1500:]
        )
    return dest


def write_sidecar(path: Path, payload: dict) -> None:
    # Never persist the bearer. Sidecar is model/request/hash/duration/USD only.
    safe = {
        k: payload[k]
        for k in payload
        if k.lower() not in {"authorization", "api_key", "bearer", "token"}
    }
    path.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def _http_detail(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = ""
        return f"HTTP {exc.code} {body or exc.reason}"
    return str(exc)[:500]


def generate_or_fallback(
    *,
    still_hash: str,
    proxy: Path,
    dest: Path,
    sidecar_path: Path,
    prompt: str,
    dry_run: bool,
    confirm_live: bool,
    spend_cap: float,
    already_spent: float,
    api_key: str | None,
    kenburns_fn,
    output_duration_s: float | None = None,
) -> I2VResult:
    estimate = estimate_clip_usd()
    out_dur = float(output_duration_s or I2V_DURATION_S)
    sidecar = {
        "model": I2V_MODEL,
        "still_sha256": still_hash,
        "proxy": str(proxy),
        "duration_s": I2V_DURATION_S,
        "output_duration_s": round(out_dur, 4),
        "estimated_usd": estimate,
        "generate_audio": False,
    }
    try:
        assert_live_allowed(
            dry_run=dry_run,
            confirm_live=confirm_live,
            spend_cap=spend_cap,
            estimated_usd=estimate,
            already_spent=already_spent,
        )
    except SpendBlocked as exc:
        kenburns_fn(dest)
        sidecar.update({"ok": False, "fallback": "kenburns", "reason": str(exc)})
        write_sidecar(sidecar_path, sidecar)
        return I2VResult(ok=True, path=dest, fallback=True, reason=str(exc), sidecar=sidecar)

    if not api_key:
        kenburns_fn(dest)
        sidecar.update({"ok": False, "fallback": "kenburns", "reason": "no api key"})
        write_sidecar(sidecar_path, sidecar)
        return I2VResult(ok=True, path=dest, fallback=True, reason="no api key", sidecar=sidecar)

    try:
        image = {"url": still_to_data_url(proxy)}
        try:
            request_id = start_generation(image, prompt, api_key)
        except RuntimeError as exc:
            # Some accounts want Files API / file_id instead of a data URI.
            if "image" not in str(exc).lower() and "url" not in str(exc).lower():
                raise
            file_id = upload_file(proxy, api_key)
            sidecar["file_id"] = file_id
            request_id = start_generation({"file_id": file_id}, prompt, api_key)
        sidecar["request_id"] = request_id
        result = poll(request_id, api_key)
        url = (result.get("video") or {}).get("url") or result.get("url")
        if not url:
            raise RuntimeError("I2V done but no video url")
        raw = dest.with_suffix(".raw.mp4")
        download_video(url, raw)
        conform_i2v(raw, dest, out_dur)
        sidecar.update(
            {
                "ok": True,
                "fallback": False,
                "status": "done",
                "raw": str(raw),
            }
        )
        write_sidecar(sidecar_path, sidecar)
        return I2VResult(ok=True, path=dest, fallback=False, sidecar=sidecar)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        RuntimeError,
        TimeoutError,
        OSError,
        ValueError,
    ) as exc:
        kenburns_fn(dest)
        sidecar.update(
            {"ok": False, "fallback": "kenburns", "reason": _http_detail(exc)}
        )
        write_sidecar(sidecar_path, sidecar)
        return I2VResult(
            ok=True, path=dest, fallback=True, reason=_http_detail(exc), sidecar=sidecar
        )
