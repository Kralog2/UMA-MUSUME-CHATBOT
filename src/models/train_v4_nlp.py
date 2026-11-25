"""Etapa 12: compara NLP clásico, caracteres y enmascaramiento con CV.

Solo usa entrenamiento de las 18 clases. Selecciona el mejor F1 macro OOF,
calibra el ganador y busca umbrales con predicciones fuera de partición.
No utiliza los test históricos para decidir modelo o umbrales.
"""
from __future__ import annotations
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.svm import LinearSVC
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import accuracy_score, f1_score
from src.models.train_v4_intenciones import datos
from src.preprocessing.entity_masker import EntityMasker, catalogar_entidades

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/processed/etapa12'


def construir_pipeline(variante: str, entidades=None) -> Pipeline:
    """Crea un pipeline sin fuga; máscara, TF-IDF y SVM quedan juntos."""
    word = TfidfVectorizer(strip_accents='unicode', ngram_range=(1, 2), sublinear_tf=True)
    char = TfidfVectorizer(analyzer='char', ngram_range=(3, 5), min_df=2, sublinear_tf=True)
    pasos = []
    if variante == 'mascara_palabras_caracteres':
        pasos.append(('entidades', EntityMasker(entidades=entidades)))
    if variante == 'palabras':
        pasos.append(('tfidf', word))
    elif variante in ('palabras_caracteres', 'mascara_palabras_caracteres'):
        pasos.append(('tfidf', FeatureUnion([('palabras', word), ('caracteres', char)])))
    else:
        raise ValueError(f'Variante desconocida: {variante}')
    pasos.append(('clasificador', LinearSVC(class_weight='balanced', random_state=42)))
    return Pipeline(pasos)


def seleccionar_politica(probabilidades, etiquetas, clases):
    """Selecciona una política con cobertura >=65%, maximizando exactitud aceptada.

    Los mínimos se fijan ANTES de evaluar los datos históricos de prueba.
    Los datos OOF se utilizan para selección, no son una estimación ciega.
    """
    orden = np.argsort(-probabilidades, axis=1)
    p1 = probabilidades[np.arange(len(orden)), orden[:,0]]
    p2 = probabilidades[np.arange(len(orden)), orden[:,1]]
    aciertos = clases[orden[:,0]] == np.asarray(etiquetas)
    filas = []
    for minimo in np.arange(.20, .61, .05):
        for margen in np.arange(.0, .251, .05):
            aceptados = (p1 >= minimo) & ((p1-p2) >= margen)
            cobertura = float(aceptados.mean())
            precision = float(aciertos[aceptados].mean()) if aceptados.any() else 0.0
            filas.append({'minimo':round(float(minimo),3),'margen':round(float(margen),3),
                          'cobertura':cobertura,'exactitud_aceptadas':precision,
                          'aceptadas':int(aceptados.sum())})
    tabla = pd.DataFrame(filas)
    viables=tabla[tabla.cobertura >= .65]
    # Si no hay política viable, escoger la de cobertura mayor.
    ordenada = (viables if len(viables) else tabla).sort_values(
        ['exactitud_aceptadas','cobertura','minimo'], ascending=[False,False,False])
    return ordenada.iloc[0].to_dict(), tabla


def entrenar():
    """Compara variantes con pliegues idénticos; guarda modelo y política V4."""
    OUT.mkdir(parents=True, exist_ok=True)
    df=datos()
    textos=df['texto'].astype(str).to_numpy()
    etiquetas=df['intencion'].astype(str).to_numpy()
    entidades=catalogar_entidades()
    cv=StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
    variantes=['palabras','palabras_caracteres','mascara_palabras_caracteres']
    resultados=[]
    for variante in variantes:
        pipeline=construir_pipeline(variante, entidades)
        pred=cross_val_predict(pipeline,textos,etiquetas,cv=cv,n_jobs=1)
        fila={'variante':variante,'accuracy_oof':float(accuracy_score(etiquetas,pred)),
              'f1_macro_oof':float(f1_score(etiquetas,pred,average='macro',zero_division=0))}
        resultados.append(fila)
        print(variante, fila, flush=True)
    tabla=pd.DataFrame(resultados).sort_values(['f1_macro_oof','accuracy_oof'],ascending=False)
    tabla.to_csv(OUT/'comparacion_variantes.csv',index=False)
    ganadora=str(tabla.iloc[0]['variante'])
    # Calibración dentro de cada fold externo. Costosa, pero sin fuga.
    def calibrado():
        """Construye un calibrador con CV interna sobre el pipeline seleccionado."""
        return CalibratedClassifierCV(estimator=construir_pipeline(ganadora,entidades),
                                       method='sigmoid',cv=3)
    probas=cross_val_predict(calibrado(),textos,etiquetas,cv=cv,method='predict_proba',n_jobs=1)
    clases=np.array(sorted(np.unique(etiquetas)))
    politica,tabla_politicas=seleccionar_politica(probas,etiquetas,clases)
    politica={'minimo':politica['minimo'],'margen_minimo':politica['margen'],
              'minimo_aclaracion':0.25, 'cobertura_cv':politica['cobertura'],
              'exactitud_aceptadas_cv':politica['exactitud_aceptadas'],
              'variante':ganadora,'criterio':'OOF 5 folds; cobertura >= 65%; no test final'}
    tabla_politicas.to_csv(OUT/'evaluacion_umbrales.csv',index=False)
    pd.DataFrame(probas,columns=clases).assign(texto=textos,intencion=etiquetas).to_csv(
        OUT/'predicciones_oof_calibradas.csv',index=False)
    modelo=calibrado();modelo.fit(textos,etiquetas)
    (ROOT/'artifacts').mkdir(exist_ok=True)
    joblib.dump(modelo,ROOT/'artifacts/modelo_v4_etapa12.joblib')
    (OUT/'politica_confianza_v4.json').write_text(json.dumps(politica,ensure_ascii=False,indent=2),encoding='utf8')
    print('Seleccionada',json.dumps(politica,ensure_ascii=False),flush=True)
    return modelo,politica


if __name__ == '__main__':
    entrenar()
