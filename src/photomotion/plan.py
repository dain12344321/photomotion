"""Select ~10–12 stills and order a 30s tour."""

from __future__ import annotations

from photomotion.constants import ROOM_ORDER, TARGET_CLIPS, TARGET_SECONDS
from photomotion.motion import coerce_motion, default_focal, normalize_room, orbit_yaw


def _rank(room: str) -> int:
    r = normalize_room(room)
    try:
        return ROOM_ORDER.index(r)
    except ValueError:
        for i, key in enumerate(ROOM_ORDER):
            if key in r or r in key:
                return i
        return 50


def plan_tour(classified: list[dict], max_clips: int = TARGET_CLIPS) -> dict:
    selected = [c for c in classified if not c.get("skip")]
    # Dedup similar rooms if we have extras, keep first of each after sort.
    selected.sort(key=lambda c: (_rank(c.get("room", "")), c.get("filename", "")))

    # Prefer diversity but keep MLS narrative.
    if len(selected) > max_clips:
        # Keep all exteriors/heroes first, then fill.
        must = []
        rest = []
        seen_rooms: dict[str, int] = {}
        for c in selected:
            room = normalize_room(c.get("room", "interior"))
            role = c.get("role")
            if role in {"hero_open", "hero_interior", "closer"} or room in {
                "exterior_front",
                "living",
                "kitchen",
                "bedroom_primary",
                "drone",
            }:
                cap = 2 if room in {"exterior_front", "bedroom", "bedroom_primary"} else 1
                if seen_rooms.get(room, 0) < cap:
                    must.append(c)
                    seen_rooms[room] = seen_rooms.get(room, 0) + 1
                    continue
            rest.append(c)
        picked = must[:]
        for c in rest:
            if len(picked) >= max_clips:
                break
            picked.append(c)
        selected = picked[:max_clips]

    clips = []
    prev = None
    for i, c in enumerate(selected):
        room = normalize_room(c.get("room", "interior"))
        motion = coerce_motion(room, c.get("motion"), index=i, role=c.get("role"), prev=prev)
        prev = motion
        fx, fy = default_focal(room)
        clips.append(
            {
                "index": i,
                "filename": c["filename"],
                "room": room,
                "label": c.get("label") or room.replace("_", " ").title(),
                "motion": motion,
                "lane": "kenburns",
                "role": c.get("role") or room,
                "duration_s": None,  # filled after beat-snap
                "yaw": orbit_yaw(i),
                "focal": {"x": fx, "y": fy},
            }
        )

    return {
        "clip_count": len(clips),
        "target_seconds": TARGET_SECONDS,
        "clips": clips,
        "dropped": [c["filename"] for c in classified if c.get("skip")],
    }
