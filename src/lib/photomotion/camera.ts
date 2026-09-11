import {
  HOLD_IN,
  HOLD_OUT,
  KB_PLATE_H,
  KB_PLATE_W,
  ORBIT_TRAVEL,
  ORBIT_Z0,
  ORBIT_ZOOM,
  PUSH_ZOOM,
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

/** Hold the still, then cosine-ease, then hold the landing. */
export function shapedEase(t: number): number {
  const x = clamp(t, 0, 1);
  if (x <= HOLD_IN) return 0;
  if (x >= 1 - HOLD_OUT) return 1;
  const span = 1 - HOLD_IN - HOLD_OUT;
  return cosineEase((x - HOLD_IN) / span);
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

function motionProfile(motion: MotionName): { z0: number; z1: number; travel: number } {
  if (motion === "orbit") return { z0: ORBIT_Z0, z1: ORBIT_ZOOM, travel: ORBIT_TRAVEL };
  if (motion === "push_in") return { z0: 1, z1: PUSH_ZOOM, travel: 0 };
  return { z0: 1, z1: STATIC_ZOOM, travel: 0 };
}

/** Crop window on the 4K plate at local progress t∈[0,1]. Always in-frame. */
export function cameraWindowAt(
  motion: string,
  t01: number,
  yaw: number = 1,
  focal: Focal = { x: 0.5, y: 0.46 },
): CropWindow {
  const m = assertAllowed(motion);
  const { z0, z1, travel } = motionProfile(m);
  const e = shapedEase(t01);
  const sign = yaw >= 0 ? 1 : -1;
  const z = z0 + (z1 - z0) * e;
  const w = KB_PLATE_W / z;
  const h = KB_PLATE_H / z;
  const maxX = KB_PLATE_W - w;
  const maxY = KB_PLATE_H - h;
  const ox = (e - 0.5) * 2 * travel * sign;
  const oy = Math.sin(e * Math.PI) * travel * 0.14 * sign;
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
