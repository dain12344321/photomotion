import { useEffect, useRef, type RefObject } from "react";
import { Play } from "lucide-react";
import { cameraSourceWindow, cosineEase } from "@/lib/photomotion/camera";
import { XFADE_S } from "@/lib/photomotion/constants";
import type { FrameAspect, PlannedClip, TourPlan } from "@/lib/photomotion/types";
import { cn } from "@/lib/utils";

export type Aspect = FrameAspect;

type Props = {
  plan: TourPlan | null;
  images: Map<string, HTMLImageElement>;
  audioRef: RefObject<HTMLAudioElement | null>;
  canvasRef?: RefObject<HTMLCanvasElement | null>;
  musicStart: number;
  playing: boolean;
  aspect: Aspect;
  address?: string;
  city?: string;
  showAddress?: boolean;
  busy?: boolean;
  progress?: number;
  onTime?: (t: number, clip: PlannedClip | null) => void;
  onEnded?: () => void;
  onToggle?: () => void;
};

function clipAt(plan: TourPlan, t: number): { clip: PlannedClip; local: number } | null {
  if (!plan.clips.length) return null;
  for (const clip of plan.clips) {
    const start = clip.start ?? 0;
    const dur = clip.duration_s ?? 2.5;
    if (t >= start && t < start + dur - 1e-4) {
      return { clip, local: dur > 0 ? (t - start) / dur : 1 };
    }
  }
  const last = plan.clips[plan.clips.length - 1];
  return { clip: last, local: 1 };
}

