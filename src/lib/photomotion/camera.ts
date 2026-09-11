import {
  FRAME_TRAVEL_X,
  FRAME_TRAVEL_X_1X1,
  FRAME_TRAVEL_X_9X16,
  FRAME_TRAVEL_Y,
  FRAME_TRAVEL_Y_1X1,
  FRAME_TRAVEL_Y_9X16,
  HOLD_OUT,
  KB_PLATE_H,
  KB_PLATE_W,
  KEN_BURNS_DRIFT_X,
  KEN_BURNS_DRIFT_Y,
  KEN_BURNS_ZOOM,
  ORBIT_ARC,
  ORBIT_TRAVEL,
  ORBIT_Z0,
  ORBIT_ZOOM,
  PUSH_DRIFT_X,
  PUSH_DRIFT_Y,
  PUSH_ZOOM,
  STATIC_ZOOM,
} from "./constants.ts";
import { assertAllowed } from "./motion.ts";
import type { CropWindow, Focal, FrameAspect, MotionName } from "./types.ts";

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

export function cosineEase(t: number): number {
  const x = clamp(t, 0, 1);
  return (1 - Math.cos(Math.PI * x)) / 2;
}

export function aspectRatio(aspect: FrameAspect): number {
  if (aspect === "9x16") return 9 / 16;
  if (aspect === "1x1") return 1;
  return 16 / 9;
}

/**
 * Operator ease: sine in-out, no cruise, no hold-in.
 * Tiny hold-out so the outgoing pose is parked for the mix.
 */
export function speedRamp(t: number): number {
  const x = clamp(t, 0, 1);
  if (x >= 1 - HOLD_OUT) return 1;
  return cosineEase(x / (1 - HOLD_OUT));
}

/** Normalized velocity of speedRamp. Zero at the cut; walking through the middle. */
export function rampVelocity(t: number): number {
  const x = clamp(t, 0, 1);
  if (x >= 1 - HOLD_OUT) return 0;
  const span = 1 - HOLD_OUT;
  const u = x / span;
  return ((Math.PI / 2) * Math.sin(Math.PI * u)) / span;
}

/** @deprecated use speedRamp — kept as the public name tests already import. */
export function shapedEase(t: number): number {
  return speedRamp(t);
}

/** Largest window of the given aspect (width/height) that fits inside the image. */
export function largestAspect(width: number, height: number, ratio: number): CropWindow {
  const src = width / height;
  let x: number;
  let y: number;
  let w: number;
  let h: number;
  if (src >= ratio) {
    h = height;
    w = h * ratio;
    x = (width - w) / 2;
    y = 0;
  } else {
    w = width;
    h = w / ratio;
    x = 0;
    y = (height - h) / 2;
  }
  return { x, y, w, h };
}

export function largest16x9(width: number, height: number): CropWindow {
  const win = largestAspect(width, height, 16 / 9);
  let { x, y, w, h } = win;
  x = Math.floor(x);
  y = Math.floor(y);
  w = Math.round(w);
  h = Math.round(h);
  w -= w % 2;
  h -= h % 2;
  return { x, y, w, h };
}

export function plateRect(width: number, height: number, focal: Focal = { x: 0.5, y: 0.46 }): CropWindow {
  const base = largest16x9(width, height);
  let { x, y, w, h } = base;
  if (width > w) x = clamp(Math.round(focal.x * (width - w)), 0, width - w);
  if (height > h) y = clamp(Math.round(focal.y * (height - h)), 0, height - h);
  return { x, y, w, h };
}

function motionOffset(
  motion: MotionName,
  e: number,
  sign: number,
): { z0: number; z1: number; ox: number; oy: number } {
  if (motion === "orbit") {
    const theta = (e - 0.5) * 2;
    return {
      z0: ORBIT_Z0,
      z1: ORBIT_ZOOM,
      ox: theta * ORBIT_TRAVEL * sign,
      oy: Math.sin(e * Math.PI) * ORBIT_ARC * sign,
    };
  }
  if (motion === "push_in") {
    return {
      z0: 1,
      z1: PUSH_ZOOM,
      ox: e * PUSH_DRIFT_X * sign,
      oy: e * PUSH_DRIFT_Y * sign,
    };
  }
  if (motion === "pull_out") {
    return {
      z0: PUSH_ZOOM,
      z1: 1,
      ox: (1 - e) * PUSH_DRIFT_X * sign,
      oy: (1 - e) * PUSH_DRIFT_Y * sign,
    };
  }
  if (motion === "ken_burns") {
    return {
      z0: 1,
      z1: KEN_BURNS_ZOOM,
      ox: e * KEN_BURNS_DRIFT_X * sign,
      oy: e * KEN_BURNS_DRIFT_Y * sign,
    };
  }
  return { z0: 1, z1: STATIC_ZOOM, ox: 0, oy: 0 };
}

