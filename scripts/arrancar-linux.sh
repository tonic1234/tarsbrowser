#!/bin/bash
# arrancar-linux.sh — igual que el de macOS pero para Linux con Chrome/Chromium.
#   bash arrancar-linux.sh [url]
set -uo pipefail

PERFIL="${TARS_PERFIL:-$HOME/.tars-chrome}"
PUERTO="${TARS_CDP_REMOTO:-9222}"
URL="${1:-about:blank}"

BIN=""
for c in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then BIN="$c"; break; fi
done
if [ -z "$BIN" ]; then echo "SIN_CHROME"; exit 1; fi

mkdir -p "$PERFIL"
pkill -f "user-data-dir=$PERFIL" 2>/dev/null && sleep 2

nohup "$BIN" --user-data-dir="$PERFIL" --remote-debugging-port="$PUERTO" \
  --no-first-run --no-default-browser-check --new-window "$URL" \
  >/dev/null 2>&1 &

for _ in $(seq 1 30); do
  sleep 1
  if V=$(curl -s --max-time 2 "http://127.0.0.1:$PUERTO/json/version" 2>/dev/null); then
    echo "CDP_OK $(printf '%s' "$V" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("Browser","?"))' 2>/dev/null)"
    exit 0
  fi
done
echo "CDP_FAIL"
exit 1
