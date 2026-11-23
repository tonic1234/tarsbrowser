#!/usr/bin/env python3
"""tarsbrowser — maneja el Chrome propio de TARS en la PC del usuario, por CDP.

Un solo comando por acción. Todo lo que hace se verifica: si algo falla, lo dice.

    python3 tarsbrowser.py abrir                     # abre/reabre la ventana visible y espera CDP
    python3 tarsbrowser.py estado                    # ¿está vivo? pestañas abiertas
    python3 tarsbrowser.py nav <url>                 # navega la pestaña de trabajo (la crea si no hay)
    python3 tarsbrowser.py captura <salida.png>      # captura la pestaña de trabajo
    python3 tarsbrowser.py buscar "<consulta>"       # Google normal, devuelve título + captura
    python3 tarsbrowser.py imagenes "<consulta>" [n] [carpeta]
    python3 tarsbrowser.py bajar <url> [carpeta]     # descarga autónoma (sin diálogo, nombre del servidor)
    python3 tarsbrowser.py escribir <selector> <texto>   # tipeo humano (NO usar con contraseñas)
    python3 tarsbrowser.py login <url> <sel_usuario> <sel_clave> <usuario> <nombre_secreto> [--enviar]
    python3 tarsbrowser.py tipear_secreto <selector> <nombre_secreto>   # del buzón, nunca por el chat
    python3 tarsbrowser.py clic <x> <y> [captura.png]  # clic real con onda visible (y captura opcional)
    python3 tarsbrowser.py cursor [on|off]           # prende/apaga el cursor dibujado (default: prendido)
    python3 tarsbrowser.py apuntar "<selector>" ["texto"]   # lo lleva animado y resalta el elemento
    python3 tarsbrowser.py demo                      # recorrido de muestra (no clickea nada)
    python3 tarsbrowser.py sistema                   # host, sistema, Chrome y estado de CDP
    python3 tarsbrowser.py ventana <izq,arr,ancho,alto|0>   # fija la geometría de la ventana
    python3 tarsbrowser.py cerrar                    # cierra la pestaña de trabajo
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HOST = os.environ.get("TARS_HOST") or os.environ.get("TARS_PC", "anram@100.111.30.59")
KEY = os.environ.get("TARS_PC_KEY") or os.environ.get("TARS_KEY", os.path.expanduser("~/.ssh/id_ed25519"))
PUERTO_LOCAL = int(os.environ.get("TARS_CDP_PORT", "9223"))
PUERTO_REMOTO = int(os.environ.get("TARS_CDP_REMOTO", "9222"))
AQUI = os.path.dirname(os.path.abspath(__file__))
CURSOR_JS = os.environ.get("TARS_CURSOR_JS") or os.path.join(AQUI, "cursor.js")
CURSOR_ON = os.environ.get("TARS_CURSOR", "1") != "0"
SECRETOS = os.environ.get("TARS_SECRETOS", "/root/.hermes/secretos")
CONFIG = os.environ.get("TARS_CONFIG", os.path.join(os.path.expanduser("~"), ".tarsbrowser", "config.json"))


# ------------------------------------------------------------------ utilidades
def _decodificar(b: bytes) -> str:
    """Windows devuelve cp850, mac/linux UTF-8: se prueba en ese orden."""
    for codec in ("utf-8", "cp850", "latin-1"):
        try:
            return b.decode(codec)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def sh(comando: str, timeout: int = 120) -> str:
    """Corre un comando shell en el host remoto (mac/linux) por SSH."""
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "-i", KEY, HOST, comando],
                       capture_output=True, timeout=timeout)
    return _decodificar(r.stdout) + _decodificar(r.stderr)


def ps(script: str, timeout: int = 120) -> str:
    """Corre PowerShell en Windows (base64 UTF-16LE, sin infierno de comillas)."""
    b = base64.b64encode(script.encode("utf-16-le")).decode()
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "-i", KEY, HOST,
                        f"powershell -NoProfile -EncodedCommand {b}"],
                       capture_output=True, timeout=timeout)
    crudo = _decodificar(r.stdout) + _decodificar(r.stderr)
    # PowerShell mete ruido CLIXML en stderr cuando arranca los módulos: no es salida del comando.
    return "\n".join(l for l in crudo.splitlines()
                      if not l.startswith("#< CLIXML") and not l.startswith("<Objs"))


_sistema_cache: str | None = None


def sistema() -> str:
    """'windows' | 'macos' | 'linux', detectado en el host remoto una sola vez."""
    global _sistema_cache
    if _sistema_cache:
        return _sistema_cache
    # En Windows `uname` no existe y devuelve el error del shell: sin darwin/linux => windows.
    o = sh("uname -s", timeout=30).lower()
    if "darwin" in o:
        _sistema_cache = "macos"
    elif "linux" in o:
        _sistema_cache = "linux"
    else:
        _sistema_cache = "windows"
    return _sistema_cache


def perfil() -> str:
    """Carpeta del perfil dedicado, según el sistema del host remoto."""
    if os.environ.get("TARS_PERFIL"):
        return os.environ["TARS_PERFIL"]
    return {"windows": r"C:\tars-chrome", "macos": "~/.tars-chrome", "linux": "~/.tars-chrome"}[sistema()]


def leer_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guardar_config(d: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)


def bounds() -> str:
    """Geometría fijada de la ventana ('izq,arriba,ancho,alto'), o '' si no se toca."""
    return os.environ.get("TARS_BOUNDS", leer_config().get("bounds", ""))


def _puerto_abierto() -> bool:
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", PUERTO_LOCAL))
        return True
    except OSError:
        return False
    finally:
        s.close()


def tunel(arrancar: bool = True) -> bool:
    if _puerto_abierto():
        return True
    if not arrancar:
        return False
    subprocess.Popen(["ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                      "-o", "ServerAliveInterval=20", "-i", KEY, HOST,
                      "-L", f"{PUERTO_LOCAL}:127.0.0.1:{PUERTO_REMOTO}"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(20):
        time.sleep(0.5)
        if _puerto_abierto():
            return True
    return False


def ws_url() -> str:
    if not tunel():
        raise SystemExit("no hay túnel ni CDP: corré `tarsbrowser.py abrir`")
    with urllib.request.urlopen(f"http://127.0.0.1:{PUERTO_LOCAL}/json/version", timeout=5) as r:
        return json.load(r)["webSocketDebuggerUrl"]


# ------------------------------------------------------------------------ CDP
class CDP:
    def __init__(self, url: str):
        self.url = url
        self.ws = None
        self._id = 0
        self._pend: dict = {}
        self.eventos: asyncio.Queue = asyncio.Queue()

    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect(self.url, max_size=64 * 1024 * 1024)
        self._t = asyncio.create_task(self._leer())
        return self

    async def __aexit__(self, *a):
        self._t.cancel()
        await self.ws.close()

    async def _leer(self):
        try:
            async for crudo in self.ws:
                m = json.loads(crudo)
                if "id" in m:
                    f = self._pend.pop(m["id"], None)
                    if f and not f.done():
                        f.set_result(m)
                else:
                    await self.eventos.put(m)
        except Exception:
            pass

    async def send(self, metodo, params=None, session=None, timeout=45):
        self._id += 1
        ident = self._id
        msg = {"id": ident, "method": metodo, "params": params or {}}
        if session:
            msg["sessionId"] = session
        fut = asyncio.get_running_loop().create_future()
        self._pend[ident] = fut
        await self.ws.send(json.dumps(msg))
        r = await asyncio.wait_for(fut, timeout)
        if "error" in r:
            raise RuntimeError(f"{metodo} -> {r['error']}")
        return r.get("result", {})

    async def evaluar(self, expr, session, timeout=45):
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                 "awaitPromise": True, "userGesture": True},
                            session=session, timeout=timeout)
        return r.get("result", {}).get("value")

    async def pagina(self):
        """Adjunta (o crea) una pestaña de trabajo http y devuelve (targetId, sessionId)."""
        paginas = [t for t in (await self.send("Target.getTargets"))["targetInfos"]
                   if t.get("type") == "page" and t.get("url", "").startswith("http")]
        if paginas:
            t = paginas[-1]
        else:
            t = await self.send("Target.createTarget", {"url": "about:blank"})
            await asyncio.sleep(0.4)
        s = await self.send("Target.attachToTarget", {"targetId": t["targetId"], "flatten": True})
        ses = s["sessionId"]
        # Page.enable puede quedarse sin respuesta al adjuntarse a una pestaña ya existente.
        try:
            await self.send("Page.enable", session=ses, timeout=8)
        except Exception:
            s = await self.send("Target.attachToTarget", {"targetId": t["targetId"], "flatten": True})
            ses = s["sessionId"]
        await normalizar_ventana(self, t["targetId"])
        await instalar_cursor(self, ses)
        return t["targetId"], ses


async def normalizar_ventana(c, target_id):
    """La ventana dedicada tiende a achicarse sola (Chrome restaura tamaños): se reafirma."""
    geometria = bounds()
    if not geometria or geometria == "0":
        return
    try:
        izq, arr, ancho, alto = (int(v) for v in geometria.split(","))
        w = await c.send("Browser.getWindowForTarget", {"targetId": target_id}, timeout=10)
        b = w.get("bounds", {})
        if (abs(b.get("width", 0) - ancho) > 40 or abs(b.get("height", 0) - alto) > 40
                or b.get("left") != izq):
            await c.send("Browser.setWindowBounds", {"windowId": w["windowId"], "bounds": {
                "windowState": "normal", "left": izq, "top": arr, "width": ancho, "height": alto}}, timeout=10)
            await asyncio.sleep(0.5)
    except Exception:
        pass


def _fuente_cursor() -> str:
    try:
        return open(CURSOR_JS, encoding="utf-8").read()
    except OSError:
        return "(() => 'sin cursor.js');"


async def instalar_cursor(c, ses):
    """Cursor dibujado dentro de la página: se ve cada movimiento y cada clic."""
    if not CURSOR_ON:
        return
    src = _fuente_cursor()
    try:
        await c.send("Page.addScriptToEvaluateOnNewDocument", {"source": src}, session=ses)
    except Exception:
        pass
    await c.evaluar(src, ses, timeout=15)


async def posicion_cursor(c, ses):
    p = await c.evaluar("window.__tarsCursor ? JSON.stringify(window.__tarsCursor.posicion()) : null", ses, timeout=8)
    if not p:
        return (0.0, 0.0)
    d = json.loads(p)
    return (float(d["x"]), float(d["y"]))


async def mover_humano(c, ses, destino_x, destino_y, ms=None):
    """Lleva el mouse por una curva con eventos REALES: el cursor dibujado la sigue sola.

    La animación va del lado del cliente (no requestAnimationFrame) para que no dependa
    del foco de la ventana: si la ventana está sin foco, rAF se estrangula y el cursor
    se quedaría clavado.
    """
    x0, y0 = await posicion_cursor(c, ses)
    dx, dy = destino_x - x0, destino_y - y0
    dist = (dx * dx + dy * dy) ** 0.5
    if dist < 3:
        return
    dur = ms if ms else max(240, min(240 + dist * 0.75, 950))
    pasos = max(10, min(int(dur / 16), 60))
    # control perpendicular: se lee como una mano, no como una regla
    nx, ny = -dy, dx
    norma = (nx * nx + ny * ny) ** 0.5 or 1
    curva = min(70, dist * 0.22) * (1 if random.random() < 0.5 else -1)
    cx, cy = x0 + dx / 2 + (nx / norma) * curva, y0 + dy / 2 + (ny / norma) * curva
    for i in range(1, pasos + 1):
        t = i / pasos
        e = t * t * (3 - 2 * t)          # smoothstep
        x = (1 - e) ** 2 * x0 + 2 * (1 - e) * e * cx + e * e * destino_x
        y = (1 - e) ** 2 * y0 + 2 * (1 - e) * e * cy + e * e * destino_y
        await c.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": int(round(x)), "y": int(round(y))},
                     session=ses, timeout=10)
        await asyncio.sleep(random.uniform(0.010, 0.022))


async def mover_a(c, ses, selector, texto=None, tipo=None):
    """Lleva el cursor al elemento (curva animada) y lo deja resaltado con su etiqueta."""
    caja = await c.evaluar("""(() => { const e = document.querySelector(%s);
        if (!e) return null; e.scrollIntoView({block:'center'});
        const r = e.getBoundingClientRect();
        return JSON.stringify({left:r.left, top:r.top, width:r.width, height:r.height,
                               x: r.left + Math.min(r.width/2, 120), y: r.top + r.height/2}); })()"""
                            % json.dumps(selector), ses)
    if not caja:
        return False
    d = json.loads(caja)
    await c.evaluar("(() => { const C = window.__tarsCursor; if (!C) return 0;"
                    " return C.apuntar(%s, %s, %s); })()"
                    % (json.dumps({k: d[k] for k in ("left", "top", "width", "height")}),
                       json.dumps(texto), json.dumps(tipo)), ses)
    await mover_humano(c, ses, d["x"], d["y"])
    return True


async def captura_bytes(c, ses) -> bytes:
    r = await c.send("Page.captureScreenshot", {"format": "png"}, session=ses, timeout=60)
    return base64.b64decode(r["data"])


def guardar(ruta: str, datos: bytes) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
    open(ruta, "wb").write(datos)
    return os.path.getsize(ruta)


# ------------------------------------------------------------ tipeo humano
async def tipear(c, ses, selector: str, texto: str, pausa=(0.04, 0.13)):
    """Tipea como una persona: foco por clic real y una tecla por carácter."""
    ok = await c.evaluar(f"""(() => {{ const e = document.querySelector({json.dumps(selector)});
        if (!e) return false; e.scrollIntoView({{block:'center'}}); e.focus(); e.select && e.select(); return true; }})()""", ses)
    if not ok:
        raise SystemExit(f"no encontré el campo {selector}")
    etiqueta_campo = (await c.evaluar("""(() => { const e = document.querySelector(%s);
        return e ? (e.getAttribute('placeholder') || e.getAttribute('aria-label') || e.name || e.id || 'campo') : 'campo'; })()"""
                                      % json.dumps(selector), ses)) or "campo"
    await mover_a(c, ses, selector, "escribiendo en «%s»" % etiqueta_campo, "escribiendo")
    for ch in texto:
        await c.send("Input.dispatchKeyEvent", {"type": "char", "text": ch}, session=ses)
        await asyncio.sleep(random.uniform(*pausa))
    await c.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab",
                                            "windowsVirtualKeyCode": 9}, session=ses)
    await c.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab",
                                            "windowsVirtualKeyCode": 9}, session=ses)


def leer_secreto(nombre: str) -> str:
    """Trae el secreto del buzón cifrado. NUNCA se imprime."""
    r = subprocess.run(["python3", os.path.join(SECRETOS, "secreto.py"), "get", nombre],
                       capture_output=True, text=True, timeout=30, cwd=SECRETOS)
    valor = (r.stdout or "").strip()
    if not valor or "no existe" in valor.lower() or r.returncode != 0:
        raise SystemExit(f"no pude leer el secreto '{nombre}' del buzón")
    return valor


# ---------------------------------------------------------------- comandos
def cmd_abrir():
    """Abre (o reabre) la ventana dedicada en el host remoto y espera CDP."""
    sis = sistema()
    if sis in ("macos", "linux"):
        script = "arrancar-macos.sh" if sis == "macos" else "arrancar-linux.sh"
        salida = sh(f'bash "$HOME/.tars-chrome/{script}"', timeout=120).strip()
        print((salida.splitlines() or ["sin salida"])[-1])
        print("tunel:", "ok" if tunel() else "caido")
        return
    salida = ps(r"""
