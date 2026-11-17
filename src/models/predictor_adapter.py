"""Adaptador entre SVM calibrado y gestor de diálogo del compañero."""
from pathlib import Path
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def construir_predictor(ruta_modelo=None):
    ruta=Path(ruta_modelo) if ruta_modelo else ROOT / "artifacts/mejor_modelo.joblib"
    if not ruta.is_file():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Ejecuta primero: python -m src.models.train"
        )
    modelo=joblib.load(ruta)  # Cargar únicamente modelos locales de confianza.
    if not hasattr(modelo, "predict_proba"):
        raise TypeError("Este modelo no tiene probabilidades calibradas; entrénalo con src.models.train.")

    def predictor(texto):
        if not isinstance(texto,str) or not texto.strip():
            raise ValueError("El texto debe ser una cadena no vacía")
        probabilidades=modelo.predict_proba([texto])[0]
        indice=int(np.argmax(probabilidades))
        return str(modelo.classes_[indice]),float(probabilidades[indice])

    predictor.modelo=modelo
    return predictor
