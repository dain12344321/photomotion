import { TARGET_SECONDS } from "./constants.ts";
import { classifyItems } from "./classify.ts";
import { detectBeatsFromPcm, fallbackGrid, snapClipDurations } from "./beats.ts";
import { pickTrack, resolveTrack } from "./music.ts";
import { planTour } from "./plan.ts";
import type { BeatGrid, ClassifiedStill, DemoListing, MusicTrack, TourPlan } from "./types.ts";

export type BuiltTour = {
  plan: TourPlan;
  beats: BeatGrid;
  track: MusicTrack;
  classified: ClassifiedStill[];
};

export function stillsToFilenames(listing: DemoListing): string[] {
  return listing.stills.map((s) => s.file);
}

export function classifiedFromListing(listing: DemoListing): ClassifiedStill[] {
  const names = stillsToFilenames(listing);
  const override: Record<string, Partial<ClassifiedStill>> = {};
  for (const s of listing.stills) {
    override[s.file] = {
      room: s.room,
      label: s.label,
      role: s.role,
      skip: s.skip,
    };
  }
  return classifyItems(names, override).map((c) => ({
    ...c,
    src: listing.basePath + c.filename,
  }));
}

export function classifiedFromFiles(files: { name: string; src: string }[]): ClassifiedStill[] {
  const names = files.map((f) => f.name);
  const classified = classifyItems(names);
  const byName = new Map(files.map((f) => [f.name, f.src]));
  return classified.map((c) => ({ ...c, src: byName.get(c.filename) }));
}

export function assembleTour(
  classified: ClassifiedStill[],
  opts: { musicId?: string; beats?: BeatGrid } = {},
): BuiltTour {
  const plan = planTour(classified);
  const track = pickTrack(plan.clips, opts.musicId);
  const beats = opts.beats ?? fallbackGrid(track.bpm, track.intro_s);
  const snaps = snapClipDurations(plan.clips, beats, TARGET_SECONDS);
  for (let i = 0; i < plan.clips.length; i++) {
    const clip = plan.clips[i];
    const snap = snaps[i];
    if (!snap) continue;
    clip.duration_s = snap.duration_s;
    clip.music_time = snap.music_time;
    clip.start = snap.start;
    clip.beats = snap.beats;
  }
  plan.beats = { bpm: beats.bpm, phase: beats.phase, interval: beats.beat_interval };
  plan.total_s = Math.round(plan.clips.reduce((a, c) => a + (c.duration_s || 0), 0) * 1000) / 1000;
  plan.music_id = track.id;
  plan.music_title = track.title;
  return { plan, beats, track, classified };
}

export function retargetMusic(plan: TourPlan, musicId: string, beats?: BeatGrid): BuiltTour {
  const track = resolveTrack(musicId);
  const grid = beats ?? fallbackGrid(track.bpm, track.intro_s);
  return assembleTour(
    plan.clips.map((c) => ({
      filename: c.filename,
      src: c.src,
      room: c.room,
      label: c.label,
      motion: c.motion,
      method: "override",
      skip: false,
      role: c.role,
    })),
    { musicId: track.id, beats: grid },
  );
}

export { detectBeatsFromPcm };
