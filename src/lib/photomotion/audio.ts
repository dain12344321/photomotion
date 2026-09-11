import { detectBeatsFromAudioBuffer, fallbackGrid } from "./beats.ts";
import type { BeatGrid } from "./types.ts";
import type { MusicTrack } from "./types.ts";

const cache = new Map<string, BeatGrid>();

export async function detectTrackBeats(track: MusicTrack): Promise<BeatGrid> {
  const hit = cache.get(track.id);
  if (hit) return hit;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const res = await fetch(track.preview);
    const raw = await res.arrayBuffer();
    const buf = await ctx.decodeAudioData(raw.slice(0));
    const grid = detectBeatsFromAudioBuffer(buf, { bpm: track.bpm, introS: track.intro_s });
    cache.set(track.id, grid);
    void ctx.close();
    return grid;
  } catch {
    const grid = fallbackGrid(track.bpm, track.intro_s);
    cache.set(track.id, grid);
    return grid;
  }
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load ${src}`));
    img.src = src;
  });
}
