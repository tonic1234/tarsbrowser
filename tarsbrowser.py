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
    python3 tarsbrowser.py clicax button "Log in"    # clic por rol/nombre accesible (sin coordenadas)
    python3 tarsbrowser.py sesion <url> <selector>   # ¿la sesión sigue viva?
    python3 tarsbrowser.py subir "<selector>" <ruta> # sube un archivo al input[type=file]
    python3 tarsbrowser.py pdf <salida.pdf>          # PDF con el medio de impresión emulado
    python3 tarsbrowser.py extraer "<selector>" [attr]   # JSON de lo que matchea
    python3 tarsbrowser.py bloquear "doubleclick.net,google-analytics.com"
    python3 tarsbrowser.py permitir "ejemplo.com,otro.com"   # allowlist (vacío = todos)
    python3 tarsbrowser.py mapa [max]                # elementos accionables numerados
    python3 tarsbrowser.py clicref <n|eN> [captura.png]  # por número del mapa o ref del snapshot
    python3 tarsbrowser.py snapshot [si|no]          # árbol de accesibilidad con refs (e1, e2…)
    python3 tarsbrowser.py acciones                  # qué se puede hacer ahora, en una lista
    python3 tarsbrowser.py diagnostico [url] [seg]   # red + consola: qué falló y qué tardó
    python3 tarsbrowser.py guardar-sesion / reabrir  # pestañas persistentes (sin tocar cookies)
    python3 tarsbrowser.py grabar <salida.mp4> [seg] # screencast de la pestaña
    python3 tarsbrowser.py mock "<patron>" "<json>" [seg]   # interceptar y responder
    python3 tarsbrowser.py registro [n]              # últimas acciones registradas
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
import shutil
import subprocess
import sys
import tempfile
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
    if not tunel() and os.environ.get("TARS_AUTORECUPERAR", "1") != "0":
        # A7: si el túnel/CDP no está, se intenta abrir la ventana una vez antes de fallar.
        print("(CDP caído: intentando abrir la ventana)", file=sys.stderr)
        try:
            cmd_abrir()
        except Exception:
            pass
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

    async def enviar(self, metodo, params=None, session=None):
        """Manda el comando SIN esperar la respuesta.

        Cada `await send(...)` cuesta un ida y vuelta (medido: ~190 ms por SSH hasta la PC).
        Para animar el mouse eso es la diferencia entre 300 ms y 13 segundos: los pasos
        intermedios se encolan sin esperar y el orden lo garantiza el WebSocket.
        """
        self._id += 1
        msg = {"id": self._id, "method": metodo, "params": params or {}}
        if session:
            msg["sessionId"] = session
        await self.ws.send(json.dumps(msg))

    async def evaluar(self, expr, session, timeout=45):
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                 "awaitPromise": True, "userGesture": True},
                            session=session, timeout=timeout)
        return r.get("result", {}).get("value")

    async def pagina(self, fijar=True):
        """Adjunta (o crea) la pestaña de trabajo y devuelve (targetId, sessionId).

        La pestaña de trabajo se recuerda en la config: si sigue abierta se usa ESA, no la
        última (tomar la última puede operar sobre la pestaña equivocada).
        """
        paginas = [t for t in (await self.send("Target.getTargets"))["targetInfos"]
                   if t.get("type") == "page" and t.get("url", "").startswith("http")]
        recordada = leer_config().get("target")
        t = next((x for x in paginas if x["targetId"] == recordada), None)
        if t is None:
            t = paginas[-1] if paginas else None
        if t is None:
            t = await self.send("Target.createTarget", {"url": "about:blank"})
            await asyncio.sleep(0.4)
        if fijar and recordada != t["targetId"]:
            cfg = leer_config()
            cfg["target"] = t["targetId"]
            guardar_config(cfg)

        async def _adjuntar():
            s = await self.send("Target.attachToTarget", {"targetId": t["targetId"], "flatten": True},
                                timeout=20)
            ses = s["sessionId"]
            # Page.enable puede quedarse sin respuesta al adjuntarse a una pestaña ya existente.
            await self.send("Page.enable", session=ses, timeout=8)
            return ses

        ses = await con_reintentos(_adjuntar, intentos=3)
        await normalizar_ventana(self, t["targetId"])
        await instalar_cursor(self, ses)
        return t["targetId"], ses


# ------------------------------------------------- esperas, reintentos, auditoría
async def esperar(c, ses, expresion, timeout=15.0, intervalo=0.2):
    """Espera a que una expresión JS devuelva algo verdadero. Mejor que sleep fijo."""
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            if await c.evaluar(expresion, ses, timeout=10):
                return True
        except Exception:
            pass
        await asyncio.sleep(intervalo)
    return False


