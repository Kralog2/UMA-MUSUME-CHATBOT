"""Pruebas unitarias de las métricas y exportaciones de la Etapa 6.

No reentrena el modelo ni altera la base de datos. Comprueba cálculo,
contratos de evaluación, estructura de resultados y rúbrica en blanco.
Ejecutar: python -m unittest discover -s tests -p 'test_evaluacion_integral.py'
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.evaluation.evaluacion_integral import (
    comprobar_paso, crear_rubrica, evaluar_confianza, percentil_95,
)
from src.models.predictor_adapter import construir_predictor


class IntegralTests(unittest.TestCase):
    """Agrupa verificaciones independientes de la generación del informe."""

    @classmethod
    def setUpClass(cls):
        """Carga una vez el SVM real utilizado en la evaluación."""
        cls.predictor = construir_predictor(RAIZ / 'artifacts' / 'modelo_v3.joblib')

    def test_percentiles(self):
        """Confirma que el percentil maneja muestras y listas vacías."""
        self.assertEqual(percentil_95([10., 10., 10.]), 10.)
        self.assertIsNone(percentil_95([]))

    def test_comprobacion_dialogo(self):
        """Detecta mensajes correctos y discrepancias de intención o contenido."""
        esperado = {'intencion': 'info_personaje', 'contiene': ['Gold Ship'], 'slots': {'personaje': 'gold_ship'}}
        salida = {'intencion': 'info_personaje', 'respuesta': 'Gold Ship puede correr.', 'fuente':'modelo', 'contexto': {'slots': {'personaje': 'gold_ship'}}}
        self.assertEqual(comprobar_paso(esperado, salida), [])
        salida['intencion'] = 'cartas_soporte'
        self.assertTrue(comprobar_paso(esperado, salida))

    def test_plantilla_humana_sin_calificaciones(self):
        """Comprueba que las puntuaciones humanas nunca se inventan."""
        with tempfile.TemporaryDirectory() as folder:
            destino = Path(folder)
            crear_rubrica(destino)
            with (destino/'rubrica_evaluacion_humana.csv').open(encoding='utf-8-sig', newline='') as f:
                filas = list(csv.reader(f))
            self.assertEqual(len(filas), 1)
            self.assertIn('exactitud_factual_1a5', filas[0])

    def test_confianza_conserva_contabilidad(self):
        """Verifica que aceptar, aclarar y reformular suman todas las preguntas."""
        with tempfile.TemporaryDirectory() as folder:
            r = evaluar_confianza(self.predictor, RAIZ/'data/challenge/evaluacion_nueva_v1.csv', Path(folder))
            self.assertEqual(sum(r['acciones'].values()), r['muestras'])
            self.assertAlmostEqual(r['cobertura'], r['acciones']['aceptar']/r['muestras'], places=4)


if __name__ == '__main__':
    unittest.main()
