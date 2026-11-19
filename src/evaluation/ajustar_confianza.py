"""Compara políticas de confianza sobre las predicciones OOF de V3, sin consultar test.
Genera una tabla reproducible; no modifica automáticamente la política en producción.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def calcular_metricas(probabilidad, margen, correctas, umbral, margen_minimo):
    """Mide cobertura, exactitud selectiva y errores aceptados para una pareja de umbrales."""
    aceptadas = (probabilidad >= umbral) & (margen >= margen_minimo)
    n = int(aceptadas.sum())
    aciertos = int((aceptadas & correctas).sum())
    return dict(umbral=umbral, margen_minimo=margen_minimo, cobertura=n/len(correctas),
                exactitud_aceptadas=aciertos/n if n else 0.0,
                aceptadas=n, aciertos_aceptados=aciertos, errores_aceptados=n-aciertos)


def main():
    """Explora una rejilla y selecciona la mayor exactitud con cobertura mínima de dos tercios."""
    datos = pd.read_csv(ROOT / 'data/processed/etapa51/oof_v3_reforzado.csv')
    probs = datos.filter(regex='^p_')
    matriz = probs.to_numpy()
    ordenadas = np.sort(matriz, axis=1)
    correctas = probs.columns.to_numpy()[matriz.argmax(axis=1)] == ('p_' + datos.intencion).to_numpy()
    filas = [calcular_metricas(ordenadas[:, -1], ordenadas[:, -1]-ordenadas[:, -2], correctas, u, m)
             for u in (.30, .35, .40, .45, .50) for m in (0, .05, .10, .15, .20)]
    tabla = pd.DataFrame(filas)
    elegible = tabla[tabla.cobertura >= 2/3].sort_values(['exactitud_aceptadas', 'cobertura'], ascending=False)
    salida = ROOT / 'data/processed/etapa52'
    salida.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salida / 'comparacion_umbrales.csv', index=False)
    elegible.iloc[:1].to_csv(salida / 'politica_seleccionada.csv', index=False)
    print(elegible.iloc[0].to_string())


if __name__ == '__main__':
    main()
