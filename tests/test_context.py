"""Pruebas del contexto avanzado: decisiones controladas y conversaciones con SVM V3.
No se utilizan para entrenar el clasificador ni se presentan como evaluación independiente.
"""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.models.predictor_adapter import construir_predictor
from src.conversation.dialogue_manager import DialogueManager


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Carga una vez el modelo real para las pruebas de integración."""
        cls.predictor = staticmethod(construir_predictor(ROOT/'artifacts/modelo_v3.joblib'))

    def manager(self, predictor=None):
        """Crea un diálogo independiente y reproducible."""
        return DialogueManager(predictor or self.predictor, ROOT/'data/game', seed=0)

    def ambiguo(self):
        """Crea un predictor controlado para forzar la rama de aclaración."""
        def top_k(texto):
            """Genera una ambigüedad salvo cuando se pregunta explícitamente por Stamina."""
            if 'Stamina' in texto:
                return [('stats_funcion', .85), ('cartas_soporte', .08), ('herencias', .03)]
            return [('cartas_soporte', .44), ('cartas_recomendadas', .40), ('info_carta', .10)]
        def predictor(texto):
            """Devuelve la primera alternativa en el formato anterior."""
            return top_k(texto)[0]
        predictor.top_k = top_k
        predictor.politica_v3 = True
        return self.manager(predictor)

    def test_eleccion(self):
        """Confirma una opción sin perder entidades de la pregunta original."""
        d = self.ambiguo()
        r = d.responder('¿Y las cartas de Gold Ship?')
        self.assertIsNone(r['contexto']['slots']['personaje'])
        self.assertIn('1)', r['respuesta'])
        r = d.responder('2')
        self.assertEqual(r['intencion'], 'cartas_recomendadas')
        self.assertEqual(r['fuente'], 'aclaracion_confianza')
        self.assertEqual(r['contexto']['slots']['personaje'], 'gold_ship')
        self.assertIsNone(r['contexto']['pendiente_confianza'])

    def test_cambio_tema(self):
        """Una pregunta nueva cancela la selección pendiente."""
        d = self.ambiguo()
        d.responder('¿Y las cartas de Gold Ship?')
        r = d.responder('¿Para qué sirve Stamina?')
        self.assertEqual(r['intencion'], 'stats_funcion')
        self.assertIsNone(r['contexto']['pendiente_confianza'])
        self.assertIsNone(r['contexto']['slots']['personaje'])

    def test_filtros(self):
        """Comprueba la persistencia de preferencias y su separación de la rareza."""
        d = self.manager()
        d.responder('Háblame de Gold Ship')
        d.responder('¿Qué cartas me recomiendas para ella?')
        r = d.responder('Para largas y que sean F2P')
        self.assertEqual(r['contexto']['preferencias']['distancia'], 'larga')
        self.assertTrue(r['contexto']['preferencias']['f2p'])
        self.assertIsNone(r['contexto']['tema']['rareza'])
        r = d.responder('¿Y si no tengo SSR?')
        self.assertTrue(r['contexto']['preferencias']['sin_ssr'])
        self.assertNotIn('(SSR ', r['respuesta'])
        self.assertEqual(r['contexto']['slots']['personaje'], 'gold_ship')
        r = d.responder('dame más opciones')
        self.assertNotIn('(SSR ', r['respuesta'])
        self.assertTrue(r['contexto']['preferencias']['f2p'])

    def test_escenario(self):
        """Cambia de escenario sin perder la estadística explícita."""
        d = self.manager()
        d.responder('¿Qué cartas me recomiendas para Unity Cup?')
        d.responder('Stamina')
        r = d.responder('¿Y para el otro escenario es lo mismo?')
        self.assertEqual(r['contexto']['tema']['stat'], 'Stamina')
        self.assertEqual(r['contexto']['slots']['escenario'], 'ura_finale')

    def test_reinicio_y_copia(self):
        """Verifica que una respuesta previa no cambia y que el reinicio borra lo pendiente."""
        d = self.ambiguo()
        r = d.responder('¿Y las cartas de Gold Ship?')
        d.responder('sí')
        self.assertIsNotNone(d.ctx.pendiente_confianza)
        d.reiniciar()
        self.assertIsNone(d.ctx.pendiente_confianza)
        self.assertEqual(d.ctx.preferencias, {})
        self.assertIsNotNone(r['contexto']['pendiente_confianza'])

    def test_aislamiento_http(self):
        """Comprueba que una aclaración pendiente no se comparte entre sesiones HTTP."""
        from fastapi.testclient import TestClient
        from src.api import app as modulo
        from unittest.mock import patch
        with patch.object(modulo, 'construir_predictor', return_value=self.ambiguo().predictor):
            with TestClient(modulo.build_app()) as client:
                a = client.post('/api/chat', json={'mensaje':'¿Y las cartas de Gold Ship?'}).json()
                b = client.post('/api/chat', json={'mensaje':'¿Para qué sirve Stamina?'}).json()
                self.assertNotEqual(a['session_id'], b['session_id'])
                self.assertIsNone(b['contexto']['pendiente_confianza'])
                c = client.post('/api/chat', json={'mensaje':'2','session_id':a['session_id']}).json()
                self.assertEqual(c['fuente'], 'aclaracion_confianza')
                client.post('/api/reset', json={'session_id':a['session_id']})
                r = client.post('/api/chat', json={'mensaje':'¿Para qué sirve Stamina?','session_id':a['session_id']}).json()
                self.assertIsNone(r['contexto']['slots']['personaje'])

if __name__ == '__main__':
    unittest.main()
