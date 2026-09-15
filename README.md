# tvd-linux — the TV DIABLO Linux seat

A Linux box that can **look at** TV DIABLO: open THE SHELF, click a session, scrub a reel, open
the VAULT — against real data, without touching the Mac that owns it.

Built so the visual agent's eyes can run standing verification on this machine, and so **other people can
work on the Linux side** without going through the main repo's 12-minute publish gate.

---

## The console is deliberately NOT in this repo

`d2r-bible-tests/tv/control_app.py` imports **57 local modules**; the tree is 551 Python files.
A copy here would be a second console that must stay in step with the first and eventually would
not — so `install.sh` **pins** it into `vendor/` (gitignored) instead. One source, upstream.

**This repo owns:** the launcher, the systemd unit, the read-only guest bridge, the doctor, the
UI staging step, and the docs. That is the whole Linux-specific surface, and it is all anyone
needs to contribute to.

---

## Install (fresh box)

```bash
git clone https://github.com/KonyoDigital/tvd-linux.git
cd tvd-linux && bash install.sh          # noninteractive deps + pin + stage UI + self-test
bin/tvd-guest                            # start the seat on 127.0.0.1:18772
bin/tvd-doctor                           # must be green before any drive
```

`install.sh` is **noninteractive by default** (`DEBIAN_FRONTEND=noninteractive`, apt
`force-confdef`/`force-confold`). It will not hang on `fuse.conf`. `apt update` retries on a
transient Debian-mirror **502** and does **not** abort the rest of install (pin → stage → guest)
if `python3`, `git` and `rsync` are already present. Pin a known console with
`CONSOLE_REF=<sha-or-branch> bash install.sh` (v3189 is commit `9f4f1d0e4c1e189cb83abbaf5c43b874de8819a5`
on `KonyoDigital/d2r-bible-tests`).

Seat laws (no network, no apt): `python3 -m unittest tests.test_linux_seat -v`

Run it at boot:

```bash
mkdir -p ~/.config/systemd/user && cp systemd/tvd-guest.service ~/.config/systemd/user/
systemctl --user enable --now tvd-guest
```

If the clone is not at `~/tvd-linux`, edit `ExecStart` / `EnvironmentFile` in the unit to match.

---

## Feeding it — on the **Mac**, then one restage here

```bash
GUEST_BOX_HOST=<this-box> GUEST_BOX_PATH=<clone>/api-live bash tv/sync_guest_api.sh --to-box
```

Then on this box:

```bash
bin/tvd-guest && bin/tvd-doctor
```

`tvd-guest` runs `bin/tvd-stage-ui` first. That is required: the Mac script mirrors JSON (and a
scrubbed `board.html` when live `/board` answered) but **does not copy `control_ui.html`**. A
JSON-only seed therefore left the bridge serving 503 for `/`. Staging copies:

| dest | source |
|---|---|
| `api-live/control_ui.html` | `vendor/d2r-bible-tests/tv/control_ui.html` (always) |
| `api-live/board.html` | kept if already present; else `vendor/.../bible.html` (live `/board`) |
| `api-live/api/sessions.json` | moved here if the seed dropped `sessions.json` at the mirror root |

The doctor reads **nested** `api-live/api/sessions.json`. `rsync --delete` from a JSON-only Mac
mirror can wipe staged HTML; starting `bin/tvd-guest` puts it back.

That mirrors the read-only endpoints, scrubs every one of the owner's machine identifiers,
restages the fixture packs, runs a leak gate, and only then copies. Measured on a real run:
**12 endpoints, 419 sessions, 300 tombstone rows**, clean against 7 secrets.

---

## Identity — Cursor by default, Grok only when selected

The bridge used to hardcode `Grok` / `grok-bot` / `guest: true`. That is the **Grok Bot** box,
not this seat. Default actor is **Cursor** / `cursor` / `guest: false`.

Override with env or a repo-root `seat.env` (copy `seat.env.example`; gitignored):

```bash
# Cursor (default) — fleet machine `cursor`
GUEST_NICKNAME=Cursor GUEST_COMPUTER=cursor GUEST_SEAT_GUEST=0 bin/tvd-guest

# Grok guest profile — only when that seat is intentionally selected
GUEST_NICKNAME=Grok GUEST_COMPUTER=grok-bot GUEST_USER=grok GUEST_SEAT_GUEST=1 bin/tvd-guest
```

`bin/tvd-doctor` asserts the configured nickname and `identity.guest`, not a hardcoded Grok label.

To appear in THE FLEET under a nickname on a machine that runs the **full** console (`:17772`,
not this read-only bridge):

```bash
curl -X POST http://127.0.0.1:17772/api/identity_name \
  -H 'Content-Type: application/json' -d '{"name":"Cursor"}'
```

The guest bridge on `:18772` refuses that POST (405). Its identity is env / `seat.env` only.

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

## Diablo — re-run install / doctor / eyes

On this box:

```bash
cd <clone>
bash install.sh                 # safe to re-run; noninteractive; restages UI
bin/tvd-guest                   # restage HTML + listen on 127.0.0.1:18772
bin/tvd-doctor                  # all green, then eyes
```

On the Mac, once per seed (or whenever live should refresh the mirror):

```bash
GUEST_BOX_HOST=<this-box> GUEST_BOX_PATH=<clone>/api-live bash tv/sync_guest_api.sh --to-box
```

Then `bin/tvd-guest && bin/tvd-doctor` again here. Do not point eyes at `:18772` until doctor is
green.

---

## Never committed

`api-live/`, `guest-mirror/`, `fixtures/`, `seed_progress.json`, `verify-evidence/`, `seat.env`.

They are cut from the owner's live console — his ledger, his sessions, real frames of his game.
Scrubbed of his machine's *identifiers* is not the same as being his to *publish*, and this repo
is public. They arrive by rsync, never by git.
