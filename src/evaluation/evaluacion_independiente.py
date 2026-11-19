"""Evaluación de una sola pasada sobre un desafío separado, nunca usado al entrenar.

No hay ajuste automático ni búsqueda de hiperparámetros usando este desafío.
"""
from pathlib import Path
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix, classification_report
from src.utils.data_loader import cargar_dataset

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/processed/etapa3/evaluacion_independiente'

def ejecutar():
    ruta=ROOT/'data/challenge/evaluacion_nueva_v1.csv'
    manifest=json.loads((ROOT/'data/challenge/manifiesto.json').read_text(encoding='utf-8'))
    huella=hashlib.sha256(ruta.read_bytes()).hexdigest()
    if huella!=manifest['hash_sha256_desafio']:
        raise RuntimeError('El desafío ha cambiado: revisar manifiesto y origen de los datos antes de evaluar.')
    if (OUT/'resultado.json').exists():
        raise RuntimeError('El desafío ya fue evaluado. No se repite para elegir modificaciones.')
    modelo_path=ROOT/'artifacts/modelo_reforzado_etapa3.joblib'
    model=joblib.load(modelo_path) # cargar solo el artefacto local y confiable
    df=cargar_dataset(ruta)
    assert len(df)==68 and df.intencion.nunique()==17
    pred=model.predict(df.texto)
    prob=model.predict_proba(df.texto)
    confianza=prob.max(axis=1)
    umbral=0.30  # fijado antes de abrir el desafío: valor de la etapa 2.
    aceptada=confianza>=umbral
    etiquetas=sorted(df.intencion.unique())
    resultados={
        'nota':'Desafío nuevo separado: 68 preguntas sintéticas redactadas para esta etapa; no es un muestreo de usuarios reales.',
        'sha256_desafio':huella,'sha256_modelo':hashlib.sha256(modelo_path.read_bytes()).hexdigest(),
        'ejemplos':len(df),'intenciones':len(etiquetas),'umbral_congelado':umbral,
        'accuracy_sin_rechazo':float(accuracy_score(df.intencion,pred)),
        'f1_macro_sin_rechazo':float(f1_score(df.intencion,pred,average='macro',zero_division=0)),
        'precision_macro_sin_rechazo':float(precision_score(df.intencion,pred,average='macro',zero_division=0)),
        'recall_macro_sin_rechazo':float(recall_score(df.intencion,pred,average='macro',zero_division=0)),
        'cobertura_con_umbral':float(aceptada.mean()),
        'exactitud_de_aceptadas':float((pred[aceptada]==df.intencion.to_numpy()[aceptada]).mean()) if aceptada.any() else None,
        'rechazados':int((~aceptada).sum())
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'resultado.json').write_text(json.dumps(resultados,indent=2,ensure_ascii=False),encoding='utf-8')
    pd.DataFrame(confusion_matrix(df.intencion,pred,labels=etiquetas),index=etiquetas,columns=etiquetas).to_csv(OUT/'matriz_confusion.csv',encoding='utf-8-sig')
    pd.DataFrame(classification_report(df.intencion,pred,output_dict=True,zero_division=0)).T.to_csv(OUT/'reporte_clases.csv',encoding='utf-8-sig')
    df.assign(predicha=pred,confianza=confianza,aceptada=aceptada,correcta=(pred==df.intencion.to_numpy())).to_csv(OUT/'predicciones.csv',index=False,encoding='utf-8-sig')
    print(json.dumps(resultados,ensure_ascii=False,indent=2))
    print(classification_report(df.intencion,pred,zero_division=0))
    return resultados
if __name__=='__main__': ejecutar()
