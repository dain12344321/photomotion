"""CLI: python -m photomotion run --input ./INBOX/demo --dry-run"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from photomotion.auth import (
    AuthError,
    clear_credentials,
    login_interactive,
    save_from_env,
    status as auth_status,
)
from photomotion.constants import DEFAULT_SPEND_CAP, HARD_SPEND_CAP
from photomotion.job import doctor, remux_job, restabilize_job, run_job
from photomotion.music import DEFAULT_TRACK_ID, catalog


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="photomotion", description="PhotoMotion™ listing reels")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Ingest a property folder and write DELIVER mp4s")
    run.add_argument("--input", required=True, type=Path, help="INBOX property folder or zip")
    run.add_argument("--job-dir", type=Path, default=None)
    run.add_argument("--address", default=None)
    run.add_argument("--city", default=None)
    run.add_argument("--dry-run", action="store_true", default=False)
    run.add_argument("--live", action="store_true", help="Allow Grok Imagine I2V")
    run.add_argument("--confirm-live", action="store_true", help="Required with --live")
    run.add_argument("--spend-cap", type=float, default=DEFAULT_SPEND_CAP)
    run.add_argument("--i2v-heroes", type=int, default=0, help="Max I2V clips (0 = Ken Burns only)")
    run.add_argument("--music", default=DEFAULT_TRACK_ID, help="Bed id: easy-lemon | wallpaper | carefree | funkorama")
    run.add_argument("--address-card", action="store_true", help="Burn property address on the open (off by default)")
    run.add_argument("--plan-only", action="store_true")
    run.add_argument("--workers", type=int, default=4)

    remux = sub.add_parser("remux", help="Swap music bed on an existing job (no I2V spend)")
    remux.add_argument("--job-dir", required=True, type=Path)
    remux.add_argument("--music", required=True)
    remux.add_argument("--address-card", action="store_true", default=None)
    remux.add_argument("--no-address-card", action="store_true")

    stab = sub.add_parser("stabilize", help="Re-QC I2V and rebuild in-frame Ken Burns (no I2V spend)")
    stab.add_argument("--job-dir", required=True, type=Path)

    auth = sub.add_parser("auth", help="Store or inspect the xAI key (never printed)")
    auth.add_argument(
        "--login",
        action="store_true",
        help="Open console.x.ai (X login) and paste a key (hidden)",
    )
    auth.add_argument("--from-env", action="store_true", help="Copy XAI_API_KEY to ~/.photomotion/credentials.json")
    auth.add_argument("--status", action="store_true", help="Show whether a key is configured")
    auth.add_argument("--clear", action="store_true", help="Delete stored credentials")

    serve = sub.add_parser("serve", help="Local photos-in / videos-out desk")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--jobs", type=Path, default=Path("data/jobs"))
    serve.add_argument("--no-browser", action="store_true")

    sub.add_parser("catalog", help="List music beds")
    sub.add_parser("check", help="ffmpeg, numpy, pillow, and xAI key status")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "catalog":
        print(json.dumps(catalog(), indent=2))
        return 0
    if args.cmd == "check":
        rec = doctor()
        print(json.dumps(rec, indent=2))
        return 0 if rec.get("ok") else 1
    if args.cmd == "auth":
        try:
            if args.clear:
                print(json.dumps(clear_credentials(), indent=2))
                return 0
            if args.login:
                print(json.dumps(login_interactive(open_browser=True), indent=2))
                return 0
            if args.from_env:
                print(json.dumps(save_from_env(), indent=2))
                return 0
            print(json.dumps(auth_status(), indent=2))
            return 0
        except AuthError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except (EOFError, KeyboardInterrupt):
            print("error: login cancelled", file=sys.stderr)
            return 2
    if args.cmd == "serve":
        from photomotion.desk import serve as serve_desk

        serve_desk(host=args.host, port=args.port, jobs=args.jobs, open_browser=not args.no_browser)
        return 0
    if args.cmd == "remux":
        show = True if args.address_card else (False if args.no_address_card else None)
        job = remux_job(args.job_dir, args.music, show_address=show)
        print(json.dumps({k: job[k] for k in job if k != "plan"}, indent=2, default=str))
        return 0 if job.get("status") == "done" else 1
    if args.cmd == "stabilize":
        job = restabilize_job(args.job_dir)
        print(json.dumps({k: job[k] for k in job if k != "plan"}, indent=2, default=str))
        return 0 if job.get("status") == "done" else 1
    if args.cmd == "run":
        dry_run = not args.live
        if args.dry_run:
            dry_run = True
        if args.live and not args.confirm_live:
            print("error: --live requires --confirm-live", file=sys.stderr)
            return 2
        if args.spend_cap > HARD_SPEND_CAP:
            print(f"error: spend cap exceeds hard cap ${HARD_SPEND_CAP}", file=sys.stderr)
            return 2
        job_dir = args.job_dir or Path("data/jobs") / args.input.name
        job = run_job(
            input_path=args.input,
            job_dir=job_dir,
            address=args.address,
            city=args.city,
            dry_run=dry_run,
            confirm_live=args.confirm_live,
            spend_cap=args.spend_cap,
            i2v_heroes=args.i2v_heroes,
            plan_only=args.plan_only,
            workers=args.workers,
            music_id=args.music,
            show_address=bool(args.address_card),
        )
        print(json.dumps({k: job[k] for k in job if k != "plan"}, indent=2, default=str))
        return 0 if job.get("status") in {"done", "planned"} else 1
    return 1
