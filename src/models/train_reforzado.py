"""Compara y entrena una variante del clasificador con ejemplos de refuerzo.

La evaluación para seleccionar si se conserva el refuerzo usa únicamente folds
sobre el train original. Los 73 ejemplos de refuerzo se agregan a cada fold de
entrenamiento, nunca a los folds de validación. El modelo reforzado se guarda
como un artefacto independiente; no lee challenge ni test.
"""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold
from src.models.train import construir_modelo_base
from src.utils.data_loader import cargar_dataset

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/processed/etapa3'

def ejecutar():
    """Compara variantes con validación cruzada y guarda el modelo reforzado."""
    train = cargar_dataset(ROOT/'data/raw/train.csv').reset_index(drop=True)
    extra = cargar_dataset(ROOT/'data/raw/refuerzo_etapa3.csv').reset_index(drop=True)
    assert set(extra.intencion).issubset(set(train.intencion))
    folds = StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
    resultados = []
    for nombre,reforzado in [('base',False),('con_refuerzo',True)]:
        pred = np.empty(len(train),dtype=object)
        for idx_train, idx_val in folds.split(train.texto,train.intencion):
            datos=train.iloc[idx_train]
            if reforzado:
                datos=pd.concat([datos,extra],ignore_index=True)
            modelo=construir_modelo_base()
            modelo.fit(datos.texto,datos.intencion)
            pred[idx_val]=modelo.predict(train.iloc[idx_val].texto)
        resultados.append({'variante':nombre,'accuracy_oof':float(accuracy_score(train.intencion,pred)),
                           'f1_macro_oof':float(f1_score(train.intencion,pred,average='macro',zero_division=0)),
                           'errores_oof':int((pred!=train.intencion.to_numpy()).sum())})
    OUT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(resultados).to_csv(OUT/'comparacion_refuerzo_cv.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(resultados).to_string(index=False))
    # Entrenar archivo independiente para no sobrescribir el modelo original.
    datos=pd.concat([train,extra],ignore_index=True)
    cv=StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
    model=CalibratedClassifierCV(estimator=construir_modelo_base(),method='sigmoid',cv=cv)
    model.fit(datos.texto,datos.intencion)
    destino=ROOT/'artifacts/modelo_reforzado_etapa3.joblib'
    joblib.dump(model,destino)
    (OUT/'registro_entrenamiento.json').write_text(json.dumps({
       'original':len(train),'refuerzo':len(extra),'entrenamiento_total':len(datos),
       'seleccion':'Comparación OOF original solamente; desafío independiente no consultado',
       'modelo':str(destino.relative_to(ROOT)),'variantes':resultados
    },ensure_ascii=False,indent=2),encoding='utf-8')
    print('Modelo reforzado guardado:',destino.relative_to(ROOT))
    return model
if __name__=='__main__': ejecutar()
