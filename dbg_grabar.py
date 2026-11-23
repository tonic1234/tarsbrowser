
import asyncio, sys, json, time, base64
sys.path.insert(0,"/root/tarsbrowser-repo")
import tarsbrowser as tb

async def main():
    ws = tb.ws_url()
    async with tb.CDP(ws) as c:
        tid, ses = await c.pagina()
        print("tab", tid, "ses", ses[:8])
        r = await c.send("Page.startScreencast", {"format":"jpeg","quality":60,"everyNthFrame":1}, session=ses, timeout=15)
        print("start:", r)
        tipos = {}
        frames = 0
        fin = time.time()+4
        while time.time() < fin:
            try:
                ev = await asyncio.wait_for(c.eventos.get(), 0.4)
            except asyncio.TimeoutError:
                continue
            m = ev.get("method")
            tipos[m] = tipos.get(m,0)+1
            if m == "Page.screencastFrame":
                frames += 1
                p = ev["params"]
                await c.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]}, session=ses)
        print("frames:", frames, "| eventos:", json.dumps(tipos)[:300])
        await c.send("Page.stopScreencast", session=ses)
asyncio.run(main())
