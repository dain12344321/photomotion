import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ALLOWED_MOTIONS,
  HOLD_IN,
  HOLD_OUT,
  KB_PLATE_H,
  KB_PLATE_W,
  ORBIT_ZOOM,
  PUSH_ZOOM,
  STATIC_ZOOM,
} from "./constants.ts";
import { cameraPath, cameraSourceWindow, cameraWindowAt, rampVelocity, shapedEase, speedRamp } from "./camera.ts";
import { detectBeatsFromPcm, snapClipDurations } from "./beats.ts";
import { classifyItems, WANATAH_OVERRIDE } from "./classify.ts";
import { assembleTour, classifiedFromListing } from "./tour.ts";
import { listingById } from "./listings.ts";
import {
  assertAllowed,
  assignMotion,
  coerceMotion,
  MotionPolicyError,
  motionForRoom,
} from "./motion.ts";
import { catalog, DEFAULT_TRACK_ID, resolveTrack } from "./music.ts";

describe("motion policy", () => {
  it("freezes baths laundry garage", () => {
    assert.equal(motionForRoom("bathroom"), "static");
    assert.equal(motionForRoom("laundry"), "static");
    assert.equal(motionForRoom("garage"), "static");
    assert.equal(motionForRoom("vanity"), "static");
  });
  it("moves wide rooms", () => {
    assert.equal(motionForRoom("living"), "orbit");
    assert.equal(motionForRoom("exterior_front"), "orbit");
    assert.equal(motionForRoom("kitchen"), "pull_out");
  });
  it("bans pan", () => {
    for (const banned of ["pan", "pan_left", "zoom_out"]) {
      assert.throws(() => assertAllowed(banned), MotionPolicyError);
    }
  });
  it("allows in-frame orbit, pull-out, ken burns", () => {
    assert.equal(assertAllowed("orbit"), "orbit");
    assert.equal(assertAllowed("pull_out"), "pull_out");
    assert.equal(assertAllowed("pull-out"), "pull_out");
    assert.equal(assertAllowed("ken_burns"), "ken_burns");
    assert.equal(assertAllowed("kenburns"), "ken_burns");
  });
  it("bath cannot be overridden to push", () => {
    assert.equal(coerceMotion("bathroom", "push_in"), "static");
  });
  it("assigns room-aware cinematography", () => {
    assert.equal(assignMotion("living", 0), "orbit");
    assert.equal(assignMotion("kitchen", 0), "pull_out");
    assert.equal(assignMotion("bathroom", 1), "static");
    assert.equal(assignMotion("bedroom", 0), "push_in");
    assert.equal(assignMotion("living", 1, undefined, "orbit"), "pull_out");
    assert.equal(assignMotion("exterior_front", 0, "hero_open"), "push_in");
    assert.equal(assignMotion("backyard", 9, "closer"), "pull_out");
  });
  it("allowed set", () => {
    assert.deepEqual([...ALLOWED_MOTIONS].sort(), ["ken_burns", "orbit", "pull_out", "push_in", "static"]);
  });
});

