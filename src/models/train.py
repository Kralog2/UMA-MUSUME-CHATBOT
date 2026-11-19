"""Entrenamiento reproducible de SVM con calibración interna (solo train)."""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from src.preprocessing.text_preprocessor import crear_vectorizador
from src.utils.data_loader import cargar_dataset

ROOT = Path(__file__).resolve().parents[2]


def construir_modelo_base():
    return Pipeline([
        ("tfidf", crear_vectorizador()),
        ("clasificador", LinearSVC(class_weight="balanced", random_state=42)),
    ])


def entrenar():
    train = cargar_dataset(ROOT / "data/versions/dbc_v2/train.csv")
    test = cargar_dataset(ROOT / "data/versions/dbc_v2/test.csv")
    assert set(test.intencion) <= set(train.intencion), "El test tiene intenciones que no están en train"
    assert train.intencion.value_counts().min() >= 5, "Se requieren al menos cinco ejemplos por clase"
    # La calibración se ajusta SOLO sobre entrenamiento con CV; no toca test.
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    base = construir_modelo_base()
    puntajes = cross_validate(base, train.texto, train.intencion, cv=cv,
                              scoring={"accuracy":"accuracy", "f1_macro":"f1_macro"})
    print("SVM sin calibrar - CV accuracy:", round(puntajes["test_accuracy"].mean(),4))
    print("SVM sin calibrar - CV F1 macro:", round(puntajes["test_f1_macro"].mean(),4))
    # Internamente cada fold calibra un pipeline completo sin fuga del vectorizador.
    model = CalibratedClassifierCV(estimator=construir_modelo_base(), method="sigmoid", cv=cv)
    model.fit(train.texto,train.intencion)
    # Este test ya se utilizó en el proyecto anterior; informar como reevaluación, no test virgen.
    pred = model.predict(test.texto)
    probs = model.predict_proba(test.texto)
    metricas = {
        "modelo":"SVM lineal calibrado (sigmoid, CV=5)",
        "train_ejemplos":int(len(train)),"test_ejemplos":int(len(test)),
        "accuracy":float(accuracy_score(test.intencion,pred)),
        "precision_macro":float(precision_score(test.intencion,pred,average="macro",zero_division=0)),
        "recall_macro":float(recall_score(test.intencion,pred,average="macro",zero_division=0)),
        "f1_macro":float(f1_score(test.intencion,pred,average="macro",zero_division=0)),
        "cv_f1_macro_svm_sin_calibrar":float(puntajes["test_f1_macro"].mean()),
        "nota":"El conjunto test se había usado en una evaluación anterior; no considerarlo test independiente nuevo."
    }
    (ROOT/"artifacts").mkdir(exist_ok=True)
    (ROOT/"data/processed").mkdir(parents=True,exist_ok=True)
    joblib.dump(model, ROOT/"artifacts/mejor_modelo.joblib")
    (ROOT/"data/processed/metricas_integracion.json").write_text(json.dumps(metricas,ensure_ascii=False,indent=2),encoding="utf8")
    labels=sorted(train.intencion.unique())
    pd.DataFrame(confusion_matrix(test.intencion,pred,labels=labels),index=labels,columns=labels).to_csv(ROOT/"data/processed/matriz_confusion_integracion.csv",encoding="utf-8-sig")
    errores=test.assign(intencion_predicha=pred, confianza=probs.max(axis=1))
    errores[errores.intencion!=errores.intencion_predicha].to_csv(ROOT/"data/processed/errores_integracion.csv",index=False,encoding="utf-8-sig")
    print("\nEvaluación de regresión sobre test previamente utilizado:")
    print(json.dumps(metricas,ensure_ascii=False,indent=2))
    print(classification_report(test.intencion,pred,zero_division=0))
    print("Modelo guardado en artifacts/mejor_modelo.joblib")
    return model

if __name__=="__main__":
    entrenar()