async def esperar_selector(c, ses, selector, timeout=15.0):
    return await esperar(c, ses, "!!document.querySelector(%s)" % json.dumps(selector), timeout)


async def esperar_carga(c, ses, timeout=20.0):
    return await esperar(c, ses, "document.readyState === 'complete'", timeout)


async def con_reintentos(fn, intentos=3, espera=0.5):
    """Reintenta una corrutina idempotente (attach, enable, etc.)."""
    ultimo = None
    for i in range(intentos):
        try:
            return await fn()
        except Exception as e:      # noqa: BLE001 - se propaga el último
            ultimo = e
            if i < intentos - 1:
                await asyncio.sleep(espera * (i + 1))
    raise ultimo


def auditar(accion: str, detalle: str = "") -> None:
    """Registro append-only de lo que hizo la herramienta. Nunca guarda credenciales."""
    try:
        ruta = os.environ.get("TARS_AUDITORIA", os.path.join(os.path.dirname(CONFIG), "auditoria.log"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        linea = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "host": HOST,
                            "accion": accion, "detalle": detalle[:400]}, ensure_ascii=False)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def dominios_permitidos() -> list:
    """Allowlist opcional de dominios; vacía = todos permitidos."""
    valor = os.environ.get("TARS_DOMINIOS", leer_config().get("dominios", ""))
    return [d.strip().lower() for d in valor.split(",") if d.strip()]


def dominio_permitido(url: str) -> bool:
    permitidos = dominios_permitidos()
    if not permitidos:
        return True
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in permitidos)


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
    dur = ms if ms else max(200, min(150 + dist * 0.25, 380))
    # Con el suavizado en la página alcanzan pocos eventos: cada uno fija un objetivo y el
    # cursor dibujado interpola a 60 fps entre ellos.
    pasos = max(6, min(int(dur / 40), 10))
    # control perpendicular: se lee como una mano, no como una regla
    nx, ny = -dy, dx
    norma = (nx * nx + ny * ny) ** 0.5 or 1
    curva = min(70, dist * 0.22) * (1 if random.random() < 0.5 else -1)
    cx, cy = x0 + dx / 2 + (nx / norma) * curva, y0 + dy / 2 + (ny / norma) * curva
    # Reloj de pared: cada paso se duerme hasta su hora, así el desfasaje por comando no
    # se acumula y la duración total es la prometida.
    inicio = time.perf_counter()
    for i in range(1, pasos + 1):
        t = i / pasos
        e = t * t * (3 - 2 * t)          # smoothstep
        x = int(round((1 - e) ** 2 * x0 + 2 * (1 - e) * e * cx + e * e * destino_x))
        y = int(round((1 - e) ** 2 * y0 + 2 * (1 - e) * e * cy + e * e * destino_y))
        evento = {"type": "mouseMoved", "x": x, "y": y}
        # Todos sin esperar respuesta: el ida y vuelta por SSH (~190 ms) no aporta nada acá
        # y es lo que hacía que el movimiento tardara segundos.
        await c.enviar("Input.dispatchMouseEvent", evento, session=ses)
        objetivo_t = inicio + (dur / 1000.0) * t
        resto = objetivo_t - time.perf_counter()
        if resto > 0:
            await asyncio.sleep(resto)


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


async def captura_bytes(c, ses, intentos=3) -> bytes:
    """Captura con reintentos: en pestañas de fondo o renderers ocupados puede colgarse."""
    ultimo = None
    for i in range(intentos):
        try:
            r = await c.send("Page.captureScreenshot", {"format": "png"}, session=ses, timeout=20)
            return base64.b64decode(r["data"])
        except Exception as e:      # noqa: BLE001
            ultimo = e
            try:
                await c.send("Page.bringToFront", session=ses, timeout=8)
            except Exception:
                pass
            await asyncio.sleep(0.4 * (i + 1))
    raise SystemExit("no pude capturar la pestaña: %s" % ultimo)


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


def cmd_nav(url, selector=None):
    if not dominio_permitido(url):
        raise SystemExit(f"dominio no permitido por la allowlist: {urllib.parse.urlsplit(url).hostname}")
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Page.navigate", {"url": url}, session=ses)
            await esperar_carga(c, ses)
            await instalar_cursor(c, ses)
            if selector:
                ok = await esperar_selector(c, ses, selector)
                print("selector", selector, "->", "apareció" if ok else "NO apareció")
            print(await c.evaluar("JSON.stringify({u:location.href,t:document.title})", ses))
    asyncio.run(_())
    auditar("nav", url)


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


