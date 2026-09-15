#!/usr/bin/env bash
# One command to make this box a TV DIABLO Linux seat.
#   bash install.sh            # deps + pin the console + stage UI + a first self-test
#   CONSOLE_REF=9f4f1d0e4c1e189cb83abbaf5c43b874de8819a5 bash install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# ⚠ The org is KonyoDigital. A prior "say the owner rather than a name" rewrite
# turned that URL into `the ownerDigital` and broke a fresh clone.
CONSOLE_REPO="${CONSOLE_REPO:-https://github.com/KonyoDigital/d2r-bible-tests.git}"
CONSOLE_REF="${CONSOLE_REF:-main}"

# Noninteractive by default: fuse.conf / tzdata / needrestart must not hang a fresh box.
export DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-noninteractive}"
export DEBCONF_NONINTERACTIVE_SEEN="${DEBCONF_NONINTERACTIVE_SEEN:-true}"
export NEEDRESTART_MODE="${NEEDRESTART_MODE:-l}"
export UCF_FORCE_CONFFOLD="${UCF_FORCE_CONFFOLD:-1}"
export APT_LISTCHANGES_FRONTEND="${APT_LISTCHANGES_FRONTEND:-none}"
export GIT_TERMINAL_PROMPT=0

if [ -f "$ROOT/seat.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/seat.env"
  set +a
fi

_apt() {
  sudo DEBIAN_FRONTEND=noninteractive \
    DEBCONF_NONINTERACTIVE_SEEN=true \
    UCF_FORCE_CONFFOLD=1 \
    NEEDRESTART_MODE=l \
    apt-get -y \
      -o Dpkg::Options::=--force-confdef \
      -o Dpkg::Options::=--force-confold \
      "$@"
}

echo "── system deps (pywebview needs GTK + WebKit; the bridge needs only python3)"
if command -v apt-get >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a || true
  _apt update -qq
  _apt install python3 python3-pip python3-gi gir1.2-gtk-3.0 \
       gir1.2-webkit2-4.1 libcairo2-dev rsync git || \
  _apt install python3 python3-pip python3-gi gir1.2-gtk-3.0 \
       gir1.2-webkit2-4.0 libcairo2-dev rsync git
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3 python3-pip python3-gobject gtk3 webkit2gtk4.1 rsync git
else
  echo "   ⚠ unknown package manager — install python3, GTK3, WebKit2GTK, rsync and git by hand"
fi

echo "── the console itself is NOT in this repo, deliberately."
# ⚠ ONE SOURCE. control_app.py imports 57 local modules; a copy here would be a second console
# that must stay in step with the Mac's and eventually would not. It is PINNED, not vendored,
# and vendor/ is gitignored so this repo never carries a fork of it. [[copy-drift]]
mkdir -p "$ROOT/vendor"
DEST="$ROOT/vendor/d2r-bible-tests"
if [ ! -d "$DEST/.git" ]; then
  git clone --depth 1 "$CONSOLE_REPO" "$DEST"
fi
if git -C "$DEST" fetch --depth 1 origin "$CONSOLE_REF"; then
  git -C "$DEST" checkout -q --detach FETCH_HEAD
else
  echo "   ⚠ could not fetch CONSOLE_REF=$CONSOLE_REF — leaving the existing pin"
fi
echo "   pinned: $(git -C "$DEST" rev-parse --short HEAD)  ($CONSOLE_REPO @$CONSOLE_REF)"

echo "── stage the HTML the bridge serves (Mac JSON-only seeds do not include it)"
bash "$ROOT/bin/tvd-stage-ui"

echo "── start the seat so doctor can talk to it"
bash "$ROOT/bin/tvd-guest" || true

echo "── self-test"
bash "$ROOT/bin/tvd-doctor" || {
  echo "   doctor is not green yet — that is expected before the first sync."
  echo "   On the MAC:  GUEST_BOX_HOST=<this-box> GUEST_BOX_PATH=$ROOT/api-live bash tv/sync_guest_api.sh --to-box"
  echo "   Then here:   bin/tvd-guest && bin/tvd-doctor"
}
echo "── done. Start the seat:  bin/tvd-guest"
