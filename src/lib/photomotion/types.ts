export type MotionName = "push_in" | "orbit" | "static";

export type RoomName =
  | "exterior_front"
  | "exterior"
  | "exterior_deck"
  | "backyard"
  | "drone"
  | "living"
  | "dining"
  | "kitchen"
  | "bedroom_primary"
  | "bedroom"
  | "bathroom"
  | "laundry"
  | "garage"
  | "interior";

export type CropWindow = { x: number; y: number; w: number; h: number };

export type Focal = { x: number; y: number };

export type ClassifiedStill = {
  filename: string;
  src?: string;
  room: string;
  label: string;
  motion: MotionName;
  method: "heuristic" | "override" | "drop";
  skip: boolean;
  role?: string;
};

export type PlannedClip = {
  index: number;
  filename: string;
  src?: string;
  room: string;
  label: string;
  motion: MotionName;
  lane: "kenburns";
  role: string;
  duration_s: number | null;
  start?: number;
  music_time?: number;
  beats?: number;
  yaw: number;
  focal: Focal;
};

export type BeatGrid = {
  bpm: number;
  beat_interval: number;
  phase: number;
  beats: number[];
  duration: number;
  bar_s: number;
  source: "tagged" | "detected";
};

export type CutSnap = {
  index: number;
  start: number;
  music_time: number;
  duration_s: number;
  beats: number;
};

export type MusicTrack = {
  id: string;
  title: string;
  artist: string;
  mood: string;
  file: string;
  preview: string;
  bpm: number;
  intro_s: number;
};

export type TourPlan = {
  clip_count: number;
  target_seconds: number;
  clips: PlannedClip[];
  dropped: string[];
  beats?: Pick<BeatGrid, "bpm" | "phase"> & { interval: number };
  total_s?: number;
  music_id?: string;
  music_title?: string;
};

export type ListingStill = {
  file: string;
  room?: string;
  label?: string;
  role?: string;
  skip?: boolean;
};

export type DemoListing = {
  id: string;
  address: string;
  city: string;
  basePath: string;
  stills: ListingStill[];
};
