# Etapa 6 — Evaluación integral del chatbot

## Objetivo

Evaluar el sistema **UMA MUSUME ChatBot v3.0** como conjunto: clasificador,
política de confianza, gestor conversacional y API. La calidad de las
recomendaciones se evalúa mediante reglas automatizadas y una **rúbrica humana
pendiente de completar**. Se mantiene el modelo y los umbrales de la Etapa 5.4.

## Procedimiento de reproducción

Desde la raíz y con las dependencias instaladas:

```powershell
$env:UMABOT_MODELO = "v3"
python -m src.evaluation.evaluacion_integral --modelo v3 --peticiones 25
python tests/test_recommendations.py
python tests/test_context.py
python tests/test_confidence.py
python tests/run_conversation_tests.py --modelo v3
python tests/test_api.py
python -m unittest discover -s tests -p 'test_evaluacion_integral.py'
```

Resultados: `data/processed/etapa6/v3/`, en especial `resultados.json`,
`RESUMEN_RESULTADOS.md`, matrices de confusión, errores, decisiones de confianza
y registro de turnos. Los tiempos varían según el ordenador.

## Dimensiones y criterios

| Dimensión | Indicador | Fuente | Interpretación |
|---|---|---|---|
| Clasificación | Exactitud, precisión, recall, F1 macro, Top-3 | Datos de prueba DBCv3 (170) y challenge previo (68) | Son conjuntos **ya utilizados**, no evaluación ciega nueva |
| Confianza | Cobertura, precisión de aceptadas, aclaraciones, reformulaciones | 68 preguntas de challenge previo | Mide solo la decisión inicial, no resolución posterior |
| Conversación | Turnos correctos y escenarios completos | 15 escenarios / 34 turnos definidos antes | Pruebas de regresión, no muestra representativa de usuarios |
| Recomendaciones | Cumplimiento de filtros, aptitudes, ranking estable, paginación, bonos verificables | `tests/test_recommendations.py` | Comprueba código y consistencia del catálogo, no estrategia óptima |
| API | Respuestas HTTP y latencia local p50/p95 | FastAPI TestClient | No representa rendimiento de despliegue o carga concurrente |
| Calidad percibida | Precisión factual, relevancia, contexto, claridad, utilidad (1–5) | `rubrica_evaluacion_humana.csv` | **Pendiente:** los campos quedan vacíos hasta recibir puntuaciones reales |

## Protocolo propuesto para una evaluación humana independiente

1. Reclutar al menos dos evaluadores familiarizados con el videojuego y, si es
   posible, un tercero sin experiencia para valorar claridad.
2. Preparar al menos 10 conversaciones nuevas de 3–5 turnos y registrar sus
   preguntas **antes** de ejecutar el chatbot; no reescribirlas para mejorar el resultado.
3. Pedir a cada evaluador que puntúe, por separado y en escala de 1 a 5:
   **exactitud factual**, **relevancia**, **seguimiento del contexto**,
   **claridad** y **utilidad**. El 1 indica deficiencia grave y el 5
   cumplimiento completo.
4. Solicitar una referencia verificable (datos de DBCv3, material de juego u otra
   fuente citada) para las afirmaciones factuales. No atribuir certeza factual a
   consejos estratégicos sin respaldo.
5. Guardar una fila por evaluador y turno en la rúbrica CSV. Calcular después
   promedios por dimensión y dispersión entre evaluadores, e identificar
   desacuerdos; no sustituirlos por una única nota automática.
6. Mantener estas conversaciones fuera del ajuste del modelo y de los umbrales;
   si se utilizan para mejorar la aplicación, registrar una futura evaluación
   con otro conjunto nuevo.

### Ejemplos de casos a incluir en la revisión humana

- Referencia pronombre: «Háblame de Gold Ship» → «¿Y para ella qué cartas?».
- Restricciones acumulativas: «para largas» → «F2P» → «sin SSR».
- Aclaración de intención: consulta ambigua → «la segunda opción».
- Cambio de tema: recomendaciones de cartas → consulta sobre Stamina.
- Desconocido: cocina, historia o tecnología (fuera del juego).
- Conflicto de filtros: preferencia de rareza SSR y exclusión SSR.
- Solicitud que exceda el catálogo: carta no documentada.
- Reinicio y separación de dos sesiones concurrentes.

## Cautelas para el reporte

- No comparar accuracy del SVM con «exactitud entre aceptadas» como si fueran
  métricas idénticas: la segunda excluye parte de las preguntas.
- El 100 % en pruebas escritas por el equipo **no implica** 100 % de precisión
  en conversaciones reales.
- Los tiempos son de la máquina y ejecución presentes, sin garantía de
  repetibilidad exacta en otra infraestructura.
- Las evaluaciones de los 170 y 68 ejemplos **no** se deben anunciar como
  evaluación independiente nueva.
- Los datos y recomendaciones del juego se limitan a la base DBCv3.

## Archivos agregados

- `src/evaluation/evaluacion_integral.py`: ejecutor de mediciones y exportación.
- `tests/test_evaluacion_integral.py`: validación de cálculos y contratos.
- `data/processed/etapa6/v3/`: resultados y plantilla de evaluación humana.
- `docs/ETAPA_6_EVALUACION_INTEGRAL.md`: metodología y limitaciones.

Los archivos `.py` agregados están documentados con encabezados y docstrings
de módulo, clase y funciones en español.