def hash_remoto(ruta: str) -> str:
    """sha256 + tamaño del archivo en la máquina del navegador (verificación de la descarga)."""
    if sistema() == "windows":
        o = ps(f"if (Test-Path '{ruta}') {{ $f = Get-Item '{ruta}'; "
               f"Write-Output ('{{0}}|{{1}}' -f $f.Length, (Get-FileHash -Algorithm SHA256 '{ruta}').Hash) }} "
               f"else {{ Write-Output 'NO_EXISTE' }}", timeout=120)
    else:
        o = sh(f"[ -f '{ruta}' ] && echo \"$(wc -c < '{ruta}')|$(shasum -a 256 '{ruta}' | cut -d' ' -f1)\" || echo NO_EXISTE",
               timeout=120)
    return o.strip()


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
                    os.environ["TARS_ULTIMO_ARCHIVO"] = str(ev["params"].get("suggestedFilename") or "")
                if ev.get("method") == "Browser.downloadProgress" and ev["params"].get("state") == "completed":
                    bytes_ev = ev["params"].get("receivedBytes")
                    print("bytes:", bytes_ev, "->", carpeta)
                    # A5: se comprueba en el destino, no se confía sólo en el evento
                    nombre = os.environ.get("TARS_ULTIMO_ARCHIVO", "")
                    if nombre:
                        ruta = (carpeta.rstrip("\\") + "\\" + nombre) if ":" in carpeta else \
                               (carpeta.rstrip("/") + "/" + nombre)
                        print("destino:", hash_remoto(ruta)[:160])
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


def cmd_clicax(rol, nombre, captura=None):
    """Clic por ROL y NOMBRE accesibles, no por coordenadas (Accessibility.getFullAXTree)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await con_reintentos(lambda: c.send("Accessibility.enable", session=ses, timeout=10))
            await con_reintentos(lambda: c.send("DOM.enable", session=ses, timeout=10))
            arbol = await c.send("Accessibility.getFullAXTree", session=ses, timeout=30)
            nodos = arbol.get("nodes", [])
            buscado_rol = (rol or "").lower()
            buscado_nombre = (nombre or "").lower()
            elegido = None
            for n in nodos:
                rol_n = (n.get("role", {}).get("value") or "").lower()
                nom_n = (n.get("name", {}).get("value") or "").lower()
                if buscado_rol and rol_n != buscado_rol:
                    continue
                if buscado_nombre and buscado_nombre not in nom_n:
                    continue
                if not n.get("backendDOMNodeId"):
                    continue
                elegido = n
                break
            if not elegido:
                raise SystemExit(f"no encontré {rol} «{nombre}» en el árbol de accesibilidad")
            etiqueta = elegido.get("name", {}).get("value", "")[:34]
            x, y = await clic_por_backend(c, ses, elegido["backendDOMNodeId"], etiqueta, captura)
            print(f"clic accesible: rol={rol} nombre=«{etiqueta}» en ({x},{y})")
    asyncio.run(_())
    auditar("clicax", f"{rol}:{nombre}")


def cmd_sesion(url, selector):
    """¿La sesión sigue viva? Navega y dice si aparece el selector de "logueado"."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Page.navigate", {"url": url}, session=ses)
            await esperar_carga(c, ses)
            hay = await esperar_selector(c, ses, selector, timeout=8)
            titulo = await c.evaluar("document.title", ses)
            print("sesion:", "viva" if hay else "caida", "|", titulo)
    asyncio.run(_())


def cmd_subir(selector, ruta):
    """Sube un archivo: lo copia a la máquina del navegador y lo pone en el input."""
    if not os.path.isfile(ruta):
        raise SystemExit(f"no existe el archivo local {ruta}")
    remoto = "/tmp/" + os.path.basename(ruta) if sistema() != "windows" else "C:\\Windows\\Temp\\" + os.path.basename(ruta)
    r = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", "-i", KEY, ruta, f"{HOST}:{remoto}"],
                       capture_output=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit("no pude copiar el archivo: " + _decodificar(r.stderr)[:200])
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("DOM.enable", session=ses)
            doc = await c.send("DOM.getDocument", {"depth": 0}, session=ses)
            nodo = await c.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector},
                                session=ses)
            if not nodo.get("nodeId"):
                raise SystemExit(f"no encontré el input {selector}")
            await c.send("DOM.setFileInputFiles", {"files": [remoto], "nodeId": nodo["nodeId"]}, session=ses)
            print("subido:", remoto, "->", selector)
    asyncio.run(_())
    auditar("subir", f"{ruta} -> {selector}")