describe("camera path", () => {
  it("windows stay in the plate", () => {
    for (const motion of ["push_in", "orbit", "pull_out", "ken_burns", "static"] as const) {
      for (const yaw of [1, -1]) {
        const wins = cameraPath(motion, 48, yaw, { x: 0.28, y: 0.42 });
        assert.equal(wins.length, 48);
        for (const w of wins) {
          assert.ok(w.x >= -1e-6);
          assert.ok(w.y >= -1e-6);
          assert.ok(w.x + w.w <= KB_PLATE_W + 1e-6);
          assert.ok(w.y + w.h <= KB_PLATE_H + 1e-6);
          assert.ok(w.w > 0 && w.h > 0);
        }
      }
    }
  });
  it("orbit trucks and push zooms", () => {
    const orbit = cameraPath("orbit", 60, 1);
    assert.ok(Math.abs(orbit[orbit.length - 1].x - orbit[0].x) > 80);
    const push = cameraPath("push_in", 60, 1);
    assert.ok(push[0].w > push[push.length - 1].w);
    assert.ok(PUSH_ZOOM > ORBIT_ZOOM);
    assert.ok(ORBIT_ZOOM > STATIC_ZOOM);
    assert.ok(PUSH_ZOOM >= 1.35);
    assert.ok(ORBIT_ZOOM >= 1.28);
  });
  it("pull_out zooms out", () => {
    const pull = cameraPath("pull_out", 60, 1);
    assert.ok(pull[0].w < pull[pull.length - 1].w);
    const push = cameraPath("push_in", 60, 1);
    assert.ok(Math.abs(pull[0].w - push[push.length - 1].w) < 1e-6);
    assert.ok(Math.abs(pull[pull.length - 1].w - push[0].w) < 1e-6);
  });
  it("ken burns drifts while zooming", () => {
    const kb = cameraPath("ken_burns", 60, 1);
    assert.ok(kb[0].w > kb[kb.length - 1].w);
    assert.ok(Math.abs(kb[kb.length - 1].x - kb[0].x) > 20);
  });
  it("holds the still before the move", () => {
    assert.equal(shapedEase(0), 0);
    assert.equal(shapedEase(HOLD_IN), 0);
    assert.ok(shapedEase(HOLD_IN + 0.05) > 0);
    const push = cameraPath("push_in", 100, 1);
    assert.ok(Math.abs(push[0].w - push[2].w) < 1);
  });
  it("speed ramp rests at both ends", () => {
    assert.equal(speedRamp(0), 0);
    assert.equal(speedRamp(1), 1);
    assert.equal(rampVelocity(0), 0);
    assert.equal(rampVelocity(1), 0);
    assert.equal(rampVelocity(HOLD_IN), 0);
    assert.equal(rampVelocity(1 - HOLD_OUT), 0);
    assert.ok(rampVelocity(0.5) > 0);
  });
  it("cameraWindowAt matches path endpoints", () => {
    const a = cameraWindowAt("push_in", 0);
    const b = cameraWindowAt("push_in", 1);
    const path = cameraPath("push_in", 2);
    assert.equal(path[0].w, a.w);
    assert.equal(path[1].w, b.w);
  });
  it("9:16 is a real vertical slice, not letterboxed 16:9", () => {
    const imgW = 4000;
    const imgH = 2667;
    const start = cameraSourceWindow("orbit", 0, 1, { x: 0.5, y: 0.46 }, imgW, imgH, "9x16");
    const mid = cameraSourceWindow("orbit", 0.5, 1, { x: 0.5, y: 0.46 }, imgW, imgH, "9x16");
    const end = cameraSourceWindow("orbit", 1, 1, { x: 0.5, y: 0.46 }, imgW, imgH, "9x16");
    const ratio = (w: { w: number; h: number }) => w.w / w.h;
    assert.ok(Math.abs(ratio(start) - 9 / 16) < 0.01);
    assert.ok(Math.abs(ratio(mid) - 9 / 16) < 0.01);
    assert.ok(start.y >= -1e-6);
    assert.ok(start.y + start.h <= imgH + 1e-6);
    assert.ok(start.x >= -1e-6);
    assert.ok(start.x + start.w <= imgW + 1e-6);
    // Landscape leftover: the 9:16 slice trucks across the still.
    assert.ok(Math.abs(end.x - start.x) > 200);
    // At the wide end it uses nearly the full still height.
    assert.ok(start.h > imgH * 0.7);
    const wide = cameraSourceWindow("push_in", 0, 1, { x: 0.5, y: 0.46 }, imgW, imgH, "16x9");
    assert.ok(Math.abs(wide.w / wide.h - 16 / 9) < 0.01);
  });
});

