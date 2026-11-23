#!/usr/bin/env python3
"""Servidor MCP (stdio) que expone tarsbrowser como herramientas.

    {"command": "python3", "args": ["/ruta/mcp_server.py"]}

Protocolo: JSON-RPC 2.0, un mensaje JSON por línea en stdin/stdout (MCP stdio).
Cada herramienta ejecuta el CLI en un subproceso: así el bucle de eventos del
servidor queda libre y cada comando corre aislado.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(AQUI, "tarsbrowser.py")
VERSION = "1.2.1"
PROTOCOLO = "2024-11-05"

HERRAMIENTAS = [
    {"name": "sistema", "command": ["sistema"], "description":
     "Estado del host: sistema operativo, versión de Chrome, perfil y si el CDP responde.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "estado", "command": ["estado"], "description":
     "Navegador vivo y pestañas abiertas.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "abrir", "command": ["abrir"], "description":
     "Abre o reabre la ventana dedicada del navegador y espera a que el CDP responda.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "nav", "command": ["nav"], "description":
     "Navega la pestaña de trabajo y opcionalmente espera un selector CSS.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string"}, "selector": {"type": "string"}}, "required": ["url"]}},
    {"name": "captura", "command": ["captura"], "description": "Captura la pestaña a un PNG.",
     "inputSchema": {"type": "object", "properties": {"salida": {"type": "string"}},
                     "required": ["salida"]}},
    {"name": "buscar", "command": ["buscar"], "description":
     "Busca en Google y guarda una captura. Devuelve el título de la página de resultados.",
     "inputSchema": {"type": "object", "properties": {
         "consulta": {"type": "string"}, "captura": {"type": "string"}}, "required": ["consulta"]}},
    {"name": "bajar", "command": ["bajar"], "description":
     "Descarga una URL sin diálogo (nombre y carpeta automáticos).",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string"}, "carpeta": {"type": "string"}}, "required": ["url"]}},
    {"name": "clicax", "command": ["clicax"], "description":
     "Clic por rol y nombre accesibles (button, link, textbox...), sin coordenadas.",
     "inputSchema": {"type": "object", "properties": {
         "rol": {"type": "string"}, "nombre": {"type": "string"}}, "required": ["rol", "nombre"]}},
    {"name": "clic", "command": ["clic"], "description": "Clic por coordenadas del viewport.",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
    {"name": "escribir", "command": ["escribir"], "description":
     "Escribe texto en un campo, carácter por carácter.",
     "inputSchema": {"type": "object", "properties": {
         "selector": {"type": "string"}, "texto": {"type": "string"}},
         "required": ["selector", "texto"]}},
    {"name": "extraer", "command": ["extraer"], "description":
     "Devuelve como JSON los elementos que matchean un selector (texto, href o un atributo).",
     "inputSchema": {"type": "object", "properties": {
         "selector": {"type": "string"}, "atributo": {"type": "string"}}, "required": ["selector"]}},
    {"name": "pdf", "command": ["pdf"], "description": "Guarda la página actual como PDF.",
     "inputSchema": {"type": "object", "properties": {"salida": {"type": "string"}},
                     "required": ["salida"]}},
    {"name": "sesion", "command": ["sesion"], "description":
     "Dice si la sesión sigue viva: navega y comprueba un selector de 'logueado'.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string"}, "selector": {"type": "string"}},
         "required": ["url", "selector"]}},
    {"name": "mapa", "command": ["mapa"], "description":
     "Lista numerada de los elementos accionables de la página (rol, nombre, posición).",
     "inputSchema": {"type": "object", "properties": {"maximo": {"type": "integer"}}}},
    {"name": "clicref", "command": ["clicref"], "description":
     "Clic sobre el elemento número N del mapa.",
     "inputSchema": {"type": "object", "properties": {"indice": {"type": "integer"}},
                     "required": ["indice"]}},
    {"name": "registro", "command": ["registro"], "description":
     "Últimas acciones registradas (append-only, sin credenciales).",
     "inputSchema": {"type": "object", "properties": {"n": {"type": "integer"}}}},
]

POR_NOMBRE = {h["name"]: h for h in HERRAMIENTAS}


def ejecutar(nombre: str, argumentos: dict) -> tuple[str, bool]:
    h = POR_NOMBRE.get(nombre)
    if not h:
        return f"herramienta desconocida: {nombre}", True
    esquema = h["inputSchema"]
    orden = list(h["command"])
    for campo in esquema.get("properties", {}):
        if campo in argumentos and argumentos[campo] is not None:
            orden.append(str(argumentos[campo]))
    try:
        r = subprocess.run([sys.executable, CLI, *orden], capture_output=True, text=True, timeout=900)
        salida = (r.stdout or "") + (r.stderr or "")
        return salida.strip() or "(sin salida)", r.returncode != 0
    except subprocess.TimeoutExpired:
        return "timeout ejecutando la herramienta", True


def responder(ident, resultado=None, error=None):
    msg = {"jsonrpc": "2.0", "id": ident}
    if error:
        msg["error"] = error
    else:
        msg["result"] = resultado
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def manejar(msg: dict) -> None:
    ident = msg.get("id")
    metodo = msg.get("method")
    if metodo == "initialize":
        responder(ident, {"protocolVersion": PROTOCOLO,
                          "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "tarsbrowser", "version": VERSION}})
    elif metodo == "tools/list":
        responder(ident, {"tools": [{"name": h["name"], "description": h["description"],
                                     "inputSchema": h["inputSchema"]} for h in HERRAMIENTAS]})
    elif metodo == "tools/call":
        params = msg.get("params") or {}
        texto, fallo = ejecutar(params.get("name", ""), params.get("arguments") or {})
        responder(ident, {"content": [{"type": "text", "text": texto}], "isError": fallo})
    elif metodo == "ping":
        responder(ident, {})
    elif ident is not None:
        responder(ident, error={"code": -32601, "message": f"método no soportado: {metodo}"})


def main() -> None:
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except ValueError:
            responder(None, error={"code": -32700, "message": "JSON inválido"})
            continue
        if isinstance(msg, list):
            for m in msg:
                manejar(m)
        else:
            manejar(msg)


if __name__ == "__main__":
    main()
