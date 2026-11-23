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
    """Importa el módulo con variables de entorno dadas (sin tocar las del proceso)."""
    viejas = {k: os.environ.get(k) for k in entorno}
    os.environ.update({k: v for k, v in entorno.items() if v is not None})
    try:
        import tarsbrowser
        return importlib.reload(tarsbrowser)
    finally:
        for k, v in viejas.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


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


if __name__ == "__main__":
    unittest.main()
