"""Etapa 8: pruebas de regresión de filtros y memoria conversacional.

Cada prueba reproduce un defecto reportado por el equipo y verifica que
una consulta nueva no herede filtros inválidos ni contamine el contexto.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.conversation.dialogue_manager import DialogueManager
from src.conversation.knowledge_base import KnowledgeBase


class PruebasEstadoFiltros(unittest.TestCase):
    """Regresiones críticas relacionadas con cartas, personajes y filtros."""

    def setUp(self):
        """Crea una sesión aislada con una intención controlada y determinista."""
        self.chat = DialogueManager(lambda mensaje: ("cartas_recomendadas", 1.0), RAIZ / "data/game", seed=0)
        self.kb = KnowledgeBase(RAIZ / "data/game")

    def test_mazo_no_es_estadistica(self):
        """La palabra «mazo» no debe activar el filtro estadística."""
        r = self.chat.responder("Ármame un mazo para Oguri Cap")
        self.assertIsNone(r["contexto"]["tema"]["stat"])
        self.assertEqual(r["contexto"]["tema"]["personaje"], "oguri_cap")
        self.assertIn("Cartas recomendadas", r["respuesta"])
        self.assertIn("no es un mazo optimizado", r["respuesta"])

    def test_mazo_no_contamina_siguiente_turno(self):
        """Después de mencionar «mazo» es posible seguir recomendando."""
        self.chat.responder("Ármame un mazo para Oguri Cap")
        r = self.chat.responder("Mejores cartas para Oguri Cap")
        self.assertIsNone(r["contexto"]["tema"]["stat"])
        self.assertIn("Cartas recomendadas", r["respuesta"])

    def test_cambio_de_personaje_limpia_preferencias(self):
        """Cambiar de Uma elimina distancia, F2P, rareza y stat heredados."""
        a = self.chat.responder("Cartas de Stamina para Gold Ship, largas y F2P")
        self.assertEqual(a["contexto"]["tema"]["stat"], "Stamina")
        self.assertTrue(a["contexto"]["preferencias"]["f2p"])
        b = self.chat.responder("Recomiéndame cartas para Silence Suzuka")
        self.assertEqual(b["contexto"]["tema"]["personaje"], "silence_suzuka")
        self.assertIsNone(b["contexto"]["tema"]["stat"])
        self.assertEqual(b["contexto"]["preferencias"], {})
        self.assertIsNone(b["contexto"]["slots"]["card"])

    def test_mismo_personaje_conserva_preferencias(self):
        """Continuaciones para la misma Uma conservan los filtros válidos."""
        self.chat.responder("Cartas de Stamina para Gold Ship, largas y F2P")
        b = self.chat.responder("Más cartas para Gold Ship")
        self.assertEqual(b["contexto"]["tema"]["stat"], "Stamina")
        self.assertEqual(b["contexto"]["preferencias"]["distancia"], "larga")
        self.assertTrue(b["contexto"]["preferencias"]["f2p"])

    def test_personaje_no_es_carta_homonima(self):
        """Una mención del personaje no debe seleccionar su SSR homónima."""
        ent = self.kb.extraer_entidades("Háblame de Silence Suzuka")
        self.assertEqual(ent["personaje"], "silence_suzuka")
        self.assertNotIn("card", ent)
        ent = self.kb.extraer_entidades("Recomiéndame cartas para Silence Suzuka")
        self.assertNotIn("card", ent)
        explicita = self.kb.extraer_entidades("Háblame de la carta de Silence Suzuka")
        self.assertEqual(explicita["card"], "silence_suzuka_ssr")

    def test_resultado_vacio_no_modifica_contexto(self):
        """Una recomendación fallida restaura tema, preferencias y slots."""
        self.chat.responder("Cartas para Gold Ship")
        anterior = self.chat.ctx.snapshot()
        with patch("src.conversation.dialogue_manager.ordenar", return_value=[]):
            r = self.chat.responder("Cartas para Silence Suzuka")
        self.assertIn("No encontré cartas", r["respuesta"])
        self.assertEqual(r["contexto"]["tema"], anterior["tema"])
        self.assertEqual(r["contexto"]["preferencias"], anterior["preferencias"])
        self.assertEqual(r["contexto"]["slots"], anterior["slots"])

    def test_estadisticas_permitidas(self):
        """Solo se admiten estadísticas de cartas definidas en el catálogo."""
        self.assertIsNone(self.chat._estadistica_carta({"k_carta": "mazo de soporte"}))
        self.assertEqual(self.chat._estadistica_carta({"k_carta": "stamina (carta)"}), "Stamina")
        self.assertEqual(self.chat._estadistica_carta({"k_stat": "speed"}), "Speed")
        self.assertIsNone(self.chat._estadistica_carta({"k_stat": "algo inexistente"}))


if __name__ == "__main__":
    unittest.main()
