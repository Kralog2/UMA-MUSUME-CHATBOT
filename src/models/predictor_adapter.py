"""Carga el clasificador calibrado y adapta sus predicciones al gestor de diálogo.

Expone un callable que devuelve la intención predicha junto con su confianza.
"""
from pathlib import Path
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def construir_predictor(ruta_modelo=None):
    """Carga el modelo local y devuelve una función que predice intención y confianza."""
    ruta=Path(ruta_modelo) if ruta_modelo else ROOT / "artifacts/mejor_modelo.joblib"
    if not ruta.is_file():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Ejecuta primero: python -m src.models.train"
        )
    modelo=joblib.load(ruta)  # Cargar únicamente modelos locales de confianza.
    if not hasattr(modelo, "predict_proba"):
        raise TypeError("Este modelo no tiene probabilidades calibradas; entrénalo con src.models.train.")

    def predictor(texto):
        """Predice la intención más probable para un texto no vacío."""
        if not isinstance(texto,str) or not texto.strip():
            raise ValueError("El texto debe ser una cadena no vacía")
        probabilidades=modelo.predict_proba([texto])[0]
        indice=int(np.argmax(probabilidades))
        return str(modelo.classes_[indice]),float(probabilidades[indice])

    predictor.modelo=modelo
    return predictor
