"""Motion policy: in-frame push_in / orbit, or static. Never invent off-frame."""

from photomotion.constants import ALLOWED_MOTIONS, BANNED_MOTIONS, STATIC_ROOMS


class MotionPolicyError(ValueError):
    pass


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


def motion_for_room(room: str) -> str:
    r = normalize_room(room)
    if r in STATIC_ROOMS or any(k in r for k in STATIC_ROOMS):
        return "static"
    return "push_in"


def assign_motion(room: str, index: int) -> str:
    """Alternate dolly and in-frame orbit. Baths stay frozen."""
    if motion_for_room(room) == "static":
        return "static"
    return "orbit" if index % 2 else "push_in"


def orbit_yaw(index: int) -> int:
    """Alternate orbit direction so consecutive clips don't drift the same way."""
    return 1 if (index // 2) % 2 == 0 else -1


def assert_allowed(motion: str) -> str:
    m = (motion or "").strip().lower().replace(" ", "_")
    if m in BANNED_MOTIONS or m not in ALLOWED_MOTIONS:
        raise MotionPolicyError(
            f"Banned or unknown motion {motion!r}. Automatic pipeline allows only {sorted(ALLOWED_MOTIONS)}."
        )
    return m


def coerce_motion(room: str, requested: str | None, index: int = 0) -> str:
    """Requested motion wins only if allowed; baths/etc. force static."""
    if motion_for_room(room) == "static":
        return "static"
    default = motion_for_room(room)
    if requested and requested != default:
        return assert_allowed(requested)
    return assign_motion(room, index)
