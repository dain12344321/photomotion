"""Motion policy: in-frame push_in / orbit / pull_out / ken_burns, or static."""

from photomotion.constants import (
    ALLOWED_MOTIONS,
    BANNED_MOTIONS,
    MOTION_CYCLE,
    STATIC_ROOMS,
    WIDE_ORBIT_ROOMS,
)


class MotionPolicyError(ValueError):
    pass


MOTION_ALIASES = {
    "pull-out": "pull_out",
    "kenburns": "ken_burns",
    "ken-burns": "ken_burns",
    "ken_burn": "ken_burns",
}


def normalize_room(room: str) -> str:
    r = (room or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "bath": "bathroom",
        "primary_bathroom": "bathroom",
        "master_bath": "bathroom",
        "ensuite": "bathroom",
        "half_bath": "bathroom",
        "powder_room": "bathroom",
        "vanity": "bathroom",
        "tub": "bathroom",
        "shower": "bathroom",
        "master_bedroom": "bedroom_primary",
        "primary_bedroom": "bedroom_primary",
        "primary": "bedroom_primary",
        "bed": "bedroom",
        "living_room": "living",
        "great_room": "living",
        "family_room": "living",
        "dining_room": "dining",
        "kitchen_dining": "kitchen",
        "mudroom": "laundry",
        "garage_interior": "garage",
        "front_exterior": "exterior_front",
        "curb": "exterior_front",
        "aerial": "drone",
        "yard": "backyard",
        "deck": "exterior_deck",
        "patio": "exterior_deck",
        "porch": "exterior_front",
    }
    return aliases.get(r, r)


def _is_static_room(room: str) -> bool:
    r = normalize_room(room)
    return r in STATIC_ROOMS or any(k in r for k in STATIC_ROOMS)


def _is_wide_room(room: str) -> bool:
    r = normalize_room(room)
    return r in WIDE_ORBIT_ROOMS or r.startswith("exterior")


def motion_for_room(room: str) -> str:
    r = normalize_room(room)
    if _is_static_room(r):
        return "static"
    if _is_wide_room(r):
        return "orbit"
    if r == "kitchen":
        return "pull_out"
    return "push_in"


def _avoid_repeat(preferred: str, prev: str | None) -> str:
    if not prev or preferred == "static" or preferred != prev:
        return preferred
    try:
        i = MOTION_CYCLE.index(preferred)
    except ValueError:
        return preferred
    return MOTION_CYCLE[(i + 1) % len(MOTION_CYCLE)]


def assign_motion(
    room: str,
    index: int,
    role: str | None = None,
    prev: str | None = None,
) -> str:
    """Room/role cinematography. Baths stay frozen. No consecutive repeats."""
    r = normalize_room(room)
    if _is_static_room(r):
        return "static"
    tag = (role or "").strip().lower()
    if tag == "hero_open":
        preferred = "push_in"
    elif tag == "closer":
        preferred = "pull_out"
    elif _is_wide_room(r):
        preferred = "orbit"
    elif r == "kitchen":
        preferred = "pull_out"
    else:
        preferred = MOTION_CYCLE[index % len(MOTION_CYCLE)]
    return _avoid_repeat(preferred, prev)


def orbit_yaw(index: int) -> int:
    """Alternate orbit direction so consecutive clips don't drift the same way."""
    return 1 if (index // 2) % 2 == 0 else -1


def assert_allowed(motion: str) -> str:
    m = (motion or "").strip().lower().replace(" ", "_")
    m = MOTION_ALIASES.get(m, m)
    if m in BANNED_MOTIONS or m not in ALLOWED_MOTIONS:
        raise MotionPolicyError(
            f"Banned or unknown motion {motion!r}. Automatic pipeline allows only {sorted(ALLOWED_MOTIONS)}."
        )
    return m


def coerce_motion(
    room: str,
    requested: str | None,
    index: int = 0,
    role: str | None = None,
    prev: str | None = None,
) -> str:
    """Requested motion wins only if allowed; baths/etc. force static."""
    if _is_static_room(room):
        return "static"
    default = motion_for_room(room)
    if requested and requested != default:
        return assert_allowed(requested)
    return assign_motion(room, index, role=role, prev=prev)


def default_focal(room: str) -> tuple[float, float]:
    r = normalize_room(room)
    if r == "drone":
        return 0.5, 0.5
    if "bathroom" in r or "laundry" in r or "garage" in r:
        return 0.5, 0.5
    if r.startswith("exterior") or r == "backyard":
        return 0.5, 0.46
    if r in {"kitchen", "living", "dining"}:
        return 0.5, 0.42
    return 0.5, 0.44
