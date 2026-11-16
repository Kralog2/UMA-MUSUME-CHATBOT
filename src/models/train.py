
from pathlib import Path
import json
import joblib
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)
from sklearn.metrics import make_scorer

from src.preprocessing.text_preprocessor import crear_vectorizador
from src.utils.data_loader import cargar_dataset


# ==========================================
# 1. RUTAS DEL PROYECTO
# ==========================================

RUTA_ENTRENAMIENTO = "data/raw/train.csv"
RUTA_PRUEBA = "data/raw/test.csv"

CARPETA_MODELOS = Path("artifacts")
CARPETA_RESULTADOS = Path("data/processed")

CARPETA_MODELOS.mkdir(parents=True, exist_ok=True)
CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)


# ==========================================
# 2. CARGAR LOS DATASETS
# ==========================================

print("\n========== CARGANDO DATASETS ==========")

datos_train = cargar_dataset(RUTA_ENTRENAMIENTO)
datos_test = cargar_dataset(RUTA_PRUEBA)

if datos_train is None or datos_test is None:
    raise SystemExit("No fue posible cargar los archivos CSV.")

X_train = datos_train["texto"]
y_train = datos_train["intencion"]

X_test = datos_test["texto"]
y_test = datos_test["intencion"]

print(f"Ejemplos de entrenamiento: {len(X_train)}")
print(f"Ejemplos de prueba: {len(X_test)}")
print(f"Intenciones de entrenamiento: {y_train.nunique()}")


# ==========================================
# 3. DEFINIR LOS CLASIFICADORES
# ==========================================

modelos = {
    "Regresion Logistica": LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42
    ),

    "SVM": LinearSVC(
        class_weight="balanced",
        random_state=42
    )
}


# ==========================================
# 4. VALIDACION CRUZADA
# ==========================================

print("\n========== VALIDACION CRUZADA ==========")

conteo_clases = y_train.value_counts()
minimo_ejemplos = conteo_clases.min()

if minimo_ejemplos < 2:
    raise SystemExit(
        "Cada intención necesita al menos 2 ejemplos para "
        "realizar validación cruzada estratificada."
    )

numero_folds = min(5, minimo_ejemplos)

validacion = StratifiedKFold(
    n_splits=numero_folds,
    shuffle=True,
    random_state=42
)

metricas_cv = {
    "accuracy": "accuracy",
    "precision_macro": make_scorer(
        precision_score,
        average="macro",
        zero_division=0
    ),
    "recall_macro": make_scorer(
        recall_score,
        average="macro",
        zero_division=0
    ),
    "f1_macro": make_scorer(
        f1_score,
        average="macro",
        zero_division=0
    )
}

resultados_cv = {}

for nombre, clasificador in modelos.items():

    pipeline = Pipeline([
        ("tfidf", crear_vectorizador()),
        ("clasificador", clasificador)
    ])

    resultados = cross_validate(
        pipeline,
        X_train,
        y_train,
        cv=validacion,
        scoring=metricas_cv,
        n_jobs=-1
    )

    resultados_cv[nombre] = {
        metrica: resultados[f"test_{metrica}"].mean()
        for metrica in metricas_cv
    }

    print(f"\nModelo: {nombre}")

    for metrica, valor in resultados_cv[nombre].items():
        print(f"{metrica}: {valor:.4f}")


# ==========================================
# 5. SELECCIONAR EL MEJOR MODELO
# ==========================================

mejor_modelo_nombre = max(
    resultados_cv,
    key=lambda nombre: resultados_cv[nombre]["f1_macro"]
)

print("\n========== SELECCION DEL MODELO ==========")
print(f"Mejor modelo: {mejor_modelo_nombre}")

mejor_clasificador = modelos[mejor_modelo_nombre]

mejor_pipeline = Pipeline([
    ("tfidf", crear_vectorizador()),
    ("clasificador", mejor_clasificador)
])


# ==========================================
# 6. ENTRENAMIENTO FINAL
# ==========================================

print("\n========== ENTRENAMIENTO FINAL ==========")

mejor_pipeline.fit(X_train, y_train)

print("Modelo entrenado correctamente.")


# ==========================================
# 7. EVALUACION CON EL DATASET DE PRUEBA
# ==========================================

print("\n========== EVALUACION FINAL ==========")

predicciones = mejor_pipeline.predict(X_test)

metricas_finales = {
    "accuracy": accuracy_score(y_test, predicciones),
    "precision_macro": precision_score(
        y_test, predicciones, average="macro", zero_division=0
    ),
    "recall_macro": recall_score(
        y_test, predicciones, average="macro", zero_division=0
    ),
    "f1_macro": f1_score(
        y_test, predicciones, average="macro", zero_division=0
    )
}

for metrica, valor in metricas_finales.items():
    print(f"{metrica}: {valor:.4f}")


# ==========================================
# 8. REPORTE DE CLASIFICACION
# ==========================================

reporte = classification_report(
    y_test,
    predicciones,
    zero_division=0,
    output_dict=True
)

print("\n========== REPORTE DE CLASIFICACION ==========")

print(
    classification_report(
        y_test,
        predicciones,
        zero_division=0
    )
)


# ==========================================
# 9. MATRIZ DE CONFUSION
# ==========================================

etiquetas = sorted(set(y_test) | set(predicciones))

matriz = confusion_matrix(
    y_test,
    predicciones,
    labels=etiquetas
)

df_matriz = pd.DataFrame(
    matriz,
    index=etiquetas,
    columns=etiquetas
)

df_matriz.to_csv(
    CARPETA_RESULTADOS / "matriz_confusion.csv",
    encoding="utf-8-sig"
)


# ==========================================
# 10. GUARDAR MODELO Y RESULTADOS
# ==========================================

joblib.dump(
    mejor_pipeline,
    CARPETA_MODELOS / "mejor_modelo.joblib"
)

with open(
    CARPETA_RESULTADOS / "metricas_finales.json",
    "w",
    encoding="utf-8"
) as archivo:

    json.dump(
        {
            "mejor_modelo": mejor_modelo_nombre,
            "validacion_cruzada": resultados_cv,
            "evaluacion_final": metricas_finales,
            "reporte_clasificacion": reporte
        },
        archivo,
        ensure_ascii=False,
        indent=4
    )

resultados_comparacion = pd.DataFrame(resultados_cv).T
resultados_comparacion.to_csv(
    CARPETA_RESULTADOS / "comparacion_modelos.csv",
    encoding="utf-8-sig"
)

# ==========================================
# 11. GUARDAR PREDICCIONES INCORRECTAS
# ==========================================

errores = pd.DataFrame({
    "pregunta": X_test.reset_index(drop=True),
    "intencion_real": y_test.reset_index(drop=True),
    "intencion_predicha": predicciones
})

errores = errores[
    errores["intencion_real"] != errores["intencion_predicha"]
]

errores.to_csv(
    CARPETA_RESULTADOS / "errores_clasificacion.csv",
    index=False,
    encoding="utf-8-sig"
)

print(f"\nTotal de errores: {len(errores)}")
print(errores.to_string(index=False))

print("\n========== PROCESO TERMINADO ==========")
print("Modelo guardado en: artifacts/mejor_modelo.joblib")
print("Resultados guardados en: data/processed/")
