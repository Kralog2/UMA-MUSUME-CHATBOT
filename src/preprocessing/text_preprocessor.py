"""Define la vectorización TF-IDF compartida por el entrenamiento y la inferencia."""
from sklearn.feature_extraction.text import TfidfVectorizer


def crear_vectorizador():
    """Crea el vectorizador TF-IDF configurado para unigramas y bigramas."""
    return TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