function drawAddress(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  address: string,
  city: string,
  alpha: number,
) {
  if (alpha <= 0) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  const s = Math.min(w / 720, h / 1280) * (w < h ? 1.15 : 1.6);
  const pad = 28 * s;
  const barW = 22 * s;
  const grad = ctx.createLinearGradient(0, h - 140 * s, 0, h);
  grad.addColorStop(0, "rgba(13,16,19,0)");
  grad.addColorStop(1, "rgba(13,16,19,0.72)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, h - 160 * s, w, 160 * s);
  ctx.fillStyle = "#7aa2c4";
  ctx.fillRect(pad, h - 78 * s, barW, 2 * s);
  ctx.fillStyle = "#efece6";
  ctx.font = `600 ${Math.round(22 * s)}px Montserrat, sans-serif`;
  ctx.fillText(address, pad, h - 48 * s);
  if (city) {
    ctx.fillStyle = "rgba(239,236,230,0.75)";
    ctx.font = `500 ${Math.round(12 * s)}px Montserrat, sans-serif`;
    ctx.fillText(city, pad, h - 28 * s);
  }
  ctx.restore();
}

function drawClip(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  clip: PlannedClip,
  local: number,
  cw: number,
  ch: number,
  aspect: Aspect,
  clear: boolean,
) {
  const src = cameraSourceWindow(
    clip.motion,
    local,
    clip.yaw,
    clip.focal,
    img.naturalWidth,
    img.naturalHeight,
    aspect,
  );
  if (clear) {
    ctx.fillStyle = "#0d1013";
    ctx.fillRect(0, 0, cw, ch);
  }
  ctx.drawImage(img, src.x, src.y, src.w, src.h, 0, 0, cw, ch);
}

export function TourPlayer({
  plan,
  images,
  audioRef,
  canvasRef: canvasRefProp,
  musicStart,
  playing,
  aspect,
  address,
  city,
  showAddress,
  busy,
  progress,
  onTime,
  onEnded,
  onToggle,
}: Props) {
  const localCanvas = useRef<HTMLCanvasElement>(null);
  const canvasRef = canvasRefProp ?? localCanvas;
  const raf = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !plan) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    void document.fonts.load("600 28px Montserrat");
    void document.fonts.load("500 14px Montserrat");

    const sizeFor = () => {
      if (aspect === "9x16") return { w: 540, h: 960 };
      if (aspect === "1x1") return { w: 720, h: 720 };
      return { w: 1280, h: 720 };
    };

    let ended = false;
    const paint = () => {
      const { w, h } = sizeFor();
      if (canvas.width !== w) canvas.width = w;
      if (canvas.height !== h) canvas.height = h;
      const total = plan.total_s ?? 30;
      const audio = audioRef.current;
      const raw = audio ? audio.currentTime : musicStart;
      const t = Math.max(0, raw - musicStart);
      if (playing && t >= total - 0.04) {
        if (!ended) {
          ended = true;
          onEnded?.();
        }
      }
      const hit = clipAt(plan, Math.min(t, total - 0.001));
      ctx.fillStyle = "#0d1013";
      ctx.fillRect(0, 0, w, h);
      if (hit) {
        const img = images.get(hit.clip.filename);
        if (img) {
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = "high";
          const dur = hit.clip.duration_s ?? 2.5;
          const elapsed = hit.local * dur;
          const remaining = dur - elapsed;
          const prev = plan.clips[hit.clip.index - 1];
          const next = plan.clips[hit.clip.index + 1];
          const prevImg = prev ? images.get(prev.filename) : undefined;
          const nextImg = next ? images.get(next.filename) : undefined;
          const prevDur = prev?.duration_s ?? 2.5;
          const xfade = Math.min(XFADE_S, dur * 0.08, (prev ? prevDur : dur) * 0.08);
          const half = xfade / 2;
          const nearStart = Boolean(prev && prevImg && elapsed < half && xfade > 0.02);
          const nearEnd = Boolean(next && nextImg && remaining < half && xfade > 0.02);

          if (nearStart && prev && prevImg) {
            drawClip(ctx, prevImg, prev, 1, w, h, aspect, true);
            ctx.save();
            ctx.globalAlpha = cosineEase((elapsed + half) / xfade);
            drawClip(ctx, img, hit.clip, hit.local, w, h, aspect, false);
            ctx.restore();
          } else {
            drawClip(ctx, img, hit.clip, hit.local, w, h, aspect, true);
            if (nearEnd && next && nextImg) {
              ctx.save();
              ctx.globalAlpha = cosineEase((half - remaining) / xfade);
              drawClip(ctx, nextImg, next, 0, w, h, aspect, false);
              ctx.restore();
            }
          }
        }
        onTime?.(t, hit.clip);
        if (showAddress && address && t < 3.6) {
          const alpha = t < 0.25 ? t / 0.25 : t > 2.9 ? Math.max(0, 1 - (t - 2.9) / 0.7) : 1;
          drawAddress(ctx, w, h, address, city || "", alpha);
        }
      } else {
        onTime?.(t, null);
      }
      raf.current = requestAnimationFrame(paint);
    };
    raf.current = requestAnimationFrame(paint);
    return () => cancelAnimationFrame(raf.current);
  }, [plan, images, audioRef, canvasRef, musicStart, playing, aspect, address, city, showAddress, onTime, onEnded]);

  return (
    <div
      className={cn(
        "relative min-w-0 overflow-hidden rounded-[var(--radius-lg)] bg-ink shadow-[var(--shadow-md)]",
        aspect === "9x16" && "mx-auto w-full max-w-[22rem]",
        aspect === "1x1" && "mx-auto max-w-[520px]",
      )}
    >
      <canvas
        ref={canvasRef}
        className="block h-auto w-full max-w-full cursor-pointer bg-ink"
        style={{ aspectRatio: aspect === "9x16" ? "9 / 16" : aspect === "1x1" ? "1 / 1" : "16 / 9" }}
        onClick={onToggle}
      />
      <div
        className={cn(
          "pointer-events-none absolute inset-0 grid place-items-center transition-[opacity] duration-[var(--motion-fast)] ease-[var(--ease-out)]",
          playing || busy || !plan ? "opacity-0" : "opacity-100",
        )}
      >
        <span className="play-orb">
          <Play className="size-6" strokeWidth={2} fill="currentColor" />
        </span>
      </div>
      {typeof progress === "number" ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 bg-ink/40">
          <div
            className="h-full bg-lake"
            style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }}
          />
        </div>
      ) : null}
      {busy ? (
        <div className="absolute inset-0 grid place-items-center bg-ink/70">
          <p className="text-sm font-medium text-muted">Planning tour…</p>
        </div>
      ) : null}
    </div>
  );
}
