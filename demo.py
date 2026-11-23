#!/usr/bin/env python3
"""Demo en vivo: recorre lo que hace tarsbrowser, en la ventana visible del usuario.

    python3 demo.py [carpeta_de_salida]

Mientras corre, el cursor dibujado se ve trabajando en la pantalla del navegador.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import tarsbrowser as tb  # noqa: E402

SALIDA = sys.argv[1] if len(sys.argv) > 1 else "/root/demo-tarsbrowser"
EJECT = "https://es.wikipedia.org/wiki/Red_Dead_Redemption_2"


def acto(n, texto):
    print("\n=== ACTO %d · %s" % (n, texto))


def foto(nombre, datos):
    ruta = os.path.join(SALIDA, nombre)
    tb.guardar(ruta, datos)
    print("   captura:", nombre, len(datos), "bytes")


async def limpiar():
    """Deja una sola pestaña http: menos ruido y capturas más confiables."""
    async with tb.CDP(tb.ws_url()) as c:
        paginas = [t for t in (await c.send("Target.getTargets"))["targetInfos"]
                   if t.get("type") == "page" and t.get("url", "").startswith("http")]
        for t in paginas[1:]:
            await c.send("Target.closeTarget", {"targetId": t["targetId"]})
        print("   pestañas cerradas:", max(0, len(paginas) - 1))


async def estado():
    acto(1, "estado del navegador")
    async with tb.CDP(tb.ws_url()) as c:
        v = await c.send("Browser.getVersion")
        print("   navegador:", v.get("product"), "| headless:", "Headless" in v.get("userAgent", ""))
        for t in (await c.send("Target.getTargets"))["targetInfos"]:
            if t.get("type") == "page":
                print("   pestaña:", t.get("title", "")[:50], "|", t.get("url", "")[:60])


async def navegar(url, selector, nombre_foto):
    acto(2, "navegar y esperar (sin sleeps a ciegas)")
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        await c.send("Page.navigate", {"url": url}, session=ses)
        print("   carga completa:", await tb.esperar_carga(c, ses),
              "| selector presente:", await tb.esperar_selector(c, ses, selector))
        await tb.instalar_cursor(c, ses)
        print("   título:", await c.evaluar("document.title", ses))
        foto(nombre_foto, await tb.captura_bytes(c, ses))


async def snapshot_acciones():
    acto(3, "mapa de accesibilidad con refs y acciones posibles")
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        nodos = await tb.ax_nodos(c, ses)
        lineas, mapa = tb.ax_resumen(nodos, solo_interactivos=True)
        tb.guardar_refs(mapa)
        print("   %d elementos accionables" % len(lineas))
        for l in lineas[:8]:
            print("  ", l)
        foto("02-snapshot.png", await tb.captura_bytes(c, ses))
        return mapa


async def clic_por_nombre(mapa):
    acto(4, "clic por nombre accesible (no por coordenadas)")
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        nodos = await tb.ax_nodos(c, ses)
        lineas, mapa = tb.ax_resumen(nodos, solo_interactivos=True)
        elegido = next((l for l in lineas if 'link "' in l and "More information" in l), None)
        if not elegido:
            elegido = next((l for l in lineas if 'link "' in l), None)
        if not elegido:
            print("   sin links: salteado")
            return
        ref = elegido.rsplit("[ref=", 1)[-1].split("]")[0]
        nombre = elegido.split('"')[1]
        antes = await c.evaluar("location.href", ses)
        print("   objetivo: [%s] «%s»" % (ref, nombre[:50]))
        await c.send("DOM.enable", session=ses)
        await tb.clic_por_backend(c, ses, mapa[ref], nombre, os.path.join(SALIDA, "03-clic.png"))
        await tb.esperar_carga(c, ses, timeout=10)
        await asyncio.sleep(1.5)
        despues = await c.evaluar("location.href", ses)
        print("   antes:", antes[:60])
        print("   ahora:", despues[:60])
        print("   navegó:", antes != despues)
        foto("04-despues-del-clic.png", await tb.captura_bytes(c, ses))


async def extraer_pdf():
    acto(5, "extraer datos y generar PDF")
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        await c.send("Page.navigate", {"url": EJECT}, session=ses)
        await tb.esperar_selector(c, ses, "#firstHeading")
        r = await c.evaluar("""JSON.stringify([...document.querySelectorAll('h2')]
            .map(e => e.innerText.trim()).filter(Boolean).slice(0, 5))""", ses)
        print("   secciones:", json.loads(r))
        await c.send("Emulation.setEmulatedMedia", {"media": "print"}, session=ses)
        try:
            pdf = await c.send("Page.printToPDF", {"printBackground": True}, session=ses, timeout=90)
        finally:
            await c.send("Emulation.setEmulatedMedia", {"media": ""}, session=ses)
        datos = base64.b64decode(pdf["data"])
        tb.guardar(os.path.join(SALIDA, "articulo.pdf"), datos)
        print("   PDF:", len(datos), "bytes | cabecera:", datos[:5])


async def descargar():
    acto(6, "descarga autónoma: nombre y carpeta automáticos, sin diálogo")
    async with tb.CDP(tb.ws_url()) as c:
        await c.send("Browser.setDownloadBehavior",
                     {"behavior": "allow", "downloadPath": "C:\\tars-descargas", "eventsEnabled": True})
        await c.send("Target.createTarget",
                     {"url": "https://github.com/octocat/Hello-World/archive/refs/heads/master.zip"})
        nombre = None
        while True:
            ev = await asyncio.wait_for(c.eventos.get(), 90)
            if ev.get("method") == "Browser.downloadWillBegin":
                nombre = ev["params"].get("suggestedFilename")
                print("   archivo:", nombre)
            if ev.get("method") == "Browser.downloadProgress" and ev["params"].get("state") == "completed":
                print("   bytes:", ev["params"].get("receivedBytes"))
                print("   verificado en disco:", tb.hash_remoto("C:\\\\tars-descargas\\\\" + str(nombre))[:120])
                return


async def diagnostico():
    acto(7, "diagnóstico de red y consola")
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        await c.send("Network.enable", session=ses)
        await c.send("Runtime.enable", session=ses)
        await c.send("Page.reload", {"ignoreCache": True}, session=ses)
        fin, total, fallas, lentos = time.time() + 4, 0, 0, []
        while time.time() < fin:
            try:
                ev = await asyncio.wait_for(c.eventos.get(), 0.4)
            except asyncio.TimeoutError:
                continue
            m, p = ev.get("method"), ev.get("params", {})
            if m == "Network.requestWillBeSent":
                total += 1
            elif m == "Network.responseReceived":
                if p["response"]["status"] >= 400:
                    fallas += 1
                    lentos.append("%s %s" % (p["response"]["status"], p["response"]["url"][:70]))
        print("   pedidos:", total, "| fallas:", fallas)
        for l in lentos[:3]:
            print("   FALLA", l)


async def main():
    os.makedirs(SALIDA, exist_ok=True)
    t0 = time.time()
    print("DEMO tarsbrowser — mirá el segundo monitor: el cursor se mueve solo")
    await estado()
    await limpiar()
    await navegar("https://example.com", "body a", "01-navegacion.png")
    mapa = await snapshot_acciones()

    video = os.path.join(SALIDA, "demo.mp4")
    grabador = subprocess.Popen([sys.executable, os.path.join(AQUI, "tarsbrowser.py"),
                                 "grabar", video, "6"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    await asyncio.sleep(1)
    await clic_por_nombre(mapa)
    print("\n   [video]", grabador.communicate()[0].strip().replace("\n", " | ")[:180])

    await extraer_pdf()
    await descargar()
    await diagnostico()

    print("\n=== RESUMEN (%.0f s) ===" % (time.time() - t0))
    for f in sorted(os.listdir(SALIDA)):
        print("   %-24s %9d bytes" % (f, os.path.getsize(os.path.join(SALIDA, f))))


if __name__ == "__main__":
    asyncio.run(main())
