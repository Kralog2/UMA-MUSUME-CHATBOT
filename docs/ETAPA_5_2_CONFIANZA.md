# Etapa 5.2 — Gestor de confianza

Se conserva el modelo V3 y DBCv3. El adaptador ofrece `top_k` y mantiene su interfaz histórica. La política nueva se activa para `modelo_v3.joblib` si no se especifica un umbral manual; los modelos anteriores mantienen la política previa.

## Selección
`python -m src.evaluation.ajustar_confianza` evalúa 25 combinaciones en las 510 predicciones OOF de la etapa 5.1. Se exige cobertura >= 2/3 (criterio de diseño elegido para esta etapa) y se maximiza exactitud entre aceptadas. Resultado: confianza >= .45, margen >= .20. Política anterior: 384 correctas y 75 errores entre 459 aceptadas; nueva: 312 correctas y 31 errores entre 343 aceptadas. Estos son resultados de ajuste, no una evaluación independiente. No se releen los conjuntos test. El límite .25 para solicitar aclaración específica es heurístico, no validado.

## Flujo
Las reglas de seguimiento y aclaraciones de entidades existentes tienen prioridad. Cuando interviene el clasificador, se obtiene el Top-3. Si supera ambos criterios se acepta; si no y p1 >= .25 se solicita aclarar; si p1 < .25 se pide reformular. La abstención no modifica las entidades activas ni el tema; sí registra el turno. No se identifica automáticamente fuera de dominio a partir de confianza baja. Las aclaraciones nuevas piden expresar de nuevo la pregunta, no mantienen todavía una elección pendiente entre intenciones; eso se aborda en 5.3. Por compatibilidad el campo `confianza` histórico se conserva (las reglas pueden devolver 1.0, que no es probabilidad del modelo). `diagnostico_confianza` es objeto opcional con accion, margen y candidatos; null cuando no se evalúa la política nueva. Las respuestas ambiguas conservan `intencion=desconocido`.

## Ejecución
- `python -m src.chat_console --modelo v3`
- `python tests/test_confidence.py`
- `python tests/run_conversation_tests.py --modelo v3`
- PowerShell: `$env:UMABOT_MODELO = "v3"`; `python tests/test_api.py`
- API: `python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000`

## Resultados y límites
34/34 pasos originales para cada uno de los tres modelos, 4/4 grupos HTTP V3 y 4 pruebas nuevas. Las pruebas de diálogo existentes no son una muestra independiente de usuarios. La política puede abstenerse de preguntas válidas y aceptar errores con confianza alta. Falta medir recuperación de aclaraciones y mejorar resolución de contexto en 5.3. No se modificaron datasets, modelos ni endpoints existentes. Se agregó documentación de módulos y funciones de los archivos Python nuevos/modificados.
