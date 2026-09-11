import { SUMAVA_OVERRIDE, WANATAH_OVERRIDE } from "./classify.ts";
import type { DemoListing, ListingStill } from "./types.ts";

function stillsFromOverride(ov: Record<string, { room?: string; label?: string; role?: string; skip?: boolean }>): ListingStill[] {
  return Object.entries(ov)
    .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
    .map(([file, rec]) => ({
      file,
      room: rec.room,
      label: rec.label,
      role: rec.role,
      skip: rec.skip,
    }));
}

export const DEMOS: DemoListing[] = [
  {
    id: "wanatah",
    address: "405 N Main St",
    city: "Wanatah, IN 46390",
    basePath: "/listings/wanatah/",
    stills: stillsFromOverride(WANATAH_OVERRIDE),
  },
  {
    id: "sumava",
    address: "11477 N 250 W",
    city: "Sumava Resorts, IN 46379",
    basePath: "/listings/sumava/",
    stills: stillsFromOverride(SUMAVA_OVERRIDE),
  },
];

export function listingById(id: string): DemoListing | undefined {
  return DEMOS.find((d) => d.id === id);
}
