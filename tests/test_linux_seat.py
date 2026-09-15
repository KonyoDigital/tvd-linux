#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Laws for a fresh Linux seat: install defaults, identity, HTML staging, doctor green."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import guest_bridge as gb  # noqa: E402


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class InstallSh(unittest.TestCase):
    def test_console_repo_is_konyo_digital_not_the_owner_typo(self):
        src = _read("install.sh")
        self.assertRegex(
            src,
            r'CONSOLE_REPO="\$\{CONSOLE_REPO:-https://github\.com/KonyoDigital/d2r-bible-tests\.git\}"',
            "CONSOLE_REPO default must be the real org — a name-rewrite once broke it",
        )
        readme = _read("README.md")
        self.assertIn("https://github.com/KonyoDigital/tvd-linux.git", readme)
        self.assertNotIn("the ownerDigital", readme)

    def test_apt_is_noninteractive_and_force_confold(self):
        src = _read("install.sh")
        self.assertIn("DEBIAN_FRONTEND", src)
        self.assertIn("noninteractive", src)
        self.assertIn("force-confold", src)
        self.assertIn("force-confdef", src)
        self.assertIn("dpkg --configure -a", src)

    def test_install_stages_ui_and_starts_the_seat(self):
        src = _read("install.sh")
        self.assertIn("bin/tvd-stage-ui", src)
        self.assertIn("bin/tvd-guest", src)


class Identity(unittest.TestCase):
    def setUp(self):
        gb._SEAT_ENV_LOADED = True  # skip seat.env; tests own the env
        self._saved = {k: os.environ.get(k) for k in list(os.environ) if k.startswith("GUEST_")}
        for k in list(self._saved):
            del os.environ[k]

    def tearDown(self):
        for k in list(os.environ):
            if k.startswith("GUEST_"):
                del os.environ[k]
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_is_cursor_not_grok_guest(self):
        ident = gb.seat_identity()
        self.assertEqual(ident["nickname"], "Cursor")
        self.assertEqual(ident["computer"], "cursor")
        self.assertIs(ident["guest"], False)
        self.assertEqual(ident["id"], "05a80969e8afcb209541d8f39002f064")

    def test_grok_guest_is_opt_in(self):
        os.environ["GUEST_NICKNAME"] = "Grok"
        os.environ["GUEST_COMPUTER"] = "grok-bot"
        os.environ["GUEST_USER"] = "grok"
        os.environ["GUEST_SEAT_GUEST"] = "1"
        ident = gb.seat_identity()
        self.assertEqual(ident["nickname"], "Grok")
        self.assertEqual(ident["computer"], "grok-bot")
        self.assertIs(ident["guest"], True)
        self.assertEqual(ident["id"], "4af27ed51bf8693eaa3c19df86fc7b67")

    def test_bridge_has_no_write_open_or_subprocess(self):
        src = _read("guest_bridge.py")
        self.assertNotIn("import subprocess", src)
        self.assertNotRegex(src, r"open\([^)]*['\"]w")
        self.assertIn("do_POST = do_PUT = do_DELETE = do_PATCH = _refuse", src)


