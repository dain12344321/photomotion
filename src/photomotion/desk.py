"""Local photos-in / videos-out desk. stdlib only. ffmpeg writes MP4s on this machine."""

from __future__ import annotations

import json
import re
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from photomotion.auth import AuthError, resolve_api_key, save_key, status as auth_status
from photomotion.job import doctor, run_job
from photomotion.music import DEFAULT_TRACK_ID, catalog


JOBS_ROOT = Path("data/jobs")
INBOX_ROOT = Path("data/INBOX")
STATE: dict[str, dict] = {}
STATE_LOCK = threading.Lock()

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_JOB = re.compile(r"^[A-Za-z0-9._-]+$")


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PhotoMotion desktop</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {
      --bg: #12161a; --surface: #1a2128; --elevated: #222a32;
      --fg: #efece6; --muted: #9aa3ab; --subtle: #6d767e;
      --border: #2a333c; --lake: #7aa2c4; --accent: #c43c3c;
      --ink: #0d1013; --ok: #7aa671;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; background: var(--bg); color: var(--fg);
      font: 400 16px/1.5 Montserrat, "Segoe UI", system-ui, sans-serif;
      -webkit-font-smoothing: antialiased; }
    main { max-width: 42rem; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
    h1 { font-weight: 600; letter-spacing: -0.03em; font-size: 2rem; margin: 0.25rem 0 0; }
    .kicker { font-size: 0.6875rem; font-weight: 600; letter-spacing: 0.2em;
      text-transform: uppercase; color: var(--lake); }
    p { color: var(--muted); }
    .card { background: var(--surface); box-shadow: 0 0 0 1px rgba(255,255,255,0.08);
      border-radius: 28px; padding: 1.25rem 1.35rem; margin-top: 1.25rem; }
    label { display: block; font-size: 0.8rem; color: var(--muted); margin-top: 0.75rem; }
    input[type=text], select { width: 100%; height: 2.75rem; margin-top: 0.3rem;
      border-radius: 8px; border: 1px solid var(--border); background: var(--ink);
      color: var(--fg); padding: 0 0.75rem; font: inherit; }
    .drop { margin-top: 0.85rem; min-height: 8rem; border: 1px dashed var(--border);
      border-radius: 12px; display: grid; place-items: center; text-align: center;
      color: var(--muted); padding: 1rem; cursor: pointer; }
    .drop.over { border-color: var(--lake); background: #1c2833; }
    button { appearance: none; border: 1px solid var(--accent); background: var(--accent);
      color: #fff7f5; border-radius: 999px; min-height: 2.75rem; padding: 0 1.5rem;
      font: 600 0.8rem/1 Montserrat, "Segoe UI", system-ui, sans-serif; letter-spacing: 0.14em;
      text-transform: uppercase; cursor: pointer; }
    button.secondary { background: transparent; color: var(--fg); border-color: var(--fg); }
    button:disabled { opacity: 0.4; cursor: default; }
    .row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; align-items: center; }
    .files { font-size: 0.8rem; color: var(--subtle); margin-top: 0.5rem; }
    a { color: var(--lake); }
    pre { background: var(--ink); border-radius: 12px; padding: 1rem; overflow: auto;
      font: 12px/1.45 "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--fg); }
    .ok { color: var(--ok); } .err { color: var(--accent); }
    .status { font-size: 0.8rem; color: var(--muted); margin-top: 0.75rem; }
    input[type=password] { width: 100%; height: 2.75rem; margin-top: 0.3rem;
      border-radius: 8px; border: 1px solid var(--border); background: var(--ink);
      color: var(--fg); padding: 0 0.75rem; font: inherit; }
  </style>
</head>
<body>
  <main>
    <p class="kicker">Lakeshore Listing Media</p>
    <h1>PhotoMotion desktop</h1>
    <p>Drop 5+ listing stills. This machine writes 16:9, 9:16, and 1:1 MP4s with offline Ken Burns. Imagine stays opt-in.</p>
    <p class="status" id="machine">Checking ffmpeg…</p>
    <form class="card" id="form">
      <label>Address <input type="text" name="address" placeholder="405 N Main St" /></label>
      <label>City <input type="text" name="city" placeholder="Wanatah, IN 46390" /></label>
      <label>Music
        <select name="music" id="music"></select>
      </label>
      <label><input type="checkbox" name="address_card" /> Address card on the open</label>
      <div class="drop" id="drop">Drop JPEGs here or click to choose</div>
      <input type="file" id="file" accept="image/jpeg,image/png,image/webp" multiple hidden />
      <div class="files" id="filelist">No stills yet</div>
      <div class="row">
        <button type="submit">Render MP4s</button>
        <button type="button" class="secondary" id="auth">Auth status</button>
      </div>
    </form>
    <form class="card" id="keyform">
      <p class="kicker">X / xAI</p>
      <p>Sign in at <a href="https://console.x.ai" target="_blank" rel="noreferrer">console.x.ai</a> with your X account, create a key, paste it here. Ken Burns does not need this. The key is never shown back.</p>
      <label>xAI API key <input type="password" name="api_key" autocomplete="off" /></label>
      <div class="row">
        <button type="submit" class="secondary">Store key</button>
      </div>
    </form>
    <section class="card">
      <p class="kicker">Job</p>
      <pre id="log">Idle. Ken Burns is the product.</pre>
      <div id="links"></div>
    </section>
  </main>
  <script>
    const music = document.getElementById("music");
    const drop = document.getElementById("drop");
    const file = document.getElementById("file");
    const filelist = document.getElementById("filelist");
    const log = document.getElementById("log");
    const links = document.getElementById("links");
    let files = [];
    fetch("/catalog").then(r => r.json()).then(beds => {
      beds.forEach(b => {
        const o = document.createElement("option");
        o.value = b.id; o.textContent = b.title + " · " + b.bpm + " BPM";
        music.appendChild(o);
      });
    });
    function list() {
      filelist.textContent = files.length ? files.length + " stills · " + files.map(f => f.name).join(", ") : "No stills yet";
    }
    function take(list) {
      files = Array.from(list).filter(f => /\\.(jpe?g|png|webp|tif{1,2})$/i.test(f.name));
      list();
    }
    drop.addEventListener("click", () => file.click());
    drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); take(e.dataTransfer.files); });
    file.addEventListener("change", () => take(file.files));
    fetch("/health").then(r => r.json()).then(h => {
      const el = document.getElementById("machine");
      const ff = h.ffmpeg && h.ffmpeg.ok ? "ffmpeg ready" : "ffmpeg missing — MP4 encode will fail";
      const key = h.auth && h.auth.configured ? "xAI key stored" : "no xAI key (Ken Burns still runs)";
      el.textContent = ff + " · " + key;
      el.className = "status " + (h.ffmpeg && h.ffmpeg.ok ? "ok" : "err");
    });
    document.getElementById("auth").addEventListener("click", async () => {
      const s = await fetch("/auth/status").then(r => r.json());
      log.textContent = JSON.stringify(s, null, 2);
    });
    document.getElementById("keyform").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const res = await fetch("/auth/login", { method: "POST", body: fd });
      const rec = await res.json();
      e.target.reset();
      log.textContent = JSON.stringify(rec, null, 2);
    });
    document.getElementById("form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (files.length < 5) { log.textContent = "Need at least 5 listing stills."; return; }
      const fd = new FormData(e.target);
      files.forEach(f => fd.append("files", f, f.name));
      log.textContent = "Rendering… originals stay untouched.";
      links.innerHTML = "";
      const res = await fetch("/run", { method: "POST", body: fd });
      const job = await res.json();
      const id = job.id;
      const poll = async () => {
        const j = await fetch("/jobs/" + id).then(r => r.json());
        log.textContent = JSON.stringify({ status: j.status, stage: j.stage, progress: j.progress, error: j.error, music_id: j.music_id }, null, 2);
        if (j.status === "done") {
          const names = ["master_16x9_clean.mp4", "vertical_9x16_clean.mp4", "square_1x1_clean.mp4"];
          links.innerHTML = names.map(n => '<p><a href="/jobs/' + id + '/file/' + n + '" download>' + n + "</a></p>").join("");
          return;
        }
        if (j.status === "error") return;
        setTimeout(poll, 1500);
      };
      poll();
    });
  </script>
