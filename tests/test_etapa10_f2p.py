"""Pruebas de regresión de la Etapa 10: fuentes F2P, orden y mensajes.

Las verificaciones no modifican modelos ni datasets de entrenamiento;
comprueban el catálogo estructurado y el comportamiento de diálogo.
"""
import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.conversation.card_recommender import ordenar
from src.conversation.context_resolver import preferencias
from src.conversation.dialogue_manager import DialogueManager
from src.conversation.knowledge_base import KnowledgeBase
from src.models.predictor_adapter import construir_predictor


class Etapa10Tests(unittest.TestCase):
    """Agrupa casos relevantes a las seis incidencias sobre accesibilidad."""

    @classmethod
    def setUpClass(cls):
        """Carga la misma base de conocimiento que consume la API."""
        cls.kb = KnowledgeBase(ROOT / 'data/game')

    def test_01_columna_estructurada_y_fuentes(self):
        """Cada disponibilidad positiva tiene evidencia; no se inventan negativos."""
        cartas = list(self.kb.cartas.values())
        self.assertEqual(len(cartas), 33)
        self.assertEqual(sum(c['f2p'] == '1' for c in cartas), 6)
        self.assertEqual(sum(c['f2p'] == '' for c in cartas), 27)
        self.assertTrue(all(c['f2p_fuente'] for c in cartas if c['f2p'] == '1'))

    def test_02_mejiro_gratuita(self):
        """Mejiro McQueen se identifica F2P pese a no decir 'f2p' literalmente."""
        c = self.kb.cartas['mejiro_mcqueen_ssr']
        self.assertEqual(c['f2p'], '1')
        self.assertIn('Gratuita', c['f2p_fuente'])
        r = next(f for f in ordenar(self.kb, pref={'f2p': True}) if f['id'] == 'mejiro_mcqueen_ssr')
        self.assertTrue(r['f2p'])

    def test_03_f2p_no_equivale_sr(self):
        """Una preferencia F2P debe permitir SSR gratuitas y cartas R."""
        filas = ordenar(self.kb, pref={'f2p': True})
        primeras = filas[:6]
        self.assertTrue(all(f['f2p'] for f in primeras))
        self.assertTrue(any(self.kb.cartas[f['id']]['rarity'] == 'SSR' for f in primeras))
        self.assertTrue(any(self.kb.cartas[f['id']]['rarity'] == 'R' for f in primeras))

    def test_04_desconocidas_no_son_negativas(self):
        """Disponibilidad desconocida se conserva en resultados sin filtros estrictos."""
        filas = ordenar(self.kb, pref={'f2p': True})
        self.assertEqual(len(filas), 33)
        self.assertTrue(all(f['f2p_estado'] == '' for f in filas[6:]))

    def test_05_no_rareza_por_sinonimos(self):
        """La base no convierte 'free 2 play' o 'gratis' en SR."""
        for mensaje in ['quiero opciones gratis', 'soy f2p', 'free 2 play']:
            ent = self.kb.extraer_entidades(mensaje)
            self.assertNotEqual(ent.get('k_rareza'), 'SR')
            self.assertTrue(preferencias(mensaje, ent).get('f2p'))

    def test_06_exclusion_ssr_sigue_firme(self):
        """F2P nunca anula una restricción explícita sin SSR."""
        filas = ordenar(self.kb, pref={'f2p': True, 'sin_ssr': True})
        self.assertTrue(filas)
        self.assertTrue(all(self.kb.cartas[f['id']]['rarity'] != 'SSR' for f in filas))

    def test_07_rareza_orden_desempate(self):
        """Orden sin preferencia F2P considera rareza tras compatibilidad y bonos."""
        filas = ordenar(self.kb)
        for a, b in zip(filas, filas[1:]):
            if a['puntos'] == b['puntos'] and a['bonos'] == b['bonos']:
                rank = {'SSR': 0, 'SR': 1, 'R': 2}
                self.assertLessEqual(rank[self.kb.cartas[a['id']]['rarity']],
                                     rank[self.kb.cartas[b['id']]['rarity']])

    def test_08_sin_resultados_menciona_restricciones(self):
        """Un fallo de filtros informa sus criterios sin modificar contexto válido."""
        modelo = construir_predictor(ROOT/'artifacts/modelo_v3.joblib')
        dialogo = DialogueManager(modelo, ROOT/'data/game', seed=11)
        dialogo.responder('Háblame de Gold Ship')
        dialogo.responder('¿Qué cartas me recomiendas para ella?')
        previo = dialogo.ctx.snapshot()
        dialogo._texto = 'Quiero SR de Speed en Unity Cup'
        respuesta = dialogo._h_cartas_recomendadas({'k_stat': 'Speed', 'k_rareza': 'SR', 'k_escenario': 'Unity Cup'})
        # El resultado puede ser válido, por lo que forzamos una combinación imposible.
        dialogo._texto = 'Cartas SR de rol inexistente'
        dialogo._h_cartas_recomendadas({'k_stat':'Speed'})
        t = dict(dialogo.ctx.tema)
        t['stat'] = 'RolImposible'
        salida = dialogo._pagina_cartas(t, 0)
        self.assertIn('stat=RolImposible', salida)
        self.assertIn('No encontré cartas', salida)
        self.assertTrue(previo['slots']['personaje'])

    def test_09_exportador_y_excel(self):
        """Los CSV deben reproducir el catálogo del Excel activo."""
        import pandas as pd
        libro = pd.read_excel(ROOT/'data/source/DBCv4_etapa10.xlsx',sheet_name='Cards',dtype=str).fillna('')
        with (ROOT/'data/game/cards.csv').open(encoding='utf-8',newline='') as archivo:
            csv_data=list(csv.DictReader(archivo))
        self.assertEqual(len(libro),len(csv_data))
        self.assertEqual(list(libro['f2p']),[c['f2p'] for c in csv_data])

    def test_10_orden_determinista(self):
        """Las recomendaciones repetidas deben devolver el mismo orden."""
        self.assertEqual(ordenar(self.kb,personaje='gold_ship',pref={'f2p':True}),
                         ordenar(self.kb,personaje='gold_ship',pref={'f2p':True}))


if __name__=='__main__':
    unittest.main()
