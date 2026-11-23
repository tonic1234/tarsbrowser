#!/usr/bin/env python3
"""Mide suavidad del cursor: intervalo entre eventos de mouse que llegan a la página."""
import asyncio
import json
import statistics
import sys
import time

sys.path.insert(0, "/root/tarsbrowser-repo")
import tarsbrowser as tb

MEDIR = """(() => {
  window.__mm = [];
  window.__mmOn = true;
  if (!window.__mmHook) {
    window.__mmHook = (e) => { if (window.__mmOn) window.__mm.push(performance.now()); };
    window.addEventListener('mousemove', window.__mmHook, true);
  }
  window.__mm.length = 0;
  return 'ok';
})()"""

LEER = "(() => { window.__mmOn = false; return JSON.stringify(window.__mm); })()"


async def main():
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        await tb.instalar_cursor(c, ses)
        vp = json.loads(await c.evaluar("JSON.stringify({w:innerWidth,h:innerHeight})", ses))
        x0, y0 = 40, 60
        x1, y1 = int(vp["w"] * 0.8), int(vp["h"] * 0.8)
        await c.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x0, "y": y0}, session=ses)
        await asyncio.sleep(0.3)
        await c.evaluar(MEDIR, ses)
        t0 = time.perf_counter()
        await tb.mover_humano(c, ses, x1, y1)
        dur = (time.perf_counter() - t0) * 1000
        marcas = json.loads(await c.evaluar(LEER, ses))
        if len(marcas) >= 5:
            dt = [b - a for a, b in zip(marcas, marcas[1:])]
            centro = dt[1:-1] or dt
            centro_ord = sorted(centro)
            p90 = centro_ord[int(len(centro_ord) * 0.9) - 1]
            print("eventos: %d | duración total: %.0f ms" % (len(marcas), dur))
            print("  todos        → medio %.1f | mediana %.1f | máx %.1f | desvío %.1f"
                  % (statistics.mean(dt), statistics.median(dt), max(dt), statistics.pstdev(dt)))
            print("  sin extremos → medio %.1f | mediana %.1f | p90 %.1f | máx %.1f | desvío %.1f"
                  % (statistics.mean(centro), statistics.median(centro), p90, max(centro),
                     statistics.pstdev(centro)))
        else:
            print("eventos insuficientes:", len(marcas))


asyncio.run(main())