</body>
</html>
"""


def _set_state(job_id: str, payload: dict) -> None:
    with STATE_LOCK:
        STATE[job_id] = payload


def _get_state(job_id: str) -> dict | None:
    with STATE_LOCK:
        rec = STATE.get(job_id)
        return dict(rec) if rec else None


def _parse_multipart(headers: dict[str, str], body: bytes) -> tuple[dict[str, str], list[tuple[str, bytes]]]:
    ctype = headers.get("Content-Type") or headers.get("content-type") or ""
    if "boundary=" not in ctype:
        return {}, []
    boundary = ctype.split("boundary=", 1)[1].strip().strip('"').encode("utf-8")
    fields: dict[str, str] = {}
    files: list[tuple[str, bytes]] = []
    for raw in body.split(b"--" + boundary):
        if not raw or raw in (b"--\r\n", b"--", b"\r\n"):
            continue
        if raw.startswith(b"--"):
            continue
        header, sep, data = raw.partition(b"\r\n\r\n")
        if not sep:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        disp = ""
        for line in header.decode("utf-8", "replace").split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disp = line
        name = ""
        filename = ""
        for piece in disp.split(";"):
            piece = piece.strip()
            if piece.startswith("name="):
                name = piece.split("=", 1)[1].strip().strip('"')
            elif piece.startswith("filename="):
                filename = piece.split("=", 1)[1].strip().strip('"')
        filename = Path(filename).name
        if filename:
            files.append((filename, data))
        elif name:
            fields[name] = data.decode("utf-8", "replace")
    return fields, files


def _slug(address: str, fallback: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (address or fallback).lower()).strip("-")
    return (base or fallback)[:40]


def _run_job_thread(job_id: str, inbox: Path, job_dir: Path, fields: dict[str, str]) -> None:
    try:
        job = run_job(
            input_path=inbox,
            job_dir=job_dir,
            address=fields.get("address") or None,
            city=fields.get("city") or None,
            dry_run=True,
            confirm_live=False,
            i2v_heroes=0,
            music_id=fields.get("music") or DEFAULT_TRACK_ID,
            show_address=fields.get("address_card") in {"on", "true", "1"},
        )
        _set_state(job_id, job)
    except Exception as exc:  # noqa: BLE001 — surface to the local operator
        _set_state(job_id, {"id": job_id, "status": "error", "error": str(exc)[:500]})


class DeskHandler(BaseHTTPRequestHandler):
    server_version = "PhotoMotionDesk/0.2"

    def log_message(self, fmt: str, *args) -> None:
        msg = fmt % args
        if "XAI_API_KEY" in msg or "sk-" in msg:
            return
        super().log_message("%s", msg)

    def _send(self, code: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict | list) -> None:
        raw = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path in {"/", "/index.html"}:
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/catalog":
            self._json(200, catalog())
            return
        if path == "/auth/status":
            self._json(200, {**auth_status(), "has_runtime_key": bool(resolve_api_key())})
            return
        if path == "/health":
            rec = doctor()
            rec["has_runtime_key"] = bool(resolve_api_key())
            self._json(200, rec)
            return
        m = re.fullmatch(r"/jobs/([^/]+)", path)
        if m:
            job_id = m.group(1)
            if not SAFE_JOB.match(job_id):
                self._json(400, {"error": "bad id"})
                return
            rec = _get_state(job_id)
            job_json = JOBS_ROOT / job_id / "job.json"
            if job_json.exists():
                rec = json.loads(job_json.read_text(encoding="utf-8"))
            self._json(200 if rec else 404, rec or {"error": "unknown job"})
            return
        m = re.fullmatch(r"/jobs/([^/]+)/file/([^/]+)", path)
        if m:
            job_id, name = m.group(1), m.group(2)
            if not SAFE_JOB.match(job_id) or not SAFE_NAME.match(name):
                self._json(400, {"error": "bad path"})
                return
            deliver = (JOBS_ROOT / job_id / "DELIVER").resolve()
            target = (deliver / name).resolve()
            try:
                target.relative_to(deliver)
            except ValueError:
                self._json(400, {"error": "bad path"})
                return
            if not target.is_file():
                self._json(404, {"error": "missing"})
                return
            data = target.read_bytes()
            ctype = "video/mp4" if name.endswith(".mp4") else "application/octet-stream"
            self._send(200, data, ctype, {"Content-Disposition": f'attachment; filename="{name}"'})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/auth/login":
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 16 * 1024:
                self._json(413, {"error": "payload too large"})
                return
            body = self.rfile.read(length)
            headers = {k: v for k, v in self.headers.items()}
            fields, _files = _parse_multipart(headers, body)
            key = fields.get("api_key") or ""
            if not key:
                try:
                    payload = json.loads(body.decode("utf-8"))
                    if isinstance(payload, dict):
                        key = str(payload.get("api_key") or "")
                except json.JSONDecodeError:
                    key = ""
            try:
                rec = save_key(key, source="desk")
                rec.pop("path", None)
                rec["note"] = "Key stored. It will never be printed."
                self._json(200, rec)
            except AuthError as exc:
                self._json(400, {"ok": False, "error": str(exc)})
            return
        if parsed.path != "/run":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 400 * 1024 * 1024:
            self._json(413, {"error": "payload too large"})
            return
        body = self.rfile.read(length)
        headers = {k: v for k, v in self.headers.items()}
        fields, files = _parse_multipart(headers, body)
        images = [(n, b) for n, b in files if Path(n).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}]
        if len(images) < 5:
            self._json(400, {"error": "Need at least 5 listing stills."})
            return
        job_id = _slug(fields.get("address") or "", "tour") + "-" + uuid.uuid4().hex[:6]
        inbox = INBOX_ROOT / job_id
        inbox.mkdir(parents=True, exist_ok=True)
        for name, blob in images:
            safe = Path(name).name
            if not SAFE_NAME.match(safe.replace(" ", "-")):
                safe = re.sub(r"[^A-Za-z0-9._-]+", "-", safe)
            (inbox / safe).write_bytes(blob)
        job_dir = JOBS_ROOT / job_id
        _set_state(job_id, {"id": job_id, "status": "queued", "stage": "ingest", "progress": 1})
        threading.Thread(
            target=_run_job_thread,
            args=(job_id, inbox, job_dir, fields),
            daemon=True,
        ).start()
        self._json(202, {"id": job_id, "status": "queued"})


def serve(host: str = "127.0.0.1", port: int = 8765, jobs: Path | None = None, open_browser: bool = True) -> None:
    global JOBS_ROOT
    if jobs:
        JOBS_ROOT = Path(jobs)
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    INBOX_ROOT.mkdir(parents=True, exist_ok=True)
    rec = doctor()
    ff = rec.get("ffmpeg") or {}
    if not ff.get("ok"):
        print("warning: ffmpeg is not on PATH — MP4 encode will fail. Ken Burns still plans.", file=sys.stderr)
    else:
        print(ff.get("version") or "ffmpeg ready")
    auth = rec.get("auth") or {}
    if auth.get("configured"):
        print("xAI key present (Imagine). Ken Burns does not need it.")
    else:
        print("No xAI key. Ken Burns still runs. Sign in at https://console.x.ai with X, then python3 -m photomotion auth --login")
    httpd = ThreadingHTTPServer((host, port), DeskHandler)
    url = f"http://{host}:{port}"
    print(f"PhotoMotion desk {url}")
    print("Drop 5+ stills. Ctrl-C to stop.")
    if open_browser and host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        try:
            import webbrowser

            webbrowser.open(url if host != "0.0.0.0" else f"http://127.0.0.1:{port}")
        except Exception:
            pass
    httpd.serve_forever()
