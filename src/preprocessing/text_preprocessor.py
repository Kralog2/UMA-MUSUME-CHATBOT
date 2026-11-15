
from sklearn.feature_extraction.text import TfidfVectorizer


def crear_vectorizador():
    """
    Construye el vectorizador TF-IDF.
    """

    vectorizador = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True
    )

    return vectorizador