describe("beats", () => {
  it("snaps every cut to a 4-beat bar", () => {
    const beats = { bpm: 96, beat_interval: 0.625, phase: 0.4 };
    const clips = [{ room: "exterior_front", role: "hero_open" }, ...Array.from({ length: 10 }, () => ({ room: "living" }))];
    const snaps = snapClipDurations(clips, beats, 30);
    assert.equal(snaps.length, 11);
    for (const s of snaps) {
      assert.equal(s.beats % 4, 0);
      assert.ok(s.beats >= 4);
    }
    const total = snaps[snaps.length - 1].start + snaps[snaps.length - 1].duration_s;
    assert.ok(total >= 27);
    assert.ok(total <= 36);
  });
  it("detects a synthetic 96 bpm click track offline", () => {
    const sr = 22050;
    const bpm = 96;
    const interval = 60 / bpm;
    const dur = 12;
    const pcm = new Float32Array(sr * dur);
    const phase = 0.5;
    for (let t = phase; t < dur; t += interval) {
      const i0 = Math.floor(t * sr);
      for (let k = 0; k < 80 && i0 + k < pcm.length; k++) {
        pcm[i0 + k] = Math.sin((Math.PI * k) / 80) * (k < 8 ? 1 : 0.4);
      }
    }
    const grid = detectBeatsFromPcm(pcm, sr, { introS: 0.4 });
    assert.ok(grid.bpm > 70 && grid.bpm < 130);
    assert.ok(Math.abs(grid.bpm - 96) < 8 || Math.abs(grid.bpm - 48) < 8);
    assert.ok(Math.abs(grid.phase - phase) < 0.08, `phase ${grid.phase} should lock to onset ${phase}, not intro 0.4`);
    const snaps = snapClipDurations(8, grid, 30);
    for (const s of snaps) assert.equal(s.beats % 4, 0);
    for (const s of snaps) {
      const err = Math.abs((s.music_time - grid.phase) / grid.beat_interval / 4 - Math.round((s.music_time - grid.phase) / grid.beat_interval / 4));
      assert.ok(err < 1e-6);
    }
  });
  it("uses tagged bpm when provided", () => {
    const sr = 22050;
    const pcm = new Float32Array(sr * 4);
    const grid = detectBeatsFromPcm(pcm, sr, { bpm: 82, introS: 0.4 });
    assert.equal(grid.bpm, 82);
    assert.equal(grid.source, "tagged");
  });
});

describe("music catalog", () => {
  it("keeps the four licensed beds", () => {
    const ids = new Set(catalog().map((t) => t.id));
    assert.deepEqual(ids, new Set(["easy-lemon", "wallpaper", "carefree", "funkorama"]));
    assert.equal(DEFAULT_TRACK_ID, "easy-lemon");
    assert.equal(resolveTrack(null).id, "easy-lemon");
    assert.equal(resolveTrack("hidden-agenda").id, "easy-lemon");
    assert.equal(resolveTrack("backbay-lounge").id, "funkorama");
    assert.equal(resolveTrack("air-prelude").id, "easy-lemon");
  });
});

describe("wanatah listing", () => {
  it("plans a ~30s in-frame tour", () => {
    const listing = listingById("wanatah");
    assert.ok(listing);
    const classified = classifiedFromListing(listing!);
    const { plan, track } = assembleTour(classified);
    assert.ok(plan.clip_count >= 8);
    assert.ok(plan.clip_count <= 11);
    assert.ok((plan.total_s || 0) >= 24);
    assert.ok((plan.total_s || 0) <= 40);
    assert.equal(plan.clips[0].role, "hero_open");
    assert.equal(plan.clips[0].motion, "push_in");
    assert.ok(plan.clips.some((c) => c.motion === "orbit"));
    assert.ok(plan.clips.some((c) => c.motion === "pull_out"));
    const allowed = new Set(["push_in", "orbit", "static", "pull_out", "ken_burns"]);
    for (let i = 0; i < plan.clips.length; i++) {
      const c = plan.clips[i];
      assert.ok(allowed.has(c.motion));
      if (c.room === "bathroom") assert.equal(c.motion, "static");
      assert.ok(c.yaw === 1 || c.yaw === -1);
      assert.ok(c.focal.x > 0 && c.focal.x < 1);
      if (i > 0 && c.motion !== "static" && plan.clips[i - 1].motion !== "static") {
        assert.notEqual(c.motion, plan.clips[i - 1].motion);
      }
    }
    assert.equal(track.id, "wallpaper");
    assert.ok(!plan.dropped.includes("001.jpg"));
    assert.ok(plan.dropped.includes("010.jpg"));
  });
  it("classifies wanatah stems", () => {
    const names = Object.keys(WANATAH_OVERRIDE);
    const items = classifyItems(names);
    const front = items.find((i) => i.filename === "001.jpg");
    assert.equal(front?.room, "exterior_front");
    const bath = items.find((i) => i.filename === "010.jpg");
    assert.equal(bath?.skip, true);
  });
});
