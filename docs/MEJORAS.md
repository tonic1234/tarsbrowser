# Mejoras propuestas

Ordenadas por lo que más duele hoy. **Esfuerzo**: S = menos de 1 h, M = media jornada,
L = una jornada o más. Todas son mecanismos reales del protocolo o del sistema, no deseos.

## A. Robustez — lo que hoy puede fallar en silencio

| # | Mejora | Por qué | Cómo | Esf. |
|---|---|---|---|---|
| A1 | **Localizadores por accesibilidad** | Hoy `clic` usa coordenadas. Si la página se reacomoda, el clic cae en otro lado y no da error | `Accessibility.getFullAXTree` + `DOM.getBoxModel` del nodo elegido: se elige el elemento por rol/nombre («botón *Log in*») y se calculan las coordenadas en el momento | M |
| A2 | **Esperas explícitas** | Los `sleep` fijos son la causa nº 1 de flakiness y de lentitud | `Page.navigate` + `Page.loadEventFired` / `Network.idle`; `Runtime.evaluate` con polling de un predicado (`hasta(cond, 10s)`) en vez de `sleep(4)` | S |
| A3 | **Reintentos con backoff** | Un `attachToTarget` colgado hoy cuesta una corrida entera | Decorador `reintentar(n=3, backoff)` en las llamadas CDP idempotentes; el attach ya tiene 1 reintento | S |
| A4 | **Multipestaña ordenada** | `pagina()` toma la última pestaña http: puede operar sobre la pestaña equivocada | Registrar la pestaña de trabajo por `targetId` en el archivo de config, y `cerrar` sólo esa | S |
| A5 | **Verificación de descargas** | Hoy se confía en el evento `completed` | Sumar tamaño esperado + `sha256` cuando el sitio lo publique; y listar el destino al final | S |
| A6 | **Detectar sesión caída** | Si el perfil se desloguea, todo lo demás falla con errores raros | Comando `sesion <url> <selector-de-logueado>`: dice en una línea si la sesión sigue viva | S |
| A7 | **Supervisor del proceso Chrome** | Si Chrome se cierra, el túnel queda vivo y todo falla con timeout | `estado` ya detecta; agregar relanzado automático opcional antes de cada acción | M |

## B. Capacidades que faltan

| # | Mejora | Para qué sirve | Mecanismo CDP | Esf. |
|---|---|---|---|---|
| B1 | **Subir archivos** | Bajar anda; subir (formularios, tickets, imágenes) no existe | `DOM.setFileInputFiles` sobre el `input[type=file]` | S |
| B2 | **Cookies y sesión** | Exportar/importar la sesión para reusarla en otro perfil o depurar | `Storage.getCookies` / `Storage.setCookies` (ojo: nunca volcarlas al chat) | M |
| B3 | **Bloqueo de dominios** | Acelerar y evitar trackers/ads que ensucian la captura | `Network.setBlockedURLs` con una lista configurable | S |
| B4 | **PDF de una página** | Entregables imprimibles sin pasar por el navegador del usuario | `Page.printToPDF` (con `Emulation.setEmulatedMedia: print`) | S |
| B5 | **Grabación de la sesión** | Prueba visual de lo que hizo el agente, sin depender de capturas sueltas | `Page.startScreencast` → frames → GIF/MP4 con ffmpeg | M |
| B6 | **Interceptar y responder red** | Testear landings sin backend, simular errores | `Fetch.enable` + `Fetch.fulfillRequest` | M |
| B7 | **Extracción estructurada** | Devolver tablas/listas como JSON en vez de texto suelto | `Runtime.evaluate` con un selector + mapeo declarativo | S |
| B8 | **Modo headless para CI** | Correr los tests sin ventana | `--headless=new` + `Emulation.setFocusEmulationEnabled` (sin esto los timers se congelan) | S |

## C. Producto

| # | Mejora | Por qué | Esf. |
|---|---|---|---|
| C1 | **Empaquetado instalable** (`pyproject.toml` + `pipx install`) | Hoy es un archivo suelto que hay que copiar | S |
| C2 | **Servidor MCP** | Cualquier agente (Claude, Hermes, Cursor) lo usa como herramienta estándar en vez de por CLI. Es el salto de «script mío» a «herramienta» | M |
| C3 | **CI en 3 sistemas** | `ruff` + `unittest` en ubuntu/macos/windows, con Chrome headless para el test de integración: es lo único que evita que el adaptador de macOS se rompa sin que nadie lo note | M |
| C4 | **Releases con changelog** | Poder volver a una versión que andaba | S |
| C5 | **Docker para el lado servidor** | Que el cliente no dependa de Python en la máquina que orquesta | M |

## D. Seguridad

| # | Mejora | Por qué | Esf. |
|---|---|---|---|
| D1 | **Token en cabecera, no en query** | Un token en la URL queda en logs y en el historial | S |
| D2 | **Escuchar sólo en loopback / tailnet** | CDP es control total del navegador: nunca en 0.0.0.0 | S |
| D3 | **Allowlist de dominios** | Que el agente no navegue a cualquier lado por error | S |
| D4 | **Auditoría de acciones** | Registro append-only de qué se hizo, cuándo y sobre qué URL (sin credenciales) | S |
| D5 | **Rotación del buzón** | `secreto.py` ya cifra; falta rotar clave maestra y auditar accesos | M |

## E. Rendimiento

| # | Mejora | Por qué | Esf. |
|---|---|---|---|
| E1 | **Una sola conexión CDP por corrida** | Hoy cada comando abre y cierra WebSocket + re-adjunta: ~300 ms por acción | Un cliente persistente tipo `tarsbrowser serve` | M |
| E2 | **Cachear la detección de sistema** | Ya se cachea en proceso; con E1 quedaría cacheada entre comandos | — |
| E3 | **Menos `evaluate` por acción** | Cada `evaluar` es un ida y vuelta; se pueden agrupar en una sola expresión | S |

## F. Específico de macOS (pendiente de verificar en la Mac)

| # | Punto | Qué mirar |
|---|---|---|
| F1 | `open -na` desde SSH | Si la ventana no aparece en el escritorio del usuario, el fallback es `sudo launchctl asuser $(id -u) ...` |
| F2 | Pantallas con Spaces separados | Si el usuario usa «cada pantalla con su propio Space», mover la ventana a la otra pantalla puede requerir AppleScript (permiso de Accesibilidad) |
| F3 | Retina | El `dpr` es 2: las capturas salen al doble. El cliente ya lee `devicePixelRatio`, pero hay que confirmar coordenadas en capturas |
| F4 | Permisos | Automatización/Accesibilidad sólo si se usa AppleScript; con CDP puro no hace falta |

## Orden sugerido

1. **A1 + A2 + A3** (media jornada): es lo que convierte la herramienta de «funciona cuando sale
   bien» a «funciona».
2. **B1 + B4 + B8** (media jornada): subir archivos y PDF abren casos de uso nuevos; headless
   habilita el CI.
3. **C1 + C3** (media jornada): instalable y con tests en 3 sistemas.
4. **C2** (una jornada): servidor MCP — el techo de la herramienta.
5. D1–D4, A4–A6, B5: mejoras continuas.
