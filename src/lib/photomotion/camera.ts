import {
  HOLD_IN,
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
  PUSH_ZOOM,
  RAMP_ACCEL,
  RAMP_DECEL,
  STATIC_ZOOM,
} from "./constants.ts";
import { assertAllowed } from "./motion.ts";
import type { CropWindow, Focal, MotionName } from "./types.ts";

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

export function cosineEase(t: number): number {
  const x = clamp(t, 0, 1);
  return (1 - Math.cos(Math.PI * x)) / 2;
}

function rampPeak(): number {
  const cruise = 1 - RAMP_ACCEL - RAMP_DECEL;
  return 1 / (RAMP_ACCEL / 2 + cruise + RAMP_DECEL / 2);
}

/**
 * Trapezoidal speed ramp: hold, accel, cruise, decel, hold.
 * Velocity is 0 at both ends of the clip. Same math as the Python engine.
 */
export function speedRamp(t: number): number {
  const x = clamp(t, 0, 1);
  if (x <= HOLD_IN) return 0;
  if (x >= 1 - HOLD_OUT) return 1;
  const span = 1 - HOLD_IN - HOLD_OUT;
  const u = (x - HOLD_IN) / span;
  const a = RAMP_ACCEL;
  const d = RAMP_DECEL;
  const c = 1 - a - d;
  const vPeak = rampPeak();
  if (u <= a) return vPeak * ((u * u) / (2 * a));
  if (u <= a + c) return vPeak * (a / 2 + (u - a));
  const s = u - a - c;
  return vPeak * (a / 2 + c + s - (s * s) / (2 * d));
}

/** Normalized velocity of speedRamp. Zero during holds and at both ends of the move. */
export function rampVelocity(t: number): number {
  const x = clamp(t, 0, 1);
  if (x <= HOLD_IN || x >= 1 - HOLD_OUT) return 0;
  const span = 1 - HOLD_IN - HOLD_OUT;
  const u = (x - HOLD_IN) / span;
  const a = RAMP_ACCEL;
  const d = RAMP_DECEL;
  const c = 1 - a - d;
  const vPeak = rampPeak();
  let dPdu: number;
  if (u <= a) dPdu = (vPeak * u) / a;
  else if (u <= a + c) dPdu = vPeak;
  else {
    const s = u - a - c;
    dPdu = vPeak * (1 - s / d);
  }
  return dPdu / span;
}

/** @deprecated use speedRamp — kept as the public name tests already import. */
export function shapedEase(t: number): number {
  return speedRamp(t);
}

export function largest16x9(width: number, height: number): CropWindow {
  const target = 16 / 9;
  const src = width / height;
  let x: number;
  let y: number;
  let w: number;
  let h: number;
  if (src >= target) {
    h = height;
    w = Math.round(h * target);
    x = Math.floor((width - w) / 2);
    y = 0;
  } else {
    w = width;
    h = Math.round(w / target);
    x = 0;
    y = Math.floor((height - h) / 2);
  }
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
  if (motion === "push_in") return { z0: 1, z1: PUSH_ZOOM, ox: 0, oy: 0 };
  if (motion === "pull_out") return { z0: PUSH_ZOOM, z1: 1, ox: 0, oy: 0 };
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

/** Crop window on the 4K plate at local progress t∈[0,1]. Always in-frame. */
export function cameraWindowAt(
  motion: string,
  t01: number,
  yaw: number = 1,
  focal: Focal = { x: 0.5, y: 0.46 },
): CropWindow {
  const m = assertAllowed(motion);
  const e = speedRamp(t01);
  const sign = yaw >= 0 ? 1 : -1;
  const { z0, z1, ox, oy } = motionOffset(m, e, sign);
  const z = z0 + (z1 - z0) * e;
  const w = KB_PLATE_W / z;
  const h = KB_PLATE_H / z;
  const maxX = KB_PLATE_W - w;
  const maxY = KB_PLATE_H - h;
  // leftover * (focal + offset/2). Offsets are sized so a focal in [0.28, 0.72] never clamps.
  let x = maxX * (focal.x + ox * 0.5);
  let y = maxY * (focal.y + oy * 0.5);
  x = clamp(x, 0, Math.max(0, maxX));
  y = clamp(y, 0, Math.max(0, maxY));
  if (x + w > KB_PLATE_W) x = KB_PLATE_W - w;
  if (y + h > KB_PLATE_H) y = KB_PLATE_H - h;
  return { x, y, w, h };
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

/** Map a plate window onto source-image pixels (the 16:9 plate inside the still). */
export function windowOnImage(win: CropWindow, imgW: number, imgH: number, focal: Focal = { x: 0.5, y: 0.46 }): CropWindow {
  const plate = plateRect(imgW, imgH, focal);
  return {
    x: plate.x + (win.x / KB_PLATE_W) * plate.w,
    y: plate.y + (win.y / KB_PLATE_H) * plate.h,
    w: (win.w / KB_PLATE_W) * plate.w,
    h: (win.h / KB_PLATE_H) * plate.h,
  };
}
