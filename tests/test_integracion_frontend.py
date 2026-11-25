"""Pruebas de contrato del frontend Streamlit y defaults de la API.

Comprueba que los archivos existen y el frontend utiliza las rutas
/api/chat y /api/reset; no requiere ejecutar Streamlit ni conexiones HTTP.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IntegracionFrontendTests(unittest.TestCase):
    """Valida que el frontend y el backend conserven el contrato HTTP."""

    def test_archivos_frontend(self):
        """Comprueba la presencia de interfaz, avatar y dependencias."""
        self.assertTrue((ROOT / "frontend/app_frontend.py").is_file())
        self.assertTrue((ROOT / "frontend/avatar.png").is_file())
        self.assertTrue((ROOT / "frontend/requirements.txt").is_file())

    def test_contrato_http(self):
        """Comprueba que el frontend utiliza los endpoints y session_id."""
        codigo = (ROOT / "frontend/app_frontend.py").read_text(encoding="utf-8")
        for fragmento in ("/api/chat", "/api/reset", '"session_id"', '"mensaje"'):
            self.assertIn(fragmento, codigo)
        ast.parse(codigo)

    def test_modelo_v4_predeterminado(self):
        """Comprueba que consola y API utilizan V4 salvo selección explícita."""
        api = (ROOT / "src/api/app.py").read_text(encoding="utf-8")
        consola = (ROOT / "src/chat_console.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("UMABOT_MODELO", "v4")', api)
        self.assertIn('default="v4"', consola)


if __name__ == "__main__":
    unittest.main()
