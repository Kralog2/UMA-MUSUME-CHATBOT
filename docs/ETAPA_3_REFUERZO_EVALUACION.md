# Etapa 3 — Refuerzo focalizado y evaluación separada

## 1. ¿En qué consiste?

1. **Diagnóstico de intenciones confundidas:** usamos los errores *out-of-fold* (OOF) de la Etapa 2, que solo se calcularon sobre entrenamiento; no se reutiliza el test antiguo para seleccionar una mejora.
2. **Refuerzo focalizado:** se redactaron **73 ejemplos adicionales**, etiquetados, para siete intenciones con confusiones conocidas. Están en `data/raw/refuerzo_etapa3.csv`. No se sustituyen ni reetiquetan los 425 ejemplos anteriores.
3. **Validación previa a la evaluación separada:** para comparar la variante base con la reforzada, se mantuvieron exactamente los mismos cinco folds sobre las **425 preguntas originales**. En cada fold, los 73 ejemplos extra se agregan únicamente al entrenamiento; el fold de validación contiene solo ejemplos originales no vistos en ese fold. La comparación mide el SVM **sin calibrar**, usando la misma construcción del clasificador en ambos casos.
4. **Modelo de conversación:** después se entrena un SVM calibrado con los 425+73 ejemplos, guardándolo con un **nombre diferente**; se conserva el modelo original.
5. **Evaluación separada:** se prepararon **68 preguntas nuevas, cuatro por cada una de las 17 intenciones**, en `data/challenge/evaluacion_nueva_v1.csv`. Se congeló el contenido (hash SHA-256), el modelo y el umbral **0.30** antes de evaluar. Este archivo **no** es leído por el entrenador y no debe utilizarse después para ajustar el clasificador.

## 2. ¿Qué no se modifica?

- `data/raw/train.csv` (425 ejemplos), `data/raw/test.csv` (136, ya evaluado previamente), `data/legacy/`, la base de conocimientos (`data/game/`) y la lógica principal del gestor conversacional.
- `artifacts/mejor_modelo.joblib` se mantiene para ejecutar la variante anterior por defecto.
- Las mejoras no consisten en añadir reglas que memoricen preguntas del examen.

## 3. Resultados medidos

**Validación cruzada OOF (solo preguntas originales del entrenamiento):**

| Variante | Accuracy OOF | F1 macro OOF | Errores / 425 |
|---|---:|---:|---:|
| SVM lineal base | 70.82 % | 70.31 % | 124 |
| SVM lineal con refuerzo | 73.65 % | 73.39 % | 112 |

**Desafío nuevo, una sola evaluación del SVM calibrado reforzado:**

| Métrica | Valor |
|---|---:|
| Ejemplos | 68 (4 por clase) |
| Exactitud sin rechazo | 82.35 % |
| F1 macro sin rechazo | 82.87 % |
| Precisión macro sin rechazo | 86.01 % |
| Recall macro sin rechazo | 82.35 % |
| Cobertura con confianza >= 0.30 | 89.71 % |
| Exactitud entre mensajes aceptados | 86.89 % |
| Mensajes con confianza menor de 0.30 | 7 |

La exactitud sin rechazo **no** incorpora la lógica conversacional ni las aclaraciones del gestor. La cobertura considera el umbral como filtro independientemente de si una clase predicha es `fuera_dominio`.

**Regresión conversacional**: `python tests/run_conversation_tests.py --modelo reforzado` → **34/34 pasos**; prueba la interacción con ejemplos específicos, no una tasa de clasificación independiente.

### Limitaciones honestas

- Los ejemplos adicionales y del desafío se redactaron de manera sintética para este proyecto; las etiquetas **deben ser revisadas por el equipo**. El desafío estaba separado y no se utilizó para entrenamiento ni para selección, pero no es una muestra aleatoria de preguntas reales de jugadores ni demuestra generalización en producción.
- Hay solo **cuatro preguntas por intención** en el desafío: las métricas por clase tienen mucha incertidumbre.
- La intención `fuera_dominio` sigue siendo débil (recall de **2/4** y F1 **0.44**). No debe afirmarse que el filtro de preguntas desconocidas está resuelto.
- La comparación OOF valida el **modelo lineal sin calibrar**; el artefacto del chat es la versión **calibrada**, cuyo F1 se cuantifica de forma independiente sobre el desafío. No confundir esas métricas.
- La evaluación del conjunto de 136 preguntas de `data/raw/test.csv` ya no es "virgen" y no se usa aquí para decidir cambios.
- El desafío se evaluó una vez y el evaluador se niega a sobrescribir automáticamente los resultados. Si se mejora el clasificador otra vez, **se debe crear un nuevo desafío** antes de proclamar un nuevo resultado independiente.

## 4. Archivos agregados o modificados

| Archivo | Operación | Para qué sirve |
|---|---|---|
| `data/raw/refuerzo_etapa3.csv` | Nuevo | 73 preguntas etiquetadas, usadas exclusivamente para mejorar el modelo |
| `data/challenge/evaluacion_nueva_v1.csv` | Nuevo | 68 preguntas de evaluación, **nunca** utilizadas para entrenar |
| `data/challenge/manifiesto.json` | Nuevo | Procedencia, cantidad y huella SHA-256 del desafío |
| `src/models/train_reforzado.py` | Nuevo | Comparación OOF y entrenamiento de SVM calibrado reforzado |
| `src/evaluation/evaluacion_independiente.py` | Nuevo | Métricas, reporte por clase, matriz y predicciones del desafío; bloquea segunda evaluación |
| `artifacts/modelo_reforzado_etapa3.joblib` | Nuevo | Modelo entrenado con 498 ejemplos |
| `data/processed/etapa3/` | Nuevo | Comparación CV, registro de entrenamiento, métricas y errores evaluados |
| `tests/run_conversation_tests.py` | Modificado | Agrega `--modelo reforzado`, sin cambiar el predeterminado original |
| `src/chat_console.py` | Modificado | Agrega `--modelo reforzado`, sin cambiar el predeterminado original |
| `README.md` | Modificado | Instrucciones de esta etapa y cómo reproducir pruebas |
| `docs/ETAPA_3_REFUERZO_EVALUACION.md` | Nuevo | Este documento y registro de decisiones |

## 5. Pasos para reproducir en Windows / VS Code

Desde la raíz `UMA-MUSUME-CHATBOT`, con `.venv` activado y dependencias instaladas:

```powershell
# Compara base/reforzado por validación cruzada y entrena un nuevo modelo
python -m src.models.train_reforzado

# Conversación con el modelo reforzado
python -m src.chat_console --modelo reforzado

# Pruebas conversacionales originales contra el modelo reforzado
python tests/run_conversation_tests.py --modelo reforzado
```

La evaluación separada **ya se ejecutó y está guardada** en `data/processed/etapa3/evaluacion_independiente/`. El comando siguiente **no debe ejecutarse de nuevo** para ajustar el modelo, y rechazará la operación si existe el resultado:

```powershell
python -m src.evaluation.evaluacion_independiente
```

Para leer los resultados sin reejecutar:

```powershell
Get-Content data/processed/etapa3/evaluacion_independiente/resultado.json
```

## 6. Próximo paso

Solicitar revisión humana de etiquetas y de las preguntas ambiguas, observar conversaciones reales de estudiantes/jugadores y diseñar una segunda evaluación con datos reales no usados en ajustes. Después, desarrollar API por sesión para el frontend; mantener el contexto por usuario, no en una instancia global compartida.
