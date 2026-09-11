import { ROOM_ORDER, TARGET_CLIPS, TARGET_SECONDS } from "./constants.ts";
import { coerceMotion, defaultFocal, normalizeRoom, orbitYaw } from "./motion.ts";
import type { ClassifiedStill, PlannedClip, TourPlan } from "./types.ts";

function rank(room: string): number {
  const r = normalizeRoom(room);
  const exact = ROOM_ORDER.indexOf(r as (typeof ROOM_ORDER)[number]);
  if (exact >= 0) return exact;
  for (let i = 0; i < ROOM_ORDER.length; i++) {
    const key = ROOM_ORDER[i];
    if (r.includes(key) || key.includes(r)) return i;
  }
  return 50;
}

export function planTour(classified: ClassifiedStill[], maxClips = TARGET_CLIPS): TourPlan {
  let selected = classified.filter((c) => !c.skip);
  selected.sort((a, b) => {
    const ra = rank(a.room);
    const rb = rank(b.room);
    if (ra !== rb) return ra - rb;
    return a.filename.localeCompare(b.filename);
  });

  if (selected.length > maxClips) {
    const must: ClassifiedStill[] = [];
    const rest: ClassifiedStill[] = [];
    const seen: Record<string, number> = {};
    for (const c of selected) {
      const room = normalizeRoom(c.room || "interior");
      const role = c.role;
      if (
        role === "hero_open" ||
        role === "hero_interior" ||
        role === "closer" ||
        room === "exterior_front" ||
        room === "living" ||
        room === "kitchen" ||
        room === "bedroom_primary" ||
        room === "drone"
      ) {
        const cap = room === "exterior_front" || room === "bedroom" || room === "bedroom_primary" ? 2 : 1;
        if ((seen[room] || 0) < cap) {
          must.push(c);
          seen[room] = (seen[room] || 0) + 1;
          continue;
        }
      }
      rest.push(c);
    }
    selected = [...must, ...rest].slice(0, maxClips);
  }

  const clips: PlannedClip[] = selected.map((c, i) => {
    const room = normalizeRoom(c.room || "interior");
    const motion = coerceMotion(room, c.motion, i);
    return {
      index: i,
      filename: c.filename,
      src: c.src,
      room,
      label: c.label || room.replace(/_/g, " "),
      motion,
      lane: "kenburns",
      role: c.role || room,
      duration_s: null,
      yaw: orbitYaw(i),
      focal: defaultFocal(room),
    };
  });

  return {
    clip_count: clips.length,
    target_seconds: TARGET_SECONDS,
    clips,
    dropped: classified.filter((c) => c.skip).map((c) => c.filename),
  };
}
