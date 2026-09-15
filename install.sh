#!/usr/bin/env bash
# One command to make this box a TV DIABLO Linux seat.
#   bash install.sh            # deps + pin the console + a first self-test
#   CONSOLE_REF=v3189 bash install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CONSOLE_REPO="${CONSOLE_REPO:-https://github.com/the ownerDigital/d2r-bible-tests.git}"
CONSOLE_REF="${CONSOLE_REF:-main}"

echo "── system deps (pywebview needs GTK + WebKit; the bridge needs only python3)"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y python3 python3-pip python3-gi gir1.2-gtk-3.0 \
       gir1.2-webkit2-4.1 libcairo2-dev rsync git || \
  sudo apt-get install -y python3 python3-pip python3-gi gir1.2-gtk-3.0 \
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
if [ -d "$ROOT/vendor/d2r-bible-tests/.git" ]; then
  git -C "$ROOT/vendor/d2r-bible-tests" fetch --depth 1 origin "$CONSOLE_REF" -q
  git -C "$ROOT/vendor/d2r-bible-tests" checkout -q FETCH_HEAD
else
  git clone --depth 1 --branch "$CONSOLE_REF" "$CONSOLE_REPO" \
      "$ROOT/vendor/d2r-bible-tests" 2>/dev/null || \
  git clone --depth 1 "$CONSOLE_REPO" "$ROOT/vendor/d2r-bible-tests"
fi
echo "   pinned: $(git -C "$ROOT/vendor/d2r-bible-tests" rev-parse --short HEAD)"

echo "── self-test"
bash "$ROOT/bin/tvd-doctor" || {
  echo "   doctor is not green yet — that is expected before the first sync."
  echo "   On the MAC:  GUEST_BOX_HOST=<this-box> bash tv/sync_guest_api.sh --to-box"
}
echo "── done. Start the seat:  bin/tvd-guest"
