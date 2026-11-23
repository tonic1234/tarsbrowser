# tarsbrowser

Maneja un **Chrome propio** (perfil aparte) en la máquina del usuario desde otro equipo, por
**CDP sobre un túnel SSH**. Pensado para que un agente busque, baje archivos, capture pantallas y
se loguee **sin mover el puntero del usuario ni robarle el foco**, y con un **cursor dibujado**
dentro de la página para que se vea exactamente qué está haciendo.

Funciona en **Windows, macOS y Linux**.

## Qué resuelve

| Problema | Cómo lo resuelve |
|---|---|
| Chrome del usuario con "preguntar dónde guardar" | `Browser.setDownloadBehavior` fija carpeta: nombre y destino automáticos, sin diálogo |
| El agente no puede usar la sesión del usuario sin molestarlo | Perfil dedicado + CDP: los clics no mueven el puntero real |
| Nadie ve qué está haciendo el agente | Cursor dibujado con movimiento en curva, recuadro del objetivo y etiqueta de la acción |
| Las contraseñas terminan en el chat | `login` lee del buzón cifrado y tipea carácter por carácter; nunca imprime la clave |
| Chrome 136+ no deja depurar el perfil por defecto | Siempre `--user-data-dir` propio |

## Instalación rápida

```bash
git clone git@github.com:tonic1234/tarsbrowser.git
cd tarsbrowser
python3 -m pip install websockets      # única dependencia
export TARS_HOST=usuario@host         # a dónde conectarse por SSH
```

En la máquina destino hay que dejar el lanzador una vez:

- **Windows**: copiar `scripts/arrancar-windows.ps1` y crear la tarea programada
  (`LogonType Interactive`, si no la ventana no se ve). Ver `docs/INSTALACION.md`.
- **macOS / Linux**: `mkdir -p ~/.tars-chrome && cp scripts/arrancar-macos.sh ~/.tars-chrome/`
  (en Linux, `arrancar-linux.sh`).

## Uso

```bash
python3 tarsbrowser.py sistema                  # host, SO, Chrome, estado de CDP
python3 tarsbrowser.py abrir                    # abre/reabre la ventana y espera CDP
python3 tarsbrowser.py ventana 1924,4,856,760   # fija la geometría de la ventana
python3 tarsbrowser.py estado                   # pestañas abiertas
python3 tarsbrowser.py nav https://ejemplo.com
python3 tarsbrowser.py captura /tmp/x.png
python3 tarsbrowser.py buscar "consulta" /tmp/b.png
python3 tarsbrowser.py imagenes "consulta" 4 /tmp/imgs
python3 tarsbrowser.py bajar https://sitio/archivo.zip 'C:\tars-descargas'
python3 tarsbrowser.py clic 420 520             # con onda visible
python3 tarsbrowser.py apuntar "#campo" "escribiendo el correo"
python3 tarsbrowser.py demo                     # recorrido de muestra, no clickea nada
python3 tarsbrowser.py escribir "#campo" "texto"
python3 tarsbrowser.py login https://sitio/login "#user" "#pass" usuario nombre-en-buzon
python3 tarsbrowser.py clicax button "Log in"   # clic por rol/nombre accesible, sin coordenadas
python3 tarsbrowser.py subir "#file" /tmp/a.pdf  # sube un archivo al input
python3 tarsbrowser.py pdf /tmp/pagina.pdf      # PDF con medio de impresión
python3 tarsbrowser.py mapa 40                  # elementos accionables numerados
python3 tarsbrowser.py clicref 5                # clic por número del mapa
python3 tarsbrowser.py extraer "a[href]" href   # JSON de lo que matchea
python3 tarsbrowser.py sesion https://sitio/panel "#avatar"   # ¿la sesión sigue viva?
python3 tarsbrowser.py permitir "ejemplo.com"   # allowlist (vacío = todos)
python3 tarsbrowser.py registro 20              # auditoría de acciones
python3 tarsbrowser.py cursor off
```

## Como servidor MCP

`mcp_server.py` expone la herramienta por stdio (JSON-RPC), con 14 herramientas tipadas. Sirve para
que cualquier agente la use como herramienta estándar en vez de por CLI:

```json
{
  "mcpServers": {
    "tarsbrowser": {
      "command": "python3",
      "args": ["/ruta/a/tarsbrowser/mcp_server.py"],
      "env": { "TARS_HOST": "usuario@maquina" }
    }
  }
}
```

## Variables de entorno

| Variable | Para qué | Default |
|---|---|---|
| `TARS_HOST` | host SSH del navegador (`usuario@maquina`) | `anram@100.111.30.59` |
| `TARS_KEY` | clave SSH | `~/.ssh/id_ed25519` |
| `TARS_CDP_PORT` / `TARS_CDP_REMOTO` | puerto local del túnel / puerto en el destino | `9223` / `9222` |
| `TARS_PERFIL` | carpeta del perfil dedicado | por sistema |
| `TARS_BOUNDS` | geometría `izq,arriba,ancho,alto` | la guardada con `ventana` |
| `TARS_CURSOR` | `0` apaga el cursor dibujado | encendido |
| `TARS_SECRETOS` | carpeta del buzón de secretos | `/root/.hermes/secretos` |

## Cursor dibujado

En Windows/macOS hay **un solo puntero**: no existe un segundo mouse. El cursor que se ve es un
overlay dibujado por `cursor.js` **dentro de la página**; lo mueve el cliente CDP enviando eventos
de mouse reales a lo largo de una curva, así que coincide siempre con la acción.

No intercepta nada (`pointer-events: none`) y no toca el puntero del sistema.

## Límites (honestos)

- **El captcha no se automatiza.** Un challenge interactivo (Cloudflare Turnstile) lo resuelve una
  persona: es el control anti-bot del sitio, no una traba técnica nuestra.
- **El perfil arranca sin sesión.** Hay que loguearse una vez en esa ventana; después queda.
- **`Page.enable` puede colgarse** al adjuntarse a una pestaña ya existente: el cliente reintenta el
  attach una vez.
- **La ventana se achica sola** (Chrome restaura tamaños): `ventana` + reafirmación en cada comando.
- **`requestAnimationFrame` no se usa para animar**: se estrangula cuando la ventana no tiene foco.

## Estado

Probado de punta a punta en **Windows 11 + Chrome 157**: ventana, descargas verificadas por
sha256, búsquedas, clic por accesibilidad, PDF, cursor y login. **19 tests sin red + 6 de
integración** contra el Chrome real (todos en verde).

El adaptador **macOS** está escrito y a la espera de una corrida real en la Mac
(`abrir` → `sistema` → `demo`); el de Linux comparte el mismo camino.

Roadmap de mejoras: `docs/MEJORAS.md`.
Repos abiertos que inspiran la navegación (y qué tomamos de cada uno): `docs/REPOS-PARA-NAVEGACION.md`.

MIT.
