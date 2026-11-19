# Etapa 5.4 — Recomendaciones personalizadas

Se conserva DBCv3, el SVM V3, sus umbrales y los endpoints. El nuevo módulo `card_recommender.py` lee los datos a través de KnowledgeBase, sin cambiar los CSV. `dialogue_manager.py` conecta el ranking con el estado de conversación y presenta páginas de cinco cartas. El método histórico `KnowledgeBase.recomendar_cartas` permanece por compatibilidad; el diálogo usa el nuevo módulo.

## Política heurística

1. Excluir cartas que incumplan escenario, estadística, rareza, exclusión SSR o distancia/estilo/pista explícitos. Excluir carta del mismo personaje cuando coincide el nombre corto. `any` se interpreta como etiqueta general del catálogo, no como garantía de que toda habilidad sirva para cualquier carrera.
2. Si falta distancia, estilo o pista, recuperar todas las mejores aptitudes registradas del personaje. Una preferencia explícita tiene prioridad y se advierte si su aptitud es inferior a A/S. Si no hay personaje ni preferencia, no se aplica ese criterio.
3. Sumar por cada dimensión: +4 coincidencia especializada explícita, +2 coincidencia especializada inferida, +1 etiqueta general, -2 especialización fuera de aptitudes inferidas. Las incompatibilidades explícitas se excluyen en vez de penalizarse.
4. Orden descendente por puntuación de compatibilidad, luego evidencia F2P cuando se solicita, luego suma de porcentajes de entrenamiento, amistad y carrera; desempate por ID. Para F2P se buscan notas que mencionan F2P en los efectos de DBCv3; no se deduce inventario ni se equipara F2P con SR.
5. Mostrar los bonos del límite MLB registrado (o mayor disponible), habilidad y escenario. Si no hay coincidencias, no relajar filtros. La paginación usa el mismo ranking y contexto. Una nueva solicitud de recomendaciones vuelve a la primera página.

Los pesos son decisiones de diseño no optimizadas experimentalmente. No son una predicción de rendimiento en carrera ni una recomendación de mazo completo. Los niveles y etiquetas son los registrados en el catálogo, no verificados contra el juego actual. No se modelan propiedad de cartas, sinergias, préstamos, disponibilidad, ni todos los efectos de habilidades. Las recomendaciones sin escenario específico pueden incluir cartas de escenarios distintos, identificados individualmente. Las aptitudes inferidas son preferencias blandas: una carta con especialización distinta puede aparecer más abajo con advertencia.

## Pruebas

Desde la raíz, con dependencias instaladas:

```powershell
python tests/test_recommendations.py
python tests/test_context.py
python tests/test_confidence.py
python tests/run_conversation_tests.py --modelo v3
$env:UMABOT_MODELO = 'v3'
python tests/test_api.py
```

Resultados en `data/processed/etapa54/`. Las pruebas verifican restricciones, aptitudes, evidencia F2P, orden, bonos, paginación y HTTP. No sustituyen una evaluación humana de relevancia. Se conserva la clasificación de fuera de dominio; se aseguró que todas las variantes de esa respuesta mencionen Umamusume, tras detectar una regresión de texto por el cambio de secuencia aleatoria de plantillas.
