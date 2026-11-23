"""Tests de integración: corren contra el Chrome real por CDP.

Se saltean solos si no hay túnel/CDP (por ejemplo en CI). Para correrlos:

    TARS_HOST=usuario@maquina python3 -m unittest tests.test_integracion -v

Ojo: navegan a `users.nexusmods.com/auth/sign_in`, que es una página pública de login.
No escriben credenciales ni aprietan botones que envíen formularios.
"""
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import tarsbrowser as tb  # noqa: E402

LOGIN = "https://users.nexusmods.com/auth/sign_in"


def hay_cdp():
    try:
        tb.ws_url()
        return True
    except Exception:
        return False


@unittest.skipUnless(hay_cdp(), "sin CDP: no hay túnel ni navegador disponible")
class Integracion(unittest.TestCase):
    def _correr(self, *args):
        """Ejecuta un comando del CLI en un proceso aparte y devuelve su salida."""
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "tarsbrowser.py"), *args],
                           capture_output=True, text=True, timeout=180, cwd=RAIZ)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def test_01_sistema_detecta_navegador(self):
        rc, salida = self._correr("sistema")
        self.assertEqual(rc, 0, salida)
        self.assertIn("cdp: Chrome", salida)

    def test_02_nav_espera_selector(self):
        rc, salida = self._correr("nav", LOGIN, "#password")
        self.assertEqual(rc, 0, salida)
        self.assertIn("apareció", salida)

    def test_03_extraer_devuelve_json(self):
        rc, salida = self._correr("nav", LOGIN)
        self.assertEqual(rc, 0, salida)
        rc, salida = self._correr("extraer", "a[href]", "href")
        self.assertEqual(rc, 0, salida)
        self.assertIn('"texto"', salida)

    def test_04_pdf_es_un_pdf(self):
        rc, salida = self._correr("nav", LOGIN)
        self.assertEqual(rc, 0, salida)
        with tempfile.TemporaryDirectory() as d:
            destino = os.path.join(d, "pagina.pdf")
            rc, salida = self._correr("pdf", destino)
            self.assertEqual(rc, 0, salida)
            with open(destino, "rb") as f:
                self.assertEqual(f.read(5), b"%PDF-")

    def test_05_clicax_encuentra_el_campo(self):
        rc, salida = self._correr("nav", LOGIN, "#user_login")
        self.assertEqual(rc, 0, salida)
        rc, salida = self._correr("clicax", "textbox", "Email")
        self.assertEqual(rc, 0, salida)
        self.assertIn("clic accesible", salida)

    def test_06_registro_anota_las_acciones(self):
        rc, salida = self._correr("registro", "5")
        self.assertEqual(rc, 0, salida)
        self.assertIn("|", salida)


if __name__ == "__main__":
    unittest.main()