def cmd_pdf(salida):
    """PDF de la página actual, con el medio de impresión emulado."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Emulation.setEmulatedMedia", {"media": "print"}, session=ses)
            try:
                r = await c.send("Page.printToPDF", {"printBackground": True,
                                                     "preferCSSPageSize": True}, session=ses, timeout=90)
            finally:
                await c.send("Emulation.setEmulatedMedia", {"media": ""}, session=ses)
            datos = base64.b64decode(r["data"])
            print("pdf:", salida, guardar(salida, datos))
    asyncio.run(_())
    auditar("pdf", salida)


def cmd_extraer(selector, atributo=""):
    """Devuelve los elementos que matchean como JSON (texto o un atributo)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            expr = ("""(sel, attr) => JSON.stringify([...document.querySelectorAll(sel)].map(e => ({
                        texto: (e.innerText || e.value || '').trim().replace(/\\s+/g, ' ').slice(0, 300),
                        href: e.href || undefined,
                        dato: attr ? e.getAttribute(attr) : undefined })))"""
                    )
            r = await c.evaluar("(%s)(%s, %s)" % (expr, json.dumps(selector), json.dumps(atributo)), ses)
            print(r)
    asyncio.run(_())


def cmd_bloquear(dominios):
    """Bloquea dominios (ads, trackers) para acelerar y limpiar capturas."""
    lista = [d.strip() for d in dominios.split(",") if d.strip()]
    patrones = []
    for d in lista:
        patrones += [f"*://*.{d}/*", f"*://{d}/*"]
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Network.enable", session=ses)
            await c.send("Network.setBlockedURLs", {"urls": patrones}, session=ses)
            print("bloqueados:", ", ".join(lista), f"({len(patrones)} patrones)")
    asyncio.run(_())


def cmd_permitir(dominios):
    """Fija la allowlist de dominios (vacío = todos)."""
    cfg = leer_config()
    cfg["dominios"] = ",".join(d.strip() for d in dominios.split(",") if d.strip())
    guardar_config(cfg)
    print("allowlist:", cfg["dominios"] or "(todos)")


def cmd_registro(n=20):
    """Últimas acciones registradas (append-only, sin credenciales)."""
    ruta = os.environ.get("TARS_AUDITORIA", os.path.join(os.path.dirname(CONFIG), "auditoria.log"))
    try:
        with open(ruta, encoding="utf-8") as f:
            lineas = f.readlines()[-int(n):]
    except OSError:
        print("sin registro todavía")
        return
    for l in lineas:
        try:
            d = json.loads(l)
            print(d["ts"], "|", d["accion"], "|", d["detalle"][:90])
        except ValueError:
            print(l.rstrip())


MAPEO_JS = '''(() => {
  const visible = (e) => { const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],'
            + '[role=tab],[role=menuitem],[contenteditable=true],[onclick]';
  const vistos = new Set();
  const items = [];
  for (const e of document.querySelectorAll(sel)) {
    if (!visible(e) || vistos.has(e)) continue;
    vistos.add(e);
    const r = e.getBoundingClientRect();
    const nombre = (e.innerText || e.value || e.getAttribute('aria-label') || e.placeholder
                    || e.title || e.name || '').trim().replace(/\\s+/g, ' ').slice(0, 70);
    const rol = (e.getAttribute('role') || e.tagName.toLowerCase()).trim();
    items.push({ i: items.length + 1, rol, nombre,
                 x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                 w: Math.round(r.width), h: Math.round(r.height) });
    if (items.length >= 200) break;
  }
  return JSON.stringify({ url: location.href, titulo: document.title, items });
})()'''


