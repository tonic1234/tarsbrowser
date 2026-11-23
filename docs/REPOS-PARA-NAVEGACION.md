# Repos abiertos que sirven para mejorar la navegación

Investigación del 22-nov-2026. Todos los elegidos son **MIT o Apache-2.0**, compatibles con este
repo (MIT), siempre citando el origen. El criterio no fue «qué proyecto es famoso» sino **qué
mecanismo concreto nos falta**.

## Los cinco que importan

| Repo | Licencia | Estrellas | Qué tiene que nos sirve |
|---|---|---|---|
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | Apache-2.0 | 40k | **Snapshot de accesibilidad con refs** (`[ref=e12]`): un texto compacto con los elementos accionables y una referencia estable. Es la forma más robusta conocida de que un agente elija qué tocar |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | MIT | 121.8k | `buildDomTree.js`: script inyectado que **indexa los elementos interactivos** y devuelve un árbol chico con índices y marcas visuales (Set-of-Mark) |
| [browserbase/stagehand](https://github.com/browserbase/stagehand) | MIT | 26.1k | `observe()`: devuelve **la lista de acciones posibles** en la página (con sus selectores), antes de actuar. Cambia el flujo de «adivinar» a «elegir de una lista» |
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Apache-2.0 | 58.9k | El MCP oficial de Chrome: **consola, red, trazas de performance** y esperas basadas en eventos, no en tiempos |
| [steel-dev/steel-browser](https://github.com/steel-dev/steel-browser) | Apache-2.0 | 8k | **Sesiones de navegador** de primera clase: estado guardado, reanudar, vista en vivo. Es el modelo de «sesión» que a nosotros nos falta |

## Qué tomamos de cada uno, y en qué orden

### 1. `mapa` + `clicref` — **ya implementado en 1.2.1**

Adaptado de la idea de playwright-mcp y de `buildDomTree.js` de browser-use, sin dependencias:
se recorre el DOM, se filtran los elementos visibles y accionables (link, button, input, select,
role=tab/menuitem, contenteditable) y se devuelve una lista numerada con rol, nombre y centro.

```
# Nexus Mods - Users - Login
# 8 elementos
[1] input      'Email or Username' @421,157 482x36
[2] input      'Password' @209 482x36
[5] input      'Log in' @421,381 482x36
[6] a          'Register here' @360,427 94x18
```

Con eso el agente puede decir «clic en [5]» en vez de inventar coordenadas, y el clic se sigue
dibujando con el cursor. Ganancia medida: en la misma página pasamos de «adivinar un selector CSS»
a una lista corta y legible.

### 2. Snapshot de accesibilidad con refs (siguiente, ~4 h)

Nuestro `clicax` ya usa el árbol de accesibilidad, pero devuelve un clic, no un mapa. Lo que falta
es el **snapshot**: un texto con la estructura (`- button "Log in" [ref=e5]`) que sirva de contexto
completo de la página. Ventaja sobre el mapa del DOM: incluye lo que el DOM no expone bien
(roles ARIA calculados, labels asociados, estados checked/disabled/expanded).

Plan: `snapshot [--interactivos]` que use `Accessibility.getFullAXTree` + refs por
`backendDOMNodeId`, y `clicref` acepte tanto `5` (mapa DOM) como `e5` (snapshot).

### 3. `observe` (stagehand) → `acciones` (~3 h)

En vez de que el agente lea toda la página, un comando que devuelve **qué se puede hacer ahora**:
lista de acciones con su verbo, su objetivo y su selector. Es la diferencia entre «mirá todo el DOM»
y «elegí de estas 6 acciones».

### 4. Diagnóstico de red y consola (chrome-devtools-mcp) (~3 h)

Cuando una automatización falla, hoy adivinamos. Con `Network.enable` + `Runtime.consoleAPICalled`
podemos dar `diagnostico`: peticiones fallidas (4xx/5xx), errores de consola y tiempo por recurso.
Es la herramienta que convierte «no anduvo» en «el POST devolvió 403 porque falta el token».

### 5. Sesiones persistentes (steel-browser) (~1 jornada)

Modelo: un `sesion.json` por sitio con perfil, cookies (nunca en claro fuera del perfil), estado y
última URL. Permite reanudar sin volver a loguearse y aislar sitios entre sí. Es el paso previo
obligatorio para cookies (B2), que hoy está frenado por una decisión de seguridad.

## Los que miré y descarté (con motivo)

| Repo | Por qué no |
|---|---|
| **Playwright / Puppeteer** | Resuelven lo mismo pero traen su propio runtime y su propio navegador: reemplazan el diseño (CDP crudo sobre el Chrome del usuario) en vez de mejorarlo. Sí tomamos sus ideas (locators por accesibilidad, `waitForLoadState`) |
| **Skyvern** (AGPL) | Licencia incompatible con MIT si se copia código, y su enfoque es visión + LLM por paso: caro y lento para lo nuestro |
| **OmniParser** | Solo tiene sentido cuando el DOM no sirve (canvas, juegos). Nuestro caso es web normal |
| **nodriver / undetected-chromedriver** | Son para **evadir** detección de bots. No es nuestro problema y no queremos ese camino |
| **Steel Browser como servicio** | Habría que correr un contenedor con su propio navegador; nosotros usamos el Chrome real del usuario, que es justo la ventaja (sesión y IP doméstica) |

## Criterio para adoptar algo

1. ¿Resuelve algo que hoy falla **en silencio**? (Prioridad máxima: `mapa`, `snapshot`, diagnóstico).
2. ¿Se puede tomar el **mecanismo** sin traer la dependencia? (Todos los elegidos sí).
3. ¿Aporta licencia compatible y se puede citar? (MIT/Apache-2.0).
4. ¿Se puede testear sin red? (Si no, va con test de integración marcado).
