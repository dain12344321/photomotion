"""Job folder schema + runner: ingest → plan → render → QC → assemble."""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from photomotion.assemble import assemble, trim_or_pad
from photomotion.beats import detect_bpm_and_beats, snap_clip_durations
from photomotion.classify import classify_items, load_override
from photomotion.constants import DEFAULT_SPEND_CAP, I2V_DURATION_S, I2V_LOCK, TARGET_SECONDS
from photomotion.ingest import ingest, originals_untouched
from photomotion.i2v import generate_or_fallback
from photomotion.kenburns import render_clip
from photomotion.motion import assign_motion, default_focal, orbit_yaw
from photomotion.music import music_file, pick_track, resolve_track
from photomotion.plan import plan_tour
from photomotion.qc import qc_i2v_against_still
from photomotion.spend import clamp_cap, estimate_job_usd


ROOT = Path(__file__).resolve().parents[2]


def ffmpeg_status() -> dict:
    path = shutil.which("ffmpeg")
    if not path:
        return {"ok": False, "path": None, "version": None}
    try:
        proc = subprocess.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        first = (proc.stdout or proc.stderr or "").splitlines()
        version = first[0][:160] if first else None
        return {"ok": proc.returncode == 0, "path": path, "version": version}
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return {"ok": False, "path": path, "version": None}


def doctor() -> dict:
    from photomotion.auth import status as auth_status

    numpy_ok = True
    pillow_ok = True
    try:
        import numpy  # noqa: F401
    except ImportError:
        numpy_ok = False
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pillow_ok = False
    ff = ffmpeg_status()
    auth = auth_status()
    return {
        "ok": bool(ff.get("ok") and numpy_ok and pillow_ok),
        "ffmpeg": ff,
        "numpy": numpy_ok,
        "pillow": pillow_ok,
        "auth": auth,
        "note": "Ken Burns MP4s need ffmpeg + numpy + pillow. Imagine needs an xAI key from console.x.ai (X login).",
    }


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def update_job(job_dir: Path, **patch) -> dict:
    path = job_dir / "job.json"
    data = read_json(path) if path.exists() else {}
    data.update(patch)
    data["updated_at"] = utcnow()
    write_json(path, data)
    return data


def _clip_focal(clip: dict) -> tuple[float, float]:
    f = clip.get("focal")
    if isinstance(f, dict):
        return float(f.get("x", 0.5)), float(f.get("y", 0.46))
    if isinstance(f, (list, tuple)) and len(f) >= 2:
        return float(f[0]), float(f[1])
    return default_focal(str(clip.get("room") or ""))


def _clip_yaw(clip: dict) -> int:
    y = clip.get("yaw")
    if y is None:
        return orbit_yaw(int(clip.get("index") or 0))
    return 1 if int(y) >= 0 else -1


def music_path(track_id: str | None = None) -> Path:
    return music_file(track_id)


def select_hero_indexes(clips: list[dict], n: int) -> list[int]:
    """Push-ins only. Orbits and baths never go to I2V."""
    if n <= 0:
        return []
    picked: list[int] = []

    def eligible(clip: dict) -> bool:
        return clip.get("motion") == "push_in"

    def take_one(pred) -> None:
        if len(picked) >= n:
            return
        for clip in clips:
            if clip["index"] in picked:
                continue
            if not eligible(clip):
                continue
            if pred(clip):
                picked.append(clip["index"])
                return

    take_one(lambda c: c.get("role") == "hero_open" or c.get("room") == "exterior_front")
    take_one(lambda c: c.get("role") == "hero_interior" or c.get("room") == "living")
    take_one(lambda c: c.get("room") in {"kitchen", "dining"})
    take_one(lambda c: c.get("room") in {"drone", "backyard", "exterior_deck"})
    for clip in clips:
        if len(picked) >= n:
            break
        if clip["index"] in picked:
            continue
        if not eligible(clip):
            continue
        picked.append(clip["index"])
    return picked[:n]


