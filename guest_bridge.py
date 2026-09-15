#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THE GUEST BRIDGE — TV DIABLO's Linux seat, served read-only from a mirror.

Grok Bot drives TV DIABLO on this machine at http://127.0.0.1:18772/ against a MIRROR of Konyo's
live console. It never reaches his Mac, and it cannot write anything anywhere.

═══ WHAT THIS IS NOT ══════════════════════════════════════════════════════════════════════════

It is NOT the console. The console is ~57 interlocked Python modules in `d2r-bible-tests/tv/`,
and copying it here would make two consoles that must stay in step and eventually would not.
This serves static, already-scrubbed JSON and HTML that the Mac produced.

    Mac:  bash tv/sync_guest_api.sh --to-box     ->  api-live/
    Here: this bridge serves api-live/ at :18772

═══ READ-ONLY BY CONSTRUCTION, NOT BY INTENTION ═══════════════════════════════════════════════

⚠ There is no write path in this file at all: no POST, no PUT, no DELETE, no subprocess, no file
open in any write mode. A guest seat that could register an item or delete a reel would let an
eyes-loop change what Konyo owns, and footage has no un-delete. The Mac's sync refuses to mirror
a write endpoint; this refuses to serve a write METHOD. Two locks, different keys.

⚠ AND AN ABSENT MIRROR IS SAID OUT LOUD. If `api-live/` has not been synced, every endpoint
answers with an explicit `NEED_SYNC` record rather than `{}` or `[]`. An empty vault and an
unsynced vault look identical on screen and only one of them means "you own nothing" — the guest
reported exactly that confusion before this existed. [[zero-needs-a-denominator]]
"""
import http.server
import io
import json
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MIRROR = os.environ.get("GUEST_MIRROR", os.path.join(ROOT, "api-live"))
PORT = int(os.environ.get("GUEST_PORT", "18772"))

# The actor this seat reports as. Must match the Mac's tv/guest_profile.py — the box doctor
# asserts identity.nickname == "Grok".
GROK = {
    "id": "4af27ed51bf8693eaa3c19df86fc7b67",
    "computer": "grok-bot",
    "user": "grok",
    "platform": "linux",
    "createdAt": "2026-09-15T00:00:00",
    "nickname": "Grok",
    "guest": True,
}

ALLOWED_SUFFIX = (".json", ".html", ".jpg", ".png", ".css", ".js", ".svg", ".ico")


def _need_sync(what):
    return {
        "ok": False, "guest": True, "unreadable": True, "needSync": True, "what": what,
        "why": ("this guest has no mirror for %s yet — run `bash tv/sync_guest_api.sh --to-box` "
                "on the Mac. This is NOT an empty result: nothing has been read here." % what),
    }


def _safe(rel):
    """Contain every path to the mirror. A guest that can read ../.. is a file server for the box."""
    p = os.path.realpath(os.path.join(MIRROR, rel.lstrip("/")))
    root = os.path.realpath(MIRROR)
    return p if (p == root or p.startswith(root + os.sep)) else None


class Bridge(http.server.BaseHTTPRequestHandler):
    server_version = "tvd-guest-bridge"

    def log_message(self, fmt, *args):
        sys.stderr.write("[guest] %s %s\n" % (self.address_string(), fmt % args))

    # ── every write method, refused by name ───────────────────────────────────────────────────
    def _refuse(self):
        self._json(405, {"ok": False, "guest": True,
                         "why": "the guest seat is read-only: it exists to LOOK at a mirror of "
                                "his console, never to change it"})

    do_POST = do_PUT = do_DELETE = do_PATCH = _refuse

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            self._json(404, _need_sync(os.path.basename(path)))
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = (self.path or "/").split("?", 1)[0].split("#", 1)[0]

        # identity is answered from THIS file, never from the mirror: the doctor's whole job is to
        # prove the seat is Grok, and a mirror that failed to sync must not be able to make it
        # answer as someone else.
        if path == "/api/status":
            p = _safe("api/status.json")
            out = {}
            if p and os.path.isfile(p):
                try:
                    with io.open(p, encoding="utf-8") as fh:
                        out = json.load(fh)
                except Exception:
                    out = {}
            if not isinstance(out, dict):
                out = {}
            if not out:
                out = _need_sync("api/status")
            out["identity"] = dict(GROK)
            out["guest"] = True
            self._json(200, out)
            return

        if path in ("/", "/index.html", "/control_ui.html"):
            p = _safe("control_ui.html")
            if p and os.path.isfile(p):
                self._file(p, "text/html; charset=utf-8")
            else:
                self._json(503, _need_sync("control_ui.html"))
            return

        if path in ("/board", "/board.html"):
            p = _safe("board.html")
            if p and os.path.isfile(p):
                self._file(p, "text/html; charset=utf-8")
            else:
                self._json(503, _need_sync("board.html"))
            return

        if path.startswith("/api/"):
            p = _safe(path[1:] + ".json")
            if p and os.path.isfile(p):
                self._file(p, "application/json; charset=utf-8")
            else:
                self._json(200, _need_sync(path))
            return

        # frames and static assets out of the mirror
        if path.endswith(ALLOWED_SUFFIX):
            p = _safe(path)
            if p and os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                self._file(p, {".json": "application/json", ".html": "text/html; charset=utf-8",
                               ".jpg": "image/jpeg", ".png": "image/png", ".css": "text/css",
                               ".js": "application/javascript", ".svg": "image/svg+xml",
                               ".ico": "image/x-icon"}.get(ext, "application/octet-stream"))
                return
        self._json(404, {"ok": False, "guest": True, "why": "no such thing in the mirror"})


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    if not os.path.isdir(MIRROR):
        sys.stderr.write("[guest] no mirror at %s — serving NEED_SYNC for everything.\n"
                         "        On the Mac: bash tv/sync_guest_api.sh --to-box\n" % MIRROR)
    # loopback only: this seat is for the eyes on THIS box, never for the network
    with Server(("127.0.0.1", PORT), Bridge) as httpd:
        sys.stderr.write("[guest] TV DIABLO guest seat on http://127.0.0.1:%d/  (mirror: %s)\n"
                         % (PORT, MIRROR))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
