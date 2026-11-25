"""Adaptador de SVM calibrado a intención y Top-K del diálogo.

Etapa 11: permite modelo de 18 intenciones; sus umbrales se revisarán en Etapa 12.
"""
from pathlib import Path
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
    predictor.modelo=modelo
    return predictor
