"""Comprueba restricciones, ranking, explicaciones y continuidad de recomendaciones con DBCv3."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.conversation.knowledge_base import KnowledgeBase
from src.conversation.card_recommender import ordenar, objetivos, describir
from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor


class RecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Carga el catálogo y el modelo real una vez."""
        cls.kb = KnowledgeBase(ROOT/'data/game')
        cls.predictor = staticmethod(construir_predictor(ROOT/'artifacts/modelo_v3.joblib'))

    def test_restricciones(self):
        """Comprueba filtros explícitos, incluso cuando no hay resultados."""
        filas = ordenar(self.kb, 'unity_cup', 'Stamina', personaje='gold_ship', pref={'distancia':'larga','sin_ssr':True})
        self.assertTrue(filas)
        for r in filas:
            c = self.kb.cartas[r['id']]
            self.assertIn(c['scenario'], ('both','unity_cup'))
            self.assertEqual(c['stat'], 'Stamina')
            self.assertNotEqual(c['rarity'], 'SSR')
            self.assertTrue({'long','any'} & set(c['distance'].split('|')))
        self.assertEqual(ordenar(self.kb, rareza='SSR', pref={'sin_ssr':True}), [])

    def test_aptitudes(self):
        """Conserva empates de aptitud y permite objetivos explícitos distintos."""
        metas = objetivos(self.kb, 'gold_ship', {})
        self.assertEqual(metas['distancia'], ({'medium','long'},False))
        self.assertEqual(metas['estilo'], ({'end'},False))
        self.assertEqual(objetivos(self.kb,'gold_ship',{'distancia':'sprint'})['distancia'], ({'sprint'},True))
        ids = [r['id'] for r in ordenar(self.kb, personaje='rice_shower')]
        self.assertNotIn('rice_shower_ssr',ids)

    def test_f2p(self):
        """No convierte F2P en SR y comprueba la evidencia estructurada de la Etapa 10."""
        filas = ordenar(self.kb, pref={'f2p':True})
        self.assertEqual(len(filas),len(self.kb.cartas))
        self.assertTrue(any(r['f2p'] and self.kb.cartas[r['id']]['rarity']=='SSR' for r in filas))
        for r in filas:
            if r['f2p']:
                self.assertEqual(self.kb.cartas[r['id']]['f2p'], '1')
                self.assertTrue(self.kb.cartas[r['id']]['f2p_fuente'])

    def test_orden_y_bonos(self):
        """Verifica estabilidad del orden, ausencia de duplicados y bonos trazables."""
        filas = ordenar(self.kb, personaje='gold_ship')
        self.assertEqual(filas, ordenar(self.kb, personaje='gold_ship'))
        self.assertEqual(len(filas),len({r['id'] for r in filas}))
        for r in filas:
            if r['efecto']:
                self.assertEqual(r['efecto'],self.kb.efectos[r['id']][r['lb']])
                self.assertIn(r['lb'],describir(self.kb,r))

    def test_conversacion(self):
        """Un diálogo real conserva filtros y usa las mismas cartas en cada página."""
        d = DialogueManager(self.predictor, ROOT/'data/game', seed=0)
        for texto in ('Háblame de Gold Ship','¿Qué cartas me recomiendas para ella?','Para largas y que sean F2P','¿Y si no tengo SSR?'):
            r = d.responder(texto)
        self.assertIn('Gold Ship',r['respuesta'])
        self.assertIn('larga',r['respuesta'].replace('long','larga'))
        self.assertIn('F2P',r['respuesta'])
        self.assertNotIn('(SSR ',r['respuesta'])
        t = r['contexto']['tema']; p = r['contexto']['preferencias']
        filas = ordenar(self.kb,t['escenario'],t['stat'],t['rareza'],t['personaje'],p)
        self.assertGreater(len(filas),5)
        sig = d.responder('dame más opciones')
        self.assertEqual(sig['contexto']['preferencias'],p)
        for f in filas[5:10]: self.assertIn(self.kb.etiqueta_carta(f['id']),sig['respuesta'])
        for f in filas[:5]: self.assertNotIn(self.kb.etiqueta_carta(f['id']),sig['respuesta'])

    def test_http(self):
        """Verifica que la respuesta personalizada y los filtros llegan por HTTP."""
        from fastapi.testclient import TestClient
        from src.api import app as modulo
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'UMABOT_MODELO':'v3'}):
            with TestClient(modulo.build_app()) as client:
                a = client.post('/api/chat',json={'mensaje':'Háblame de Gold Ship'}).json()
                b = client.post('/api/chat',json={'mensaje':'¿Qué cartas me recomiendas para ella?','session_id':a['session_id']}).json()
                self.assertIn('Gold Ship',b['respuesta'])
                self.assertEqual(b['contexto']['tema']['personaje'],'gold_ship')

if __name__ == '__main__':
    unittest.main()