def i2v_prompt(clip: dict) -> str:
    room = clip.get("label") or clip.get("room") or "listing still"
    return f"{I2V_LOCK} Subject: {room}."


def run_job(
    *,
    input_path: Path,
    job_dir: Path,
    address: str | None = None,
    city: str | None = None,
    dry_run: bool = True,
    confirm_live: bool = False,
    spend_cap: float = DEFAULT_SPEND_CAP,
    i2v_heroes: int = 0,
    plan_only: bool = False,
    workers: int = 4,
    music_id: str | None = None,
    show_address: bool = False,
) -> dict:
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "CLIPS").mkdir(exist_ok=True)
    (job_dir / "QC").mkdir(exist_ok=True)
    (job_dir / "SIDECARS").mkdir(exist_ok=True)
    (job_dir / "DELIVER").mkdir(exist_ok=True)

    spend_cap = clamp_cap(spend_cap)
    track = pick_track(None, music_id)
    job = {
        "id": job_dir.name,
        "status": "ingest",
        "stage": "ingest",
        "progress": 5,
        "dry_run": dry_run,
        "confirm_live": confirm_live,
        "spend_cap_usd": spend_cap,
        "spend_usd": 0.0,
        "address": address,
        "city": city,
        "i2v_heroes": i2v_heroes if not dry_run else 0,
        "music_id": track["id"],
        "show_address": bool(show_address),
        "created_at": utcnow(),
        "error": None,
    }
    write_json(job_dir / "job.json", job)

    if not plan_only:
        ff = ffmpeg_status()
        if not ff.get("ok"):
            update_job(
                job_dir,
                status="error",
                stage="ffmpeg",
                error="ffmpeg is not on PATH — install it, then retry. Ken Burns still plans with --plan-only.",
            )
            raise RuntimeError("ffmpeg is not on PATH")

    hashes = ingest(Path(input_path), job_dir)
    update_job(job_dir, stage="classify", progress=15, source_count=hashes["count"])

    override = load_override(Path(input_path) / "tour.override.json")
    filenames = [it["filename"] for it in hashes["items"]]
    classified = classify_items(filenames, override)
    write_json(job_dir / "classified.json", {"items": classified})

    plan = plan_tour(classified)
    if not music_id:
        track = pick_track(plan["clips"], None)
    by_name = {it["filename"]: it for it in hashes["items"]}
    for clip in plan["clips"]:
        rec = by_name[clip["filename"]]
        clip["source_path"] = rec["source_path"]
        clip["sha256"] = rec["sha256"]
        clip["proxy_path"] = str(job_dir / "PROXIES" / clip["filename"])

    music = music_path(track["id"])
    beats = (
        detect_bpm_and_beats(music, bpm=track.get("bpm"), intro_s=float(track.get("intro_s") or 0.4))
        if music.exists() and not plan_only
        else {
            "bpm": float(track.get("bpm") or 82.0),
            "beat_interval": 60.0 / float(track.get("bpm") or 82.0),
            "phase": float(track.get("intro_s") or 0.4),
            "beats": [],
            "duration": 180.0,
        }
    )
    snaps = snap_clip_durations(plan["clips"], beats, target_total=TARGET_SECONDS)
    for clip, snap in zip(plan["clips"], snaps):
        clip["duration_s"] = snap["duration_s"]
        clip["music_time"] = snap["music_time"]
        clip["start"] = snap["start"]
        clip["beats"] = snap["beats"]
    plan["beats"] = {"bpm": beats["bpm"], "phase": beats["phase"], "interval": beats["beat_interval"]}
    plan["total_s"] = round(sum(c["duration_s"] for c in plan["clips"]), 3)
    plan["music"] = str(music)
    plan["music_id"] = track["id"]
    plan["music_title"] = track["title"]
    write_json(job_dir / "plan.json", plan)
    write_json(job_dir / "DELIVER" / "plan.json", plan)
    update_job(job_dir, stage="plan", progress=25, status="planned", plan=plan)

    if plan_only:
        update_job(job_dir, status="planned", stage="plan", progress=100)
        return read_json(job_dir / "job.json")

    hero_idxs: list[int] = []
    if i2v_heroes > 0 and not dry_run and confirm_live:
        hero_idxs = select_hero_indexes(plan["clips"], i2v_heroes)
        est = estimate_job_usd(len(hero_idxs), I2V_DURATION_S)
        update_job(job_dir, estimated_i2v_usd=est, i2v_clip_indexes=hero_idxs)

    from photomotion.auth import resolve_api_key

    api_key = resolve_api_key() if not dry_run else None
    spent = 0.0
    total = max(1, len(plan["clips"]))
    rendered: list[dict | None] = [None] * len(plan["clips"])
    done_n = 0

    def mark_done(clip_out: dict) -> None:
        nonlocal done_n
        rendered[clip_out["index"]] = clip_out
        done_n += 1
        update_job(
            job_dir,
            progress=30 + int(50 * done_n / total),
            stage="render",
            clips=[c for c in rendered if c],
            spend_usd=round(spent, 4),
        )

    def render_kb(clip: dict) -> dict:
        motion = clip["motion"]
        out = job_dir / "CLIPS" / f"{clip['index']:02d}_{motion}.mp4"
        still = Path(clip["source_path"])
        render_clip(
            still,
            out,
            motion,
            float(clip["duration_s"]),
            focal=_clip_focal(clip),
            yaw=_clip_yaw(clip),
        )
        clip_out = dict(clip)
        clip_out["lane"] = "kenburns"
        clip_out["clip_path"] = str(out)
        clip_out["status"] = "rendered"
        return clip_out

    def render_i2v(clip: dict) -> dict:
        nonlocal spent
        out = job_dir / "CLIPS" / f"{clip['index']:02d}_{clip['motion']}.mp4"
        still = Path(clip["source_path"])
        duration = float(clip["duration_s"])

        def kb(_dest=out, _motion=clip["motion"], _clip=clip):
            render_clip(
                still,
                _dest,
                _motion,
                duration,
                focal=_clip_focal(_clip),
                yaw=_clip_yaw(_clip),
            )

        sidecar = job_dir / "SIDECARS" / f"{clip['index']:02d}.json"
        result = generate_or_fallback(
            still_hash=clip["sha256"],
            proxy=Path(clip["proxy_path"]),
            dest=out,
            sidecar_path=sidecar,
            prompt=i2v_prompt(clip),
            dry_run=dry_run,
            confirm_live=confirm_live,
            spend_cap=spend_cap,
            already_spent=spent,
            api_key=api_key,
            kenburns_fn=kb,
            output_duration_s=duration,
        )
        clip_out = dict(clip)
        if result.fallback:
            clip_out["lane"] = "kenburns_fallback"
            clip_out["i2v_reason"] = result.reason
        else:
            clip_out["lane"] = "i2v"
            qc = qc_i2v_against_still(still, out, job_dir / "QC")
            clip_out["qc"] = qc
            if not qc["pass"]:
                kb(out)
                clip_out["lane"] = "kenburns_fallback"
                clip_out["i2v_reason"] = "qc_failed"
            else:
                spent += float(result.sidecar.get("estimated_usd") or 0)
        clip_out["sidecar"] = str(sidecar)
        clip_out["clip_path"] = str(out)
        clip_out["status"] = "rendered"
        return clip_out

    update_job(job_dir, stage="render", status="rendering", progress=30)
    kb_clips = [c for c in plan["clips"] if c["index"] not in hero_idxs]
    i2v_clips = [
        c for c in plan["clips"] if c["index"] in hero_idxs and c.get("motion") == "push_in"
    ]

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {pool.submit(render_kb, c): c["index"] for c in kb_clips}
        for fut in as_completed(futs):
            mark_done(fut.result())

    for clip in i2v_clips:
        mark_done(render_i2v(clip))

    rendered_sorted = [c for c in rendered if c]
    cut_list = {
        "clips": rendered_sorted,
        "total_s": round(sum(c["duration_s"] for c in rendered_sorted), 3),
        "music_start": rendered_sorted[0]["music_time"] if rendered_sorted else 0,
    }
    write_json(job_dir / "cut_list.json", cut_list)
    write_json(job_dir / "DELIVER" / "cut_list.json", cut_list)

    update_job(job_dir, stage="assemble", status="assembling", progress=80, clips=rendered_sorted)
    clip_paths = [Path(c["clip_path"]) for c in rendered_sorted]
    deliver = assemble(
        clip_paths,
        music,
        job_dir / "DELIVER",
        address=address,
        city=city,
        music_start=cut_list["music_start"],
        duration_s=cut_list["total_s"],
        show_address=bool(show_address),
    )

    dirty = originals_untouched(hashes)
    public_dir = ROOT / "public" / "jobs" / job_dir.name
    public_dir.mkdir(parents=True, exist_ok=True)
    for key, src in deliver.items():
        shutil.copy2(src, public_dir / Path(src).name)

    job = update_job(
        job_dir,
        stage="done",
        status="done",
        progress=100,
        deliverables=deliver,
        spend_usd=round(spent, 4),
        originals_dirty=dirty,
        public_base=f"/jobs/{job_dir.name}",
        music_id=track["id"],
        show_address=bool(show_address),
    )
    return job