$t = 'tars-chrome-abrir'
if (-not (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue)) {
  Write-Output 'NO_TAREA'; exit 1
}
Start-ScheduledTask -TaskName $t
for ($i=0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try { $v = Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 2
        if ($v.'User-Agent' -notlike '*Headless*') { Write-Output ('OK ' + $v.Browser); exit 0 } } catch {}
}
Write-Output 'FALLO'
""", timeout=120)
    print(salida.strip().splitlines()[-1] if salida.strip() else "sin salida")
    print("tunel:", "ok" if tunel() else "caido")


def cmd_estado():
    ws = ws_url()
    async def _():
        async with CDP(ws) as c:
            v = await c.send("Browser.getVersion")
            print("navegador:", v.get("product"), "| UA headless:", "Headless" in v.get("userAgent", ""))
            for t in (await c.send("Target.getTargets"))["targetInfos"]:
                if t.get("type") == "page":
                    print("  -", t.get("title", "")[:50], "|", t.get("url", "")[:70])
    asyncio.run(_())


def cmd_nav(url):
    ws = ws_url()
    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Page.navigate", {"url": url}, session=ses)
            await asyncio.sleep(2.5)
            await instalar_cursor(c, ses)
            print(await c.evaluar("JSON.stringify({u:location.href,t:document.title})", ses))
    asyncio.run(_())


def cmd_captura(salida):
    ws = ws_url()
    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            print("bytes:", guardar(salida, await captura_bytes(c, ses)))
    asyncio.run(_())


def cmd_buscar(consulta, salida=None):
    ws = ws_url()
    q = urllib.parse.quote(consulta)
    salida = salida or os.path.join("/tmp", "busqueda.png")

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Page.navigate", {"url": f"https://www.google.com/search?hl=es&gl=uy&pws=0&q={q}"}, session=ses)
            await asyncio.sleep(4)
            await instalar_cursor(c, ses)
            await c.evaluar("""(() => { const b=[...document.querySelectorAll('button,div[role=button]')]
                .find(e=>/Aceptar todo|Accept all|I agree/i.test(e.innerText||'')); if(b){b.click();return 1;} return 0; })()""", ses)
            await asyncio.sleep(1.5)
            print(await c.evaluar("document.title", ses))
            print("captura:", salida, guardar(salida, await captura_bytes(c, ses)))
    asyncio.run(_())


def cmd_imagenes(consulta, n=4, carpeta="/tmp/imgs"):
    ws = ws_url()
    q = urllib.parse.quote(consulta)

    async def _():
        async with CDP(ws) as c:
            await c.send("Browser.setDownloadBehavior",
                         {"behavior": "allow", "downloadPath": r"C:\tars-descargas"})
            _, ses = await c.pagina()
            await c.send("Page.navigate", {"url": f"https://www.google.com/search?hl=es&gl=uy&pws=0&tbm=isch&q={q}"}, session=ses)
            await asyncio.sleep(5)
            urls = await c.evaluar("""(() => { const o=[];
                for (const a of document.querySelectorAll('a[href*="imgurl="]')) { try {
                  const u=new URL(a.href), iu=u.searchParams.get('imgurl');
                  if (iu && /^https?:/.test(iu) && !o.includes(iu)) o.push(iu); } catch(e){} }
                for (const i of document.querySelectorAll('img')) { const s=i.currentSrc||i.src||'';
                  if (/^https?:/.test(s) && i.naturalWidth>200 && !o.includes(s)) o.push(s); }
                return o.slice(0, %d); })()""" % (int(n) + 6), ses)
            os.makedirs(carpeta, exist_ok=True)
            bajadas = 0
            for u in urls:
                if bajadas >= int(n):
                    break
                try:
                    await c.send("Page.navigate", {"url": u}, session=ses)
                    await asyncio.sleep(2.2)
                    b64 = await c.evaluar("""(async () => { try {
                        const r = await fetch(location.href, {cache:'force-cache'});
                        if (!r.ok) return 'HTTP_'+r.status;
                        const b = await r.arrayBuffer();
                        if (b.byteLength < 8000) return 'CHICA';
                        let s=''; const v=new Uint8Array(b);
                        for (let i=0;i<v.length;i+=8192) s+=String.fromCharCode.apply(null, v.subarray(i,i+8192));
                        return btoa(s); } catch(e) { return 'ERR_'+e.message; } })()""", ses, timeout=60)
                    if not isinstance(b64, str) or b64[:4] in ("HTTP", "CHIC", "ERR_"):
                        print("  salteada:", u[:70], b64 if isinstance(b64, str) else "?")
                        continue
                    datos = base64.b64decode(b64)
                    ext = ".png" if datos[:8] == b"\x89PNG\r\n\x1a\n" else (".webp" if datos[:4] == b"RIFF" else ".jpg")
                    bajadas += 1
                    ruta = os.path.join(carpeta, f"imagen-{bajadas}{ext}")
                    print("  bajada:", ruta, guardar(ruta, datos), "bytes")
                except Exception as e:
                    print("  error:", str(e)[:80])
            print("total:", bajadas)
    asyncio.run(_())


def cmd_bajar(url, carpeta=r"C:\tars-descargas"):
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            await c.send("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": carpeta,
                                                         "eventsEnabled": True})
            await c.send("Target.createTarget", {"url": url})
            print("esperando descarga…")
            while True:
                ev = await asyncio.wait_for(c.eventos.get(), 120)
                if ev.get("method") == "Browser.downloadWillBegin":
                    print("archivo:", ev["params"].get("suggestedFilename"))
                if ev.get("method") == "Browser.downloadProgress" and ev["params"].get("state") == "completed":
                    print("bytes:", ev["params"].get("receivedBytes"), "->", carpeta)
                    return
    asyncio.run(_())


def cmd_escribir(selector, texto):
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await tipear(c, ses, selector, texto)
            print("escrito en", selector)
    asyncio.run(_())


def cmd_login(url, sel_usuario, sel_clave, usuario, nombre_secreto, enviar=""):
    secreto = leer_secreto(nombre_secreto)   # vive sólo en memoria del proceso
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Page.navigate", {"url": url}, session=ses)
            await asyncio.sleep(3)
            await instalar_cursor(c, ses)
            await tipear(c, ses, sel_usuario, usuario)
            await tipear(c, ses, sel_clave, secreto)
            print("credenciales cargadas (la clave no se imprime: %d caracteres)" % len(secreto))
            if enviar not in ("enviar", "--enviar", "1", "si", "sí"):
                print("revisá y apretá el botón: el captcha y el Submit los da una persona")
                return
            # Botón de envío: clic por coordenadas reales del elemento (no .click() sintético).
            caja = await c.evaluar("""(() => {
                const cand = [...document.querySelectorAll('input[type=submit],button,[role=button]')]
                  .filter(e => e.offsetParent !== null)
                  .map(e => ({e, t: (e.innerText || e.value || '').trim().toLowerCase()}))
                  .filter(x => /log ?in|iniciar|entrar|sign ?in|submit|continu/.test(x.t));
                const el = cand.length ? cand[0].e : null;
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return JSON.stringify({x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), t: el.innerText || el.value});
            })()""", ses)
            if not caja:
                raise SystemExit("no encontré el botón de envío (probá un selector manual)")
            d = json.loads(caja)
            for tipo in ("mouseMoved", "mousePressed", "mouseReleased"):
                await c.send("Input.dispatchMouseEvent", {"type": tipo, "x": d["x"], "y": d["y"],
                                                          "button": "left", "clickCount": 1,
                                                          "buttons": 1 if tipo == "mousePressed" else 0},
                             session=ses)
                await asyncio.sleep(0.1)
            print("clic en el botón:", d.get("t", ""))
            await asyncio.sleep(6)
            estado = await c.evaluar("""(() => {
                const u = location.href;
                const clave = !!document.querySelector('input[type=password]');
                return JSON.stringify({url: u, sigue_formulario: clave, titulo: document.title});
            })()""", ses)
            print("resultado:", estado)
    asyncio.run(_())


def cmd_tipear_secreto(selector, nombre_secreto):
    secreto = leer_secreto(nombre_secreto)
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await tipear(c, ses, selector, secreto)
            print("secreto tipeado en", selector, "(%d caracteres)" % len(secreto))
    asyncio.run(_())


def cmd_clic(x, y, captura=None):
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            vp = json.loads(await c.evaluar("JSON.stringify({w:innerWidth,h:innerHeight})", ses))
            if int(x) >= vp["w"] or int(y) >= vp["h"]:
                raise SystemExit(f"({x},{y}) está fuera del viewport {vp['w']}x{vp['h']}: el clic no llega")
            # animar + resaltar el elemento que hay en ese punto
            objetivo = await c.evaluar("""(() => {
                // el elemento MÁS CHICO bajo el punto: si agarro el contenedor, la etiqueta
                // sale con el texto de toda la página ("clic en «Log in to Nexus Mods You need...»")
                const pila = document.elementsFromPoint(%s, %s).filter(e => e.offsetParent !== null);
                if (!pila.length) return null;
                const area = (e) => { const r = e.getBoundingClientRect(); return r.width * r.height; };
                let e = pila[0];
                for (const cand of pila) { if (area(cand) > 0 && area(cand) <= area(e) &&
                      ((cand.innerText || cand.value || cand.getAttribute('aria-label') || '').trim().length > 0
                       || ['A','BUTTON','INPUT','LABEL'].includes(cand.tagName))) e = cand; }
                const r = e.getBoundingClientRect();
                const t = ((e.innerText || e.value || e.getAttribute('aria-label') || '').trim()
                           || (e.tagName || '')).replace(/\\s+/g, ' ').slice(0, 34);
                return JSON.stringify({left:r.left, top:r.top, width:r.width, height:r.height, texto:t}); })()"""
                                     % (x, y), ses)
            if objetivo:
                o = json.loads(objetivo)
                await c.evaluar("(() => { const C = window.__tarsCursor; if (!C) return 0;"
                                " return C.apuntar(%s, %s); })()"
                                % (json.dumps({k: o[k] for k in ("left", "top", "width", "height")}),
                                   json.dumps("clic en «%s»" % (o["texto"] or "elemento"))), ses)
                await mover_humano(c, ses, int(x), int(y))
            # La captura, si se pidió, se toma JUSTO después del press: la onda dura poco.
            await c.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": int(x), "y": int(y)},
                         session=ses, timeout=10)
            await asyncio.sleep(0.06)
            await c.send("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": int(x), "y": int(y), "button": "left",
                "clickCount": 1, "buttons": 1}, session=ses, timeout=10)
            if captura:
                print("captura:", captura, guardar(captura, await captura_bytes(c, ses)))
            await c.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": int(x), "y": int(y), "button": "left",
                "clickCount": 1, "buttons": 0}, session=ses, timeout=10)
            print("clic en", x, y, "->", await c.evaluar(
                "(() => { const e = document.elementFromPoint(%s, %s); return e ? (e.tagName + ' ' + (e.innerText||'').slice(0,40)) : 'nada'; })()"
                % (x, y), ses))
    asyncio.run(_())


def cmd_apuntar(selector, texto=""):
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await instalar_cursor(c, ses)
            ok = await mover_a(c, ses, selector, texto or ("apuntando a «%s»" % selector))
            print("apuntado:", bool(ok))
    asyncio.run(_())


def cmd_demo():
    """Recorrido de muestra: el cursor pasea, resalta el campo y hace una onda (no clickea)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await instalar_cursor(c, ses)
            vp = json.loads(await c.evaluar("JSON.stringify({w:innerWidth,h:innerHeight})", ses))
            puntos = [(int(vp["w"] * .15), int(vp["h"] * .18), "arrancando"),
                      (int(vp["w"] * .72), int(vp["h"] * .35), "buscando el objetivo"),
                      (int(vp["w"] * .40), int(vp["h"] * .62), "acá está")]
            for x, y, texto in puntos:
                await c.evaluar("window.__tarsCursor.etiqueta(%s)" % json.dumps(texto), ses)
                await mover_humano(c, ses, x, y)
                await asyncio.sleep(0.35)
            await c.evaluar("window.__tarsCursor.onda(%d,%d); window.__tarsCursor.etiqueta('listo')"
                            % (int(vp["w"] * .40), int(vp["h"] * .62)), ses)
            print("demo terminada")
    asyncio.run(_())


