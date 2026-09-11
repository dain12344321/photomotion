"""Room classification: filename heuristics, optional Grok vision."""

from __future__ import annotations

import json
import re
from pathlib import Path

from photomotion.constants import CHAT_MODEL, XAI_BASE
from photomotion.motion import motion_for_room, normalize_room

NUM_RE = re.compile(r"(\d{2,4})")

# Curated read of 11477 N 250 W, Sumava Resorts — operator-selected stills.
SUMAVA_OVERRIDE = {
    "001.jpg": {"room": "exterior_front", "label": "Dusk front elevation", "role": "hero_open"},
    "002.jpg": {"room": "exterior_deck", "label": "Wraparound deck and yard", "role": "exterior_close"},
    "003.jpg": {"room": "exterior_front", "label": "Daylight three-quarter", "role": "exterior"},
    "004.jpg": {"room": "garage", "label": "Driveway and garage", "skip": True},
    "005.jpg": {"room": "backyard", "label": "Backyard toward the woods", "role": "backyard"},
    "006.jpg": {"room": "living", "label": "Living room with fireplace", "role": "hero_interior"},
    "007.jpg": {"room": "dining", "label": "Dining through to living", "role": "living"},
    "008.jpg": {"room": "kitchen", "label": "Kitchen", "role": "kitchen"},
    "009.jpg": {"room": "bedroom_primary", "label": "Primary bedroom", "role": "bedroom"},
    "010.jpg": {"room": "bedroom", "label": "Secondary bedroom", "role": "bedroom"},
    "013.jpg": {"room": "bathroom", "label": "Vanity with mirrors", "skip": True},
    "014.jpg": {"room": "bathroom", "label": "Soaking tub", "role": "bath"},
    "018.jpg": {"room": "laundry", "label": "Laundry", "skip": True},
    "043.jpg": {"room": "drone", "label": "Aerial of the wooded lot", "role": "closer"},
}

# 405 N Main St, Wanatah IN — MLS stills from the operator Drive folder.
WANATAH_OVERRIDE = {
    "001.jpg": {"room": "exterior_front", "label": "Dusk front elevation", "role": "hero_open"},
    "002.jpg": {"room": "exterior_front", "label": "Daylight front", "role": "exterior"},
    "003.jpg": {"room": "exterior_front", "label": "Covered porch", "skip": True},
    "004.jpg": {"room": "garage", "label": "Garage and drive", "skip": True},
    "005.jpg": {"room": "backyard", "label": "Rear elevation", "role": "backyard"},
    "006.jpg": {"room": "living", "label": "Living room", "role": "hero_interior"},
    "007.jpg": {"room": "living", "label": "Living toward dining", "role": "living"},
    "008.jpg": {"room": "kitchen", "label": "Kitchen", "role": "kitchen"},
    "009.jpg": {"room": "dining", "label": "Dining room", "role": "dining"},
    "010.jpg": {"room": "bathroom", "label": "Hall bath", "skip": True},
    "011.jpg": {"room": "bathroom", "label": "Vanity", "skip": True},
    "012.jpg": {"room": "bathroom", "label": "Tub and bath", "skip": True},
    "013.jpg": {"room": "bathroom", "label": "Bath detail", "skip": True},
    "014.jpg": {"room": "bedroom_primary", "label": "Primary bedroom", "role": "bedroom"},
    "015.jpg": {"room": "bedroom", "label": "Secondary bedroom", "role": "bedroom"},
    "017.jpg": {"room": "backyard", "label": "Backyard toward the woods", "role": "closer"},
}


def _stem_key(name: str) -> str:
    return Path(name).name.lower()


def heuristic_room(filename: str, index: int, total: int) -> dict:
    name = filename.lower()
    if any(k in name for k in ("drone", "aerial", "overhead")):
        room = "drone"
    elif any(k in name for k in ("bath", "vanity", "shower", "tub", "toilet")):
        room = "bathroom"
    elif any(k in name for k in ("laundry", "mudroom", "utility")):
        room = "laundry"
    elif "garage" in name:
        room = "garage"
    elif any(k in name for k in ("kitchen",)):
        room = "kitchen"
    elif any(k in name for k in ("living", "great", "family", "fireplace")):
        room = "living"
    elif any(k in name for k in ("dining",)):
        room = "dining"
    elif any(k in name for k in ("primary", "master")) and "bed" in name:
        room = "bedroom_primary"
    elif "bed" in name:
        room = "bedroom"
    elif any(k in name for k in ("deck", "patio", "porch")):
        room = "exterior_deck"
    elif any(k in name for k in ("yard", "backyard", "garden")):
        room = "backyard"
    elif any(k in name for k in ("exterior", "front", "curb", "twilight", "_vt")):
        room = "exterior_front"
    else:
        nums = NUM_RE.findall(Path(filename).stem)
        n = int(nums[-1]) if nums else index
        if n <= 5:
            room = "exterior_front"
        elif n <= 8:
            room = "living"
        elif n <= 12:
            room = "bedroom"
        elif n >= 40:
            room = "drone"
        else:
            room = "interior"
    room = normalize_room(room)
    return {
        "filename": filename,
        "room": room,
        "label": room.replace("_", " ").title(),
        "motion": motion_for_room(room),
        "method": "heuristic",
        "skip": False,
    }


def apply_override(item: dict, override: dict) -> dict:
    merged = dict(item)
    merged.update({k: v for k, v in override.items() if v is not None})
    merged["room"] = normalize_room(merged.get("room", item["room"]))
    merged["motion"] = motion_for_room(merged["room"])
    merged["method"] = "override"
    return merged


def _auto_override(filenames: list[str]) -> dict:
    stems = {_stem_key(f) for f in filenames}
    joined = " ".join(stems)
    if "043.jpg" in stems or "sumava" in joined or "11477" in joined:
        return SUMAVA_OVERRIDE
    if ("017.jpg" in stems and ("015.jpg" in stems or "014.jpg" in stems)) or "wanatah" in joined or "405_n_main" in joined:
        return WANATAH_OVERRIDE
    if stems & set(SUMAVA_OVERRIDE) and "043.jpg" in stems:
        return SUMAVA_OVERRIDE
    return {}


def classify_items(filenames: list[str], override: dict | None = None) -> list[dict]:
    total = len(filenames)
    out = []
    ov = {**_auto_override(filenames), **(override or {})}
    for i, name in enumerate(filenames, start=1):
        item = heuristic_room(name, i, total)
        key = Path(name).name
        if key in ov:
            item = apply_override(item, ov[key])
        elif _stem_key(key) in ov:
            item = apply_override(item, ov[_stem_key(key)])
        out.append(item)
    return out


def load_override(path: Path | None) -> dict:
    if path and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "selected" in data:
            return {row["file"]: row for row in data["selected"]}
        if isinstance(data, dict):
            return data
    return {}


def vision_classify(proxy_path: Path, api_key: str) -> dict | None:
    """Optional Grok vision. Never required. Returns None on failure."""
    import base64
    import urllib.request

    raw = proxy_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    body = json.dumps(
        {
            "model": CHAT_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Classify this real-estate listing photo. "
                                "Reply JSON only: {\"room\": one of "
                                "[exterior_front, exterior_deck, backyard, drone, living, dining, "
                                "kitchen, bedroom_primary, bedroom, bathroom, laundry, garage, interior], "
                                "\"label\": short caption, \"skip\": false}."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            "temperature": 0,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{XAI_BASE}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        return None
    return None
