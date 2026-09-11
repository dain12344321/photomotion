import { motionForRoom, normalizeRoom } from "./motion.ts";
import type { ClassifiedStill } from "./types.ts";

const NUM_RE = /(\d{2,4})/g;

export const SUMAVA_OVERRIDE: Record<string, Partial<ClassifiedStill>> = {
  "001.jpg": { room: "exterior_front", label: "Dusk front elevation", role: "hero_open" },
  "002.jpg": { room: "exterior_deck", label: "Wraparound deck and yard", role: "exterior_close" },
  "003.jpg": { room: "exterior_front", label: "Daylight three-quarter", role: "exterior" },
  "004.jpg": { room: "garage", label: "Driveway and garage", skip: true },
  "005.jpg": { room: "backyard", label: "Backyard toward the woods", role: "backyard" },
  "006.jpg": { room: "living", label: "Living room with fireplace", role: "hero_interior" },
  "007.jpg": { room: "dining", label: "Dining through to living", role: "living" },
  "008.jpg": { room: "kitchen", label: "Kitchen", role: "kitchen" },
  "009.jpg": { room: "bedroom_primary", label: "Primary bedroom", role: "bedroom" },
  "010.jpg": { room: "bedroom", label: "Secondary bedroom", role: "bedroom" },
  "013.jpg": { room: "bathroom", label: "Vanity with mirrors", skip: true },
  "014.jpg": { room: "bathroom", label: "Soaking tub", role: "bath" },
  "018.jpg": { room: "laundry", label: "Laundry", skip: true },
  "043.jpg": { room: "drone", label: "Aerial of the wooded lot", role: "closer" },
};

export const WANATAH_OVERRIDE: Record<string, Partial<ClassifiedStill>> = {
  "001.jpg": { room: "exterior_front", label: "Dusk front elevation", role: "hero_open" },
  "002.jpg": { room: "exterior_front", label: "Daylight front", role: "exterior" },
  "003.jpg": { room: "exterior_front", label: "Covered porch", skip: true },
  "004.jpg": { room: "garage", label: "Garage and drive", skip: true },
  "005.jpg": { room: "backyard", label: "Rear elevation", role: "backyard" },
  "006.jpg": { room: "living", label: "Living room", role: "hero_interior" },
  "007.jpg": { room: "living", label: "Living toward dining", role: "living" },
  "008.jpg": { room: "kitchen", label: "Kitchen", role: "kitchen" },
  "009.jpg": { room: "dining", label: "Dining room", role: "dining" },
  "010.jpg": { room: "bathroom", label: "Hall bath", skip: true },
  "011.jpg": { room: "bathroom", label: "Vanity", skip: true },
  "012.jpg": { room: "bathroom", label: "Tub and bath", skip: true },
  "013.jpg": { room: "bathroom", label: "Bath detail", skip: true },
  "014.jpg": { room: "bedroom_primary", label: "Primary bedroom", role: "bedroom" },
  "015.jpg": { room: "bedroom", label: "Secondary bedroom", role: "bedroom" },
  "017.jpg": { room: "backyard", label: "Backyard toward the woods", role: "closer" },
};

function stemKey(name: string): string {
  const base = name.split("/").pop() || name;
  return base.toLowerCase();
}

function lastNumber(filename: string, fallback: number): number {
  const nums = Array.from(filename.matchAll(NUM_RE)).map((m) => Number(m[1]));
  return nums.length ? nums[nums.length - 1] : fallback;
}

export function heuristicRoom(filename: string, index: number, _total: number): ClassifiedStill {
  const name = filename.toLowerCase();
  let room = "interior";
  if (/(drone|aerial|overhead)/.test(name)) room = "drone";
  else if (/(bath|vanity|shower|tub|toilet)/.test(name)) room = "bathroom";
  else if (/(laundry|mudroom|utility)/.test(name)) room = "laundry";
  else if (name.includes("garage")) room = "garage";
  else if (name.includes("kitchen")) room = "kitchen";
  else if (/(living|great|family|fireplace)/.test(name)) room = "living";
  else if (name.includes("dining")) room = "dining";
  else if (/(primary|master)/.test(name) && name.includes("bed")) room = "bedroom_primary";
  else if (name.includes("bed")) room = "bedroom";
  else if (/(deck|patio|porch)/.test(name)) room = "exterior_deck";
  else if (/(yard|backyard|garden)/.test(name)) room = "backyard";
  else if (/(exterior|front|curb|twilight|_vt)/.test(name)) room = "exterior_front";
  else {
    const n = lastNumber(filename, index);
    if (n <= 5) room = "exterior_front";
    else if (n <= 8) room = "living";
    else if (n <= 12) room = "bedroom";
    else if (n >= 40) room = "drone";
    else room = "interior";
  }
  room = normalizeRoom(room);
  return {
    filename,
    room,
    label: room.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    motion: motionForRoom(room),
    method: "heuristic",
    skip: false,
  };
}

export function applyOverride(item: ClassifiedStill, override: Partial<ClassifiedStill>): ClassifiedStill {
  const merged: ClassifiedStill = { ...item, ...override, filename: item.filename };
  merged.room = normalizeRoom(merged.room || item.room);
  merged.motion = motionForRoom(merged.room);
  merged.method = "override";
  return merged;
}

export function detectListingOverride(filenames: string[]): Record<string, Partial<ClassifiedStill>> | null {
  const stems = new Set(filenames.map(stemKey));
  if (stems.has("043.jpg")) return SUMAVA_OVERRIDE;
  if (stems.has("017.jpg") && (stems.has("015.jpg") || stems.has("014.jpg"))) return WANATAH_OVERRIDE;
  if ([...stems].some((s) => s.includes("wanatah") || s.includes("405_n_main"))) return WANATAH_OVERRIDE;
  if ([...stems].some((s) => s.includes("sumava") || s.includes("11477"))) return SUMAVA_OVERRIDE;
  return null;
}

export function classifyItems(
  filenames: string[],
  override?: Record<string, Partial<ClassifiedStill>> | null,
): ClassifiedStill[] {
  const auto = detectListingOverride(filenames);
  const ov = { ...(auto || {}), ...(override || {}) };
  return filenames.map((name, i) => {
    let item = heuristicRoom(name, i + 1, filenames.length);
    const key = name.split("/").pop() || name;
    if (ov[key]) item = applyOverride(item, ov[key]);
    else if (ov[stemKey(key)]) item = applyOverride(item, ov[stemKey(key)]);
    return item;
  });
}