def restabilize_job(job_dir: Path) -> dict:
    """Rebuild every clip as in-frame Ken Burns. No new I2V spend."""
    job_dir = Path(job_dir)
    job = read_json(job_dir / "job.json")
    update_job(job_dir, status="assembling", stage="stabilize", progress=70)
    plan = read_json(job_dir / "plan.json")
    cut = read_json(job_dir / "cut_list.json")
    clips = cut.get("clips") or plan.get("clips") or []
    rebuilt: list[dict] = []
    originals = job_dir / "CLIPS"
    prev = None
    for clip in clips:
        clip = dict(clip)
        idx = int(clip["index"])
        motion = assign_motion(clip.get("room") or "", idx, role=clip.get("role"), prev=prev)
        prev = motion
        clip["motion"] = motion
        still = Path(clip["source_path"])
        duration = float(clip["duration_s"])
        dest = originals / f"{idx:02d}_{motion}.mp4"
        render_clip(still, dest, motion, duration, focal=_clip_focal(clip), yaw=_clip_yaw(clip))
        clip["lane"] = "kenburns"
        clip["clip_path"] = str(dest)
        clip["i2v_reason"] = "locked_to_still"
        clip.pop("qc", None)
        clip["status"] = "rendered"
        rebuilt.append(clip)

    total_s = round(sum(float(c["duration_s"]) for c in rebuilt), 3)
    cut_list = {
        "clips": rebuilt,
        "total_s": total_s,
        "music_start": rebuilt[0].get("music_time", 0) if rebuilt else 0,
        "music_id": job.get("music_id") or plan.get("music_id"),
    }
    write_json(job_dir / "cut_list.json", cut_list)
    write_json(job_dir / "DELIVER" / "cut_list.json", cut_list)
    if plan.get("clips"):
        for old, new in zip(plan["clips"], rebuilt):
            old["motion"] = new["motion"]
            old["lane"] = "kenburns"
        write_json(job_dir / "plan.json", plan)
    music = music_path(str(cut_list.get("music_id") or "easy-lemon"))
    deliver = assemble(
        [Path(c["clip_path"]) for c in rebuilt],
        music,
        job_dir / "DELIVER",
        address=job.get("address"),
        city=job.get("city"),
        music_start=float(cut_list["music_start"] or 0),
        duration_s=total_s,
        show_address=bool(job.get("show_address")),
    )
    public_dir = ROOT / "public" / "jobs" / job_dir.name
    public_dir.mkdir(parents=True, exist_ok=True)
    for _key, src in deliver.items():
        shutil.copy2(src, public_dir / Path(src).name)
    return update_job(
        job_dir,
        stage="done",
        status="done",
        progress=100,
        deliverables=deliver,
        clips=rebuilt,
        plan=plan,
    )


