"""Contract tests: motion bans, spend cap, dry-run, fallback, originals, assemble."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from photomotion.constants import ALLOWED_MOTIONS, HARD_SPEND_CAP, HOLD_OUT, KB_PLATE_H, KB_PLATE_W, ORBIT_ZOOM, PUSH_ZOOM, STATIC_ZOOM
from photomotion.ingest import ingest, originals_untouched, sha256_file
from photomotion.i2v import generate_or_fallback
from photomotion.job import select_hero_indexes
from photomotion.kenburns import camera_path, ramp_velocity, shaped_ease, speed_ramp
from photomotion.motion import MotionPolicyError, assert_allowed, assign_motion, coerce_motion, motion_for_room
from photomotion.qc import flicker_score, frame_resemblance
from photomotion.spend import SpendBlocked, assert_live_allowed, clamp_cap, estimate_job_usd


class MotionPolicyTests(unittest.TestCase):
    def test_bath_is_static(self):
        self.assertEqual(motion_for_room("bathroom"), "static")
        self.assertEqual(motion_for_room("laundry"), "static")
        self.assertEqual(motion_for_room("garage"), "static")
        self.assertEqual(motion_for_room("vanity"), "static")

    def test_wide_rooms_move(self):
        self.assertEqual(motion_for_room("living"), "orbit")
        self.assertEqual(motion_for_room("exterior_front"), "orbit")
        self.assertEqual(motion_for_room("kitchen"), "pull_out")

    def test_bans_pan_pullout(self):
        for banned in ("pan", "pan_left", "zoom_out"):
            with self.assertRaises(MotionPolicyError):
                assert_allowed(banned)

    def test_orbit_is_in_frame_allowed(self):
        self.assertEqual(assert_allowed("orbit"), "orbit")
        self.assertEqual(assert_allowed("pull_out"), "pull_out")
        self.assertEqual(assert_allowed("pull-out"), "pull_out")
        self.assertEqual(assert_allowed("ken_burns"), "ken_burns")
        self.assertEqual(assert_allowed("kenburns"), "ken_burns")

    def test_bath_cannot_be_overridden_to_push(self):
        self.assertEqual(coerce_motion("bathroom", "push_in"), "static")

    def test_allowed_motions(self):
        self.assertEqual(
            ALLOWED_MOTIONS, frozenset({"push_in", "orbit", "pull_out", "ken_burns", "static"})
        )

    def test_assign_alternates_and_freezes_baths(self):
        self.assertEqual(assign_motion("living", 0), "orbit")
        self.assertEqual(assign_motion("kitchen", 0), "pull_out")
        self.assertEqual(assign_motion("bathroom", 1), "static")
        self.assertEqual(assign_motion("bedroom", 0), "push_in")
        self.assertEqual(assign_motion("living", 1, prev="orbit"), "pull_out")
        self.assertEqual(assign_motion("exterior_front", 0, role="hero_open"), "push_in")
        self.assertEqual(assign_motion("backyard", 9, role="closer"), "pull_out")


class QcTests(unittest.TestCase):
    def test_fire_patch_fails_resemblance(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            still = td_path / "s.jpg"
            Image.new("RGB", (320, 180), (40, 40, 40)).save(still)
            hot = td_path / "h.jpg"
            im = Image.new("RGB", (320, 180), (40, 40, 40))
            for x in range(80, 160):
                for y in range(80, 140):
                    im.putpixel((x, y), (255, 180, 40))
            im.save(hot)
            rec = frame_resemblance(still, hot, threshold=0.72, zoom=1.0)
            self.assertFalse(rec["pass"])

    def test_flicker_detects_pulse(self):
        import numpy as np

        a = np.zeros((90, 160), np.float32)
        b = a.copy()
        b[20:40, 40:80] = 1.0
        self.assertGreater(flicker_score([a, b, a]), 0.055)


class SpendTests(unittest.TestCase):
    def test_dry_run_blocks_live(self):
        with self.assertRaises(SpendBlocked):
            assert_live_allowed(
                dry_run=True, confirm_live=True, spend_cap=5, estimated_usd=0.5
            )

    def test_live_without_confirm_blocked(self):
        with self.assertRaises(SpendBlocked):
            assert_live_allowed(
                dry_run=False, confirm_live=False, spend_cap=5, estimated_usd=0.5
            )

    def test_cap_blocks_overage(self):
        with self.assertRaises(SpendBlocked):
            assert_live_allowed(
                dry_run=False, confirm_live=True, spend_cap=2, estimated_usd=2.5
            )

    def test_ten_heroes_under_fifteen(self):
        est = estimate_job_usd(10, 4)
        self.assertAlmostEqual(est, 10.10, places=2)
        self.assertLessEqual(est, 15)

    def test_hard_cap(self):
        self.assertEqual(clamp_cap(999), HARD_SPEND_CAP)

    def test_two_heroes_under_five_at_4s_1080p(self):
        # 1080p $0.25/s * 4s + $0.01 image = $1.01 each → $2.02 for two.
        est = estimate_job_usd(2, 4)
        self.assertAlmostEqual(est, 2.02, places=2)
        self.assertLessEqual(est, 5)


class HeroSelectTests(unittest.TestCase):
    def test_picks_open_and_living(self):
        clips = [
            {"index": 0, "room": "exterior_front", "role": "hero_open", "motion": "push_in"},
            {"index": 1, "room": "exterior_front", "role": "exterior", "motion": "orbit"},
            {"index": 2, "room": "living", "role": "hero_interior", "motion": "push_in"},
        ]
        self.assertEqual(select_hero_indexes(clips, 2), [0, 2])

    def test_fills_push_ins_and_skips_static(self):
        clips = [
            {"index": 0, "room": "exterior_front", "motion": "push_in"},
            {"index": 1, "room": "bathroom", "motion": "static"},
            {"index": 2, "room": "living", "motion": "push_in"},
            {"index": 3, "room": "kitchen", "motion": "push_in"},
        ]
        self.assertEqual(select_hero_indexes(clips, 10), [0, 2, 3])

    def test_skips_orbit_for_i2v(self):
        clips = [
            {"index": 0, "room": "exterior_front", "motion": "push_in", "role": "hero_open"},
            {"index": 1, "room": "living", "motion": "orbit", "role": "hero_interior"},
            {"index": 2, "room": "kitchen", "motion": "push_in", "role": "kitchen"},
        ]
        self.assertEqual(select_hero_indexes(clips, 10), [0, 2])

    def test_i2v_only_push_in(self):
        clips = [
            {"index": 0, "room": "exterior_front", "motion": "push_in", "role": "hero_open"},
            {"index": 1, "room": "living", "motion": "pull_out"},
            {"index": 2, "room": "kitchen", "motion": "ken_burns"},
            {"index": 3, "room": "bedroom", "motion": "push_in"},
        ]
        self.assertEqual(select_hero_indexes(clips, 10), [0, 3])


class KenBurnsPathTests(unittest.TestCase):
    def test_windows_stay_in_plate(self):
        for motion in ("push_in", "orbit", "pull_out", "ken_burns", "static"):
            for yaw in (1, -1):
                wins = camera_path(motion, 48, yaw=yaw, focal=(0.28, 0.42))
                self.assertEqual(len(wins), 48)
                for x, y, w, h in wins:
                    self.assertGreaterEqual(x, -1e-6)
                    self.assertGreaterEqual(y, -1e-6)
                    self.assertLessEqual(x + w, KB_PLATE_W + 1e-6)
                    self.assertLessEqual(y + h, KB_PLATE_H + 1e-6)
                    self.assertGreater(w, 0)
                    self.assertGreater(h, 0)

    def test_orbit_travels_and_push_zooms(self):
        orbit = camera_path("orbit", 60, yaw=1)
        self.assertGreater(abs(orbit[-1][0] - orbit[0][0]), 80)
        push = camera_path("push_in", 60, yaw=1)
        self.assertGreater(push[0][2], push[-1][2])
        self.assertGreater(PUSH_ZOOM, ORBIT_ZOOM)
        self.assertGreater(ORBIT_ZOOM, STATIC_ZOOM)
        self.assertGreaterEqual(PUSH_ZOOM, 1.35)
        self.assertGreaterEqual(ORBIT_ZOOM, 1.28)

    def test_never_trucks_vertically(self):
        from photomotion.kenburns import camera_window_at

        for motion in ("orbit", "push_in", "pull_out", "ken_burns"):
            a = camera_window_at(motion, 0.5, yaw=1)
            b = camera_window_at(motion, 0.5, yaw=-1)
            self.assertEqual(a[1], b[1])
            self.assertEqual(a[3], b[3])
        left = camera_window_at("orbit", 0.0, yaw=1)
        right = camera_window_at("orbit", 0.0, yaw=-1)
        self.assertGreater(abs(left[0] - right[0]), 40)
        self.assertEqual(left[1], right[1])

    def test_nine_sixteen_is_full_bleed_slice(self):
        from photomotion.kenburns import camera_source_window

        img_w, img_h = 4000, 2667
        start = camera_source_window("orbit", 0.0, 1, (0.5, 0.46), img_w, img_h, "9x16")
        end = camera_source_window("orbit", 1.0, 1, (0.5, 0.46), img_w, img_h, "9x16")
        x, y, w, h = start
        self.assertAlmostEqual(w / h, 9 / 16, places=2)
        self.assertGreaterEqual(y, -1e-6)
        self.assertLessEqual(y + h, img_h + 1e-6)
        self.assertGreater(abs(end[0] - start[0]), start[2] * 0.12)
        self.assertLess(abs(end[0] - start[0]), start[2] * 0.42)
        self.assertGreater(h, img_h * 0.7)

    def test_speed_ramp_into_downbeat(self):
        self.assertEqual(speed_ramp(0.0), 0.0)
        self.assertEqual(speed_ramp(1.0), 1.0)
        self.assertAlmostEqual(ramp_velocity(0.0), 0.0, places=6)
        self.assertEqual(ramp_velocity(1.0), 0.0)
        self.assertEqual(ramp_velocity(1.0 - HOLD_OUT), 0.0)
        v_rise = ramp_velocity(0.12)
        v_mid = ramp_velocity(0.5)
        v_fall = ramp_velocity(0.8)
        self.assertGreater(v_mid, v_rise)
        self.assertGreater(v_mid, v_fall)
        self.assertGreater(v_fall, 0.0)
        self.assertGreater(speed_ramp(0.5), 0.45)
        self.assertLess(speed_ramp(0.5), 0.55)

    def test_pull_out_zooms_out(self):
        pull = camera_path("pull_out", 60, yaw=1)
        self.assertLess(pull[0][2], pull[-1][2])
        push = camera_path("push_in", 60, yaw=1)
        self.assertAlmostEqual(pull[0][2], push[-1][2], places=6)
        self.assertAlmostEqual(pull[-1][2], push[0][2], places=6)

    def test_ken_burns_drifts(self):
        kb = camera_path("ken_burns", 60, yaw=1)
        self.assertGreater(kb[0][2], kb[-1][2])
        self.assertGreater(abs(kb[-1][0] - kb[0][0]), 20)


class HoldEaseTests(unittest.TestCase):
    def test_hold_then_move(self):
        self.assertEqual(shaped_ease(0.0), 0.0)
        self.assertGreater(shaped_ease(0.08), 0.01)
        push = camera_path("push_in", 100, yaw=1)
        self.assertGreater(abs(push[0][2] - push[4][2]), 1.0)

    def test_speed_ramp_rests(self):
        self.assertEqual(speed_ramp(0.0), 0.0)
        self.assertEqual(speed_ramp(1.0), 1.0)
        self.assertAlmostEqual(ramp_velocity(0.0), 0.0, places=6)
        self.assertEqual(ramp_velocity(1.0), 0.0)
        self.assertEqual(ramp_velocity(1.0 - HOLD_OUT), 0.0)
        self.assertGreater(ramp_velocity(0.5), 0.0)


class WanatahPlanTests(unittest.TestCase):
    def test_wanatah_override(self):
        from photomotion.classify import classify_items
        from photomotion.plan import plan_tour

        names = [f"{i:03d}.jpg" for i in list(range(1, 16)) + [17]]
        items = classify_items(names)
        front = next(x for x in items if x["filename"] == "001.jpg")
        self.assertEqual(front["room"], "exterior_front")
        self.assertEqual(front["role"], "hero_open")
        bath = next(x for x in items if x["filename"] == "010.jpg")
        self.assertTrue(bath["skip"])
        plan = plan_tour(items)
        self.assertGreaterEqual(plan["clip_count"], 8)
        self.assertLessEqual(plan["clip_count"], 11)
        self.assertEqual(plan["clips"][0]["motion"], "push_in")
        self.assertTrue(any(c["motion"] == "orbit" for c in plan["clips"]))
        self.assertTrue(any(c["motion"] == "pull_out" for c in plan["clips"]))
        allowed = {"push_in", "orbit", "static", "pull_out", "ken_burns"}
        prev = None
        for c in plan["clips"]:
            self.assertIn(c["motion"], allowed)
            self.assertIn("yaw", c)
            self.assertIn("focal", c)
            if prev and c["motion"] != "static" and prev != "static":
                self.assertNotEqual(c["motion"], prev)
            prev = c["motion"]



class MusicCatalogTests(unittest.TestCase):
    def test_beds_ban_old_defaults(self):
        from photomotion.music import catalog, DEFAULT_TRACK_ID, resolve_track

        beds = catalog()
        ids = {t["id"] for t in beds}
        self.assertEqual(ids, {"easy-lemon", "wallpaper", "carefree", "funkorama"})
        self.assertEqual(DEFAULT_TRACK_ID, "easy-lemon")
        self.assertEqual(resolve_track(None)["id"], "easy-lemon")
        self.assertEqual(resolve_track("hidden-agenda")["id"], "easy-lemon")
        self.assertEqual(resolve_track("backbay-lounge")["id"], "funkorama")
        self.assertEqual(resolve_track("air-prelude")["id"], "easy-lemon")

    def test_cuts_land_on_bars(self):
        from photomotion.beats import snap_clip_durations

        beats = {"bpm": 96.0, "beat_interval": 0.625, "phase": 0.4}
        clips = [{"room": "exterior_front", "role": "hero_open"}] + [
            {"room": "living"} for _ in range(10)
        ]
        snaps = snap_clip_durations(clips, beats, target_total=30.0)
        self.assertEqual(len(snaps), 11)
        for s in snaps:
            self.assertEqual(s["beats"] % 4, 0)
            self.assertGreaterEqual(s["beats"], 4)
        total = snaps[-1]["start"] + snaps[-1]["duration_s"]
        self.assertGreaterEqual(total, 27.0)
        self.assertLessEqual(total, 36.0)


class DryRunI2VTests(unittest.TestCase):
    def test_dry_run_writes_no_video_api_and_falls_back(self):
        calls = {"start": 0}

        def boom(*_a, **_k):
            calls["start"] += 1
            raise AssertionError("video API must not be called in dry-run")

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "clip.mp4"
            sidecar = Path(td) / "side.json"
            proxy = Path(td) / "p.jpg"
            Image.new("RGB", (64, 64), (20, 20, 20)).save(proxy)

            def kb(d=dest):
                d.write_bytes(b"KB")

            with patch("photomotion.i2v.start_generation", boom):
                result = generate_or_fallback(
                    still_hash="abc",
                    proxy=proxy,
                    dest=dest,
                    sidecar_path=sidecar,
                    prompt="nope",
                    dry_run=True,
                    confirm_live=True,
                    spend_cap=5,
                    already_spent=0,
                    api_key="sk-should-not-use",
                    kenburns_fn=kb,
                )
            self.assertTrue(result.fallback)
            self.assertEqual(dest.read_bytes(), b"KB")
            self.assertEqual(calls["start"], 0)
            data = json.loads(sidecar.read_text())
            self.assertNotIn("sk-should-not-use", json.dumps(data))
            self.assertIn("dry-run", data["reason"])


class FallbackTests(unittest.TestCase):
    def test_api_error_falls_back_to_kenburns_and_is_success(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "clip.mp4"
            sidecar = Path(td) / "side.json"
            proxy = Path(td) / "p.jpg"
            Image.new("RGB", (32, 32)).save(proxy)

            def kb(d=dest):
                d.write_bytes(b"FALLBACK")

            with patch(
                "photomotion.i2v.start_generation", side_effect=RuntimeError("api down")
            ):
                result = generate_or_fallback(
                    still_hash="x",
                    proxy=proxy,
                    dest=dest,
                    sidecar_path=sidecar,
                    prompt="p",
                    dry_run=False,
                    confirm_live=True,
                    spend_cap=5,
                    already_spent=0,
                    api_key="k",
                    kenburns_fn=kb,
                )
            self.assertTrue(result.ok)
            self.assertTrue(result.fallback)
            self.assertEqual(dest.read_bytes(), b"FALLBACK")


class OriginalsTests(unittest.TestCase):
    def test_originals_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "INBOX"
            job = Path(td) / "job"
            inbox.mkdir()
            src = inbox / "a.jpg"
            Image.new("RGB", (64, 48), (200, 180, 160)).save(src, "JPEG")
            before = sha256_file(src)
            mtime = src.stat().st_mtime
            hashes = ingest(inbox, job)
            self.assertEqual(hashes["items"][0]["sha256"], before)
            self.assertEqual(originals_untouched(hashes), [])
            self.assertEqual(sha256_file(src), before)
            self.assertEqual(src.stat().st_mtime, mtime)
            # SOURCE is a copy
            source = job / "SOURCE" / "a.jpg"
            self.assertTrue(source.exists())
            self.assertTrue(source.stat().st_mode & 0o444)


class OverlayTests(unittest.TestCase):
    def test_address_card_has_no_watermark(self):
        from photomotion.overlays import write_address_card

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "a.png"
            write_address_card(dest, "14465 Garden Wy", "Cedar Lake, IN")
            self.assertTrue(dest.exists())
            with Image.open(dest) as im:
                self.assertEqual(im.mode, "RGBA")
                self.assertEqual(im.size, (1920, 1080))

    def test_no_disclosure_constant(self):
        import photomotion.constants as c

        self.assertFalse(hasattr(c, "DISCLOSURE"))

    def test_three_aspect_names(self):
        names = {
            "master_16x9_clean.mp4",
            "vertical_9x16_clean.mp4",
            "square_1x1_clean.mp4",
        }
        self.assertEqual(len(names), 3)


class AuthStoreTests(unittest.TestCase):
    def test_from_env_mode_600_and_status_hides_key(self):
        import os
        from unittest.mock import patch

        from photomotion.auth import clear_credentials, resolve_api_key, save_from_env, status

        secret = "sk-test-never-print-this-value"
        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "PHOTOMOTION_HOME": str(Path(td) / ".photomotion"),
                "XAI_API_KEY": secret,
            }
            with patch.dict(os.environ, env, clear=False):
                rec = save_from_env()
                self.assertTrue(rec["configured"])
                path = Path(rec["path"])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                dumped = json.dumps(status())
                self.assertNotIn(secret, dumped)
                self.assertTrue(status()["from_file"])
                self.assertEqual(resolve_api_key(), secret)
                clear_credentials()
                with patch.dict(os.environ, {"XAI_API_KEY": ""}, clear=False):
                    self.assertIsNone(resolve_api_key())

    def test_cli_status_does_not_echo_key(self):
        import io
        import os
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from photomotion.cli import main

        secret = "sk-cli-secret-xyz"
        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "PHOTOMOTION_HOME": str(Path(td) / ".photomotion"),
                "XAI_API_KEY": secret,
            }
            with patch.dict(os.environ, env, clear=False):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = main(["auth", "--status"])
                self.assertEqual(code, 0)
                self.assertNotIn(secret, buf.getvalue())
                self.assertIn("configured", buf.getvalue())


class LoginAuthTests(unittest.TestCase):
    def test_login_stores_key_and_never_prints(self):
        import os
        from unittest.mock import patch

        from photomotion.auth import login_interactive, resolve_api_key, status

        secret = "sk-login-never-print-this"
        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "PHOTOMOTION_HOME": str(Path(td) / ".photomotion"),
                "XAI_API_KEY": "",
            }
            with patch.dict(os.environ, env, clear=False):
                rec = login_interactive(open_browser=False, prompt_fn=lambda: secret)
                self.assertTrue(rec["configured"])
                path = Path(rec["path"])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                dumped = json.dumps(status())
                self.assertNotIn(secret, dumped)
                self.assertEqual(resolve_api_key(), secret)
                self.assertEqual(status()["source"], "login")

    def test_login_opens_console(self):
        import os
        from unittest.mock import patch

        from photomotion.auth import CONSOLE_URL, login_interactive

        secret = "sk-browser-open-key"
        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "PHOTOMOTION_HOME": str(Path(td) / ".photomotion"),
                "XAI_API_KEY": "",
            }
            opened = []
            with patch.dict(os.environ, env, clear=False):
                with patch("photomotion.auth.webbrowser.open", side_effect=lambda url: opened.append(url)):
                    login_interactive(open_browser=True, prompt_fn=lambda: secret)
            self.assertEqual(opened, [CONSOLE_URL])

    def test_cli_login_does_not_echo_key(self):
        import io
        import os
        from contextlib import redirect_stdout, redirect_stderr
        from unittest.mock import patch

        from photomotion.cli import main

        secret = "sk-cli-login-secret-xyz"
        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "PHOTOMOTION_HOME": str(Path(td) / ".photomotion"),
                "XAI_API_KEY": "",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("photomotion.auth.webbrowser.open", return_value=True):
                    with patch("photomotion.auth.getpass.getpass", return_value=secret):
                        out = io.StringIO()
                        err = io.StringIO()
                        with redirect_stdout(out), redirect_stderr(err):
                            code = main(["auth", "--login"])
                self.assertEqual(code, 0)
                blob = out.getvalue() + err.getvalue()
                self.assertNotIn(secret, blob)
                self.assertIn("configured", out.getvalue())

    def test_empty_login_fails(self):
        import os
        from unittest.mock import patch

        from photomotion.auth import AuthError, login_interactive

        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "PHOTOMOTION_HOME": str(Path(td) / ".photomotion"),
                "XAI_API_KEY": "",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaises(AuthError):
                    login_interactive(open_browser=False, prompt_fn=lambda: "   ")


class DoctorTests(unittest.TestCase):
    def test_ffmpeg_present_in_this_environment(self):
        from photomotion.job import doctor, ffmpeg_status

        rec = ffmpeg_status()
        self.assertIn("ok", rec)
        self.assertIn("path", rec)
        doc = doctor()
        self.assertIn("ffmpeg", doc)
        self.assertTrue(doc["numpy"])
        self.assertTrue(doc["pillow"])
        dumped = json.dumps(doc)
        self.assertNotIn("sk-", dumped)

    def test_cli_check_json(self):
        import io
        from contextlib import redirect_stdout

        from photomotion.cli import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["check"])
        payload = json.loads(buf.getvalue())
        self.assertIn("ffmpeg", payload)
        self.assertIn("auth", payload)
        self.assertIn(code, {0, 1})


if __name__ == "__main__":
    unittest.main()

