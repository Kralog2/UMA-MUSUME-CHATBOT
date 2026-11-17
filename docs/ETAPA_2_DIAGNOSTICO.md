# Etapa 2 — Diagnóstico del clasificador

Fecha: 17 de noviembre de 2026. Dataset congelado de esta etapa: **425** ejemplos de entrenamiento, **136** de prueba; 17 intenciones (25/8 por intención).

## Metodología

- Las **comparaciones nuevas** usan exclusivamente `data/raw/train.csv`, con validación cruzada estratificada de cinco particiones (`random_state=42`).
- Se obtienen predicciones **fuera de partición** (OOF): cada ejemplo se predice con un modelo que no lo utilizó para entrenar.
- Se comparan TF-IDF (unigramas y bigramas) + regresión logística, SVM lineal y SVM lineal calibrado con sigmoide. En el calibrado, la calibración usa tres particiones internas dentro de cada partición externa.
- `data/raw/test.csv` **no participa** en selección de modelo, diagnóstico OOF o búsqueda de umbrales. Ese conjunto ya se había utilizado antes y no puede considerarse totalmente independiente para nuevas decisiones.
- El análisis de similitud entre train/test es una **auditoría**, no una evaluación de selección.

## Resultados (425 predicciones OOF; solo entrenamiento)

| Modelo | Exactitud | F1 macro | Errores |
|---|---:|---:|---:|
| SVM lineal | 70.82 % | **70.30 %** | 124 |
| SVM lineal calibrado | 70.59 % | 70.09 % | 125 |
| Regresión logística | 68.94 % | 68.35 % | 132 |

**Interpretación:** la calibración no mejora por sí sola la exactitud; sirve para obtener probabilidades utilizables por el gestor. Estas métricas **no son comparables como si fueran un mismo diseño experimental** con el 89.71 % del test anterior, que es un único conjunto posiblemente más fácil.

## Umbral de aceptación (OOF del SVM calibrado)

| Umbral | Cobertura de mensajes | Exactitud de mensajes aceptados | Rechazados (de 425) |
|---|---:|---:|---:|
| 0.20 | 94.12 % | 72.50 % | 25 |
| 0.30 | 80.00 % | 78.82 % | 85 |
| 0.35 | 68.94 % | 83.28 % | 132 |
| 0.40 | 60.47 % | 85.99 % | 168 |
| 0.50 | 44.00 % | 89.30 % | 238 |

Los porcentajes de exactitud entre aceptados no son `precision_macro`. **Más exigencia puede mejorar la exactitud de los mensajes contestados, pero reduce la cobertura y no garantiza identificar todos los fuera de dominio.** Por ello **no cambiamos** el umbral actual `0.30` sin una batería separada de pruebas de rechazo y experiencia conversacional.

## Errores más frecuentes en validación OOF del SVM calibrado

- `fuera_dominio`: 15 errores / 25 ejemplos.
- `info_personaje`: 13 / 25.
- `pedir_mas_detalle`: 11 / 25.
- `cartas_recomendadas`: 10 / 25.
- `cartas_soporte`: 8 / 25.

Esto hace prioritario revisar en el siguiente paso los ejemplos ambiguos y el tratamiento de solicitudes contextuales; la clasificación del mensaje aislado no siempre puede resolver una intención dependiente de la conversación.

## Comprobación de datos

- Duplicados exactos o normalizados entre train/test: **0**.
- Pares test/train con similitud de trigramas a pentagramas de caracteres >= 0.80: **0**; similitud máxima observada: **0.759**.
- Esta prueba no detecta todas las paráfrasis ni demuestra ausencia completa de fuga semántica.

## Archivos de evidencia y ejecución

```powershell
python -m src.evaluation.diagnostico_cv
python -m src.evaluation.auditoria_datos
python tests/run_conversation_tests.py
```

Los CSV generados en `data/processed/diagnostico_cv/` incluyen predicciones OOF, matrices de confusión, errores por pregunta y modelo, comparación, cobertura por umbral y pares más similares. No alteran `artifacts/mejor_modelo.joblib` ni los CSV originales.

## Próxima mejora

1. Revisar y corregir ejemplos cuya etiqueta sea dudosa, con el equipo responsable del dataset; documentar modificaciones.
2. Crear un **nuevo conjunto de evaluación externo** con mensajes auténticamente nuevos, fuera de dominio y de varios turnos, sin reutilizar para ajustar el modelo.
3. Ensayar reglas de aclaración y rechazo en validación, sin imponer un umbral mayor sin comprobar cobertura conversacional.
4. Integrar una API por sesión tras estabilizar la evaluación.
