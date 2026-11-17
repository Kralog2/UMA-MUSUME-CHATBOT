"""Configuración compartida de vectorización entre entrenamiento e inferencia."""
from sklearn.feature_extraction.text import TfidfVectorizer


def crear_vectorizador():
    return TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
