# Etapa 5.1 — DBCv3 y modelo V3

Se exportaron las ocho hojas del Excel (los CSV aportados coinciden en contenido con DataTrain y DataTest). Se archivan los datos V2 en `data/versions/dbc_v2/`. La base de conocimiento activa es V3 para todos los modelos; el comparativo de modelos no es un comparativo de bases de conocimiento. El exportador admite ambos nombres de la hoja de efectos y valida antes de escribir. Las respuestas adicionales permanecen intactas.

## Reproducción

Python 3.11 recomendado para el equipo (ejecución de verificación aquí: Python 3.13.5, scikit-learn 1.8.0). Instalar requirements.txt; si se usa otro entorno, reentrenar el modelo antes de cargarlo. Cargar joblib únicamente desde fuentes confiables.

```powershell
python scripts/export_from_xlsx.py
python -m src.models.train_v3
python -m src.chat_console --modelo v3
python tests/run_conversation_tests.py --modelo v3
$env:UMABOT_MODELO = "v3"
python tests/test_api.py
python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

Se conserva el modelo anterior por defecto de la API y consola; V3 se activa explícitamente. No cambia el contrato HTTP. Para volver al default de la API, `Remove-Item Env:UMABOT_MODELO`.

## Metodología y resultados

Mismos cinco folds externos estratificados (semilla 42) de 510 ejemplos. Para cada fold, se ajusta un pipeline TF-IDF + LinearSVC calibrado con sigmoid y cinco folds internos exclusivamente sobre el entrenamiento externo (más refuerzo para esa variante). No se ajusta con test. Selección por F1 macro calculado sobre todas las predicciones fuera de fold (OOF). V3 reforzado gana (78.32% frente a 76.51%); se entrena con 583 ejemplos. No existen coincidencias normalizadas de entrenamiento con test o desafío, aunque esto no descarta similitud semántica. Resultado test: 157/170; 31/34 adicionales; 55/68 en desafío anterior. No se consideran evaluaciones finales vírgenes: 136 preguntas del test y las 68 del desafío ya se habían usado. El conjunto adicional es pequeño y solo contiene dos ejemplos por clase. Fuera de dominio: recall 6/10 en test y 2/4 en desafío. No se modifican los umbrales ni se ajustan con esos resultados. No se probó la calidad factual de todos los contenidos del juego.

Resultados y probabilidades OOF para etapa 5.2: `data/processed/etapa51/`. Las pruebas originales pasaron 34/34 con V3 y con reforzado anterior; HTTP V3: 4/4 grupos. Son pruebas de regresión, no una garantía de todas las conversaciones. Los scripts históricos de entrenamiento y auditoría apuntan a la copia V2 para no mezclar versiones; al ejecutarlos pueden regenerar sus artefactos históricos. El modelo V3 es un artefacto separado.
