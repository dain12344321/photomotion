"""Locked product contract. Do not invent architecture off-frame."""

from pathlib import Path

# Orbit is in-frame crop travel only — never I2V orbit (that invents edges).
ALLOWED_MOTIONS = frozenset({"push_in", "orbit", "static"})
BANNED_MOTIONS = frozenset(
    {"pan", "pull-out", "pull_out", "pan_left", "pan_right", "zoom_out"}
)

STATIC_ROOMS = frozenset(
    {
        "bathroom",
        "bath",
        "powder",
        "laundry",
        "garage",
        "mirror",
        "vanity",
        "closet",
        "detail",
        "utility",
        "mechanical",
        "half_bath",
        "primary_bath",
    }
)

ROOM_ORDER = (
    "exterior_front",
    "exterior",
    "living",
    "dining",
    "kitchen",
    "great_room",
    "bedroom_primary",
    "bedroom",
    "bathroom",
    "laundry",
    "exterior_deck",
    "backyard",
    "drone",
)

TARGET_CLIPS = 11
TARGET_SECONDS = 30.0
CLIP_SECONDS = 2.5
FPS = 30
MASTER_W, MASTER_H = 1920, 1080
VERTICAL_W, VERTICAL_H = 1080, 1920
SQUARE = 1080
# Visible cinema dolly / truck, still entirely inside the photograph.
PUSH_ZOOM = 1.22
ORBIT_ZOOM = 1.14
ORBIT_Z0 = 1.05
ORBIT_TRAVEL = 0.55
STATIC_ZOOM = 1.016
HOLD_IN = 0.12
HOLD_OUT = 0.08
KB_PLATE_W, KB_PLATE_H = 3840, 2160
PROXY_LONG_SIDE = 1920
KB_LONG_SIDE = 3840

DEFAULT_SPEND_CAP = 15.0
HARD_SPEND_CAP = 25.0
I2V_PRICE_PER_SEC_1080P = 0.25
I2V_IMAGE_INPUT_USD = 0.01
I2V_MODEL = "grok-imagine-video-1.5"
I2V_DURATION_S = 4
CHAT_MODEL = "grok-4.5"
XAI_BASE = "https://api.x.ai/v1"

ROOT = Path(__file__).resolve().parents[2]
MUSIC_DIR = ROOT / "assets" / "music"
MUSIC_REL = Path("assets/music/easy-lemon.mp3")
FONT_SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

I2V_LOCK = (
    "Animate THIS exact real-estate photograph with a tripod-mounted cinema camera. "
    "Pixels may only move because the CAMERA dollies forward. Nothing in the scene moves. "
    "Do not add, remove, morph, or restyle any object. "
    "NO fireplace if none is lit in the still — do not add fire, flames, embers, or glow. "
    "If a stove or hearth is unlit, it stays unlit. "
    "NO spinning or rocking ceiling fans — if a fan exists, freeze the blades. "
    "No swaying plants, curtains, water, steam, flickering bulbs, or rolling clouds. "
    "No extra furniture, people, pets, rugs, art, windows, or walls. "
    "No warping, rolling shutter, or handheld shake. Rock-solid, shot on a camera. "
    "Camera motion ONLY: slow smooth dolly-in on a nodal head. No orbit, pan, or pull-out."
)
