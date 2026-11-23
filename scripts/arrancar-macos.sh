#!/bin/bash
# arrancar-macos.sh — abre el Chrome dedicado de TARS en la Mac, con su propio perfil
# y depuración remota, dentro de la sesión gráfica del usuario.
#
#   bash arrancar-macos.sh [url]
#
# Variables: TARS_PERFIL (~/.tars-chrome), TARS_CDP_REMOTO (9222), TARS_ZONA (arriba|abajo|completo)
# Imprime CDP_OK <versión> cuando quedó escuchando, o CDP_FAIL.
set -uo pipefail

PERFIL="${TARS_PERFIL:-$HOME/.tars-chrome}"
PUERTO="${TARS_CDP_REMOTO:-9222}"
URL="${1:-about:blank}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

mkdir -p "$PERFIL"

if [ ! -x "$CHROME" ]; then
  echo "SIN_CHROME (no está en $CHROME)"
  exit 1
fi

# 1. Cerrar sólo las instancias de ESTE perfil (no toca el Chrome del usuario).
if pgrep -f "user-data-dir=$PERFIL" >/dev/null 2>&1; then
  pkill -f "user-data-dir=$PERFIL" 2>/dev/null
  sleep 2
fi

# 2. Lanzar en la sesión gráfica. `open -na` habla con launchd, así la ventana
#    aparece en el escritorio del usuario y no en el contexto del SSH.
open -na "Google Chrome" --args \
  --user-data-dir="$PERFIL" \
  --remote-debugging-port="$PUERTO" \
  --no-first-run \
  --no-default-browser-check \
  --disable-features=Translate \
  --new-window "$URL" >/dev/null 2>&1

# 3. Esperar el puerto y avisar.
for _ in $(seq 1 30); do
  sleep 1
  if V=$(curl -s --max-time 2 "http://127.0.0.1:$PUERTO/json/version" 2>/dev/null); then
    echo "CDP_OK $(printf '%s' "$V" | /usr/bin/python3 -c 'import sys,json;print(json.load(sys.stdin).get("Browser","?"))' 2>/dev/null)"
    exit 0
  fi
done

echo "CDP_FAIL (el puerto $PUERTO no responde; revisar que Chrome haya abierto)"
exit 1
