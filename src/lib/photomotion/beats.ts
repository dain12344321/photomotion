/**
 * Offline beat grid. Dual-band onset (high-passed piano attacks + body),
 * tagged-BPM prior, downbeat phase lock. No network. No ffmpeg.
 */
import { TARGET_SECONDS } from "./constants.ts";
import type { BeatGrid, CutSnap } from "./types.ts";

const HOP = 512;
const WIN = 2048;
const DETECT_SR = 22050;

export function resampleMono(input: Float32Array, fromSr: number, toSr = DETECT_SR): Float32Array {
  if (fromSr === toSr) return input;
  const ratio = fromSr / toSr;
  const n = Math.max(1, Math.floor(input.length / ratio));
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = i * ratio;
    const i0 = Math.floor(x);
    const i1 = Math.min(input.length - 1, i0 + 1);
    const f = x - i0;
    out[i] = input[i0] * (1 - f) + input[i1] * f;
  }
  return out;
}

function onePoleHpf(x: Float32Array, alpha = 0.97): Float32Array {
  const y = new Float32Array(x.length);
  let prevX = 0;
  let prevY = 0;
  for (let i = 0; i < x.length; i++) {
    const yi = alpha * (prevY + x[i] - prevX);
    y[i] = yi;
    prevX = x[i];
    prevY = yi;
  }
  return y;
}

function onePoleLpf(x: Float32Array, alpha = 0.86): Float32Array {
  const y = new Float32Array(x.length);
  let acc = 0;
  for (let i = 0; i < x.length; i++) {
    acc = acc + alpha * (x[i] - acc);
    y[i] = acc;
  }
  return y;
}

function rmsEnvelope(audio: Float32Array, hop = HOP, win = WIN): Float32Array {
  const n = 1 + Math.max(0, Math.floor((audio.length - win) / hop));
  const env = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const start = i * hop;
    let acc = 0;
    const end = Math.min(audio.length, start + win);
    for (let j = start; j < end; j++) acc += audio[j] * audio[j];
    env[i] = Math.sqrt(acc / Math.max(1, end - start) + 1e-12);
  }
  return env;
}

function positiveFlux(env: Float32Array): Float32Array {
  const out = new Float32Array(env.length);
  let median = 0;
  const tmp = Array.from(env).sort((a, b) => a - b);
  median = tmp[Math.floor(tmp.length / 2)] ?? 0;
  for (let i = 0; i < env.length; i++) {
    const prev = i === 0 ? env[0] : env[i - 1];
    out[i] = Math.max(0, env[i] - prev - median * 0.02);
  }
  const med = Array.from(out).sort((a, b) => a - b)[Math.floor(out.length / 2)] ?? 0;
  for (let i = 0; i < out.length; i++) out[i] = Math.max(0, out[i] - med);
  return out;
}

export function onsetEnvelope(
  audio: Float32Array,
  sr: number,
  hop = HOP,
  win = WIN,
): { times: Float32Array; onset: Float32Array } {
  const high = onePoleHpf(audio, 0.97);
  const low = onePoleLpf(audio, 0.12);
  const highEnv = rmsEnvelope(high, hop, win);
  const lowEnv = rmsEnvelope(low, hop, win);
  const highFlux = positiveFlux(highEnv);
  const lowFlux = positiveFlux(lowEnv);
  const n = highFlux.length;
  const onset = new Float32Array(n);
  for (let i = 0; i < n; i++) onset[i] = highFlux[i] + 0.35 * lowFlux[i];
  const times = new Float32Array(n);
  for (let i = 0; i < n; i++) times[i] = (i * hop) / sr;
  return { times, onset };
}

function autocorrBpm(onset: Float32Array, sr: number, hop: number, minBpm: number, maxBpm: number): number {
  let minLag = Math.floor(sr / hop / (maxBpm / 60));
  let maxLag = Math.floor(sr / hop / (minBpm / 60));
  maxLag = Math.min(maxLag, Math.max(minLag + 1, Math.floor(onset.length / 3)));
  if (maxLag <= minLag) return 96;
  const n = onset.length;
  let bestLag = minLag;
  let best = -Infinity;
  for (let lag = minLag; lag < maxLag; lag++) {
    let acc = 0;
    for (let i = 0; i < n - lag; i++) acc += onset[i] * onset[i + lag];
    if (acc > best) {
      best = acc;
      bestLag = lag;
    }
  }
  let bpm = (sr / hop / bestLag) * 60;
  if (bpm > 118) bpm /= 2;
  return bpm;
}

