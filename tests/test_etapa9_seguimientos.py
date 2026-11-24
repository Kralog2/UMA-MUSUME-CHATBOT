"""Etapa 9: regresiones de seguimientos, negaciones y sustituciones de cartas.

Prueba el gestor con un predictor controlado para aislar las reglas lingüísticas.
Cada función documenta un caso reportado por el equipo.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.conversation.dialogue_manager import DialogueManager
from src.conversation.context_resolver import analizar_ssr, preferencias, seguimiento
from src.conversation.knowledge_base import KnowledgeBase


class PruebasEtapa9(unittest.TestCase):
    """Verifica que las expresiones del usuario no inviertan ni contaminen filtros."""

    def setUp(self):
        """Construye una conversación independiente con intención inicial controlada."""
        self.chat = DialogueManager(lambda _: ("cartas_recomendadas", 1.0), RAIZ / "data/game", seed=2)
        self.kb = KnowledgeBase(RAIZ / "data/game")
        self.chat.responder("Recomiéndame cartas para Gold Ship")

    def test_seguimiento_escenario(self):
        """Un seguimiento corto con escenario conserva el personaje y cambia el escenario."""
        r = self.chat.responder("¿Y si la quiero entrenar en la URA final?")
        self.assertEqual(r["intencion"], "cartas_recomendadas")
        self.assertEqual(r["contexto"]["tema"]["escenario"], "ura_finale")
        self.assertEqual(r["contexto"]["tema"]["personaje"], "gold_ship")

    def test_seguimiento_sr(self):
        """La expresión «y en cuanto a SR» modifica solamente la rareza."""
        self.chat.responder("¿Y si la quiero entrenar en la URA final?")
        r = self.chat.responder("y en cuanto a sr?")
        self.assertEqual(r["contexto"]["tema"]["rareza"], "SR")
        self.assertEqual(r["contexto"]["tema"]["escenario"], "ura_finale")

    def test_peticion_nueva_hablame(self):
        """Un verbo de petición nueva no debe confundirse con una entidad aislada."""
        r = self.chat.responder("Háblame de Gold Ship")
        self.assertEqual(r["intencion"], "info_personaje")
        self.assertEqual(r["contexto"]["tema"]["intent"], "info_personaje")

    def test_no_tengo_todas_no_significa_cero(self):
        """Una negación parcial solicita información sin borrar el contexto confirmado."""
        antes = self.chat.ctx.snapshot()
        r = self.chat.responder("si no tengo todas las cartas ssr")
        self.assertEqual(r["intencion"], "aclaracion_inventario")
        self.assertIn("algunas SSR", r["respuesta"])
        self.assertEqual(r["contexto"]["tema"], antes["tema"])
        self.assertEqual(r["contexto"]["preferencias"], antes["preferencias"])

    def test_ausencia_total_excluye_ssr(self):
        """No disponer de ninguna SSR sí activa una restricción explícita."""
        r = self.chat.responder("no tengo ninguna SSR")
        self.assertTrue(r["contexto"]["preferencias"]["sin_ssr"])
        self.assertNotIn("(SSR ", r["respuesta"])

    def test_sin_ssr_simple(self):
        """Conserva compatibilidad con las expresiones de versiones anteriores."""
        r = self.chat.responder("no tengo ssr")
        self.assertTrue(r["contexto"]["preferencias"]["sin_ssr"])

    def test_orden_rareza_no_invierte_negacion(self):
        """La solicitud de SR sustitutas no cambia a SSR por orden de palabras."""
        for frase in (
            "cuáles SR uso si no tengo las SSR",
            "si no tengo las SSR cuáles SR uso",
        ):
            with self.subTest(frase=frase):
                ent = self.kb.extraer_entidades(frase)
                pref = preferencias(frase, ent)
                self.assertNotEqual(pref.get("rareza"), "SSR")
                self.assertEqual(pref.get("rareza"), "SR")

    def test_sustituciones_mismo_rol_sin_asumir_inventario(self):
        """Se muestran parejas heurísticas SSR/SR sin modificar preferencias previas."""
        antes = self.chat.ctx.snapshot()
        r = self.chat.responder("si no tengo las ssr por cuales las cambio")
        self.assertEqual(r["intencion"], "sustituciones_cartas")
        self.assertIn("Alternativas SR", r["respuesta"])
        self.assertIn("→", r["respuesta"])
        self.assertIn("No conozco cuáles SSR tienes", r["respuesta"])
        self.assertEqual(antes["tema"], r["contexto"]["tema"])
        self.assertEqual(antes["preferencias"], r["contexto"]["preferencias"])

    def test_sustituciones_con_filtros(self):
        """Las alternativas respetan el escenario y no cambian el tema de cartas."""
        self.chat.responder("¿Y si la quiero entrenar en la URA final?")
        r = self.chat.responder("cuáles SR uso si no tengo las SSR")
        self.assertEqual(r["intencion"], "sustituciones_cartas")
        self.assertEqual(r["contexto"]["tema"]["escenario"], "ura_finale")
        self.assertEqual(r["contexto"]["tema"]["intent"], "cartas_recomendadas")

    def test_siguiente_consulta_sigue_funcionando(self):
        """Una negación parcial no bloquea recomendaciones posteriores."""
        self.chat.responder("si no tengo todas las cartas ssr")
        r = self.chat.responder("recomiéndame más cartas para Gold Ship")
        self.assertIn("Cartas recomendadas", r["respuesta"])


if __name__ == "__main__":
    unittest.main()
