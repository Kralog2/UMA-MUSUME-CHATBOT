# Etapa 8 — Corrección de estado y filtros

**Rama de desarrollo:** UMA MUSUME ChatBot v4.0. La integración Streamlit corresponde a la **Etapa 7**; esta corrección es la **Etapa 8**. Se mantiene el modelo SVM V3 sin reentrenarlo.

## Objetivo

Solucionar los defectos críticos del listado del equipo: (1) «mazo» interpretado como estadística, (2) filtros y preferencias heredados entre personajes y contaminación del contexto por búsquedas fallidas, (3) cartas homónimas detectadas al mencionar personajes, (4) asignación redundante de `nivel_detalle`.

## Cambios implementados

- `src/conversation/dialogue_manager.py`:
  - `_estadistica_carta`: solo convierte `k_carta` en estadística cuando el concepto termina en `(carta)` y está en la lista blanca (`Speed`, `Stamina`, `Power`, `Guts`, `Wit`, `Pal`). Para `k_stat` valida igualmente el valor.
  - `_continuidad_cartas`: solo conserva restricciones de la intención `cartas_recomendadas` cuando no cambia el personaje explícito.
  - `_filtros_cartas`: utiliza esa continuidad para heredar estadísticas, rareza y escenario; evita que un alias F2P se vuelva una rareza SR.
  - `_h_cartas_recomendadas`: calcula candidatos antes de confirmar preferencias y tema; una búsqueda sin resultados señala los filtros solicitados y mantiene el estado previo.
  - `responder`: almacena una copia previa de `slots`, `tema`, `preferencias` y `nivel_detalle`; la restaura si la recomendación no encuentra candidatos.
  - Se eliminó la asignación repetida de `nivel_detalle`; `ContextManager.set_tema` ya lo reinicia al cambiar el tema.
- `src/conversation/knowledge_base.py`: al detectar simultáneamente una Uma y una carta con el mismo nombre, se prioriza el personaje salvo que el usuario mencione explícitamente **carta** en singular o **support card**. «Recomiéndame cartas para Silence Suzuka» no selecciona su carta por accidente.
- `tests/test_etapa8_estado_filtros.py`: siete pruebas nuevas que reproducen los defectos y verifican el manejo de regresiones.

## Pruebas nuevas y criterios de aceptación

1. «Ármame un mazo para Oguri Cap» produce recomendaciones sin crear un filtro `stat=Mazo de soporte`. **Importante:** sigue siendo una lista, no un mazo optimizado; el armado por roles queda pendiente.
2. «Mejores cartas para Oguri Cap» tras «mazo» continúa sin contaminación.
3. Pasar de Gold Ship (larga, F2P, Stamina) a Silence Suzuka limpia los filtros heredados.
4. Continuar consultando cartas del mismo personaje conserva filtros válidos.
5. «Háblame de Silence Suzuka» no asigna ninguna carta; «carta de Silence Suzuka» sí.
6. Una búsqueda sin candidatos restaura tema, preferencias y entidades confirmadas, sin requerir reiniciar la sesión.
7. Únicamente las estadísticas existentes pueden utilizarse como filtro.

Pruebas ejecutadas (ejecutarlas desde la raíz con las dependencias instaladas):

```powershell
python tests/test_etapa8_estado_filtros.py
python tests/test_context.py
python tests/test_recommendations.py
python tests/test_confidence.py
python tests/test_api.py
python tests/test_integracion_frontend.py
python tests/run_conversation_tests.py --modelo v3
```

## Alcance y limitaciones

- No se alteraron `data/`, los modelos `.joblib`, el contrato HTTP ni el frontend de Streamlit.
- En esta etapa **no** se resuelven todavía seguimientos lingüísticos complejos, negaciones de SSR, `objetivos_stats` ni armado de mazos por roles.
- La detección de consultas explícitas sobre cartas homónimas utiliza palabras clave; se ampliará junto con las reglas de seguimiento.
- La reversión conserva el último estado válido de la sesión, pero el turno fallido continúa registrado en el historial para explicar qué sucedió.
- Las siete pruebas nuevas utilizan un predictor determinista para aislar la lógica de negocio; las pruebas conversacionales originales utilizan el SVM V3 real.
