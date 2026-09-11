import { ALLOWED_MOTIONS, BANNED_MOTIONS, STATIC_ROOMS } from "./constants.ts";
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

export function normalizeRoom(room: string): string {
  const r = (room || "").trim().toLowerCase().replace(/-/g, "_").replace(/ /g, "_");
  return ALIASES[r] ?? r;
}

export function motionForRoom(room: string): MotionName {
  const r = normalizeRoom(room);
  if (STATIC_ROOMS.some((k) => r === k || r.includes(k))) return "static";
  return "push_in";
}

export function assignMotion(room: string, index: number): MotionName {
  if (motionForRoom(room) === "static") return "static";
  return index % 2 ? "orbit" : "push_in";
}

export function orbitYaw(index: number): number {
  return Math.floor(index / 2) % 2 === 0 ? 1 : -1;
}

export function assertAllowed(motion: string): MotionName {
  const m = (motion || "").trim().toLowerCase().replace(/ /g, "_");
  if ((BANNED_MOTIONS as readonly string[]).includes(m) || !(ALLOWED_MOTIONS as readonly string[]).includes(m)) {
    throw new MotionPolicyError(
      `Banned or unknown motion ${JSON.stringify(motion)}. Automatic pipeline allows only ${[...ALLOWED_MOTIONS].sort().join(", ")}.`,
    );
  }
  return m as MotionName;
}

export function coerceMotion(room: string, requested: string | null | undefined, index = 0): MotionName {
  if (motionForRoom(room) === "static") return "static";
  const fallback = motionForRoom(room);
  if (requested && requested !== fallback) return assertAllowed(requested);
  return assignMotion(room, index);
}

export function defaultFocal(room: string): { x: number; y: number } {
  const r = normalizeRoom(room);
  if (r === "drone") return { x: 0.5, y: 0.5 };
  if (r.includes("bathroom") || r.includes("laundry") || r.includes("garage")) return { x: 0.5, y: 0.5 };
  if (r.startsWith("exterior") || r === "backyard") return { x: 0.5, y: 0.46 };
  if (r === "kitchen" || r === "living" || r === "dining") return { x: 0.5, y: 0.42 };
  return { x: 0.5, y: 0.44 };
}