def cmd_mapa(maximo=40):
    """Mapa de la página: elementos accionables numerados (idea de playwright-mcp / browser-use)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            datos = json.loads(await c.evaluar(MAPEO_JS, ses, timeout=40))
            print("# " + datos["titulo"] + "\n# " + datos["url"] + "\n# " + str(len(datos["items"])) + " elementos")
            for it in datos["items"][:int(maximo)]:
                print("[%d] %-10s %r @%d,%d %dx%d" % (it["i"], it["rol"], it["nombre"][:60],
                                                      it["x"], it["y"], it["w"], it["h"]))
    asyncio.run(_())


def cmd_clicref(indice, captura=None):
    """Clic por número del mapa (mismos refs que `mapa`)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            datos = json.loads(await c.evaluar(MAPEO_JS, ses, timeout=40))
            n = int(indice)
            elegido = next((x for x in datos["items"] if x["i"] == n), None)
            if not elegido:
                raise SystemExit("no hay elemento [%d] en el mapa (hay %d)" % (n, len(datos["items"])))
            etiqueta = elegido["nombre"][:34] or elegido["rol"]
            caja = {"left": elegido["x"] - elegido["w"] // 2, "top": elegido["y"] - elegido["h"] // 2,
                    "width": elegido["w"], "height": elegido["h"]}
            await c.evaluar("(() => { const C = window.__tarsCursor; if (!C) return 0;"
                            " return C.apuntar(" + json.dumps(caja) + ", " + json.dumps("clic en «" + etiqueta + "»") + "); })()", ses)
            await mover_humano(c, ses, elegido["x"], elegido["y"])
            for tipo in ("mouseMoved", "mousePressed", "mouseReleased"):
                await c.send("Input.dispatchMouseEvent", {
                    "type": tipo, "x": elegido["x"], "y": elegido["y"], "button": "left",
                    "clickCount": 1, "buttons": 1 if tipo == "mousePressed" else 0}, session=ses)
                await asyncio.sleep(0.08)
                if captura and tipo == "mousePressed":
                    print("captura:", captura, guardar(captura, await captura_bytes(c, ses)))
            print("clic [%d] %s «%s» en (%d,%d)" % (n, elegido["rol"], etiqueta, elegido["x"], elegido["y"]))
    asyncio.run(_())
    auditar("clicref", str(indice))



# --------------------------------------------------------- accesibilidad: snapshot
REFS = os.environ.get("TARS_REFS", os.path.join(os.path.dirname(CONFIG), "refs.json"))
ROLES_INTERESANTES = {"button", "link", "textbox", "searchbox", "combobox", "checkbox", "radio",
                      "switch", "tab", "menuitem", "menuitemcheckbox", "option", "slider", "spinbutton"}


def guardar_refs(mapa: dict) -> None:
    os.makedirs(os.path.dirname(REFS), exist_ok=True)
    with open(REFS, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "refs": mapa}, f)


def leer_refs() -> dict:
    try:
        with open(REFS, encoding="utf-8") as f:
            return json.load(f).get("refs", {})
    except (OSError, ValueError):
        return {}


async def ax_nodos(c, ses):
    await con_reintentos(lambda: c.send("Accessibility.enable", session=ses, timeout=10))
    return (await c.send("Accessibility.getFullAXTree", session=ses, timeout=40)).get("nodes", [])


def ax_resumen(nodos, solo_interactivos=True):
    """Convierte el árbol de accesibilidad en líneas con refs: - button "Log in" [ref=e5]."""
    por_id = {n.get("nodeId"): n for n in nodos if n.get("nodeId")}
    lineas, mapa, contador, niveles = [], {}, 0, []
    for n in nodos:
        rol = (n.get("role", {}).get("value") or "").strip()
        nom = (n.get("name", {}).get("value") or "").strip().replace("\n", " ")
        if not rol or rol in ("none", "generic", "StaticText", "InlineTextBox", "RootWebArea"):
            continue
        if solo_interactivos and rol.lower() not in ROLES_INTERESANTES:
            continue
        if not nom and rol.lower() not in ROLES_INTERESANTES:
            continue
        if n.get("ignored"):
            continue
        contador += 1
        ref = "e%d" % contador
        estado = []
        for prop in n.get("properties", []) or []:
            if prop.get("name") in ("disabled", "checked", "expanded", "required", "readonly"):
                estado.append("%s=%s" % (prop["name"], prop.get("value", {}).get("value")))
        nivel = 0
        padre = n.get("parentId")
        vistos = 0
        while padre and vistos < 20:
            padre_n = por_id.get(padre)
            padre = padre_n.get("parentId") if padre_n else None
            nivel += 1
            vistos += 1
        texto = "%s \"%s\" [ref=%s]%s" % (rol, nom[:70], ref,
                                            (" {" + ", ".join(estado) + "}") if estado else "")
        lineas.append((nivel, texto))
        if n.get("backendDOMNodeId"):
            mapa[ref] = n["backendDOMNodeId"]
    # Sangría relativa: el nodo incluido más superficial queda en el margen.
    if not lineas:
        return [], mapa
    if solo_interactivos:
        return ["- " + t for _, t in lineas], mapa      # plano: la lista es lo que importa
    base = min(n for n, _ in lineas)
    return ["  " * (n - base) + "- " + t for n, t in lineas], mapa


