# Changelog

## 1.4.0
- **Cursor suave y rápido.** Antes: 69 eventos en 13,5 s, intervalo medio 191 ms, saltos de 40-70 px.
  Ahora: 33 cuadros, intervalo 10 ms, salto mediano 12 px, ~620 ms para 1000 px.
  Causas: cada evento esperaba la respuesta por SSH (~190 ms) y Chrome coalesce a ~16 Hz.
  Arreglos: `CDP.enviar()` (sin esperar respuesta), programación por reloj de pared, y el cursor
  dibujado persiguiendo el objetivo con un lazo `requestAnimationFrame` (cursor.js v5).


## 1.3.0
- **`snapshot`**: árbol de accesibilidad con refs (`e1`, `e2`…) — formato inspirado en
  `microsoft/playwright-mcp`. Incluye estados (disabled/checked/required). Las refs se recalculan en
  cada clic porque los `backendNodeId` caducan entre conexiones.
- **`clicref e5`**: clic por ref del snapshot, además del número del mapa.
- **`acciones`**: qué se puede hacer ahora (verbo + ref + nombre), idea de `observe()` de
  `browserbase/stagehand` (MIT).
- **`diagnostico [url] [seg]`**: pedidos fallidos, mensajes de consola y recursos más lentos
  (`Network`, `Runtime.consoleAPICalled`, `Log.entryAdded`) — inspirado en `chrome-devtools-mcp`.
- **`grabar <salida.mp4> [seg]`**: screencast de la pestaña; si Chrome no compone (pestaña oculta),
  arma un timelapse con capturas. Requiere ffmpeg para el video.
- **`mock <patron> <json>`**: intercepta y responde (`Fetch.enable`), para probar landings sin backend.
- **`guardar-sesion` / `reabrir`**: pestañas persistentes. Las cookies **no** se exportan: quedan en
  el perfil, que es la decisión segura.
- **`Dockerfile`** para correr el cliente en un contenedor.
- MCP: 23 herramientas (se suman `snapshot`, `acciones`, `diagnostico`, `grabar`, `guardar_sesion`,
  `reabrir`).
- Tests: 19 sin red + 11 de integración.

## 1.2.1
- **`mapa` y `clicref`**: mapa de la página con los elementos accionables numerados (rol, nombre,
  centro y tamaño) y clic por número. Idea adaptada de `microsoft/playwright-mcp` (snapshot con refs)
  y de `buildDomTree.js` de `browser-use` (MIT): sin dependencias, sobre el DOM, con el cursor
  dibujado igual que el resto.
- **`docs/REPOS-PARA-NAVEGACION.md`**: investigación de repos abiertos (licencias, qué tomar, en qué
  orden y qué descartar con motivo).
- Tests: 2 de integración nuevos (`mapa` numera, `clicref` clickea).

## 1.2.0
- **Robustez**: `esperar`/`esperar_selector`/`esperar_carga` en lugar de `sleep` fijos; reintentos
  con backoff en `attach`/`Page.enable`; la pestaña de trabajo se recuerda en la config (antes se
  agarraba «la última» y podía operar sobre la pestaña equivocada).
- **Accesibilidad**: `clicax <rol> "<nombre>"` — clic por rol y nombre del árbol de accesibilidad
  (`Accessibility.getFullAXTree` + `DOM.getBoxModel`), sin coordenadas.
- **Capacidades nuevas**: `subir` (`DOM.setFileInputFiles`), `pdf` (`Page.printToPDF` con medio de
  impresión), `extraer` (JSON por selector), `bloquear` (`Network.setBlockedURLs`), `sesion`
  (¿sigue viva la sesión?).
- **Seguridad y auditoría**: `permitir` (allowlist de dominios, se aplica en `nav`), `registro`
  (log append-only sin credenciales) y verificación de descargas por **tamaño + sha256 medidos en
  el destino**.
- **Auto-recuperación**: si el CDP está caído, `ws_url()` intenta abrir la ventana una vez
  (`TARS_AUTORECUPERAR=0` lo apaga).
- **MCP**: `mcp_server.py` expone 14 herramientas por stdio para que cualquier agente lo use.
- Tests: 19 sin red + 6 de integración contra el Chrome real.

## 1.1.0
- **macOS y Linux**: detección de sistema en el host remoto (`uname -s`) y lanzadores
  `arrancar-macos.sh` / `arrancar-linux.sh`. El perfil y la geometría se resuelven por sistema.
- **`sistema`**: informe de host, SO, Chrome, perfil, geometría y estado de CDP.
- **`ventana <izq,arriba,ancho,alto|0>`**: fija la geometría y la persiste en `config.json`
  (el env `TARS_BOUNDS` sigue mandando).
- Decodificación de salida tolerante a Windows (cp850) y a UTF-8.
- Tests sin red + CI en Ubuntu/macOS/Windows.

## 1.0.0
- Primera versión: `abrir`, `estado`, `nav`, `captura`, `buscar`, `imagenes`, `bajar`, `clic`,
  `apuntar`, `demo`, `escribir`, `login`, `tipear_secreto`, `cursor`, `cerrar`.
- Cursor dibujado con movimiento en curva, recuadro del objetivo y etiqueta de la acción.
- Descargas autónomas por `Browser.setDownloadBehavior`.
- Login con el buzón de secretos (la clave nunca se imprime).
