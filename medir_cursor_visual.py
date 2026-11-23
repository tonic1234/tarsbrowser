#!/usr/bin/env python3
"""Mide el cursor DIBUJADO: cuánto salta por cuadro (suavidad visual real)."""
import asyncio
import json
import statistics
import sys
import time

sys.path.insert(0, "/root/tarsbrowser-repo")
import tarsbrowser as tb

SAMPLER = """(() => {
  window.__pos = [];
  window.__posOn = true;
  const leer = () => {
    const e = document.getElementById('__tars_cursor');
    if (e && window.__posOn) {
      const r = e.getBoundingClientRect();
      window.__pos.push([performance.now(), Math.round(r.x), Math.round(r.y)]);
    }
    if (window.__posOn) requestAnimationFrame(leer);
  };
  requestAnimationFrame(leer);
  return 'ok';
})()"""

LEER = "(() => { window.__posOn = false; return JSON.stringify(window.__pos); })()"


async def main():
    async with tb.CDP(tb.ws_url()) as c:
        _, ses = await c.pagina()
        await tb.instalar_cursor(c, ses)
        vp = json.loads(await c.evaluar("JSON.stringify({w:innerWidth,h:innerHeight})", ses))
        await c.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 40, "y": 50}, session=ses)
        await asyncio.sleep(0.4)
        await c.evaluar(SAMPLER, ses)
        t0 = time.perf_counter()
        await tb.mover_humano(c, ses, int(vp["w"] * 0.8), int(vp["h"] * 0.8))
        dur = (time.perf_counter() - t0) * 1000
        pos = json.loads(await c.evaluar(LEER, ses))
        saltos, dts = [], []
        for (t_a, x_a, y_a), (t_b, x_b, y_b) in zip(pos, pos[1:]):
            d = ((x_b - x_a) ** 2 + (y_b - y_a) ** 2) ** 0.5
            if d > 0.5:
                saltos.append(d)
                dts.append(t_b - t_a)
        print("cuadros con movimiento: %d | duración del movimiento: %.0f ms" % (len(saltos), dur))
        if saltos:
            print("  salto por cuadro → medio %.1f px | mediana %.1f | p90 %.1f | máx %.1f"
                  % (statistics.mean(saltos), statistics.median(saltos),
                     sorted(saltos)[int(len(saltos) * .9) - 1], max(saltos)))
            print("  intervalo → mediana %.1f ms (%.0f cuadros/s)"
                  % (statistics.median(dts), 1000 / max(statistics.median(dts), 1)))


asyncio.run(main())