def remux_job(job_dir: Path, music_id: str, show_address: bool | None = None) -> dict:
    """Swap the music bed and/or address overlay. No new I2V spend."""
    job_dir = Path(job_dir)
    job = read_json(job_dir / "job.json")
    if show_address is not None:
        job["show_address"] = bool(show_address)
    show = bool(job.get("show_address"))
    update_job(job_dir, status="assembling", stage="remux", progress=85, show_address=show)
    plan = read_json(job_dir / "plan.json")
    cut = read_json(job_dir / "cut_list.json")
    track = resolve_track(music_id)
    music = music_path(track["id"])
    clips = cut.get("clips") or plan.get("clips") or []
    originals = job_dir / "CLIPS"
    same_music = track["id"] == (job.get("music_id") or cut.get("music_id") or plan.get("music_id"))

    def original_clip(clip: dict) -> Path:
        src = Path(clip.get("clip") or clip["clip_path"])
        fallback = originals / Path(str(clip.get("clip_path") or src)).name
        if "remux" in src.parts and fallback.exists():
            return fallback
        if src.exists():
            return src
        if fallback.exists():
            return fallback
        return src

    if same_music:
        retargeted = [original_clip(c) for c in clips]
        updated = [dict(c) for c in clips]
        total_s = round(sum(float(c["duration_s"]) for c in updated), 3)
        music_start = float(
            cut.get("music_start") or (updated[0].get("music_time") if updated else 0) or 0
        )
    else:
        beats = detect_bpm_and_beats(
            music, bpm=track.get("bpm"), intro_s=float(track.get("intro_s") or 0.4)
        )
        snaps = snap_clip_durations(clips, beats, target_total=TARGET_SECONDS)
        work = job_dir / "CLIPS" / "remux"
        work.mkdir(parents=True, exist_ok=True)
        retargeted = []
        updated = []
        for clip, snap in zip(clips, snaps):
            src = original_clip(clip)
            dest = work / f"{src.stem}_{snap['beats']}b.mp4"
            trim_or_pad(src, dest, float(snap["duration_s"]))
            clip = dict(clip)
            clip["duration_s"] = snap["duration_s"]
            clip["music_time"] = snap["music_time"]
            clip["start"] = snap["start"]
            clip["beats"] = snap["beats"]
            clip["clip_path"] = str(src)
            updated.append(clip)
            retargeted.append(dest)
        total_s = round(sum(c["duration_s"] for c in updated), 3)
        music_start = updated[0]["music_time"] if updated else 0
        plan["beats"] = {
            "bpm": beats["bpm"],
            "phase": beats["phase"],
            "interval": beats["beat_interval"],
        }

    cut_list = {
        "clips": updated,
        "total_s": total_s,
        "music_start": music_start,
        "music_id": track["id"],
    }
    write_json(job_dir / "cut_list.json", cut_list)
    plan["total_s"] = total_s
    plan["music"] = str(music)
    plan["music_id"] = track["id"]
    plan["music_title"] = track["title"]
    write_json(job_dir / "plan.json", plan)
    deliver = assemble(
        retargeted,
        music,
        job_dir / "DELIVER",
        address=job.get("address"),
        city=job.get("city"),
        music_start=float(music_start or 0),
        duration_s=total_s,
        show_address=show,
    )
    public_dir = ROOT / "public" / "jobs" / job_dir.name
    public_dir.mkdir(parents=True, exist_ok=True)
    for _key, src in deliver.items():
        shutil.copy2(src, public_dir / Path(src).name)
    return update_job(
        job_dir,
        stage="done",
        status="done",
        progress=100,
        deliverables=deliver,
        music_id=track["id"],
        plan=plan,
        clips=updated,
        show_address=show,
    )
