# Instalación por sistema

El cliente (`tarsbrowser.py`) corre donde está el agente; el **navegador** corre en la máquina del
usuario. Entre los dos, un túnel SSH.

```
[ agente ] --python--> tarsbrowser.py --ssh -L 9223--> [ navegador ] Chrome :9222
```

## 1. Cliente (donde corre el agente)

```bash
python3 -m pip install websockets
export TARS_HOST=usuario@maquina   # por Tailscale o LAN
```

Comprobar:

```bash
python3 tarsbrowser.py sistema
```

## 2. Windows (navegador)

1. Copiar `scripts/arrancar-windows.ps1` a `C:\tars-chrome\arrancar.ps1`.
2. Registrar la tarea **en la sesión del usuario** (con otra sesión, la ventana no se ve):

```powershell
$acc  = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\tars-chrome\arrancar.ps1'
$prin = New-ScheduledTaskPrincipal -UserId "TUMAQUINA\usuario" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'tars-chrome-abrir' -Action $acc -Principal $prin -Force
```

El `UserId` va con `whoami`, **no** con `$env:USERDOMAIN` (con `WORKGROUP\usuario` falla el registro).

3. Fijar la zona: `TARS_ZONA=arriba|abajo|completo` (por defecto `arriba`: mitad superior del
   monitor secundario).
4. `python3 tarsbrowser.py abrir` y verificar con `sistema`.

## 3. macOS (navegador)

1. Activar **Ajustes → General → Compartir → Inicio de sesión remoto**.
2. Copiar el lanzador:

```bash
mkdir -p ~/.tars-chrome
cp scripts/arrancar-macos.sh ~/.tars-chrome/
chmod +x ~/.tars-chrome/arrancar-macos.sh
```

3. `python3 tarsbrowser.py abrir` — el lanzador usa `open -na "Google Chrome" --args …` para que la
   ventana aparezca en la sesión gráfica y no en el contexto del SSH.

**Si la ventana no aparece** (macOS a veces bloquea el lanzamiento desde SSH), el fallback:

```bash
sudo launchctl asuser $(id -u TUUSUARIO) \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir=$HOME/.tars-chrome --remote-debugging-port=9222 --no-first-run about:blank
```

**Monitores**: si usás «cada pantalla con su propio Space», mover una ventana a la otra pantalla
puede necesitar AppleScript (permiso de Accesibilidad) en vez de `Browser.setWindowBounds`.

## 4. Linux (navegador)

```bash
mkdir -p ~/.tars-chrome && cp scripts/arrancar-linux.sh ~/.tars-chrome/
python3 tarsbrowser.py abrir
```

Necesita `google-chrome`, `google-chrome-stable` o `chromium` en el PATH, y una sesión gráfica
(X11/Wayland) si querés ver la ventana.

## 5. Servidor MCP (opcional)

```bash
python3 mcp_server.py        # habla JSON-RPC por stdin/stdout
```

Se configura en el cliente MCP con `command: python3`, `args: [ruta/mcp_server.py]` y
`env: {TARS_HOST: usuario@maquina}`. Herramientas: `sistema`, `estado`, `abrir`, `nav`, `captura`,
`buscar`, `bajar`, `clicax`, `clic`, `escribir`, `extraer`, `pdf`, `sesion`, `registro`.

## 6. Primera vez

El perfil arranca **sin sesión**: hay que loguearse una vez en esa ventana (y pasar el captcha, que
es lo único que hace una persona). Después queda guardado y `login` puede usar el buzón de secretos
para tipear la clave sin que pase por el chat.
