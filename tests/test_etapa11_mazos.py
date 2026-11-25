"""Etapa 11: regresión de seis cupos, restricciones y objetivos por personaje.

Las pruebas verifican la lógica sin asumir disponibilidad F2P no documentada.
"""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.conversation.knowledge_base import KnowledgeBase
from src.conversation.deck_builder import construir_mazo, necesidades, explicar_mazo
from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor

class Etapa11Tests(unittest.TestCase):
    """Comprueba que el sistema se mantiene estable entre turnos y filtros."""
    @classmethod
    def setUpClass(cls):
        """Carga datos locales y el clasificador V4 una sola vez."""
        cls.kb=KnowledgeBase(ROOT/'data/game')
        cls.predictor=construir_predictor(ROOT/'artifacts/modelo_v4_etapa11.joblib')

    def test_seis_sin_repetir(self):
        """El armador respeta seis cupos y no duplica cartas."""
        r=construir_mazo(self.kb,personaje='oguri_cap')
        self.assertEqual(len(r['cartas']),6)
        self.assertEqual(len({x['id'] for x in r['cartas']}),6)
        self.assertEqual(sum(r['roles'].values()),6)
        for x in r['cartas']: self.assertEqual(x['rol'], self.kb.cartas[x['id']]['stat'])

    def test_metas_diferencian_personajes(self):
        """Los cupos dependen de los objetivos del catálogo."""
        a=necesidades(self.kb,'oguri_cap')
        b=necesidades(self.kb,'gold_ship')
        self.assertNotEqual(a,b)

    def test_restricciones_no_se_relajan(self):
        """Sin SSR y escenario explícito nunca producen cartas contrarias."""
        r=construir_mazo(self.kb,escenario='ura_finale',personaje='gold_ship',pref={'sin_ssr':True})
        for fila in r['cartas']:
            card=self.kb.cartas[fila['id']]
            self.assertNotEqual(card['rarity'],'SSR')
            self.assertIn(card['scenario'],('ura_finale','both'))

    def test_faltantes_explicitos(self):
        """Explica vacantes sin inventar cartas si no hay suficientes."""
        r=construir_mazo(self.kb,personaje='gold_ship',rareza='R')
        self.assertFalse(r['completo'])
        self.assertIn('No pude completar', explicar_mazo(self.kb,r,'gold_ship'))

    def test_objetivos_con_contexto(self):
        """Una consulta nueva recupera el personaje y no inventa metas por escenario."""
        dm=DialogueManager(self.predictor,ROOT/'data/game',seed=3)
        dm.responder('Háblame de Gold Ship')
        r=dm.responder('¿Cuáles son las estadísticas ideales?')
        self.assertEqual(r['intencion'],'objetivos_stats')
        self.assertIn('Gold Ship',r['respuesta'])
        self.assertIn('no están diferenciados',r['respuesta'])
        r=dm.responder('¿Y para URA Finale?')
        self.assertEqual(r['intencion'],'objetivos_stats')
        self.assertIn('URA Finale',r['respuesta'])

    def test_contexto_mazo(self):
        """Un seguimiento conserva modo mazo y modifica filtros correctamente."""
        dm=DialogueManager(self.predictor,ROOT/'data/game',seed=3)
        a=dm.responder('Ármame un mazo para Oguri Cap')
        self.assertEqual(a['intencion'],'cartas_recomendadas')
        self.assertEqual(a['contexto']['tema']['modo'],'mazo')
        b=dm.responder('¿Y para largas y F2P?')
        self.assertTrue(b['contexto']['preferencias']['f2p'])
        self.assertEqual(b['contexto']['preferencias']['distancia'],'larga')
        c=dm.responder('¿Y si no tengo SSR?')
        self.assertTrue(c['contexto']['preferencias']['sin_ssr'])
        self.assertNotIn('(SSR ',c['respuesta'])

    def test_intenciones_modelo_v4(self):
        """El modelo entrenado incorpora la clase nueva sin borrar las existentes."""
        self.assertEqual(len(self.predictor.modelo.classes_),18)
        self.assertIn('objetivos_stats',self.predictor.modelo.classes_)

if __name__=='__main__':unittest.main()
