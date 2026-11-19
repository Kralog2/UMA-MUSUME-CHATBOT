"""Selecciona por F1 macro OOF calibrado; test solo después de congelar modelo."""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix, classification_report, top_k_accuracy_score
from sklearn.model_selection import StratifiedKFold
from src.models.train import construir_modelo_base
from scripts.export_from_xlsx import norm
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/processed/etapa51'
def load(path):
    return pd.read_csv(ROOT/path,keep_default_na=False)
def model():
    return CalibratedClassifierCV(estimator=construir_modelo_base(),method='sigmoid',cv=StratifiedKFold(5,shuffle=True,random_state=42))
def metrics(df, probs, labels):
    pred=labels[probs.argmax(axis=1)]
    return dict(accuracy=accuracy_score(df.intencion,pred),f1_macro=f1_score(df.intencion,pred,average='macro',zero_division=0),precision_macro=precision_score(df.intencion,pred,average='macro',zero_division=0),recall_macro=recall_score(df.intencion,pred,average='macro',zero_division=0),top3=top_k_accuracy_score(df.intencion,probs,k=3,labels=labels))
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    tr=load('data/raw/train.csv'); extra=load('data/raw/refuerzo_etapa3.csv'); labels=np.array(sorted(tr.intencion.unique()))
    assert not pd.concat([tr,extra]).texto.map(norm).duplicated().any()
    assert set(extra.intencion)<=set(labels)
    folds=list(StratifiedKFold(5,shuffle=True,random_state=42).split(tr.texto,tr.intencion))
    results=[]
    for name, augment in [('v3_base',False),('v3_reforzado',True)]:
        probs=np.zeros((len(tr),len(labels)))
        for a,b in folds:
            fit=tr.iloc[a]
            if augment: fit=pd.concat([fit,extra],ignore_index=True)
            m=model(); m.fit(fit.texto,fit.intencion); assert np.array_equal(m.classes_,labels)
            probs[b]=m.predict_proba(tr.iloc[b].texto)
        results.append(dict(variante=name,total=len(tr)+len(extra)*augment,**metrics(tr,probs,labels)))
        pd.concat([tr,pd.DataFrame(probs,columns=['p_'+l for l in labels])],axis=1).to_csv(OUT/f'oof_{name}.csv',index=False)
    pd.DataFrame(results).to_csv(OUT/'comparacion_cv.csv',index=False)
    winner=max(results,key=lambda x:x['f1_macro']); fit=pd.concat([tr,extra],ignore_index=True) if winner['variante']=='v3_reforzado' else tr
    m=model(); m.fit(fit.texto,fit.intencion); joblib.dump(m,ROOT/'artifacts/modelo_v3.joblib')
    # Evaluación retrospectiva: el test contiene 136 ejemplos previamente usados.
    te=load('data/raw/test.csv'); old=load('data/versions/dbc_v2/test.csv'); ch=load('data/challenge/evaluacion_nueva_v1.csv')
    assert not set(fit.texto.map(norm)) & (set(te.texto.map(norm))|set(ch.texto.map(norm)))
    new=te[~te.texto.map(norm).isin(set(old.texto.map(norm)))].reset_index(drop=True)
    evaluation={}
    for name, df in [('test_v3',te),('test_v3_adicional',new),('challenge_previamente_usado',ch)]:
        probs=m.predict_proba(df.texto); pred=labels[probs.argmax(axis=1)]
        evaluation[name]=dict(n=len(df),**metrics(df,probs,labels))
        pd.DataFrame(confusion_matrix(df.intencion,pred,labels=labels),index=labels,columns=labels).to_csv(OUT/f'matriz_{name}.csv')
        pd.DataFrame(classification_report(df.intencion,pred,labels=labels,output_dict=True,zero_division=0)).T.to_csv(OUT/f'reporte_{name}.csv')
        out=df.assign(prediccion=pred,confianza=probs.max(axis=1)); out[out.intencion!=out.prediccion].to_csv(OUT/f'errores_{name}.csv',index=False)
    result=dict(seleccion=winner,comparacion=results,evaluacion=evaluation,sklearn=sklearn.__version__,nota='Selección solo por CV. Test y challenge no son evaluaciones vírgenes completas.')
    (OUT/'resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
