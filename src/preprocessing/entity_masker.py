"""Enmascara entidades de Uma Musume antes de vectorizar preguntas.

Las expresiones se obtienen del catálogo local; se aplican durante entrenamiento
Y predicción dentro del mismo Pipeline, evitando divergencia de procesamiento.
La transformación NO modifica el mensaje original del gestor conversacional.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

ROOT = Path(__file__).resolve().parents[2]


def normalizar(texto: str) -> str:
    """Convierte tildes y mayúsculas a una representación de búsqueda estable."""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto).lower())
                   if not unicodedata.combining(c))


def catalogar_entidades(carpeta: Path | None = None) -> dict[str, list[str]]:
    """Lee el catálogo actual y recopila nombres inequívocos de personajes y escenarios."""
    carpeta = Path(carpeta) if carpeta else ROOT / 'data/game'
    personajes = pd.read_csv(carpeta / 'characters.csv')['name'].dropna().astype(str).tolist()
    datos = pd.read_csv(carpeta / 'knowledge.csv').fillna('')
    escenarios = []
    for fila in datos[datos['category'] == 'escenario'].itertuples():
        escenarios.extend([fila.name, *str(fila.synonym).split('|')])
    return {'personaje': sorted({normalizar(x) for x in personajes if len(x.strip()) >= 4}, key=len, reverse=True),
            'escenario': sorted({normalizar(x) for x in escenarios if len(x.strip()) >= 3}, key=len, reverse=True),
            'rareza': ['ssr', 'sr', 'rareza r', 'carta r']}


class EntityMasker(BaseEstimator, TransformerMixin):
    """Sustituye nombres de entidades por marcadores reproducibles en cada pregunta."""

    def __init__(self, entidades=None):
        """Recibe un diccionario fijo para mantener serializable el modelo entrenado."""
        self.entidades = entidades

    def fit(self, X, y=None):
        """Prepara patrones, sin aprender información a partir de etiquetas ni del test."""
        entidades = self.entidades if self.entidades is not None else catalogar_entidades()
        patrones = []
        for tipo in ('personaje', 'escenario', 'rareza'):
            for nombre in entidades.get(tipo, []):
                patrones.append((len(nombre), re.compile(r'(?<!\w)' + re.escape(nombre) + r'(?!\w)'), tipo))
        self.patrones_ = sorted(patrones, key=lambda x: -x[0])
        return self

    def transform(self, X):
        """Enmascara sobre el texto normalizado, priorizando expresiones más largas."""
        resultado = []
        for texto in X:
            cadena = normalizar(texto)
            # Guardar intervalos evita enmascarar dos veces un mismo nombre.
            ocurrencias = []
            for largo, patron, tipo in self.patrones_:
                for match in patron.finditer(cadena):
                    if not any(match.start() < fin and match.end() > ini for ini, fin, _ in ocurrencias):
                        ocurrencias.append((match.start(), match.end(), tipo))
            for inicio, fin, tipo in sorted(ocurrencias, reverse=True):
                cadena = cadena[:inicio] + ' entidad_' + tipo + ' ' + cadena[fin:]
            resultado.append(cadena)
        return resultado
