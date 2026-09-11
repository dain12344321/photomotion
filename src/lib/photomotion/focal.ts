import { defaultFocal } from "./motion.ts";
import type { Focal } from "./types.ts";

/**
 * Center-weighted luma peak, skipping blown-out windows.
 * Operates on a packed Float32 luma buffer so it runs offline in Node and the browser.
 */
export function focalFromLuma(luma: Float32Array, w: number, h: number, room: string): Focal {
  const fallback = defaultFocal(room);
  if (w < 8 || h < 8 || luma.length < w * h) return fallback;
  let best = -1;
  let bx = fallback.x;
  let by = fallback.y;
  const cx = 0.5;
  const cy = fallback.y;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const v = luma[y * w + x];
      if (v > 0.92) continue;
      const nx = x / (w - 1);
      const ny = y / (h - 1);
      const dx = nx - cx;
      const dy = ny - cy;
      const weight = Math.exp(-(dx * dx * 3.2 + dy * dy * 4.0));
      const local =
        Math.abs(v - luma[y * w + x - 1]) +
        Math.abs(v - luma[y * w + x + 1]) +
        Math.abs(v - luma[(y - 1) * w + x]);
      const score = (0.35 + v * 0.65) * weight * (0.4 + local);
      if (score > best) {
        best = score;
        bx = nx;
        by = ny;
      }
    }
  }
  return {
    x: clamp(bx * 0.55 + fallback.x * 0.45, 0.28, 0.72),
    y: clamp(by * 0.45 + fallback.y * 0.55, 0.32, 0.62),
  };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

export function lumaFromImageData(data: Uint8ClampedArray, w: number, h: number): Float32Array {
  const luma = new Float32Array(w * h);
  for (let i = 0, p = 0; i < luma.length; i++, p += 4) {
    luma[i] = (0.2126 * data[p] + 0.7152 * data[p + 1] + 0.0722 * data[p + 2]) / 255;
  }
  return luma;
}
