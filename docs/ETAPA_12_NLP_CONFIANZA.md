# Etapa 12 — NLP y manejo de confianza (versión 4.0)

## Objetivo
Mejorar la clasificación de preguntas con nombres de personajes, escenarios, rarezas y errores de escritura, manteniendo las **18 intenciones**. Calibrar una política propia para el nuevo modelo y utilizar contexto solo ante evidencia de continuidad.

## Datos y selección metodológica

- Entrenamiento: **613** ejemplos (510 de DBCv3, 73 refuerzo, 30 objetivos_stats).
- Se utilizó **StratifiedKFold de 5 particiones**, semilla 42, con las mismas particiones para las tres variantes.
- Las transformaciones TF-IDF y de enmascaramiento se ajustan dentro del pipeline de cada fold.
- Para comparación se generaron predicciones fuera de partición (OOF) de LinearSVC con clase equilibrada.
- **No se consultaron los tests históricos para seleccionar las características o la política.**

| Variante | Accuracy OOF | F1 macro OOF |
|---|---:|---:|
| Palabras (1–2) | 76.02 % | 75.44 % |
| Palabras + caracteres (3–5) | 79.12 % | 78.66 % |
| **Enmascaramiento + palabras + caracteres** | **81.40 %** | **81.33 %** |

La variante seleccionada sustituye nombres conocidos por `entidad_personaje`, `entidad_escenario` y `entidad_rareza` **antes** de la vectorización. El catálogo procede únicamente de `data/game/`, no de los conjuntos de prueba. El mismo transformador se serializa dentro del pipeline para inferencia.

### Calibración y aceptación

El modelo seleccionado se calibra con `CalibratedClassifierCV(method='sigmoid', cv=3)` **sobre datos de entrenamiento**. Para seleccionar umbrales se volvieron a obtener probabilidades OOF con CV externa de cinco folds y calibración interna de tres folds.

La política buscó la exactitud mayor entre aceptadas, respetando una cobertura directa mínima del **65 %**. Resultado:

| Parámetro | Valor |
|---|---:|
| Confianza mínima | **0.50** |
| Margen top-1 − top-2 | **0.25** |
| Umbral mínimo de reformulación | **0.25** (heurístico) |
| Cobertura OOF durante selección | **65.74 %** |
| Exactitud OOF entre aceptadas durante selección | **93.55 %** |

**Advertencia metodológica:** los umbrales se escogieron sobre esas mismas predicciones OOF; por tanto, los indicadores de cobertura y exactitud aceptada pueden ser optimistas. No constituyen una evaluación ciega de la política. Las probabilidades calibradas tampoco garantizan un rechazo confiable de consultas fuera de dominio.

## Integración con el chatbot

- `src/models/predictor_adapter.py` carga V4 y su política desde `data/processed/etapa12/politica_confianza_v4.json`.
- `src/conversation/dialogue_manager.py` utiliza `ConfidenceManager` con los umbrales nuevos. Cuando hay ambigüedad y **el tema anterior figura entre las dos primeras clases**, una pregunta corta con marcador de continuación y sin cambio de personaje puede recuperar el tema anterior. No se fuerza continuidad por simple parecido de probabilidades.
- Dos mensajes seguidos sin entidades reconocibles pasan a una respuesta orientadora, evitando preguntar indefinidamente por intenciones alternativas.
- Las consultas sobre aptitudes de nombres que solo figuran como cartas reciben una respuesta sobre el límite del catálogo, en lugar de elegir arbitrariamente una clase incierta.
- Consola y API utilizan `v4` por defecto; se mantiene `--modelo v3` o `UMABOT_MODELO=v3` para regresión.
- No se cambiaron los datos del videojuego, los mazos ni los endpoints HTTP.

## Evaluación histórica (control posterior, no selección)

Después de congelar el modelo y la política se comprobaron los tests **ya utilizados en etapas anteriores**:

| Conjunto | V4 Etapa 11 accuracy | V4 Etapa 12 accuracy |
|---|---:|---:|
| DBCv3 test (170, histórico) | 90.00 % | 95.29 % |
| Evaluación adicional (68, histórica) | 82.35 % | 86.76 % |
| Objetivos_stats (10, sintético) | 70.00 % | 80.00 % |

El conjunto de DBCv3 y el de 68 preguntas solo cubren las clases históricas. **No se deben presentar como una evaluación independiente de las 18 intenciones.** Los ejemplos nuevos son sintéticos. El CSV de comparaciones incluye F1 macro, que en un subconjunto de una sola clase resulta difícil de interpretar y no mide desempeño global.

## Evidencias y comandos

```powershell
python -m src.models.train_v4_nlp
python -m src.evaluation.evaluar_etapa12
python tests/test_etapa12_nlp.py
python -m unittest discover -s tests -p "test_*.py"
python tests/run_conversation_tests.py --modelo v4
python tests/test_api.py
```

Los resultados están en `data/processed/etapa12/`, y el modelo serializado en `artifacts/modelo_v4_etapa12.joblib`.

## Limitaciones y próxima etapa

No hay prueba ciega nueva de 18 intenciones, ni evaluación de usuarios reales, ni medición de calibración probabilística por clase. Debemos obtener muestras independientes de mensajes libres, errores de escritura, distintas longitudes y consultas fuera del dominio antes de declarar un nivel de precisión final. La siguiente **Etapa 13** cubrirá las pruebas integrales y el cierre académico de v4.0.
