"""Pruebas de la política de confianza y su integración con el diálogo y la API.
Usa probabilidades controladas para comprobar casos límite sin depender del azar del modelo.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.conversation.confidence_manager import ConfidenceManager
from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor


class ConfidenceTests(unittest.TestCase):
    def test_decisiones(self):
        """Comprueba las tres acciones y el margen entre las primeras clases."""
        gestor = ConfidenceManager()
        for p1, p2, accion in [(0.70, 0.10, 'aceptar'), (0.49, 0.40, 'aclarar'),
                               (0.40, 0.10, 'aclarar'), (0.20, 0.18, 'reformular')]:
            r = gestor.evaluar([('cartas_soporte', p1), ('cartas_recomendadas', p2), ('info_carta', .05)])
            self.assertEqual(r['accion'], accion)
            self.assertAlmostEqual(r['margen'], p1-p2)

    def test_contexto_no_contaminado(self):
        """Una pregunta incierta no sustituye un personaje activo; el reinicio elimina el estado."""
        def predictor(texto):
            """Simula el formato histórico de predicción."""
            return predictor.top_k(texto)[0]

        def top_k(texto):
            """Entrega una predicción firme para el primer turno y ambigua para el segundo."""
            if texto == 'Dame información de Gold Ship':
                return [('info_personaje', .80), ('cartas_soporte', .10), ('subir_nivel', .05)]
            return [('cartas_soporte', .44), ('cartas_recomendadas', .40), ('info_carta', .10)]

        predictor.top_k = top_k
        predictor.politica_v3 = True
        dm = DialogueManager(predictor, ROOT/'data/game', seed=0)
        primero = dm.responder('Dame información de Gold Ship')
        self.assertEqual(primero['contexto']['slots']['personaje'], 'gold_ship')
        segundo = dm.responder('¿Y las cartas de Vodka?')
        self.assertEqual(segundo['fuente'], 'confianza_ambigua')
        self.assertEqual(segundo['contexto']['slots']['personaje'], 'gold_ship')
        self.assertEqual(segundo['contexto']['tema'], primero['contexto']['tema'])
        self.assertEqual(segundo['diagnostico_confianza']['accion'], 'aclarar')
        dm.reiniciar()
        self.assertIsNone(dm.ctx.slots['personaje'])

    def test_top_k_real(self):
        """Comprueba el orden de probabilidades y compatibilidad del adaptador V3."""
        predictor = construir_predictor(ROOT/'artifacts/modelo_v3.joblib')
        texto = '¿Para qué sirve Stamina?'
        k = predictor.top_k(texto)
        self.assertEqual(len(k), 3)
        self.assertEqual(k[0], predictor(texto))
        self.assertGreaterEqual(k[0][1], k[1][1])
        self.assertAlmostEqual(sum(p for _, p in predictor.top_k(texto, 17)), 1.0)

    def test_api_diagnostico(self):
        """Verifica que HTTP conserva sus campos históricos y expone el diagnóstico nuevo."""
        from fastapi.testclient import TestClient
        from src.api import app as modulo
        from unittest.mock import patch
        with patch.object(modulo, 'MODEL_NAME', 'v3'):
            with TestClient(modulo.build_app()) as client:
                r = client.post('/api/chat', json={'mensaje': '¿Para qué sirve Stamina?'})
                self.assertEqual(r.status_code, 200)
                datos = r.json()
                self.assertIn('session_id', datos)
                self.assertEqual(len(datos['diagnostico_confianza']['candidatos']), 3)
                self.assertIn('margen', datos['diagnostico_confianza'])


if __name__ == '__main__':
    unittest.main()
