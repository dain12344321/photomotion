import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Pause, Play, Square, Upload } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { TourPlayer, type Aspect } from "@/components/tour-player";
import { Button } from "@/components/ui/button";
import { detectTrackBeats, loadImage } from "@/lib/photomotion/audio";
import { classifiedFromFiles, classifiedFromListing, assembleTour } from "@/lib/photomotion/tour";
import { DEMOS } from "@/lib/photomotion/listings";
import { catalog, resolveTrack } from "@/lib/photomotion/music";
import { downloadBlob, recordCanvasWebm } from "@/lib/photomotion/export-webm";
import type { BuiltTour } from "@/lib/photomotion/tour";
import type { PlannedClip } from "@/lib/photomotion/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({ component: Desk });

function Desk() {
  const [listingId, setListingId] = useState("wanatah");
  const [tour, setTour] = useState<BuiltTour | null>(null);
  const [images, setImages] = useState<Map<string, HTMLImageElement>>(new Map());
  const [musicId, setMusicId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [active, setActive] = useState<PlannedClip | null>(null);
  const [aspect, setAspect] = useState<Aspect>("16x9");
  const [address, setAddress] = useState("405 N Main St");
  const [city, setCity] = useState("Wanatah, IN 46390");
  const [showAddress, setShowAddress] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [exporting, setExporting] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const onTime = useCallback((t: number, clip: PlannedClip | null) => {
    setTime(t);
    setActive(clip);
  }, []);

  const beds = catalog();

  async function buildFromListing(id: string, forcedMusic?: string) {
    const listing = DEMOS.find((d) => d.id === id);
    if (!listing) return;
    setBusy(true);
    try {
      const classified = classifiedFromListing(listing);
      const draft = assembleTour(classified, { musicId: forcedMusic ?? musicId ?? undefined });
      const beats = await detectTrackBeats(draft.track);
      const built = assembleTour(classified, { musicId: draft.track.id, beats });
      const next = new Map<string, HTMLImageElement>();
      await Promise.all(
        built.plan.clips.map(async (c) => {
          if (!c.src) return;
          next.set(c.filename, await loadImage(c.src));
        }),
      );
      setImages(next);
      setTour(built);
      setMusicId(built.track.id);
      setListingId(id);
      setAddress(listing.address);
      setCity(listing.city);
      setPlaying(false);
      setTime(0);
      if (audioRef.current) {
        audioRef.current.src = built.track.preview;
        audioRef.current.currentTime = built.beats.phase;
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not load listing");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void buildFromListing("wanatah");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      }
      if (e.code === "Escape") stopPlay();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, tour]);

  async function handleFiles(list: FileList | File[]) {
    const files = Array.from(list).filter((f) => /\.(jpe?g|png|webp|tif{1,2})$/i.test(f.name));
    if (files.length < 5) {
      toast.error("Need at least 5 listing stills.");
      return;
    }
    setBusy(true);
    try {
      const payload = files.map((f) => ({ name: f.name, src: URL.createObjectURL(f) }));
      const classified = classifiedFromFiles(payload);
      const draft = assembleTour(classified, { musicId: musicId ?? undefined });
      const beats = await detectTrackBeats(draft.track);
      const built = assembleTour(classified, { musicId: draft.track.id, beats });
      const next = new Map<string, HTMLImageElement>();
      await Promise.all(
        built.plan.clips.map(async (c) => {
          const src = payload.find((p) => p.name === c.filename)?.src;
          if (!src) return;
          next.set(c.filename, await loadImage(src));
        }),
      );
      setImages(next);
      setTour(built);
      setMusicId(built.track.id);
      setListingId("drop");
      setPlaying(false);
      toast.success(`${built.plan.clip_count}-clip tour planned`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Drop failed");
    } finally {
      setBusy(false);
    }
  }

  async function changeMusic(id: string) {
    if (!tour) return;
    setBusy(true);
    try {
      const track = resolveTrack(id);
      const beats = await detectTrackBeats(track);
      const built = assembleTour(tour.classified, { musicId: track.id, beats });
      setTour(built);
      setMusicId(track.id);
      if (audioRef.current) {
        audioRef.current.src = track.preview;
        audioRef.current.currentTime = beats.phase;
      }
    } finally {
      setBusy(false);
    }
  }

  function togglePlay() {
    const el = audioRef.current;
    if (!el || !tour) return;
    if (playing) {
      el.pause();
      setPlaying(false);
      return;
    }
    if (el.currentTime < tour.beats.phase) el.currentTime = tour.beats.phase;
    void el.play();
    setPlaying(true);
  }

  function stopPlay() {
    const el = audioRef.current;
    if (el && tour) {
      el.pause();
      el.currentTime = tour.beats.phase;
    }
    setPlaying(false);
    setTime(0);
  }

  function seekTo(clip: PlannedClip) {
    const el = audioRef.current;
    if (!el || !tour) return;
    const t = clip.music_time ?? (clip.start ?? 0) + tour.beats.phase;
    el.currentTime = t;
    setTime(clip.start ?? 0);
    setActive(clip);
  }

  async function exportWebm() {
    if (!tour) return;
    const canvas = canvasRef.current;
    const audio = audioRef.current;
    if (!canvas || !audio) {
      toast.error("Player is not ready.");
      return;
    }
    setExporting(true);
    try {
      audio.currentTime = tour.beats.phase;
      await audio.play();
      setPlaying(true);
      const blob = await recordCanvasWebm(canvas, audio, tour.plan.total_s ?? 30);
      audio.pause();
      setPlaying(false);
      downloadBlob(blob, `${listingId}-photomotion-16x9.webm`);
      toast.success("WebM downloaded. Desktop CLI writes 1080p MP4.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  const progress = tour?.plan.total_s ? Math.min(1, time / tour.plan.total_s) : 0;
  const musicStart = tour?.beats.phase ?? 0.4;
  const thumbs = useMemo(() => tour?.plan.clips ?? [], [tour]);
  const skipped = useMemo(() => (tour?.classified ?? []).filter((c) => c.skip), [tour]);

  return (
    <AppShell current="work">
      <main className="mx-auto w-full min-w-0 max-w-[88rem] overflow-x-hidden px-4 py-6 sm:px-6 sm:py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label-kicker">Listing tour</p>
            <h1 className="mt-1 font-display text-3xl tracking-tight sm:text-4xl">
              {address || "New tour"}
            </h1>
            <p className="mt-1 text-sm text-muted">{city}</p>
          </div>
          <p className="font-mono text-xs tabular-nums text-subtle">
            {tour ? `${tour.plan.total_s?.toFixed(1)}s` : "—"} ·{" "}
            {tour ? `${tour.beats.bpm} BPM` : "detecting"} · {tour?.plan.clip_count ?? "—"} clips
          </p>
        </div>

        <div className="mt-6 grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.75fr)]">
          <section className="min-w-0">
            <TourPlayer
              plan={tour?.plan ?? null}
              images={images}
              audioRef={audioRef}
              canvasRef={canvasRef}
              musicStart={musicStart}
              playing={playing}
              aspect={aspect}
              address={address}
              city={city}
              showAddress={showAddress}
              busy={busy && !tour}
              onTime={onTime}
              onEnded={stopPlay}
              onToggle={togglePlay}
              progress={progress}
            />
            <div className="mt-4 flex min-w-0 flex-wrap items-center gap-2">
              <Button type="button" size="sm" onClick={togglePlay} disabled={!tour || busy}>
                {playing ? <Pause className="size-4" /> : <Play className="size-4 ml-px" />}
                {playing ? "Pause" : "Play tour"}
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={stopPlay} disabled={!tour}>
                <Square className="size-3.5" />
                Stop
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => void exportWebm()}
                disabled={!tour || exporting}
              >
                {exporting ? "Recording…" : "Download WebM"}
              </Button>
              <div className="segmented w-full min-w-0 sm:ml-auto sm:w-auto">
                {(["16x9", "9x16", "1x1"] as const).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setAspect(key)}
                    className={cn(
                      "min-h-9 rounded-full px-4 text-xs font-semibold uppercase tracking-wider",
                      aspect === key
                        ? "bg-accent text-accent-fg"
                        : "text-muted hover:text-fg",
                    )}
                  >
                    {key === "16x9" ? "16:9" : key === "9x16" ? "9:16" : "1:1"}
                  </button>
                ))}
              </div>
            </div>
            <p className="mt-3 text-xs text-subtle">
              {active
                ? `${active.label} · ${active.motion.replace("_", " ")} · ${active.beats ?? 0} beats`
                : "Walking camera. Mix on the downbeat. Space to play."}
            </p>
          </section>

          <aside className="min-w-0 space-y-4">
            <section className="panel">
              <p className="label-kicker">Property</p>
              <div className="mt-3 grid gap-2">
                {DEMOS.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => void buildFromListing(d.id)}
                    className={cn("choice", listingId === d.id && "choice-on")}
                  >
                    <span className="block text-sm font-semibold text-fg">{d.address}</span>
                    <span className="block text-xs text-subtle">{d.city}</span>
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  if (e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files);
                }}
                className={cn(
                  "mt-3 flex min-h-24 w-full flex-col items-center justify-center rounded-[var(--radius-md)] border border-dashed px-3 text-center text-sm font-medium",
                  dragOver ? "border-lake bg-brand-subtle text-fg" : "border-border text-muted",
                )}
              >
                <Upload className="mb-2 size-4 text-lake" strokeWidth={1.5} />
                Drop stills · 5+ JPEGs
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) void handleFiles(e.target.files);
                }}
              />
              <div className="mt-3 grid gap-2">
                <label className="block">
                  <span className="text-xs text-muted">Address</span>
                  <input className="field mt-1" value={address} onChange={(e) => setAddress(e.target.value)} />
                </label>
                <label className="block">
                  <span className="text-xs text-muted">City</span>
                  <input className="field mt-1" value={city} onChange={(e) => setCity(e.target.value)} />
                </label>
                <label className="flex min-h-11 items-center gap-2 text-sm text-muted">
                  <input
                    type="checkbox"
                    checked={showAddress}
                    onChange={(e) => setShowAddress(e.target.checked)}
                  />
                  Address card on the open
                </label>
              </div>
            </section>

            <section className="panel">
              <p className="label-kicker">Music bed</p>
              <ul className="mt-3 space-y-1">
                {beds.map((b) => (
                  <li key={b.id}>
                    <button
                      type="button"
                      onClick={() => void changeMusic(b.id)}
                      className={cn(
                        "w-full rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm transition-[background-color,color] duration-[var(--motion-quick)] ease-[var(--ease-out)]",
                        musicId === b.id ? "bg-elevated text-fg" : "text-muted hover:text-fg",
                      )}
                    >
                      <span className="block font-medium">{b.title}</span>
                      <span className="block font-mono text-2xs text-subtle">
                        {b.mood} · {b.bpm} BPM
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </div>

        <section className="mt-8">
          <p className="label-kicker">Cut list</p>
          <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {thumbs.map((c) => {
              const img = images.get(c.filename);
              const on = active?.index === c.index;
              return (
                <li key={c.index}>
                  <button
                    type="button"
                    onClick={() => seekTo(c)}
                    className={cn(
                      "w-full overflow-hidden rounded-[var(--radius-md)] text-left shadow-[var(--shadow-border)] transition-[box-shadow] duration-[var(--motion-quick)] ease-[var(--ease-out)]",
                      on ? "film-on" : "hover:shadow-[var(--shadow-border-hover)]",
                    )}
                  >
                    <div className="relative">
                      {img ? (
                        <img src={img.src} alt="" className="aspect-video w-full object-cover" />
                      ) : (
                        <div className="aspect-video bg-elevated" />
                      )}
                      <span className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/85 to-transparent px-2 pb-1.5 pt-6">
                        <span className="block truncate text-2xs font-semibold uppercase tracking-wider text-fg">
                          {c.motion.replace("_", " ")}
                        </span>
                      </span>
                    </div>
                    <div className="px-2 py-1.5">
                      <p className="truncate text-xs font-medium text-fg">{c.label}</p>
                      <p className="font-mono text-2xs uppercase tracking-wider text-subtle">
                        {c.beats}b
                      </p>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
          {skipped.length ? (
            <p className="mt-4 text-xs text-subtle">
              Held static / skipped: {skipped.map((s) => s.label || s.filename).join(" · ")}
            </p>
          ) : null}
        </section>
      </main>
      <audio ref={audioRef} preload="auto" className="hidden" />
    </AppShell>
  );
}
