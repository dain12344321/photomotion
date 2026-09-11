"""Lock a music bed to its tagged tempo and snap cuts to 4-beat bars.

Dual-band onset (high-passed piano attacks + body). Works fully offline —
numpy + optional ffmpeg decode, no librosa, no network.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np


def _decode_wav(mp3: Path, sr: int = 22050) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = Path(tmp.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp3),
                "-ac",
                "1",
                "-ar",
                str(sr),
                "-sample_fmt",
                "s16",
                str(wav),
            ],
            check=True,
            capture_output=True,
        )
        import wave

        with wave.open(str(wav), "rb") as w:
            n = w.getnframes()
            raw = w.readframes(n)
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        return audio
    finally:
        wav.unlink(missing_ok=True)


def _one_pole_hpf(x: np.ndarray, alpha: float = 0.97) -> np.ndarray:
    y = np.zeros_like(x)
    prev_x = 0.0
    prev_y = 0.0
    for i, xi in enumerate(x):
        yi = alpha * (prev_y + float(xi) - prev_x)
        y[i] = yi
        prev_x = float(xi)
        prev_y = yi
    return y


def _one_pole_lpf(x: np.ndarray, alpha: float = 0.12) -> np.ndarray:
    y = np.zeros_like(x)
    acc = 0.0
    for i, xi in enumerate(x):
        acc = acc + alpha * (float(xi) - acc)
        y[i] = acc
    return y


def _rms_envelope(audio: np.ndarray, hop: int = 512, win: int = 2048) -> np.ndarray:
    n = 1 + max(0, (len(audio) - win) // hop)
    env = np.zeros(n, dtype=np.float32)
    for i in range(n):
        sl = audio[i * hop : i * hop + win]
        env[i] = np.sqrt(np.mean(sl * sl) + 1e-12)
    return env


def _positive_flux(env: np.ndarray) -> np.ndarray:
    diff = np.diff(env, prepend=env[:1])
    onset = np.clip(diff, 0, None)
    onset = onset - np.median(onset)
    return np.clip(onset, 0, None)


def _onset_envelope(audio: np.ndarray, sr: int, hop: int = 512, win: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    high = _one_pole_hpf(audio)
    low = _one_pole_lpf(audio)
    high_flux = _positive_flux(_rms_envelope(high, hop, win))
    low_flux = _positive_flux(_rms_envelope(low, hop, win))
    n = min(len(high_flux), len(low_flux))
    onset = high_flux[:n] + 0.35 * low_flux[:n]
    times = np.arange(n) * hop / sr
    return times, onset


def _infer_bpm(onset: np.ndarray, sr: int, hop: int, min_bpm: float = 70.0, max_bpm: float = 130.0) -> float:
    min_lag = int(sr / hop / (max_bpm / 60))
    max_lag = int(sr / hop / (min_bpm / 60))
    max_lag = min(max_lag, max(min_lag + 1, len(onset) // 3))
    if max_lag <= min_lag:
        return 96.0
    ac = np.correlate(onset, onset, mode="full")[len(onset) - 1 :]
    band = ac[min_lag:max_lag]
    lag = int(np.argmax(band)) + min_lag
    bpm = float(sr / hop / lag * 60.0)
    if bpm > 118:
        bpm = bpm / 2.0
    return bpm


def _lock_phase(times: np.ndarray, onset: np.ndarray, bpm: float, intro_s: float) -> float:
    interval = 60.0 / bpm
    start = max(float(intro_s), 0.2)
    window = (times >= start) & (times <= start + 6.0)
    if not np.any(window) or float(np.max(onset[window])) <= 0:
        return start
    thresh = 0.22 * float(np.max(onset[window]))
    candidates = times[window][onset[window] > thresh]
    if candidates.size == 0:
        idx = int(np.argmax(onset * window))
        return float(times[idx])
    later = times[times >= start]
    later_on = onset[times >= start]
    scored: list[tuple[float, float]] = []
    for t in candidates[:64]:
        score = 0.0
        for k in range(24):
            target = float(t) + k * interval
            if target > later[-1]:
                break
            j = int(np.argmin(np.abs(later - target)))
            mag = float(later_on[j]) if abs(later[j] - target) < interval * 0.18 else 0.0
            score += mag
            if k % 4 == 0:
                score += mag * 0.85
        score -= float(t) * 0.01
        scored.append((score, float(t)))
    best = max(s for s, _ in scored)
    early = [t for s, t in scored if s >= 0.7 * best]
    return min(early) if early else scored[0][1]


def detect_bpm_and_beats(
    mp3: Path,
    sr: int = 22050,
    bpm: float | None = None,
    intro_s: float = 0.4,
) -> dict:
    audio = _decode_wav(mp3, sr=sr)
    duration = len(audio) / sr
    times, onset = _onset_envelope(audio[: sr * 90], sr)
    hop = 512
    tagged = bpm
    if not tagged or tagged <= 0:
        tagged = _infer_bpm(onset, sr, hop)
    elif tagged > 0:
        locked = _infer_bpm(onset, sr, hop, min_bpm=tagged * 0.92, max_bpm=tagged * 1.08)
        if tagged * 0.92 <= locked <= tagged * 1.08:
            tagged = tagged  # keep operator tag; phase still locks to audio
    phase = _lock_phase(times, onset, tagged, intro_s)
    beat_interval = 60.0 / tagged
    beats = []
    t = phase
    full_duration = max(duration, 48.0)
    while t < full_duration + 40:
        beats.append(round(t, 4))
        t += beat_interval
    return {
        "bpm": round(float(tagged), 2),
        "beat_interval": round(beat_interval, 4),
        "phase": round(phase, 4),
        "beats": beats,
        "duration": round(full_duration, 3),
        "bar_s": round(4 * beat_interval, 4),
        "source": "tagged" if bpm else "detected",
    }


def detect_from_pcm(pcm: np.ndarray, sr: int, bpm: float | None = None, intro_s: float = 0.4) -> dict:
    """Same grid as the TypeScript engine. Used by tests and Hermes without an mp3."""
    duration = len(pcm) / sr
    times, onset = _onset_envelope(np.asarray(pcm, dtype=np.float32)[: sr * 90], sr)
    hop = 512
    tagged = bpm if bpm and bpm > 0 else _infer_bpm(onset, sr, hop)
    phase = _lock_phase(times, onset, tagged, intro_s)
    beat_interval = 60.0 / tagged
    beats = []
    t = phase
    full = max(duration, 48.0)
    while t < full + 40:
        beats.append(round(t, 4))
        t += beat_interval
    return {
        "bpm": round(float(tagged), 2),
        "beat_interval": round(beat_interval, 4),
        "phase": round(phase, 4),
        "beats": beats,
        "duration": round(full, 3),
        "bar_s": round(4 * beat_interval, 4),
        "source": "tagged" if bpm else "detected",
    }


def snap_clip_durations(
    n_clips: int | list,
    beats: dict,
    target_clip: float = 2.5,
    target_total: float = 30.0,
    first_extra_beats: int = 0,
    clip_roles: list[dict] | None = None,
) -> list[dict]:
    """Every cut lands on a 4-beat bar. Hero / drone may take two bars."""
    if isinstance(n_clips, list):
        clip_roles = n_clips
        n = len(n_clips)
    else:
        n = int(n_clips)
    interval = float(beats["beat_interval"])
    bar_beats = 4
    bar_s = bar_beats * interval
    bars = [1] * n
    roles = clip_roles or []
    need = max(n, int(round(target_total / bar_s)))
    extra = max(0, need - n)
    priority: list[int] = [0]
    for i, clip in enumerate(roles):
        room = str(clip.get("room") or "")
        role = str(clip.get("role") or "")
        if role in {"hero_open", "hero_interior"} or room in {"drone", "exterior_front", "living"}:
            if i not in priority:
                priority.append(i)
    if n - 1 not in priority:
        priority.append(n - 1)
    for i in priority:
        if extra <= 0:
            break
        if 0 <= i < n:
            bars[i] += 1
            extra -= 1
    if n and bars[0] == 1 and (sum(bars) + 1) * bar_s <= target_total + 4.0:
        bars[0] += 1
    if first_extra_beats and n:
        bars[0] = max(bars[0], 1 + int(round(first_extra_beats / bar_beats)))
    start_beat = float(beats["phase"])
    t = start_beat
    cuts = []
    for i in range(n):
        n_beats = bars[i] * bar_beats
        dur = n_beats * interval
        cuts.append(
            {
                "index": i,
                "start": round(t - start_beat, 4),
                "music_time": round(t, 4),
                "duration_s": round(dur, 4),
                "beats": n_beats,
            }
        )
        t += dur
    total = cuts[-1]["start"] + cuts[-1]["duration_s"] if cuts else 0
    if total < target_total - bar_s * 0.6 and cuts:
        cuts[-1]["beats"] += bar_beats
        cuts[-1]["duration_s"] = round(cuts[-1]["beats"] * interval, 4)
    _ = target_clip
    return cuts
