# Changelog

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
