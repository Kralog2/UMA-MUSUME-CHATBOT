"""Carga los modelos supervisados y adapta sus salidas al gestor de diálogo.

Etapa 12: reconoce la política de confianza específica de V4 y conserva
la compatibilidad con los modelos históricos y la interfaz Top-K.
"""
from pathlib import Path
import json
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def construir_predictor(ruta_modelo=None):
    """Carga el modelo calibrado y crea interfaces de predicción simple y Top-K."""
    ruta=Path(ruta_modelo) if ruta_modelo else ROOT / "artifacts/mejor_modelo.joblib"
    if not ruta.is_file():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Ejecuta primero: python -m src.models.train"
        )
    modelo=joblib.load(ruta)  # Cargar únicamente modelos locales de confianza.
    if not hasattr(modelo, "predict_proba"):
        raise TypeError("Este modelo no tiene probabilidades calibradas; entrénalo con src.models.train.")

    def top_k(texto, k=3):
        """Ordena las probabilidades calibradas y devuelve las k clases principales."""
        if not isinstance(texto,str) or not texto.strip():
            raise ValueError("El texto debe ser una cadena no vacía")
        probabilidades=modelo.predict_proba([texto])[0]
        indices=np.argsort(-probabilidades, kind="stable")[:k]
        return [(str(modelo.classes_[i]), float(probabilidades[i])) for i in indices]

    def predictor(texto):
        """Devuelve la clase más probable en el formato histórico del gestor."""
        return top_k(texto, 1)[0]

    predictor.top_k=top_k
    predictor.politica_v3=ruta.name == "modelo_v3.joblib"
    predictor.politica_v4=ruta.name == "modelo_v4_etapa12.joblib"
    predictor.configuracion_confianza = None
    if predictor.politica_v4:
        politica=ROOT / 'data/processed/etapa12/politica_confianza_v4.json'
        if not politica.is_file():
            raise FileNotFoundError(f"Falta la política de confianza V4: {politica}")
        predictor.configuracion_confianza=json.loads(politica.read_text(encoding='utf-8'))
    predictor.modelo=modelo
    return predictor