export function inferBpm(onset: Float32Array, sr: number, hop = HOP, prior?: number): { bpm: number; source: "tagged" | "detected" } {
  if (prior && prior > 0) {
    const lo = prior * 0.92;
    const hi = prior * 1.08;
    const locked = autocorrBpm(onset, sr, hop, lo, hi);
    if (locked >= lo && locked <= hi) return { bpm: locked, source: "tagged" };
  }
  return { bpm: autocorrBpm(onset, sr, hop, 70, 130), source: "detected" };
}

function sampleOnset(times: Float32Array, onset: Float32Array, t: number): number {
  if (times.length === 0) return 0;
  let lo = 0;
  let hi = times.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] < t) lo = mid + 1;
    else hi = mid;
  }
  const i = clampIndex(lo, times.length);
  const j = clampIndex(i - 1, times.length);
  return Math.max(onset[i] ?? 0, onset[j] ?? 0);
}

function clampIndex(i: number, n: number): number {
  return Math.min(n - 1, Math.max(0, i));
}

export function lockPhase(times: Float32Array, onset: Float32Array, bpm: number, introS: number): number {
  const interval = 60 / bpm;
  const bar = interval * 4;
  const start = Math.max(introS, 0.2);
  const windowEnd = start + 6;
  const candidates: number[] = [];
  let peak = 0;
  for (let i = 0; i < times.length; i++) {
    if (times[i] < start || times[i] > windowEnd) continue;
    peak = Math.max(peak, onset[i]);
  }
  const thresh = 0.22 * peak;
  for (let i = 0; i < times.length; i++) {
    if (times[i] < start || times[i] > windowEnd) continue;
    if (onset[i] > thresh) candidates.push(times[i]);
    if (candidates.length >= 64) break;
  }
  if (candidates.length === 0) {
    let bestI = 0;
    let bestV = -1;
    for (let i = 0; i < times.length; i++) {
      if (times[i] < start) continue;
      if (onset[i] > bestV) {
        bestV = onset[i];
        bestI = i;
      }
    }
    return times[bestI] ?? start;
  }
  const lastT = times[times.length - 1] ?? start + 20;
  const scored: { score: number; t: number }[] = [];
  for (const t of candidates) {
    let score = 0;
    for (let k = 0; k < 24; k++) {
      const target = t + k * interval;
      if (target > lastT) break;
      const mag = sampleOnset(times, onset, target);
      score += mag;
      if (k % 4 === 0) score += mag * 0.85;
    }
    // Prefer earlier downbeats among equal scores so we don't skip the intro.
    score -= t * 0.01;
    scored.push({ score, t });
  }
  scored.sort((a, b) => b.score - a.score);
  const best = scored[0]?.score ?? 0;
  const early = scored.filter((s) => s.score >= 0.7 * best).map((s) => s.t);
  const picked = early.length ? Math.min(...early) : (scored[0]?.t ?? start);
  // Snap to the nearest bar after intro so cuts land on downbeats.
  const barsFromZero = Math.round((picked - start) / bar);
  return start + Math.max(0, barsFromZero) * bar || picked;
}

export function detectBeatsFromPcm(
  pcm: Float32Array,
  sampleRate: number,
  opts: { bpm?: number; introS?: number } = {},
): BeatGrid {
  const sr = DETECT_SR;
  const audio = resampleMono(pcm, sampleRate, sr);
  const duration = audio.length / sr;
  const slice = audio.subarray(0, Math.min(audio.length, sr * 90));
  const { times, onset } = onsetEnvelope(slice, sr);
  const inferred = inferBpm(onset, sr, HOP, opts.bpm);
  const tagged = opts.bpm && opts.bpm > 0 ? opts.bpm : inferred.bpm;
  const bpm = opts.bpm && opts.bpm > 0 ? opts.bpm : inferred.bpm;
  const phase = lockPhase(times, onset, bpm, opts.introS ?? 0.4);
  const beatInterval = 60 / bpm;
  const beats: number[] = [];
  const full = Math.max(duration, 48);
  for (let t = phase; t < full + 40; t += beatInterval) beats.push(Math.round(t * 10000) / 10000);
  return {
    bpm: Math.round(bpm * 100) / 100,
    beat_interval: Math.round(beatInterval * 10000) / 10000,
    phase: Math.round(phase * 10000) / 10000,
    beats,
    duration: Math.round(full * 1000) / 1000,
    bar_s: Math.round(4 * beatInterval * 10000) / 10000,
    source: opts.bpm && opts.bpm > 0 ? "tagged" : inferred.source,
  };
  void tagged;
}