def cmd_snapshot(solo_interactivos="si"):
    """Snapshot de accesibilidad con refs (formato inspirado en playwright-mcp)."""
    ws = ws_url()
    interactivos = str(solo_interactivos).lower() not in ("no", "0", "todo")

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            nodos = await ax_nodos(c, ses)
            lineas, mapa = ax_resumen(nodos, solo_interactivos=interactivos)
            guardar_refs(mapa)
            titulo = await c.evaluar("document.title", ses)
            print("# %s" % titulo)
            print("# %s" % (await c.evaluar("location.href", ses)))
            print("# %d nodos, %d con ref" % (len(lineas), len(mapa)))
            for l in lineas[:400]:
                print(l)
    asyncio.run(_())


async def rect_de_backend(c, ses, backend_id):
    """Rectángulo del nodo en coordenadas VISIBLES (getBoxModel devuelve coordenadas de
    documento: en páginas largas el clic caía fuera del viewport y no pasaba nada)."""
    obj = await c.send("DOM.resolveNode", {"backendNodeId": backend_id}, session=ses, timeout=20)
    r = await c.send("Runtime.callFunctionOn", {
        "objectId": obj["object"]["objectId"],
        "functionDeclaration": "function(){ if (this.scrollIntoView) this.scrollIntoView({block:'center'});"
                               " const r = this.getBoundingClientRect();"
                               " return JSON.stringify({x:r.x, y:r.y, w:r.width, h:r.height}); }",
        "returnByValue": True}, session=ses, timeout=20)
    return json.loads(r["result"]["value"])


async def clic_por_backend(c, ses, backend_id, etiqueta, captura=None):
    d = await rect_de_backend(c, ses, backend_id)
    x = int(round(d["x"] + d["w"] / 2))
    y = int(round(d["y"] + d["h"] / 2))
    vp = json.loads(await c.evaluar("JSON.stringify({w:innerWidth,h:innerHeight})", ses))
    if x >= vp["w"] or y >= vp["h"] or x < 0 or y < 0:
        raise SystemExit("el elemento quedó fuera del viewport (%d,%d de %dx%d)" % (x, y, vp["w"], vp["h"]))
    await c.evaluar("(() => { const C = window.__tarsCursor; if (!C) return 0;"
                    " return C.apuntar(" + json.dumps({"left": int(d["x"]) - 4, "top": int(d["y"]) - 4,
                                                       "width": int(d["w"]) + 8,
                                                       "height": int(d["h"]) + 8}) + ", "
                    + json.dumps("clic en «%s»" % etiqueta[:34]) + "); })()", ses)
    await mover_humano(c, ses, x, y)
    for tipo in ("mouseMoved", "mousePressed", "mouseReleased"):
        await c.send("Input.dispatchMouseEvent", {"type": tipo, "x": x, "y": y, "button": "left",
                                                  "clickCount": 1,
                                                  "buttons": 1 if tipo == "mousePressed" else 0}, session=ses)
        await asyncio.sleep(0.08)
        if captura and tipo == "mousePressed":
            print("captura:", captura, guardar(captura, await captura_bytes(c, ses)))
    return x, y


def cmd_clicref_ref(ref, captura=None):
    """Clic por ref del snapshot (e5) o por número del mapa (5)."""
    if str(ref).lower().startswith("e"):
        ws = ws_url()

        async def _():
            async with CDP(ws) as c:
                _, ses = await c.pagina()
                # Los backendNodeId caducan entre conexiones: se recalcula el árbol acá mismo.
                nodos = await ax_nodos(c, ses)
                lineas, mapa = ax_resumen(nodos, solo_interactivos=True)
                guardar_refs(mapa)
                backend = mapa.get(str(ref).lower())
                if not backend:
                    raise SystemExit("ref %s no existe en esta página (%d refs). Corré `snapshot`."
                                     % (ref, len(mapa)))
                await con_reintentos(lambda: c.send("DOM.enable", session=ses, timeout=10))
                x, y = await clic_por_backend(c, ses, backend, str(ref), captura)
                print("clic %s en (%d,%d)" % (ref, x, y))
        asyncio.run(_())
        auditar("clicref", str(ref))
        return
    cmd_clicref(ref, captura)


