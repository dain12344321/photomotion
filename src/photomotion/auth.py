"""xAI credentials for the desktop CLI. Never log the bearer."""

from __future__ import annotations

import getpass
import json
import os
import stat
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path


CREDENTIALS_NAME = "credentials.json"
CONSOLE_URL = "https://console.x.ai"
MIN_KEY_LEN = 12


class AuthError(RuntimeError):
    pass


def credentials_dir() -> Path:
    override = os.environ.get("PHOTOMOTION_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".photomotion"


def credentials_path() -> Path:
    return credentials_dir() / CREDENTIALS_NAME


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_store(path: Path | None = None) -> dict:
    p = path or credentials_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthError(f"credentials file is not valid JSON: {p}") from exc
    if not isinstance(data, dict):
        raise AuthError("credentials file must be a JSON object")
    return data


def _write_store(data: dict, path: Path | None = None) -> Path:
    p = path or credentials_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(p)
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    return p


def resolve_api_key() -> str | None:
    """Env wins, then ~/.photomotion/credentials.json. Never prints the value."""
    env = (os.environ.get("XAI_API_KEY") or "").strip()
    if env:
        return env
    data = _read_store()
    key = data.get("xai_api_key") or data.get("api_key") or ""
    key = str(key).strip()
    return key or None


def save_key(key: str, source: str = "login") -> dict:
    cleaned = (key or "").strip()
    if not cleaned:
        raise AuthError("no key provided")
    if any(ch.isspace() for ch in cleaned):
        raise AuthError("API key must not contain whitespace")
    if len(cleaned) < MIN_KEY_LEN:
        raise AuthError("that does not look like an API key")
    path = _write_store(
        {
            "xai_api_key": cleaned,
            "source": source,
            "updated_at": _now(),
        }
    )
    return {"ok": True, "configured": True, "path": str(path), "source": source}


def save_from_env() -> dict:
    key = (os.environ.get("XAI_API_KEY") or "").strip()
    if not key:
        raise AuthError("XAI_API_KEY is not set in the environment")
    return save_key(key, source="env")


def login_interactive(*, open_browser: bool = True, prompt_fn=None) -> dict:
    """Open console.x.ai (X login) and store a hidden paste. Never prints the bearer."""
    if open_browser:
        try:
            webbrowser.open(CONSOLE_URL)
        except Exception:
            pass
    print(f"Sign in with X at {CONSOLE_URL}, create an API key, then paste it here.", file=sys.stderr)
    print("The key is stored at ~/.photomotion/credentials.json (mode 600) and is never printed.", file=sys.stderr)
    getter = prompt_fn or (lambda: getpass.getpass("Paste xAI API key (hidden): "))
    key = getter()
    return save_key(key if isinstance(key, str) else "", source="login")


def clear_credentials() -> dict:
    p = credentials_path()
    if p.exists():
        p.unlink()
    return {"ok": True, "configured": False, "path": str(p)}


def status() -> dict:
    env = bool((os.environ.get("XAI_API_KEY") or "").strip())
    path = credentials_path()
    file_present = False
    source = None
    if path.exists():
        data = _read_store(path)
        file_present = bool(str(data.get("xai_api_key") or data.get("api_key") or "").strip())
        source = data.get("source")
    if env:
        source = "env"
    return {
        "configured": bool(env or file_present),
        "from_env": env,
        "from_file": file_present,
        "source": source,
        "path": str(path),
        "console": CONSOLE_URL,
        "note": "Ken Burns does not need a key. Imagine does. Sign in with X at console.x.ai.",
    }


def redact(text: str, key: str | None = None) -> str:
    """Strip any known bearer from a log / JSON dump."""
    out = text
    secrets = [
        key,
        os.environ.get("XAI_API_KEY"),
        (_read_store().get("xai_api_key") if credentials_path().exists() else None),
    ]
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), "[redacted]")
    return out