export function fallbackGrid(bpm = 82, introS = 0.4): BeatGrid {
  const interval = 60 / bpm;
  const beats: number[] = [];
  for (let t = introS; t < 80; t += interval) beats.push(Math.round(t * 10000) / 10000);
  return {
    bpm,
    beat_interval: Math.round(interval * 10000) / 10000,
    phase: introS,
    beats,
    duration: 180,
    bar_s: Math.round(4 * interval * 10000) / 10000,
    source: "tagged",
  };
}

export function snapClipDurations(
  clips: { room?: string; role?: string }[] | number,
  beats: Pick<BeatGrid, "beat_interval" | "phase">,
  targetTotal = TARGET_SECONDS,
  firstExtraBeats = 0,
): CutSnap[] {
  const roles = typeof clips === "number" ? [] : clips;
  const n = typeof clips === "number" ? clips : clips.length;
  const interval = beats.beat_interval;
  const barBeats = 4;
  const barS = barBeats * interval;
  const bars = Array.from({ length: n }, () => 1);
  const need = Math.max(n, Math.round(targetTotal / barS));
  let extra = Math.max(0, need - n);
  const priority: number[] = [0];
  roles.forEach((clip, i) => {
    const room = String(clip.room || "");
    const role = String(clip.role || "");
    if (
      role === "hero_open" ||
      role === "hero_interior" ||
      room === "drone" ||
      room === "exterior_front" ||
      room === "living"
    ) {
      if (!priority.includes(i)) priority.push(i);
    }
  });
  if (n - 1 >= 0 && !priority.includes(n - 1)) priority.push(n - 1);
  for (const i of priority) {
    if (extra <= 0) break;
    if (i >= 0 && i < n) {
      bars[i] += 1;
      extra -= 1;
    }
  }
  if (n && bars[0] === 1 && (sum(bars) + 1) * barS <= targetTotal + 4) {
    bars[0] += 1;
  }
  if (firstExtraBeats && n) {
    bars[0] = Math.max(bars[0], 1 + Math.round(firstExtraBeats / barBeats));
  }
  const startBeat = beats.phase;
  let t = startBeat;
  const cuts: CutSnap[] = [];
  for (let i = 0; i < n; i++) {
    const nBeats = bars[i] * barBeats;
    const dur = nBeats * interval;
    cuts.push({
      index: i,
      start: round4(t - startBeat),
      music_time: round4(t),
      duration_s: round4(dur),
      beats: nBeats,
    });
    t += dur;
  }
  const total = cuts.length ? cuts[cuts.length - 1].start + cuts[cuts.length - 1].duration_s : 0;
  if (total < targetTotal - barS * 0.6 && cuts.length) {
    const last = cuts[cuts.length - 1];
    last.beats += barBeats;
    last.duration_s = round4(last.beats * interval);
  }
  return cuts;
}

function sum(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

/** Mix down an AudioBuffer (browser) and detect. */
export function detectBeatsFromAudioBuffer(
  buffer: { getChannelData: (c: number) => Float32Array; numberOfChannels: number; sampleRate: number; length: number },
  opts: { bpm?: number; introS?: number } = {},
): BeatGrid {
  const ch0 = buffer.getChannelData(0);
  let pcm = ch0;
  if (buffer.numberOfChannels > 1) {
    const ch1 = buffer.getChannelData(1);
    pcm = new Float32Array(buffer.length);
    for (let i = 0; i < buffer.length; i++) pcm[i] = (ch0[i] + ch1[i]) * 0.5;
  }
  return detectBeatsFromPcm(pcm, buffer.sampleRate, opts);
}