def cmd_acciones():
    """Qué se puede hacer ahora: lista corta de acciones con su ref."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            nodos = await ax_nodos(c, ses)
            lineas, mapa = ax_resumen(nodos, solo_interactivos=True)
            guardar_refs(mapa)
            verbo = {"button": "click", "link": "abrir", "textbox": "escribir", "searchbox": "escribir",
                     "combobox": "elegir", "checkbox": "marcar", "radio": "elegir", "switch": "cambiar",
                     "tab": "cambiar pestaña", "menuitem": "click", "option": "elegir"}
            print("# %s — %d acciones posibles" % (await c.evaluar("document.title", ses), len(lineas)))
            for l in lineas[:200]:
                rol = l.split("- ", 1)[-1].split(" ", 1)[0].lower()
                ref = l.rsplit("[ref=", 1)[-1].split("]")[0]
                nombre = l.split('"')[1] if '"' in l else ""
                print("  [%s] %-14s %s" % (ref, verbo.get(rol, "tocar"), nombre[:60]))
    asyncio.run(_())


# ------------------------------------------------------------ diagnóstico de red
def cmd_diagnostico(url=None, segundos=6):
    """Red + consola: qué falló, qué tardó y qué error tiró la página.

    `diagnostico 8` recarga y mide 8 s; `diagnostico https://x 8` navega a esa URL.
    """
    if url and str(url).isdigit():
        url, segundos = None, url
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Network.enable", session=ses, timeout=15)
            await c.send("Runtime.enable", session=ses, timeout=15)
            await c.send("Log.enable", session=ses, timeout=15)
            while not c.eventos.empty():
                c.eventos.get_nowait()
            if url:
                await c.send("Page.navigate", {"url": url}, session=ses, timeout=30)
            else:
                await c.send("Page.reload", {"ignoreCache": True}, session=ses, timeout=30)
            fin = time.time() + float(segundos)
            pedidos, fallas, consola, tiempos = {}, [], [], {}
            while time.time() < fin:
                try:
                    ev = await asyncio.wait_for(c.eventos.get(), 0.5)
                except asyncio.TimeoutError:
                    continue
                m, p = ev.get("method"), ev.get("params", {})
                if m == "Network.requestWillBeSent":
                    pedidos[p["requestId"]] = {"url": p["request"]["url"],
                                               "tipo": p.get("type", ""), "t": time.time()}
                elif m == "Network.responseReceived":
                    d = pedidos.get(p["requestId"])
                    if d:
                        d["estado"] = p["response"]["status"]
                        tiempos[p["requestId"]] = time.time() - d["t"]
                        if p["response"]["status"] >= 400:
                            fallas.append((p["response"]["status"], d["url"][:110]))
                elif m == "Network.loadingFailed":
                    d = pedidos.get(p["requestId"])
                    fallas.append(("FALLA", (d["url"][:110] if d else p.get("errorText", "?"))))
                elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "warning"):
                    consola.append("%s: %s" % (p.get("type"),
                                               " ".join(str(a.get("value", a.get("description", "")))[:120]
                                                        for a in p.get("args", []))))
                elif m == "Log.entryAdded" and p.get("entry", {}).get("level") in ("error", "warning"):
                    e = p["entry"]
                    consola.append("%s: %s" % (e.get("level"), e.get("text", "")[:120]))
            print("# %d pedidos, %d fallas, %d mensajes de consola" % (len(pedidos), len(fallas), len(consola)))
            for estado, u in fallas[:20]:
                print("  FALLA %-6s %s" % (estado, u))
            for m in consola[:15]:
                print("  CONSOLA %s" % m)
            lentos = sorted(((t, pedidos[i]["url"]) for i, t in tiempos.items()), reverse=True)[:5]
            for t, u in lentos:
                print("  LENTO %.2fs %s" % (t, u[:100]))
    asyncio.run(_())
    auditar("diagnostico", url or "(recarga)")


# --------------------------------------------------------------- sesiones y video
def cmd_guardar_sesion():
    """Guarda las pestañas abiertas para poder reabrirlas después (sin tocar cookies)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            paginas = [t for t in (await c.send("Target.getTargets"))["targetInfos"]
                       if t.get("type") == "page" and t.get("url", "").startswith("http")]
            cfg = leer_config()
            cfg["sesion"] = [{"url": t["url"], "titulo": t.get("title", "")} for t in paginas]
            guardar_config(cfg)
            print("guardadas %d pestañas en %s" % (len(paginas), CONFIG))
    asyncio.run(_())
    auditar("guardar-sesion", "")


def cmd_reabrir():
    """Reabre las pestañas guardadas."""
    sesion = leer_config().get("sesion") or []
    if not sesion:
        raise SystemExit("no hay sesión guardada: usá `guardar-sesion` primero")
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            for p in sesion:
                if not dominio_permitido(p["url"]):
                    print("salteada (allowlist):", p["url"][:80])
                    continue
                await c.send("Target.createTarget", {"url": p["url"]}, timeout=30)
                print("abierta:", p["url"][:100])
    asyncio.run(_())


