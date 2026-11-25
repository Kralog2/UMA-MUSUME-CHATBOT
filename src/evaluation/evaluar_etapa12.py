"""Evalúa los modelos V4 de las etapas 11 y 12 sobre conjuntos históricos.

Los resultados solo son diagnósticos posteriores a la selección por CV; NO
se usan para cambiar el modelo ni la política y NO son pruebas ciegas nuevas.
"""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/processed/etapa12'


def evaluar():
    """Calcula métricas descriptivas en test previamente utilizados y guarda errores."""
    OUT.mkdir(parents=True, exist_ok=True)
    modelos = {
        'v4_etapa11': ROOT/'artifacts/modelo_v4_etapa11.joblib',
        'v4_etapa12': ROOT/'artifacts/modelo_v4_etapa12.joblib',
    }
    conjuntos = {
        'dbc_v3_test_170_historico': ROOT/'data/raw/test.csv',
        'reto_etapa3_68_historico': ROOT/'data/challenge/evaluacion_nueva_v1.csv',
        'objetivos_10_sintetico': ROOT/'data/raw/objetivos_stats_test.csv',
    }
    filas=[]
    for nombre_modelo,ruta in modelos.items():
        modelo=joblib.load(ruta)
        for nombre_conjunto,ruta_csv in conjuntos.items():
            if not ruta_csv.is_file():
                continue
            df=pd.read_csv(ruta_csv).dropna(subset=['texto','intencion'])
            pred=modelo.predict(df.texto.astype(str))
            filas.append({'modelo':nombre_modelo,'conjunto':nombre_conjunto,'n':len(df),
                         'accuracy':accuracy_score(df.intencion,pred),
                         'f1_macro':f1_score(df.intencion,pred,average='macro',zero_division=0)})
            df.assign(prediccion=pred)[lambda x:x.intencion!=x.prediccion].to_csv(
                OUT / f'errores_{nombre_modelo}_{nombre_conjunto}.csv',index=False)
    comparacion=pd.DataFrame(filas)
    comparacion.to_csv(OUT/'comparacion_historica_no_ciega.csv',index=False)
    (OUT/'advertencia_evaluacion.txt').write_text(
        'Estos conjuntos fueron utilizados en etapas anteriores. Son controles de regresión, '
        'NO evaluaciones independientes. No ajustar características ni umbrales con ellos.\n',
        encoding='utf-8')
    print(comparacion.to_string(index=False))
    return comparacion


if __name__ == '__main__':
    evaluar()