class StageUi(unittest.TestCase):
    def test_json_only_seed_gets_html_and_nested_sessions(self):
        tmp = tempfile.mkdtemp(prefix="tvd-stage-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        vendor = os.path.join(tmp, "vendor")
        mirror = os.path.join(tmp, "api-live")
        os.makedirs(os.path.join(vendor, "tv"))
        io.open(os.path.join(vendor, "tv", "control_ui.html"), "w", encoding="utf-8").write(
            "<html>control</html>"
        )
        io.open(os.path.join(vendor, "bible.html"), "w", encoding="utf-8").write(
            "<html>board</html>"
        )
        os.makedirs(mirror)
        io.open(os.path.join(mirror, "sessions.json"), "w", encoding="utf-8").write(
            json.dumps({"sessions": [{"id": "s1"}, {"id": "s2"}]})
        )
        env = os.environ.copy()
        env["GUEST_MIRROR"] = mirror
        env["GUEST_VENDOR"] = vendor
        subprocess.check_call(
            ["bash", os.path.join(ROOT, "bin/tvd-stage-ui")],
            env=env, cwd=ROOT,
        )
        self.assertTrue(os.path.isfile(os.path.join(mirror, "control_ui.html")))
        self.assertTrue(os.path.isfile(os.path.join(mirror, "board.html")))
        self.assertTrue(os.path.isfile(os.path.join(mirror, "api", "sessions.json")))
        data = json.load(io.open(os.path.join(mirror, "api", "sessions.json"), encoding="utf-8"))
        self.assertEqual(len(data["sessions"]), 2)

    def test_existing_board_is_not_overwritten(self):
        tmp = tempfile.mkdtemp(prefix="tvd-stage-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        vendor = os.path.join(tmp, "vendor")
        mirror = os.path.join(tmp, "api-live")
        os.makedirs(os.path.join(vendor, "tv"))
        io.open(os.path.join(vendor, "tv", "control_ui.html"), "w", encoding="utf-8").write("NEW")
        io.open(os.path.join(vendor, "bible.html"), "w", encoding="utf-8").write("VENDOR-BOARD")
        os.makedirs(os.path.join(mirror, "api"))
        io.open(os.path.join(mirror, "board.html"), "w", encoding="utf-8").write("MAC-SCRUBBED")
        io.open(os.path.join(mirror, "api", "sessions.json"), "w", encoding="utf-8").write(
            json.dumps({"sessions": [{"id": "s1"}]})
        )
        env = os.environ.copy()
        env["GUEST_MIRROR"] = mirror
        env["GUEST_VENDOR"] = vendor
        subprocess.check_call(["bash", os.path.join(ROOT, "bin/tvd-stage-ui")], env=env, cwd=ROOT)
        board = io.open(os.path.join(mirror, "board.html"), encoding="utf-8").read()
        self.assertEqual(board, "MAC-SCRUBBED")


class DoctorGreen(unittest.TestCase):
    def test_fresh_json_seed_plus_stage_leaves_doctor_green(self):
        tmp = tempfile.mkdtemp(prefix="tvd-doc-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        vendor = os.path.join(tmp, "vendor")
        mirror = os.path.join(tmp, "api-live")
        os.makedirs(os.path.join(vendor, "tv"))
        os.makedirs(mirror)
        io.open(os.path.join(vendor, "tv", "control_ui.html"), "w", encoding="utf-8").write(
            "<html>control</html>"
        )
        io.open(os.path.join(vendor, "bible.html"), "w", encoding="utf-8").write(
            "<html>board</html>"
        )
        io.open(os.path.join(mirror, "sessions.json"), "w", encoding="utf-8").write(
            json.dumps({"sessions": [{"id": "a"}, {"id": "b"}, {"id": "c"}]})
        )
        port = "18779"
        env = os.environ.copy()
        env["GUEST_MIRROR"] = mirror
        env["GUEST_VENDOR"] = vendor
        env["GUEST_PORT"] = port
        env["GUEST_NICKNAME"] = "Cursor"
        env["GUEST_COMPUTER"] = "cursor"
        env["GUEST_SEAT_GUEST"] = "0"
        subprocess.check_call(["bash", os.path.join(ROOT, "bin/tvd-stage-ui")], env=env, cwd=ROOT)
        proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "guest_bridge.py")],
            env=env, cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        def _stop():
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.addCleanup(_stop)
        url = "http://127.0.0.1:%s/" % port
        for _ in range(20):
            try:
                code = subprocess.check_output(
                    ["curl", "-sS", "-m", "1", "-o", "/dev/null", "-w", "%{http_code}", url],
                    stderr=subprocess.DEVNULL, text=True,
                ).strip()
                if code == "200":
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(0.15)
        else:
            self.fail("bridge did not answer 200 at %s" % url)
        out = subprocess.check_output(
            ["bash", os.path.join(ROOT, "bin/tvd-doctor")],
            env=env, cwd=ROOT, text=True,
        )
        self.assertIn("seat answers", out)
        self.assertIn("identity is Cursor", out)
        self.assertIn("identity.guest=False", out)
        self.assertIn("writes are refused", out)
        self.assertIn("3 session(s)", out)

    def test_vendor_fallback_serves_ui_when_mirror_has_json_only(self):
        tmp = tempfile.mkdtemp(prefix="tvd-fb-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        vendor = os.path.join(tmp, "d2r-bible-tests")
        os.makedirs(os.path.join(vendor, "tv"))
        with io.open(os.path.join(vendor, "tv", "control_ui.html"), "w", encoding="utf-8") as fh:
            fh.write("<html>control</html>")
        with io.open(os.path.join(vendor, "bible.html"), "w", encoding="utf-8") as fh:
            fh.write("<html>board</html>")
        saved_vendor = gb.VENDOR
        gb.VENDOR = vendor
        try:
            p = gb._ui_path("control_ui.html", ("tv/control_ui.html",))
            self.assertTrue(p and os.path.isfile(p), "vendor fallback must find control_ui.html")
            p2 = gb._ui_path("board.html", ("tv/board.html", "bible.html"))
            self.assertTrue(p2 and os.path.isfile(p2), "vendor fallback must find board/bible.html")
        finally:
            gb.VENDOR = saved_vendor


if __name__ == "__main__":
    unittest.main(verbosity=2)
