#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THE GUEST BRIDGE — TV DIABLO's Linux seat, served read-only from a mirror.

This machine drives TV DIABLO at http://127.0.0.1:18772/ against a MIRROR of the owner's
live console. It never reaches his Mac, and it cannot write anything anywhere.

The actor this seat reports as is CONFIG, not a hardcoded Grok label. Default is Cursor
(fleet machine `cursor`). The Grok / guest:true profile is opt-in via env / seat.env.

═══ WHAT THIS IS NOT ══════════════════════════════════════════════════════════════════════════

It is NOT the console. The console is ~57 interlocked Python modules in `d2r-bible-tests/tv/`,
and copying it here would make two consoles that must stay in step and eventually would not.
This serves static, already-scrubbed JSON and HTML that the Mac produced — plus UI chrome
staged from the pinned console when a JSON-only seed did not include it.

    Mac:  bash tv/sync_guest_api.sh --to-box     ->  api-live/
    Here: bin/tvd-stage-ui then this bridge serves api-live/ at :18772

═══ READ-ONLY BY CONSTRUCTION, NOT BY INTENTION ═══════════════════════════════════════════════

⚠ There is no write path in this file at all: no POST, no PUT, no DELETE, no subprocess, no file
open in any write mode. A guest seat that could register an item or delete a reel would let an
eyes-loop change what the owner owns, and footage has no un-delete. The Mac's sync refuses to mirror
a write endpoint; this refuses to serve a write METHOD. Two locks, different keys.

⚠ AND AN ABSENT MIRROR IS SAID OUT LOUD. If `api-live/` has not been synced, every endpoint
answers with an explicit `NEED_SYNC` record rather than `{}` or `[]`. An empty vault and an
unsynced vault look identical on screen and only one of them means "you own nothing" — the guest
reported exactly that confusion before this existed. [[zero-needs-a-denominator]]
"""
import hashlib
import http.server
import io
import json
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MIRROR = os.environ.get("GUEST_MIRROR", os.path.join(ROOT, "api-live"))
PORT = int(os.environ.get("GUEST_PORT", "18772"))
VENDOR = os.path.join(ROOT, "vendor", "d2r-bible-tests")

ALLOWED_SUFFIX = (".json", ".html", ".jpg", ".png", ".css", ".js", ".svg", ".ico")

_SEAT_ENV_LOADED = False


def _truthy(val):
    return str(val or "").strip().lower() in ("1", "true", "yes", "on")


def _load_seat_env():
    """Load repo-root seat.env into os.environ without overriding a real environment."""
    global _SEAT_ENV_LOADED
    if _SEAT_ENV_LOADED:
        return
    _SEAT_ENV_LOADED = True
    path = os.path.join(ROOT, "seat.env")
    if not os.path.isfile(path):
        return
    with io.open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def seat_identity():
    """The actor this seat reports as. Env / seat.env win; Cursor is the default.

    Grok / grok-bot / guest:true is the original Grok Bot profile — set it explicitly,
    do not inherit it as a lie on a Cursor box.
    """
    _load_seat_env()
    computer = (os.environ.get("GUEST_COMPUTER") or "cursor").strip() or "cursor"
    nickname = (os.environ.get("GUEST_NICKNAME") or "Cursor").strip() or "Cursor"
    user = (os.environ.get("GUEST_USER") or computer).strip() or computer
    platform = (os.environ.get("GUEST_PLATFORM") or "linux").strip() or "linux"
    ident_id = (os.environ.get("GUEST_ID") or "").strip()
    if not ident_id:
        ident_id = hashlib.sha256(
            ("tv-diablo-guest-seat/%s/v1" % computer).encode("utf-8")
        ).hexdigest()[:32]
    return {
        "id": ident_id,
        "computer": computer,
        "user": user,
        "platform": platform,
        "createdAt": "2026-09-15T00:00:00",
        "nickname": nickname,
        "guest": _truthy(os.environ.get("GUEST_SEAT_GUEST", "0")),
    }


def _need_sync(what):
    return {
        "ok": False, "guest": True, "unreadable": True, "needSync": True, "what": what,
        "why": ("this guest has no mirror for %s yet — run `bash tv/sync_guest_api.sh --to-box` "
                "on the Mac, then `bin/tvd-stage-ui` here. This is NOT an empty result: "
                "nothing has been read here." % what),
    }


def _safe(rel):
    """Contain every path to the mirror. A guest that can read ../.. is a file server for the box."""
    p = os.path.realpath(os.path.join(MIRROR, rel.lstrip("/")))
    root = os.path.realpath(MIRROR)
    return p if (p == root or p.startswith(root + os.sep)) else None


def _vendor_file(*rel_parts):
    """Public UI chrome from the pinned console — never a path the caller chose."""
    vendor_root = os.path.realpath(VENDOR)
    p = os.path.realpath(os.path.join(VENDOR, *rel_parts))
    if not p.startswith(vendor_root + os.sep):
        return None
    return p if os.path.isfile(p) else None


def _ui_path(mirror_name, vendor_candidates):
    """Mirror file first (Mac-synced board is scrubbed live HTML); vendor pin if the seed was JSON-only."""
    p = _safe(mirror_name)
    if p and os.path.isfile(p):
        return p
    for rel in vendor_candidates:
        vp = _vendor_file(*rel.split("/"))
        if vp:
            return vp
    return None


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

        # identity is answered from THIS process, never from the mirror: a mirror that failed
        # to sync must not be able to make the seat answer as someone else. The actor is env.
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
            ident = seat_identity()
            out["identity"] = dict(ident)
            out["guest"] = bool(ident.get("guest"))
            self._json(200, out)
            return

        if path in ("/", "/index.html", "/control_ui.html"):
            p = _ui_path("control_ui.html", ("tv/control_ui.html",))
            if p:
                self._file(p, "text/html; charset=utf-8")
            else:
                self._json(503, _need_sync("control_ui.html"))
            return

        if path in ("/board", "/board.html"):
            p = _ui_path("board.html", ("tv/board.html", "bible.html"))
            if p:
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
    _load_seat_env()
    ident = seat_identity()
    if not os.path.isdir(MIRROR):
        sys.stderr.write("[guest] no mirror at %s — serving NEED_SYNC for everything.\n"
                         "        On the Mac: bash tv/sync_guest_api.sh --to-box\n" % MIRROR)
    # loopback only: this seat is for the eyes on THIS box, never for the network
    with Server(("127.0.0.1", PORT), Bridge) as httpd:
        sys.stderr.write("[guest] TV DIABLO Linux seat on http://127.0.0.1:%d/  (mirror: %s)\n"
                         "        identity: %s / %s  guest=%s\n"
                         % (PORT, MIRROR, ident.get("nickname"), ident.get("computer"),
                            ident.get("guest")))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
