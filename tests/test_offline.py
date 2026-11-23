"""Tests sin red: la lógica que no depende de Chrome ni del túnel.

    python3 -m unittest discover -s tests -v
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def cargar(**entorno):
    """Importa el módulo con las variables de entorno dadas ya puestas.

    El entorno NO se restaura solo: las funciones leen las variables en el momento de
    llamarlas (auditar, bounds, allowlist), así que restaurarlas antes las dejaría a ciegas.
    Cada test limpia lo suyo al final.
    """
    os.environ.update({k: v for k, v in entorno.items() if v is not None})
    import tarsbrowser
    return importlib.reload(tarsbrowser)


class PruebaDecodificar(unittest.TestCase):
    def test_utf8(self):
        tb = cargar()
        self.assertEqual(tb._decodificar("ñandú".encode("utf-8")), "ñandú")

    def test_cp850_de_windows(self):
        tb = cargar()
        # 0xa2 es 'ó' en cp850 y no es UTF-8 válido: antes rompía con UnicodeDecodeError
        self.assertEqual(tb._decodificar(b"Configuraci\xa2n"), "Configuración")


class PruebaConfig(unittest.TestCase):
    def test_roundtrip_de_geometria(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            tb = cargar(TARS_CONFIG=cfg)
            tb.guardar_config({"bounds": "1924,4,856,760"})
            self.assertEqual(tb.bounds(), "1924,4,856,760")
            with open(cfg, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["bounds"], "1924,4,856,760")

    def test_env_gana_sobre_archivo(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            tb = cargar(TARS_CONFIG=cfg)
            tb.guardar_config({"bounds": "1,2,3,4"})
            os.environ["TARS_BOUNDS"] = "0"      # el env manda sobre el archivo
            try:
                self.assertEqual(tb.bounds(), "0")
            finally:
                os.environ.pop("TARS_BOUNDS", None)

    def test_sin_config_no_toca_ventana(self):
        with tempfile.TemporaryDirectory() as d:
            tb = cargar(TARS_CONFIG=os.path.join(d, "no-existe.json"))
            os.environ.pop("TARS_BOUNDS", None)
            self.assertEqual(tb.bounds(), "")


class PruebaVentana(unittest.TestCase):
    def test_acepta_geometria_valida(self):
        with tempfile.TemporaryDirectory() as d:
            tb = cargar(TARS_CONFIG=os.path.join(d, "c.json"))
            tb.cmd_ventana("1924,4,856,760")
            self.assertEqual(tb.bounds(), "1924,4,856,760")

    def test_acepta_apagado(self):
        with tempfile.TemporaryDirectory() as d:
            tb = cargar(TARS_CONFIG=os.path.join(d, "c.json"))
            tb.cmd_ventana("0")
            self.assertEqual(tb.bounds(), "0")

    def test_rechaza_formato_malo(self):
        with tempfile.TemporaryDirectory() as d:
            tb = cargar(TARS_CONFIG=os.path.join(d, "c.json"))
            for malo in ("1924,4,856", "a,b,c,d", "1924;4;856;760", ""):
                with self.assertRaises(SystemExit):
                    tb.cmd_ventana(malo)


class PruebaSistema(unittest.TestCase):
    def _detectar(self, salida_uname):
        tb = cargar()
        tb.sh = lambda *a, **k: salida_uname
        return tb.sistema()

    def test_macos(self):
        self.assertEqual(self._detectar("Darwin\n"), "macos")

    def test_linux(self):
        self.assertEqual(self._detectar("Linux\n"), "linux")

    def test_windows_sin_uname(self):
        self.assertEqual(self._detectar("WINDOWS\n"), "windows")

    def test_perfil_por_sistema(self):
        tb = cargar()
        tb.sh = lambda *a, **k: "Darwin\n"
        tb._sistema_cache = None
        self.assertEqual(tb.perfil(), "~/.tars-chrome")
        tb.sh = lambda *a, **k: "WINDOWS\n"
        tb._sistema_cache = None
        self.assertEqual(tb.perfil(), r"C:\tars-chrome")


class PruebaUtilidades(unittest.TestCase):
    def test_allowlist_vacia_permite_todo(self):
        tb = cargar()
        tb.dominios_permitidos = lambda: []
        self.assertTrue(tb.dominio_permitido("https://cualquier.cosa/x"))

    def test_allowlist_por_dominio_y_subdominio(self):
        tb = cargar()
        tb.dominios_permitidos = lambda: ["ejemplo.com"]
        self.assertTrue(tb.dominio_permitido("https://ejemplo.com/a"))
        self.assertTrue(tb.dominio_permitido("https://sub.ejemplo.com/a"))
        self.assertFalse(tb.dominio_permitido("https://otro.com/a"))
        self.assertFalse(tb.dominio_permitido("https://ejemplo.com.evil.io/a"))

    def test_auditoria_escribe_sin_credenciales(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "auditoria.log")
            tb = cargar(TARS_AUDITORIA=ruta)
            tb.auditar("nav", "https://ejemplo.com")
            tb.auditar("login", "usuario=antonio")
            with open(ruta, encoding="utf-8") as f:
                lineas = [json.loads(l) for l in f if l.strip()]
            self.assertEqual([x["accion"] for x in lineas], ["nav", "login"])
            self.assertEqual(lineas[0]["detalle"], "https://ejemplo.com")


class PruebaMCP(unittest.TestCase):
    """El servidor MCP se prueba como lo usa un cliente: por stdin/stdout."""

    def _hablar(self, mensajes):
        import subprocess
        entrada = "\n".join(json.dumps(m) for m in mensajes) + "\n"
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "mcp_server.py")],
                           input=entrada, capture_output=True, text=True, timeout=60)
        return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]

    def test_initialize(self):
        r = self._hablar([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}])
        self.assertEqual(r[0]["result"]["serverInfo"]["name"], "tarsbrowser")
        self.assertIn("tools", r[0]["result"]["capabilities"])

    def test_tools_list_tiene_las_herramientas_clave(self):
        r = self._hablar([{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
        nombres = {t["name"] for t in r[0]["result"]["tools"]}
        for esperado in ("nav", "clicax", "bajar", "pdf", "extraer", "sistema"):
            self.assertIn(esperado, nombres)
        for t in r[0]["result"]["tools"]:
            self.assertIn("inputSchema", t)

    def test_metodo_desconocido_devuelve_error(self):
        r = self._hablar([{"jsonrpc": "2.0", "id": 3, "method": "no/existe"}])
        self.assertEqual(r[0]["error"]["code"], -32601)

    def test_herramienta_desconocida_marca_error(self):
        r = self._hablar([{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "inventada", "arguments": {}}}])
        self.assertTrue(r[0]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