def cmd_cursor(estado="on"):
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            if estado in ("off", "0", "apagar"):
                await c.evaluar("window.__tarsCursor && window.__tarsCursor.visible(false); 'off'", ses)
                print("cursor dibujado: apagado")
            else:
                await instalar_cursor(c, ses)
                await c.evaluar("window.__tarsCursor && window.__tarsCursor.visible(true); 'on'", ses)
                print("cursor dibujado: encendido")
    asyncio.run(_())


def cmd_sistema():
    """Qué host, qué sistema, qué Chrome y cómo está el CDP."""
    print("host:", HOST)
    print("sistema:", sistema())
    print("perfil:", perfil())
    print("bounds:", bounds() or "(sin fijar)")
    if sistema() == "windows":
        print(ps("(Get-Item 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe').VersionInfo.ProductVersion", timeout=60).strip())
    else:
        print(sh("'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --version 2>/dev/null "
                 "|| google-chrome --version 2>/dev/null || chromium --version 2>/dev/null", timeout=60).strip())
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PUERTO_LOCAL}/json/version", timeout=4) as r:
            print("cdp:", json.load(r)["Browser"])
    except Exception as e:
        print("cdp: sin conexión (", str(e)[:60], ")")


def cmd_ventana(geometria):
    """Fija la geometría de la ventana: 'izq,arriba,ancho,alto' o '0' para no tocarla."""
    if geometria != "0":
        partes = geometria.split(",")
        if len(partes) != 4 or not all(x.strip().lstrip("-").isdigit() for x in partes):
            raise SystemExit("formato: izq,arriba,ancho,alto  (ej: 1924,4,856,760)")
    cfg = leer_config()
    cfg["bounds"] = geometria
    guardar_config(cfg)
    print("geometría guardada:", geometria, "->", CONFIG)


