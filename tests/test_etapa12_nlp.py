"""Pruebas de regresión de la Etapa 12: NLP, confianza y contexto.

Incluye modelos reales y predictores controlados para distinguir reglas de
comportamiento de la calidad estadística del clasificador.
"""
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocessing.entity_masker import EntityMasker, catalogar_entidades
from src.models.predictor_adapter import construir_predictor
from src.conversation.dialogue_manager import DialogueManager


class Etapa12NLPTests(unittest.TestCase):
    """Comprueba la compatibilidad entre vectorización, modelo y conversación."""

    @classmethod
    def setUpClass(cls):
        """Carga el modelo entrenado una sola vez y guarda la política empleada."""
        cls.predictor = staticmethod(construir_predictor(ROOT / 'artifacts/modelo_v4_etapa12.joblib'))

    def test_mascara_personaje_escenario_rareza(self):
        """Enmascara entidades conservando las palabras que expresan intención."""
        m = EntityMasker(entidades=catalogar_entidades()).fit([])
        texto = m.transform(['Recomiéndame una carta SSR para Gold Ship en URA Finale'])[0]
        self.assertIn('entidad_personaje', texto)
        self.assertIn('entidad_escenario', texto)
        self.assertIn('entidad_rareza', texto)
        self.assertIn('recomiendame una carta', texto)

    def test_mascara_no_reemplaza_fragmentos(self):
        """Evita reemplazar rarezas dentro de palabras que no son entidades."""
        texto = EntityMasker().fit([]).transform(['el usuario ssrraro pide SR'])[0]
        self.assertIn('ssrraro', texto)
        self.assertIn('entidad_rareza', texto)

    def test_probabilidades_y_clases(self):
        """Verifica Top-K, sumatoria calibrada y la nueva intención de objetivos."""
        p = self.predictor
        self.assertEqual(len(p.modelo.classes_), 18)
        self.assertIn('objetivos_stats', p.modelo.classes_)
        probabilidades = p.top_k('¿Qué cartas me recomiendas para Gold Ship?', 18)
        self.assertAlmostEqual(sum(v for _, v in probabilidades), 1.0, places=6)
        self.assertEqual(probabilidades[0], p('¿Qué cartas me recomiendas para Gold Ship?'))
        self.assertTrue(p.politica_v4)
        self.assertFalse(p.politica_v3)

    def test_confianza_recalibrada(self):
        """Comprueba que el diálogo toma los umbrales específicos de V4."""
        dm = DialogueManager(self.predictor, ROOT / 'data/game')
        config = json.loads((ROOT / 'data/processed/etapa12/politica_confianza_v4.json').read_text())
        self.assertEqual(dm.gestor_confianza.minimo, config['minimo'])
        self.assertEqual(dm.gestor_confianza.margen_minimo, config['margen_minimo'])

    def test_typo_y_contenido(self):
        """Verifica una frase informal no usada como ejemplo del entrenamiento."""
        salida = DialogueManager(self.predictor, ROOT / 'data/game').responder(
            'quee cartas me recomiendas para Oguri Cap en URA finale?')
        self.assertEqual(salida['intencion'], 'cartas_recomendadas')
        self.assertIn('Oguri Cap', salida['respuesta'])

    def test_no_perder_mazo(self):
        """Una pregunta de mazo continúa llegando al armador por reglas."""
        salida = DialogueManager(self.predictor, ROOT / 'data/game').responder('Ármame un mazo para Gold Ship')
        self.assertEqual(salida['intencion'], 'cartas_recomendadas')
        self.assertEqual(salida['contexto']['tema']['modo'], 'mazo')

    def test_continuidad_top2_controlada(self):
        """Si hay indicios de continuidad, se permite recuperar el tema del top-2."""
        def predictor(texto):
            """Expone la misma interfaz que el modelo calibrado."""
            return predictor.top_k(texto)[0]
        def top_k(texto, k=3):
            """Genera una clasificación inequívoca seguida de una ambigua."""
            if texto == 'Háblame de Gold Ship':
                return [('info_personaje', .90), ('cartas_soporte', .05), ('herencias', .03)][:k]
            return [('cartas_soporte', .43), ('info_personaje', .40), ('herencias', .08)][:k]
        predictor.top_k = top_k
        predictor.politica_v4 = True
        predictor.politica_v3 = False
        predictor.configuracion_confianza = dict(minimo=.50,margen_minimo=.25,minimo_aclaracion=.25)
        dm = DialogueManager(predictor, ROOT / 'data/game')
        dm.responder('Háblame de Gold Ship')
        respuesta = dm.responder('y sobre sus características?')
        self.assertEqual(respuesta['fuente'], 'contexto_confianza')
        self.assertEqual(respuesta['intencion'], 'info_personaje')
        self.assertEqual(respuesta['diagnostico_confianza']['accion'], 'aceptar_contexto')

    def test_api_v4_predeterminado(self):
        """Valida que la API arranca con V4 y conserva el contrato HTTP."""
        from fastapi.testclient import TestClient
        from src.api.app import app
        with TestClient(app) as cliente:
            self.assertEqual(cliente.get('/api/health').json()['modelo'], 'v4')
            r=cliente.post('/api/chat',json={'mensaje':'¿Para qué sirve Stamina?'})
            self.assertEqual(r.status_code,200)
            self.assertIn('diagnostico_confianza',r.json())
            self.assertIn('session_id',r.json())


if __name__ == '__main__':
    unittest.main()
