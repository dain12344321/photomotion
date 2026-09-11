import type { MusicTrack } from "./types.ts";

const REMOVED: Record<string, string> = {
  "hidden-agenda": "easy-lemon",
  "hidden-angel": "easy-lemon",
  "backbay-lounge": "funkorama",
  "back-bay": "funkorama",
  backbay: "funkorama",
  "air-prelude": "easy-lemon",
};

export const TRACKS: MusicTrack[] = [
  {
    id: "easy-lemon",
    title: "Easy Lemon",
    artist: "Kevin MacLeod",
    mood: "Warm acoustic",
    file: "easy-lemon.mp3",
    preview: "/music/easy-lemon.mp3",
    bpm: 82,
    intro_s: 0.4,
  },
  {
    id: "wallpaper",
    title: "Wallpaper",
    artist: "Kevin MacLeod",
    mood: "Cinematic",
    file: "wallpaper.mp3",
    preview: "/music/wallpaper.mp3",
    bpm: 92,
    intro_s: 4,
  },
  {
    id: "carefree",
    title: "Carefree",
    artist: "Kevin MacLeod",
    mood: "Contemporary",
    file: "carefree.mp3",
    preview: "/music/carefree.mp3",
    bpm: 96,
    intro_s: 0.3,
  },
  {
    id: "funkorama",
    title: "Funkorama",
    artist: "Kevin MacLeod",
    mood: "Light funk",
    file: "funkorama.mp3",
    preview: "/music/funkorama.mp3",
    bpm: 101,
    intro_s: 0.5,
  },
];

export const DEFAULT_TRACK_ID = "easy-lemon";

export function catalog(): MusicTrack[] {
  return TRACKS.map((t) => ({ ...t }));
}

export function resolveTrack(trackId?: string | null): MusicTrack {
  let wanted = (trackId || DEFAULT_TRACK_ID).trim().toLowerCase();
  wanted = REMOVED[wanted] ?? wanted;
  return TRACKS.find((t) => t.id === wanted) ?? TRACKS.find((t) => t.id === DEFAULT_TRACK_ID)!;
}

export function pickTrack(clips: { room?: string; label?: string }[] | null, trackId?: string | null): MusicTrack {
  if (trackId) return resolveTrack(trackId);
  const rooms = new Set((clips || []).map((c) => String(c.room || "")));
  const labels = (clips || []).map((c) => String(c.label || "")).join(" ").toLowerCase();
  const cinematic =
    (rooms.has("drone") || rooms.has("exterior_front")) &&
    (labels.includes("dusk") || labels.includes("twilight") || labels.includes("aerial"));
  if (cinematic) return resolveTrack("wallpaper");
  return resolveTrack(DEFAULT_TRACK_ID);
}
