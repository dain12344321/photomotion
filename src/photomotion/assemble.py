"""Concat Ken Burns clips, beat-aligned music, three aspect ratios."""

from __future__ import annotations

import subprocess
from pathlib import Path

from photomotion.constants import (
    SQUARE,
    VERTICAL_H,
    VERTICAL_W,
)
from photomotion.overlays import write_address_card


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed:\n" + proc.stderr.decode("utf-8", errors="replace")[-3000:]
        )


def trim_or_pad(src: Path, dest: Path, duration_s: float) -> Path:
    """Force a clip to duration_s. Clone the last frame if we need more."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.4, float(duration_s))
    vf = f"tpad=stop_mode=clone:stop_duration=8,trim=0:{dur:.4f},setpts=PTS-STARTPTS,fps=30,format=yuv420p"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            vf,
            "-an",
            "-t",
            f"{dur:.4f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest


def concat_clips(clips: list[Path], dest: Path) -> Path:
    """Hard-cut on clip boundaries. Copy when codecs match so cuts stay sample-accurate."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    lst = dest.with_suffix(".txt")
    lines = [f"file '{c.resolve()}'" for c in clips]
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    copy_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(lst),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    try:
        _run(copy_cmd)
    except RuntimeError:
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "17",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-movflags",
                "+faststart",
                str(dest),
            ]
        )
    lst.unlink(missing_ok=True)
    return dest


def mux_music_and_overlays(
    video: Path,
    music: Path,
    dest: Path,
    *,
    address: str | None,
    city: str | None,
    music_start: float,
    duration_s: float,
    show_address: bool = False,
) -> Path:
    """Unbranded by default. Address card is opt-in. No AI disclosure line."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = dest.parent
    inputs: list[str] = ["-i", str(video)]
    branded = bool(show_address and (address or "").strip())
    maps: list[str]
    vcodec: list[str]
    if branded:
        card = write_address_card(work / "address.png", address or "", city or "")
        inputs += ["-i", str(card)]
        audio_idx = 2
        vfilter = (
            "[1:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1,"
            "fade=t=out:st=3.0:d=0.7:alpha=1[card];"
            "[0:v][card]overlay=0:0:format=auto[v];"
        )
        maps = ["-map", "[v]", "-map", "[a]"]
        vcodec = [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
        ]
    else:
        audio_idx = 1
        vfilter = ""
        maps = ["-map", "0:v", "-map", "[a]"]
        vcodec = ["-c:v", "copy"]
    inputs += ["-ss", f"{music_start:.4f}", "-i", str(music)]
    filter_complex = (
        vfilter
        + f"[{audio_idx}:a]atrim=0:{duration_s:.4f},asetpts=PTS-STARTPTS,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            *maps,
            "-t",
            f"{duration_s:.4f}",
            *vcodec,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest


def derive_vertical(master: Path, dest: Path) -> Path:
    """Real 9:16 cover-crop from the 16:9 master. Full-bleed, no letterbox."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"crop=2*trunc(ih*9/32):ih:(iw-2*trunc(ih*9/32))/2:0,"
        f"scale={VERTICAL_W}:{VERTICAL_H}:flags=lanczos,setsar=1,format=yuv420p"
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(master),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest


def derive_square(master: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = f"crop={SQUARE}:{SQUARE}:(in_w-{SQUARE})/2:(in_h-{SQUARE})/2,format=yuv420p"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(master),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest


def assemble(
    clips: list[Path],
    music: Path,
    deliver_dir: Path,
    *,
    address: str | None,
    city: str | None,
    music_start: float,
    duration_s: float,
    show_address: bool = False,
) -> dict:
    deliver_dir.mkdir(parents=True, exist_ok=True)
    silent = deliver_dir / "_silent.mp4"
    concat_clips(clips, silent)
    master = deliver_dir / "master_16x9_clean.mp4"
    mux_music_and_overlays(
        silent,
        music,
        master,
        address=address,
        city=city,
        music_start=music_start,
        duration_s=duration_s,
        show_address=show_address,
    )
    vertical = deliver_dir / "vertical_9x16_clean.mp4"
    square = deliver_dir / "square_1x1_clean.mp4"
    derive_vertical(master, vertical)
    derive_square(master, square)
    silent.unlink(missing_ok=True)
    return {
        "master_16x9_clean": str(master),
        "vertical_9x16_clean": str(vertical),
        "square_1x1_clean": str(square),
    }
