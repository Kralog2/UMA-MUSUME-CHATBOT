# Etapa 9 — Seguimientos, negaciones, rarezas y sustituciones

## Objetivo

Corregir los defectos **5 a 9** del listado del equipo, sin reentrenar el clasificador ni alterar los datos de DBCv3. Esta etapa añade un tratamiento determinista y trazable para continuaciones de conversación con cartas de soporte.

## Componentes y cambios

| Archivo | Cambio |
| --- | --- |
| `src/conversation/context_resolver.py` | Detección de continuaciones breves que modifican escenario/rareza, interpretación separada de negaciones completas o parciales y solicitudes de sustitutos. |
| `src/conversation/dialogue_manager.py` | Priorización contextual de sustituciones, petición de aclaración ante inventario parcial y regla para «Háblame de PERSONAJE» como pregunta nueva. |
| `tests/test_etapa9_seguimientos.py` | Diez pruebas de regresión reproducibles. |
| `README.md`, `docs/VERSION_4_0_PLAN.md` | Referencias y avance de etapas. |

Se mantuvieron encabezados y docstrings en español para el código Python editado y nuevo.

## Defectos atendidos

1. **Verbos de solicitud nueva:** «Háblame de Gold Ship» deja de clasificarse como una mera continuación de cartas. Se retiraron «hablame», «cuentame» y «dime» del vocabulario auxiliar y se definió una regla para consultas explícitas de ficha de personaje.
2. **Continuaciones de escenario o rareza:** mensajes breves como «¿Y si la quiero entrenar en la URA final?» y «y en cuanto a SR?» se interpretan como cambios de filtros en una conversación activa sobre cartas; el personaje se conserva.
3. **Negaciones no equivalentes:** «no tengo ninguna SSR» activa `sin_ssr`; «no tengo todas las SSR» **no** activa exclusión global ni guarda una rareza artificial y solicita información de inventario.
4. **Menciones de SR y SSR en una frase:** la extracción de rareza no depende de la primera coincidencia; las solicitudes de sustitutos SR no se convierten en una recomendación SSR.
5. **Alternativas de cartas:** la nueva acción conversacional `sustituciones_cartas` presenta hasta cuatro parejas ilustrativas SSR→SR del **mismo rol de estadística** (Speed, Stamina, Power, etc.) y considera las restricciones existentes. Este identificador es una acción del gestor, **no una nueva intención del clasificador**.

## Alcance técnico

- Se conserva la intención `cartas_recomendadas` como tema mientras el usuario aclara el inventario o solicita sustitutos.
- Las parejas se basan en los metadatos disponibles del catálogo y **no** representan equivalencias exactas de efectos o habilidades.
- No se almacena ni se inventa inventario del usuario. En particular, «no tengo todas» no revela cuáles sí posee.
- La solución de «¿y para el otro escenario?» continúa utilizando la regla contextual anterior.
- No se modificaron el predictor entrenado, los umbrales de confianza, el esquema de la API ni el frontend.

## Ejemplo de prueba

1. «Recomiéndame cartas para Gold Ship» → `cartas_recomendadas`.
2. «¿Y si la quiero entrenar en la URA final?» → conserva Gold Ship, escenario `ura_finale`.
3. «y en cuanto a sr?» → conserva escenario, rareza `SR`.
4. «si no tengo todas las cartas ssr» → `aclaracion_inventario`, conserva tema y preferencias sin inventar inventario.
5. «si no tengo las ssr por cuales las cambio» → `sustituciones_cartas`, muestra parejas orientativas SSR→SR.
6. «Háblame de Gold Ship» → nueva intención `info_personaje`.

## Ejecución

```powershell
python tests/test_etapa9_seguimientos.py
python -m unittest discover -s tests -p 'test_*.py'
python tests/run_conversation_tests.py --modelo v3
python tests/test_api.py
```

## Evidencias de la ejecución

- Pruebas nuevas: **10/10**.
- Descubrimiento automático de pruebas: **40/40**, incluye las 10 nuevas.
- Conversaciones originales: **34/34 turnos**.
- Pruebas API existentes: **4/4 grupos**.
- Conversación ilustrativa adicional: verificada con `artifacts/modelo_v3.joblib` real.

Estos resultados son pruebas de regresión, no una nueva evaluación independiente de precisión NLP o calidad de sustituciones.

## Limitaciones y siguientes etapas

- La Etapa 10 estructurará la condición F2P y la disponibilidad real documentada de cartas.
- La Etapa 11 desarrollará la composición de mazos por roles y los objetivos de estadísticas.
- La Etapa 12 revisará la robustez del SVM ante frases largas y errores ortográficos.
- Aún no existen niveles o inventario de cartas proporcionados por cada jugador; para recomendaciones personalizadas de sustitución deben solicitarse.
