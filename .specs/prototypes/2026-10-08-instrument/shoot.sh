#!/usr/bin/env bash
# Capture one prototype screen. Sequential on purpose: the machine this runs on
# has ~2 GB available and a parallel Chrome per screen will swap.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCREEN="${1:?usage: shoot.sh <screen.html> [width] [height] [out.png] [theme]}"
W="${2:-1440}"
H="${3:-1000}"
THEME="${5:-light}"
OUT="${4:-$ROOT/shots/$(basename "${SCREEN%.html}")-$W-$THEME.png}"
CHROME="/usr/bin/google-chrome"

mkdir -p "$(dirname "$OUT")"
PROFILE="$(mktemp -d)"
trap 'rm -rf "$PROFILE"' EXIT

# --headless=new keeps the renderer's sandbox on (SEC-15); --hide-scrollbars
# stops the scrollbar gutter shifting layout between captures.
"$CHROME" \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --hide-scrollbars \
  --force-device-scale-factor=2 \
  --user-data-dir="$PROFILE" \
  --virtual-time-budget=4000 \
  --window-size="${W},${H}" \
  --screenshot="$OUT" \
  "file://$ROOT/screens/$SCREEN" >/dev/null 2>&1

echo "$OUT  $(du -h "$OUT" | cut -f1)"