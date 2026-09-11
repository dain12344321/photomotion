import { ALLOWED_MOTIONS, BANNED_MOTIONS, MOTION_CYCLE, STATIC_ROOMS, WIDE_ORBIT_ROOMS } from "./constants.ts";
import type { MotionName } from "./types.ts";

export class MotionPolicyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MotionPolicyError";
  }
}

const ALIASES: Record<string, string> = {
  bath: "bathroom",
  primary_bathroom: "bathroom",
  master_bath: "bathroom",
  ensuite: "bathroom",
  half_bath: "bathroom",
  powder_room: "bathroom",
  vanity: "bathroom",
  tub: "bathroom",
  shower: "bathroom",
  master_bedroom: "bedroom_primary",
  primary_bedroom: "bedroom_primary",
  primary: "bedroom_primary",
  bed: "bedroom",
  living_room: "living",
  great_room: "living",
  family_room: "living",
  dining_room: "dining",
  kitchen_dining: "kitchen",
  mudroom: "laundry",
  garage_interior: "garage",
  front_exterior: "exterior_front",
  curb: "exterior_front",
  aerial: "drone",
  yard: "backyard",
  deck: "exterior_deck",
  patio: "exterior_deck",
  porch: "exterior_front",
};

const MOTION_ALIASES: Record<string, MotionName> = {
  "pull-out": "pull_out",
  kenburns: "ken_burns",
  "ken-burns": "ken_burns",
  ken_burn: "ken_burns",
};

export function normalizeRoom(room: string): string {
  const r = (room || "").trim().toLowerCase().replace(/-/g, "_").replace(/ /g, "_");
  return ALIASES[r] ?? r;
}

function isStaticRoom(room: string): boolean {
  const r = normalizeRoom(room);
  return STATIC_ROOMS.some((k) => r === k || r.includes(k));
}

function isWideRoom(room: string): boolean {
  const r = normalizeRoom(room);
  return (WIDE_ORBIT_ROOMS as readonly string[]).includes(r) || r.startsWith("exterior");
}

export function motionForRoom(room: string): MotionName {
  const r = normalizeRoom(room);
  if (isStaticRoom(r)) return "static";
  if (isWideRoom(r)) return "orbit";
  if (r === "kitchen") return "pull_out";
  return "push_in";
}

function avoidRepeat(preferred: MotionName, prev?: MotionName): MotionName {
  if (!prev || preferred === "static" || preferred !== prev) return preferred;
  const i = (MOTION_CYCLE as readonly string[]).indexOf(preferred);
  if (i < 0) return preferred;
  return MOTION_CYCLE[(i + 1) % MOTION_CYCLE.length];
}

export function assignMotion(room: string, index: number, role?: string, prev?: MotionName): MotionName {
  const r = normalizeRoom(room);
  if (isStaticRoom(r)) return "static";
  const tag = (role || "").trim().toLowerCase();
  let preferred: MotionName;
  if (tag === "hero_open") preferred = "push_in";
  else if (tag === "closer") preferred = "pull_out";
  else if (isWideRoom(r)) preferred = "orbit";
  else if (r === "kitchen") preferred = "pull_out";
  else preferred = MOTION_CYCLE[index % MOTION_CYCLE.length];
  return avoidRepeat(preferred, prev);
}

export function orbitYaw(index: number): number {
  return Math.floor(index / 2) % 2 === 0 ? 1 : -1;
}

export function assertAllowed(motion: string): MotionName {
  let m = (motion || "").trim().toLowerCase().replace(/ /g, "_");
  m = MOTION_ALIASES[m] ?? m;
  if ((BANNED_MOTIONS as readonly string[]).includes(m) || !(ALLOWED_MOTIONS as readonly string[]).includes(m)) {
    throw new MotionPolicyError(
      `Banned or unknown motion ${JSON.stringify(motion)}. Automatic pipeline allows only ${[...ALLOWED_MOTIONS].sort().join(", ")}.`,
    );
  }
  return m as MotionName;
}

export function coerceMotion(
  room: string,
  requested: string | null | undefined,
  index = 0,
  role?: string,
  prev?: MotionName,
): MotionName {
  if (isStaticRoom(room)) return "static";
  const fallback = motionForRoom(room);
  if (requested && requested !== fallback) return assertAllowed(requested);
  return assignMotion(room, index, role, prev);
}

export function defaultFocal(room: string): { x: number; y: number } {
  const r = normalizeRoom(room);
  if (r === "drone") return { x: 0.5, y: 0.5 };
  if (r.includes("bathroom") || r.includes("laundry") || r.includes("garage")) return { x: 0.5, y: 0.5 };
  if (r.startsWith("exterior") || r === "backyard") return { x: 0.5, y: 0.46 };
  if (r === "kitchen" || r === "living" || r === "dining") return { x: 0.5, y: 0.42 };
  return { x: 0.5, y: 0.44 };
}
