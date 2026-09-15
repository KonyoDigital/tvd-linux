# tvd-linux — the TV DIABLO Linux seat

A Linux box that can **look at** TV DIABLO: open THE SHELF, click a session, scrub a reel, open
the VAULT — against real data, without touching the Mac that owns it.

Built so Grok Bot's eyes can run standing verification on this machine, and so **other people can
work on the Linux side** without going through the main repo's 12-minute publish gate.

---

## The console is deliberately NOT in this repo

`d2r-bible-tests/tv/control_app.py` imports **57 local modules**; the tree is 551 Python files.
A copy here would be a second console that must stay in step with the first and eventually would
not — so `install.sh` **pins** it into `vendor/` (gitignored) instead. One source, upstream.

**This repo owns:** the launcher, the systemd unit, the read-only guest bridge, the doctor, and
the docs. That is the whole Linux-specific surface, and it is all anyone needs to contribute to.

---

## Install

```bash
git clone https://github.com/KonyoDigital/tvd-linux.git
cd tvd-linux && bash install.sh          # deps + pin the console + self-test
bin/tvd-guest                            # start the seat on 127.0.0.1:18772
bin/tvd-doctor                           # must be green before any drive
```

Run it at boot:

```bash
mkdir -p ~/.config/systemd/user && cp systemd/tvd-guest.service ~/.config/systemd/user/
systemctl --user enable --now tvd-guest
```

---

## Feeding it — on the **Mac**, not here

```bash
GUEST_BOX_HOST=<this-box> bash tv/sync_guest_api.sh --to-box
```

That mirrors the read-only endpoints, scrubs every one of the owner's machine identifiers,
restages the fixture packs, runs a leak gate, and only then copies. Measured on a real run:
**12 endpoints, 419 sessions, 300 tombstone rows**, clean against 7 secrets.

---

## Why writes are impossible here, twice over

| lock | where | what it stops |
|---|---|---|
| allowlist | Mac (`sync_guest_api.sh`) | `vault_apply`, `chronicle_apply`, `board_tick`, `session/delete`, `relaunch`… are never **mirrored** |
| method | here (`guest_bridge.py`) | `POST` / `PUT` / `DELETE` / `PATCH` all answer **405** |

`guest_bridge.py` contains no write-mode `open`, no `subprocess`, and no filesystem mutation —
verifiable by parsing it, not by trusting this sentence. An eyes-loop must never be able to
change what the owner owns, and footage has no un-delete.

---

## An unsynced mirror says so

Every endpoint without a mirror answers `needSync: true` with a reason — never `{}` or `[]`.
An empty vault and an unsynced vault look identical on screen and only one of them means "you own
nothing". `bin/tvd-doctor` treats **0 sessions as a FAILURE**, because painting SHELF from hollow
data and calling it smooth is the thing this seat exists to avoid.

---

## What this box shows as

A stable Grok actor: `Grok` / `grok-bot` / `guest: true`. The board itself runs in the **isolated
non-Mac world** — a seeded copy that can diverge freely (own less, own more) without ever
reaching the owner's namespace. Seed it from `seed_progress.json` via the board's own
**Tools → Backup → Import**.

To appear in THE FLEET as `Grok` rather than this machine's hostname, on this box's **own**
console:

```bash
curl -X POST http://127.0.0.1:17772/api/identity_name \
  -H 'Content-Type: application/json' -d '{"name":"Grok"}'
```

---

## Never committed

`api-live/`, `guest-mirror/`, `fixtures/`, `seed_progress.json`, `verify-evidence/`.

They are cut from the owner's live console — his ledger, his sessions, real frames of his game.
Scrubbed of his machine's *identifiers* is not the same as being his to *publish*, and this repo
is public. They arrive by rsync, never by git.
