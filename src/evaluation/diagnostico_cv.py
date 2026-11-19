"""Diagnóstico reproducible únicamente con entrenamiento (test reservado).

Ejecutar: python -m src.evaluation.diagnostico_cv
No usa ni modifica data/versions/dbc_v2/test.csv, ni el modelo desplegado.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from src.preprocessing.text_preprocessor import crear_vectorizador
from src.utils.data_loader import cargar_dataset

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data' / 'processed' / 'diagnostico_cv'

def ejecutar():
    OUT.mkdir(parents=True, exist_ok=True)
    df = cargar_dataset(ROOT / 'data' / 'versions' / 'dbc_v2' / 'train.csv').reset_index(drop=True)
    X, y = df['texto'], df['intencion']
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    candidatos = {
        'regresion_logistica': Pipeline([('tfidf', crear_vectorizador()), ('clasificador', LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42))]),
        'svm_lineal': Pipeline([('tfidf', crear_vectorizador()), ('clasificador', LinearSVC(class_weight='balanced', random_state=42))]),
        # La calibración también se hace sobre folds internos del entrenamiento.
        'svm_calibrado': CalibratedClassifierCV(
            estimator=Pipeline([('tfidf', crear_vectorizador()), ('clasificador', LinearSVC(class_weight='balanced', random_state=42))]),
            method='sigmoid', cv=3
        ),
    }
    resumen=[]
    etiquetas=sorted(y.unique())
    for nombre, modelo in candidatos.items():
        pred = cross_val_predict(modelo, X, y, cv=cv, method='predict')
        resumen.append({'modelo':nombre, 'accuracy_oof':round(accuracy_score(y,pred),4), 'f1_macro_oof':round(f1_score(y,pred,average='macro',zero_division=0),4), 'errores_oof':int((pred!=y).sum())})
        pd.DataFrame(confusion_matrix(y,pred,labels=etiquetas),index=etiquetas,columns=etiquetas).to_csv(OUT/f'matriz_{nombre}.csv',encoding='utf-8-sig')
        pd.DataFrame(classification_report(y,pred,output_dict=True,zero_division=0)).T.to_csv(OUT/f'reporte_{nombre}.csv',encoding='utf-8-sig')
        errores=df.assign(intencion_predicha=pred).loc[pred!=y,['texto','intencion','intencion_predicha']]
        errores.to_csv(OUT/f'errores_{nombre}.csv',index=False,encoding='utf-8-sig')
        if nombre=='svm_calibrado':
            probs = cross_val_predict(modelo, X, y, cv=cv, method='predict_proba')
            confianza=probs.max(axis=1)
            rows=[]
            for umbral in [0.2,0.25,0.3,0.35,0.4,0.45,0.5,0.6]:
                aceptada = confianza >= umbral
                rows.append({'umbral':umbral,'cobertura':round(float(aceptada.mean()),4), 'rechazados':int((~aceptada).sum()),
                             'precision_sobre_aceptados':round(float((pred[aceptada]==y[aceptada]).mean()),4) if aceptada.any() else None,
                             'aciertos_aceptados':int((pred[aceptada]==y[aceptada]).sum()),
                             'errores_aceptados':int((pred[aceptada]!=y[aceptada]).sum())})
            pd.DataFrame(rows).to_csv(OUT/'umbral_cobertura.csv',index=False,encoding='utf-8-sig')
            df.assign(intencion_predicha=pred,confianza=confianza,correcta=(pred==y)).to_csv(OUT/'predicciones_oof_svm_calibrado.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(resumen).sort_values('f1_macro_oof',ascending=False).to_csv(OUT/'comparacion_modelos.csv',index=False,encoding='utf-8-sig')
    (OUT/'NOTAS.txt').write_text('Predicciones OOF: cada pregunta se predice con un modelo entrenado sin esa pregunta. Solo usa train.csv.\nLa confianza es la probabilidad calibrada más alta, NO prueba que el rechazo fuera de dominio sea fiable.\nLa precisión sobre aceptados es accuracy condicional, no precision_macro.\nLos ejemplos fuera de dominio incluidos forman parte de las 17 clases; una pregunta realmente nueva podría comportarse distinto.\nEl conjunto test.csv NO se consultó ni utilizó para elegir umbral o arquitectura.\nNo usar la clase de prueba externa como validación futura si ya fue utilizada para ajustar decisiones.\n', encoding='utf-8')
    print('\nCOMPARACIÓN OOF (solo entrenamiento)')
    print(pd.DataFrame(resumen).sort_values('f1_macro_oof',ascending=False).to_string(index=False))
    print('\nUMBRAL / COBERTURA')
    print(pd.read_csv(OUT/'umbral_cobertura.csv').to_string(index=False))
    print('\nArchivos:',OUT)

if __name__=='__main__':
    ejecutar()
