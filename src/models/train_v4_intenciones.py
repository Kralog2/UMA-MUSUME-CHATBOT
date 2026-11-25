"""Etapa 11: entrena un SVM calibrado con 18 intenciones, sin ajustar con test.

La evaluación adicional de objetivos_stats es sintética. Los tests anteriores
se conservan para regresión y NO son pruebas ciegas vírgenes.
"""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import accuracy_score, f1_score
from sklearn.calibration import CalibratedClassifierCV
from src.models.train import construir_modelo_base

ROOT=Path(__file__).resolve().parents[2]

def datos():
    """Une entrenamiento existente, refuerzo y ejemplos nuevos; mantiene test aparte."""
    rutas=['data/raw/train.csv','data/raw/refuerzo_etapa3.csv','data/raw/objetivos_stats_train.csv']
    return pd.concat([pd.read_csv(ROOT/r) for r in rutas],ignore_index=True)

def entrenar():
    """Calcula métricas de CV, calibra con entrenamiento y guarda un modelo nuevo."""
    df=datos()
    assert df.intencion.nunique()==18 and df.intencion.value_counts().min()>=5
    cv=StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
    scores=cross_validate(construir_modelo_base(),df.texto,df.intencion,cv=cv,
                          scoring={'accuracy':'accuracy','f1_macro':'f1_macro'})
    model=CalibratedClassifierCV(estimator=construir_modelo_base(),method='sigmoid',cv=cv)
    model.fit(df.texto,df.intencion)
    dest=ROOT/'artifacts/modelo_v4_etapa11.joblib';joblib.dump(model,dest)
    nuevo=pd.read_csv(ROOT/'data/raw/objetivos_stats_test.csv')
    pred=model.predict(nuevo.texto)
    datos_resultado={'n_entrenamiento':len(df),'intenciones':df.intencion.nunique(),
        'cv_accuracy_media':float(scores['test_accuracy'].mean()),
        'cv_f1_macro_media':float(scores['test_f1_macro'].mean()),
        'prueba_sintetica_objetivos_n':len(nuevo),
        'prueba_sintetica_objetivos_accuracy':float(accuracy_score(nuevo.intencion,pred)),
        'prueba_sintetica_objetivos_f1':float(f1_score(nuevo.intencion,pred,average='macro',zero_division=0)),
        'advertencia':'Evaluación sintética focalizada: no prueba el rendimiento global de 18 intenciones. '
                     'La calibración/umbrales de confianza V3 no se transfieren automáticamente.'}
    out=ROOT/'data/processed/etapa11';out.mkdir(parents=True,exist_ok=True)
    (out/'metricas_v4.json').write_text(json.dumps(datos_resultado,ensure_ascii=False,indent=2),encoding='utf8')
    nuevo.assign(prediccion=pred).to_csv(out/'predicciones_objetivos.csv',index=False)
    print(json.dumps(datos_resultado,ensure_ascii=False,indent=2))
    return model

if __name__=='__main__':entrenar()
