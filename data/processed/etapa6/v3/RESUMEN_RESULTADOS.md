# Etapa 6 — Resultados de evaluación integral

Generado (UTC): 2026-11-24T18:09:58.356219+00:00

**Importante:** los datasets y escenarios provienen de etapas previas. No son pruebas ciegas nuevas.

## Clasificación

| Conjunto | Muestras | Accuracy | F1 macro | Top-3 | Errores |
|---|---:|---:|---:|---:|---:|
| dbc_v3_test_historico | 170 | 92.35% | 92.17% | 99.41% | 13 |
| challenge_etapa3_historico | 68 | 80.88% | 81.11% | 97.06% | 13 |

## Confianza (medición retrospectiva)

Cobertura: **75.00%**. Exactitud entre aceptadas: **90.20%**.
Decisiones: {'aceptar': 51, 'aclarar': 13, 'reformular': 4}. Errores aceptados: 5.

## Conversaciones de regresión

Escenarios completos: **15/15**; turnos correctos: **34/34**.
Latencia del diálogo p50/p95: 6.076 / 6.64 ms.

## API local

HTTP 200: **25/25**; latencia p50/p95: 20.496 / 22.907 ms.

## Pendiente de evaluación humana

La rúbrica `rubrica_evaluacion_humana.csv` está vacía. No atribuir puntuaciones de calidad factual, utilidad, claridad o experiencia de usuario hasta que evaluadores la completen.

## Alcance y limitaciones

- No se reentrenó ni recalibró ningún modelo durante esta etapa.
- No se ajustaron umbrales con la prueba.
- Los experimentos de clasificación y diálogo no son una prueba independiente nueva.
- La latencia de API proviene de TestClient local, no de usuarios reales.
- La recomendación de cartas debe validarse con fuentes del juego y personas conocedoras.