def cmd_grabar(salida, segundos=4):
    """Graba la pestaña (screencast) y arma un MP4 si hay ffmpeg; si no, deja los frames."""
    frames = tempfile.mkdtemp(prefix="tarsbrowser-frames-")
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            # sin foco ni pestaña al frente, Chrome no compone y no manda frames
            try:
                await c.send("Page.bringToFront", session=ses, timeout=10)
            except Exception:
                pass
            await c.send("Page.startScreencast", {"format": "jpeg", "quality": 70,
                                                  "everyNthFrame": 2}, session=ses, timeout=20)
            n = 0
            fin = time.time() + float(segundos)
            while time.time() < fin:
                try:
                    ev = await asyncio.wait_for(c.eventos.get(), 0.5)
                except asyncio.TimeoutError:
                    continue
                if ev.get("method") == "Page.screencastFrame":
                    p = ev["params"]
                    n += 1
                    with open(os.path.join(frames, "f%04d.jpg" % n), "wb") as f:
                        f.write(base64.b64decode(p["data"]))
                    await c.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]}, session=ses)
            await c.send("Page.stopScreencast", session=ses)
            if n:
                return n, "screencast"
            # Chrome sólo manda frames si la pestaña es visible. Si está oculta o minimizada,
            # se arma la secuencia con capturas: es un timelapse, no un screencast.
            n = 0
            fin = time.time() + float(segundos)
            while time.time() < fin:
                n += 1
                datos = await captura_bytes(c, ses)
                with open(os.path.join(frames, "c%04d.png" % n), "wb") as f:
                    f.write(datos)
                await asyncio.sleep(0.12)
            return n, "capturas"
    total, modo = asyncio.run(_())
    print("frames:", total, "en", frames, "| modo:", modo)
    patron = os.path.join(frames, "f%04d.jpg" if modo == "screencast" else "c%04d.png")
    if total and shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-y", "-framerate", "8", "-i", patron,
                            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",   # x264 exige lados pares
                            "-pix_fmt", "yuv420p", salida], capture_output=True)
        if r.returncode == 0:
            print("video:", salida, os.path.getsize(salida), "bytes")
        else:
            print("ffmpeg falló:", r.stderr.decode("utf-8", "replace")[-200:])
    elif total:
        print("sin ffmpeg: quedan los frames para armar el video después")
    auditar("grabar", salida)


def cmd_mock(patron, cuerpo, segundos=20):
    """Intercepta una URL y devuelve un cuerpo fijo (probar landings sin backend)."""
    ws = ws_url()

    async def _():
        async with CDP(ws) as c:
            _, ses = await c.pagina()
            await c.send("Fetch.enable", {"patterns": [{"urlPattern": patron}]}, session=ses, timeout=20)
            fin = time.time() + float(segundos)
            atendidos = 0
            print("mock activo para %s durante %ss" % (patron, segundos))
            while time.time() < fin:
                try:
                    ev = await asyncio.wait_for(c.eventos.get(), 0.5)
                except asyncio.TimeoutError:
                    continue
                if ev.get("method") == "Fetch.requestPaused":
                    p = ev["params"]
                    await c.send("Fetch.fulfillRequest", {
                        "requestId": p["requestId"], "responseCode": 200,
                        "responseHeaders": [{"name": "Content-Type", "value": "application/json"},
                                            {"name": "Access-Control-Allow-Origin", "value": "*"}],
                        "body": base64.b64encode(cuerpo.encode("utf-8")).decode()}, session=ses)
                    atendidos += 1
            await c.send("Fetch.disable", session=ses)
            print("respuestas simuladas:", atendidos)
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
    "clicax": (cmd_clicax, 2), "sesion": (cmd_sesion, 2), "subir": (cmd_subir, 2),
    "pdf": (cmd_pdf, 1), "extraer": (cmd_extraer, 1), "bloquear": (cmd_bloquear, 1),
    "permitir": (cmd_permitir, 1), "registro": (cmd_registro, 0),
    "mapa": (cmd_mapa, 0), "clicref": (cmd_clicref_ref, 1),
    "snapshot": (cmd_snapshot, 0), "acciones": (cmd_acciones, 0),
    "diagnostico": (cmd_diagnostico, 0), "guardar-sesion": (cmd_guardar_sesion, 0),
    "reabrir": (cmd_reabrir, 0), "grabar": (cmd_grabar, 1), "mock": (cmd_mock, 2),
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
