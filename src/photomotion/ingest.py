"""Hash originals, copy to SOURCE, never mutate the inbox."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

from photomotion.constants import IMAGE_EXTS, PROXY_LONG_SIDE

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _iter_images(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            files.append(p)
    return files


def maybe_unzip(input_path: Path, dest: Path) -> Path:
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() == ".zip":
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(dest)
        return dest
    if input_path.is_file() and input_path.suffix.lower() in IMAGE_EXTS:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, dest / input_path.name)
        return dest
    raise FileNotFoundError(f"No images at {input_path}")


def ingest(input_path: Path, job_dir: Path) -> dict:
    """Copy inbox → SOURCE (read-only copies). Write hashes.json. Build proxies.

    Originals under input_path are never opened for write.
    """
    source_dir = job_dir / "SOURCE"
    proxy_dir = job_dir / "PROXIES"
    source_dir.mkdir(parents=True, exist_ok=True)
    proxy_dir.mkdir(parents=True, exist_ok=True)

    inbox = maybe_unzip(input_path, job_dir / "_unpack") if input_path.suffix.lower() == ".zip" else input_path
    images = _iter_images(inbox)
    if not images:
        raise FileNotFoundError(f"No listing stills in {input_path}")

    records = []
    for i, src in enumerate(images, start=1):
        digest = sha256_file(src)
        dest_name = src.name
        dest = source_dir / dest_name
        if dest.exists() and dest.resolve() != src.resolve():
            dest.chmod(0o644)
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        os.chmod(dest, 0o444)
        rec = {
            "index": i,
            "filename": dest_name,
            "original_path": str(src.resolve()),
            "source_path": str(dest),
            "sha256": digest,
            "bytes": src.stat().st_size,
        }
        if Image is not None:
            with Image.open(dest) as im:
                rec["width"], rec["height"] = im.size
            _write_proxy(dest, proxy_dir / dest_name, PROXY_LONG_SIDE)
        records.append(rec)

    payload = {"count": len(records), "items": records}
    (job_dir / "hashes.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _write_proxy(src: Path, dest: Path, long_side: int) -> None:
    if Image is None:
        return
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = long_side / max(w, h)
        if scale < 1:
            im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=90, optimize=True)


def originals_untouched(hashes: dict) -> list[str]:
    """Re-hash inbox paths; return list of filenames that changed (should be empty)."""
    dirty = []
    for item in hashes.get("items", []):
        p = Path(item["original_path"])
        if not p.exists():
            dirty.append(item["filename"] + " (missing)")
            continue
        if sha256_file(p) != item["sha256"]:
            dirty.append(item["filename"])
    return dirty