def cmd_cerrar():
    ws = ws_url()
    async def _():
        async with CDP(ws) as c:
            paginas = [t for t in (await c.send("Target.getTargets"))["targetInfos"]
                       if t.get("type") == "page" and t.get("url", "").startswith("http")]
            for t in paginas:
                await c.send("Target.closeTarget", {"targetId": t["targetId"]})
            print("cerradas:", len(paginas))
    asyncio.run(_())


ORDENES = {
    "abrir": (cmd_abrir, 0), "estado": (cmd_estado, 0), "nav": (cmd_nav, 1),
    "captura": (cmd_captura, 1), "buscar": (cmd_buscar, 1), "imagenes": (cmd_imagenes, 1),
    "bajar": (cmd_bajar, 1), "escribir": (cmd_escribir, 2), "login": (cmd_login, 5),
    "clic": (cmd_clic, 2), "cursor": (cmd_cursor, 0), "apuntar": (cmd_apuntar, 1),
    "sistema": (cmd_sistema, 0), "ventana": (cmd_ventana, 1),
    "demo": (cmd_demo, 0),
    "tipear_secreto": (cmd_tipear_secreto, 2), "cerrar": (cmd_cerrar, 0),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        raise SystemExit(__doc__)
    orden = sys.argv[1]
    if orden not in ORDENES:
        raise SystemExit(f"orden desconocida: {orden}\n{__doc__}")
    fn, req = ORDENES[orden]
    extras = sys.argv[2 + req:]
    fn(*sys.argv[2:2 + req], *extras)


if __name__ == "__main__":
    main()
