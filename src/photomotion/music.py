"""Curated MLS beds. CC BY Kevin MacLeod. Tagged BPM is the grid."""

from __future__ import annotations

from pathlib import Path

from photomotion.constants import MUSIC_DIR, ROOT

# Hidden Agenda / Backbay Lounge / Air Prelude are banned from this build.
REMOVED_TRACKS = {
    "hidden-agenda": "easy-lemon",
    "hidden-angel": "easy-lemon",
    "backbay-lounge": "funkorama",
    "back-bay": "funkorama",
    "backbay": "funkorama",
    "air-prelude": "easy-lemon",
}

TRACKS: tuple[dict, ...] = (
    {
        "id": "easy-lemon",
        "title": "Easy Lemon",
        "artist": "Kevin MacLeod",
        "mood": "Warm acoustic",
        "file": "easy-lemon.mp3",
        "bpm": 82.0,
        "intro_s": 0.4,
    },
    {
        "id": "wallpaper",
        "title": "Wallpaper",
        "artist": "Kevin MacLeod",
        "mood": "Cinematic",
        "file": "wallpaper.mp3",
        "bpm": 92.0,
        "intro_s": 4.0,
    },
    {
        "id": "carefree",
        "title": "Carefree",
        "artist": "Kevin MacLeod",
        "mood": "Contemporary",
        "file": "carefree.mp3",
        "bpm": 96.0,
        "intro_s": 0.3,
    },
    {
        "id": "funkorama",
        "title": "Funkorama",
        "artist": "Kevin MacLeod",
        "mood": "Light funk",
        "file": "funkorama.mp3",
        "bpm": 101.0,
        "intro_s": 0.5,
    },
)

DEFAULT_TRACK_ID = "easy-lemon"


def catalog() -> list[dict]:
    return [dict(t, preview=f"/music/{t['file']}") for t in TRACKS]


def resolve_track(track_id: str | None) -> dict:
    wanted = (track_id or DEFAULT_TRACK_ID).strip().lower()
    wanted = REMOVED_TRACKS.get(wanted, wanted)
    for t in TRACKS:
        if t["id"] == wanted:
            return t
    return next(t for t in TRACKS if t["id"] == DEFAULT_TRACK_ID)


def pick_track(clips: list[dict] | None, track_id: str | None = None) -> dict:
    """Operator pick wins. Otherwise Easy Lemon, Wallpaper for dusk/drone."""
    if track_id:
        return resolve_track(track_id)
    rooms = {str(c.get("room") or "") for c in (clips or [])}
    labels = " ".join(str(c.get("label") or "") for c in (clips or [])).lower()
    cinematic = rooms & {"drone", "exterior_front"} and (
        "dusk" in labels or "twilight" in labels or "aerial" in labels
    )
    if cinematic:
        return resolve_track("wallpaper")
    return resolve_track(DEFAULT_TRACK_ID)


def music_file(track_id: str | None = None) -> Path:
    rec = resolve_track(track_id)
    p = MUSIC_DIR / rec["file"]
    if p.exists():
        return p
    return ROOT / "assets" / "music" / rec["file"]