function travelForRatio(ratio: number): { tx: number; ty: number } {
  if (ratio <= 9 / 16 + 0.02) return { tx: FRAME_TRAVEL_X_9X16, ty: FRAME_TRAVEL_Y_9X16 };
  if (ratio <= 1.05) return { tx: FRAME_TRAVEL_X_1X1, ty: FRAME_TRAVEL_Y_1X1 };
  return { tx: FRAME_TRAVEL_X, ty: FRAME_TRAVEL_Y };
}

function applyWindow(
  z0: number,
  z1: number,
  ox: number,
  oy: number,
  e: number,
  focal: Focal,
  plateW: number,
  plateH: number,
  ratio: number,
): CropWindow {
  const z = z0 + (z1 - z0) * e;
  const base = largestAspect(plateW, plateH, ratio);
  const w = base.w / z;
  const h = base.h / z;
  const maxX = Math.max(0, plateW - w);
  const maxY = Math.max(0, plateH - h);
  const { tx, ty } = travelForRatio(ratio);
  // Home on the focal. Travel is a fraction of the *visible frame* so a
  // landscape still cannot whip-pan a 9:16 slice across the whole facade.
  const homeX = maxX * clamp(focal.x, 0, 1);
  const homeY = maxY * clamp(focal.y, 0, 1);
  const x = clamp(homeX + ox * w * tx, 0, maxX);
  const y = clamp(homeY + oy * h * ty, 0, maxY);
  return { x, y, w, h };
}

/** Crop window on the 4K 16:9 plate at local progress t∈[0,1]. Always in-frame. */
export function cameraWindowAt(
  motion: string,
  t01: number,
  yaw: number = 1,
  focal: Focal = { x: 0.5, y: 0.46 },
): CropWindow {
  const m = assertAllowed(motion);
  const eMove = speedRamp(t01);
  const sign = yaw >= 0 ? 1 : -1;
  const { z0, z1, ox, oy } = motionOffset(m, eMove, sign);
  // Orbit zoom breathes on a slower cosine so truck and dolly don't lock as a 2D slider.
  const eZoom = m === "orbit" ? cosineEase(t01) : eMove;
  return applyWindow(z0, z1, ox, oy, eZoom, focal, KB_PLATE_W, KB_PLATE_H, 16 / 9);
}

/**
 * Full-bleed crop in SOURCE pixels for the output aspect.
 * 9:16 uses a real vertical slice of the still (not a letterboxed 16:9).
 * Extra landscape width becomes leftover for orbit / truck.
 */
export function cameraSourceWindow(
  motion: string,
  t01: number,
  yaw: number,
  focal: Focal,
  imgW: number,
  imgH: number,
  aspect: FrameAspect,
): CropWindow {
  const m = assertAllowed(motion);
  const eMove = speedRamp(t01);
  const sign = yaw >= 0 ? 1 : -1;
  const { z0, z1, ox, oy } = motionOffset(m, eMove, sign);
  const eZoom = m === "orbit" ? cosineEase(t01) : eMove;
  return applyWindow(z0, z1, ox, oy, eZoom, focal, imgW, imgH, aspectRatio(aspect));
}

export function cameraPath(
  motion: string,
  frames: number,
  yaw: number = 1,
  focal: Focal = { x: 0.5, y: 0.46 },
): CropWindow[] {
  const n = Math.max(2, Math.floor(frames));
  const out: CropWindow[] = [];
  for (let i = 0; i < n; i++) {
    out.push(cameraWindowAt(motion, i / (n - 1), yaw, focal));
  }
  return out;
}

/** Map a 16:9 plate window onto source-image pixels. */
export function windowOnImage(win: CropWindow, imgW: number, imgH: number, focal: Focal = { x: 0.5, y: 0.46 }): CropWindow {
  const plate = plateRect(imgW, imgH, focal);
  return {
    x: plate.x + (win.x / KB_PLATE_W) * plate.w,
    y: plate.y + (win.y / KB_PLATE_H) * plate.h,
    w: (win.w / KB_PLATE_W) * plate.w,
    h: (win.h / KB_PLATE_H) * plate.h,
  };
}
