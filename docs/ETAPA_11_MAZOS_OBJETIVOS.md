# Etapa 11 — Armador de mazos y objetivos de estadísticas

## Alcance
- `deck_builder.py`: propuesta de **seis cupos por roles** usando objetivos generales `*_goal` del archivo `characters.csv`. Se utilizan los filtros y la puntuación existente de `card_recommender.py`; las cartas no se duplican. **No es un optimizador de sinergias ni conoce el inventario**.
- `objetivos_stats`: intención 18, metas numéricas tomadas de `Characters`. La base **no distingue objetivos por escenario** y el bot lo advierte.
- Si faltan cartas compatibles, se entregan solamente las encontradas y se explican las vacantes. No se relajan restricciones de forma oculta.
- La exclusión de cartas homónimas se conservó sin alterar: pendiente de verificación de reglas del juego.

## Dataset y evaluación
- `data/raw/objetivos_stats_train.csv`: 30 nuevas frases etiquetadas sintéticas.
- `data/raw/objetivos_stats_test.csv`: 10 frases sintéticas separadas, para diagnóstico focalizado.
- Se conserva intacto el entrenamiento anterior y `modelo_v3.joblib`. Un nuevo `modelo_v4_etapa11.joblib` se genera con **18 intenciones** mediante CV estratificada y calibración sobre entrenamiento.
- La prueba focalizada de una sola intención **no mide exactitud global**, y el test anterior fue reutilizado en otras etapas. Antes del cierre, construir una evaluación ciega nueva con todas las clases.
- Los umbrales del gestor de confianza V3 no se extrapolan a V4: la recalibración contextual corresponde a Etapa 12. **V3 sigue predeterminado** y el modelo de 18 clases se activa con `--modelo v4` o `UMABOT_MODELO=v4`. V4 aún no activa la política selectiva V3.
- Validación realizada: 613 ejemplos de entrenamiento (510 DBCv4 + 73 refuerzo + 30 objetivos), 18 clases; CV F1 macro ≈ 0.7525, accuracy ≈ 0.7603. Evaluación sintética focalizada de objetivos: 7/10. Estos valores no son comparables directamente con la evaluación antigua sobre 17 clases.
- La exportación `scripts/export_from_xlsx.py` preserva la definición suplementaria `objetivos_stats` que está en `data/game/intents.json`. Los 30+10 ejemplos nuevos se conservan en CSV separados y no se escriben en DBCv4.

## Ejecución
```
python -m src.models.train_v4_intenciones
python tests/test_etapa11_mazos.py
python -m src.chat_console --modelo v4
# API opcional con V4: $env:UMABOT_MODELO = 'v4'
# python -m uvicorn src.api.app:app --reload --port 8000
```

## Pendientes
- Validez externa de pesos de compatibilidad, distribución de roles y reglas de exclusión.
- Construcción del inventario del jugador y combinaciones de habilidades.
- Nueva validación del rechazo a preguntas fuera de dominio con 18 clases.
