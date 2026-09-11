/** Locked product contract. Camera never leaves the photograph. */

export const ALLOWED_MOTIONS = ["push_in", "orbit", "static"] as const;
export const BANNED_MOTIONS = [
  "pan",
  "pull-out",
  "pull_out",
  "pan_left",
  "pan_right",
  "zoom_out",
] as const;

export const STATIC_ROOMS = [
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
] as const;

export const ROOM_ORDER = [
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
] as const;

export const TARGET_CLIPS = 11;
export const TARGET_SECONDS = 30;
export const CLIP_SECONDS = 2.5;
export const FPS = 30;
export const MASTER_W = 1920;
export const MASTER_H = 1080;
export const VERTICAL_W = 1080;
export const VERTICAL_H = 1920;
export const SQUARE = 1080;

/** Visible cinema dolly, still entirely inside the still. */
export const PUSH_ZOOM = 1.22;
export const ORBIT_ZOOM = 1.14;
export const ORBIT_Z0 = 1.05;
export const ORBIT_TRAVEL = 0.55;
export const STATIC_ZOOM = 1.016;
export const HOLD_IN = 0.12;
export const HOLD_OUT = 0.08;
export const KB_PLATE_W = 3840;
export const KB_PLATE_H = 2160;

export const DEFAULT_SPEND_CAP = 15;
export const HARD_SPEND_CAP = 25;
export const I2V_PRICE_PER_SEC_1080P = 0.25;
export const I2V_IMAGE_INPUT_USD = 0.01;
export const I2V_MODEL = "grok-imagine-video-1.5";
export const I2V_DURATION_S = 4;
export const XAI_BASE = "https://api.x.ai/v1";

export const IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"];
