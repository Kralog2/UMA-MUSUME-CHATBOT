"""Audita duplicados exactos y similitud superficial sin alterar los datos."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.utils.data_loader import cargar_dataset

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/processed/diagnostico_cv'

def normalizados(s):
    return (s.str.lower().str.normalize('NFKD')
              .str.replace(r'[\u0300-\u036f]','',regex=True)
              .str.replace(r'\W+',' ',regex=True).str.strip())

def ejecutar():
    train=cargar_dataset(ROOT/'data/versions/dbc_v2/train.csv').reset_index(drop=True)
    test=cargar_dataset(ROOT/'data/versions/dbc_v2/test.csv').reset_index(drop=True)
    tr=set(normalizados(train.texto)); te=set(normalizados(test.texto))
    v=TfidfVectorizer(analyzer='char',ngram_range=(3,5),strip_accents='unicode')
    mat=v.fit_transform(pd.concat([train.texto,test.texto],ignore_index=True))
    sim=cosine_similarity(mat[len(train):],mat[:len(train)])
    matches=sim.argmax(axis=1); best=sim.max(axis=1)
    matches_df=pd.DataFrame({'texto_test':test.texto,'clase_test':test.intencion,
                            'texto_train_cercano':train.texto.iloc[matches].to_numpy(),
                            'clase_train_cercana':train.intencion.iloc[matches].to_numpy(),
                            'similitud_caracteres':np.round(best,4)})
    OUT.mkdir(parents=True,exist_ok=True)
    matches_df.sort_values('similitud_caracteres',ascending=False).to_csv(OUT/'pares_mas_similares.csv',index=False,encoding='utf-8-sig')
    reporte={'ejemplos_train':len(train),'ejemplos_test':len(test),'clases_train':train.intencion.nunique(),
             'clases_test':test.intencion.nunique(),'duplicados_normalizados_train':int(normalizados(train.texto).duplicated().sum()),
             'duplicados_normalizados_test':int(normalizados(test.texto).duplicated().sum()),
             'solapamiento_normalizado_train_test':len(tr&te),
             'pares_test_con_similitud_mayor_igual_080':int((best>=.8).sum()),
             'similitud_maxima':float(round(best.max(),4)),
             'nota':'Similitud superficial; no prueba ausencia de paráfrasis o fuga semántica.'}
    (OUT/'auditoria_datos.json').write_text(json.dumps(reporte,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(reporte,ensure_ascii=False,indent=2))

if __name__=='__main__':
    ejecutar()
