# Etapa 5.3 — Contexto conversacional avanzado

## Objetivo
Resolver continuaciones breves, conservar filtros durante recomendaciones y permitir que el usuario confirme una clasificación ambigua sin repetir toda su pregunta. Se conserva DBCv3, el modelo SVM y la política de confianza de la etapa 5.2.

## Cambios
- `src/conversation/context_resolver.py`: reglas lingüísticas acotadas para seguimientos, preferencias explícitas y selección de opciones. F2P no equivale a SR. Las expresiones sin SSR se almacenan de manera independiente.
- `src/conversation/context_manager.py`: añade `preferencias` y `pendiente_confianza`; devuelve copias del estado y limpia ambos campos al reiniciar.
- `src/conversation/dialogue_manager.py`: integra el resolutor; almacena las entidades y probabilidades originales durante una aclaración; permite elegir 1 o 2, o cancelar mediante una pregunta nueva. Conserva filtros de estadística y rareza al cambiar escenario. La paginación respeta la exclusión explícita de SSR.
- `tests/test_context.py`: seis pruebas de integración; utiliza el modelo real y predictores controlados para forzar la ambigüedad. No es una evaluación independiente de generalización.

## Política de resolución
Primero reinicio; después selección de intención pendiente, aclaración de entidad y reglas de seguimiento. Solo después se consulta el clasificador y su política de confianza. Una selección explícita recupera las entidades de la pregunta original. Una pregunta nueva cancela la anterior. Un sí/no aislado no selecciona una opción. Se evita modificar las entidades activas con una predicción no aceptada. Los valores de confianza de las reglas (1.0) son convenciones históricas del proyecto y no probabilidades estimadas por el SVM; en la selección de opciones se conserva la puntuación original de la alternativa confirmada.

## API
Los endpoints y el esquema HTTP no cambian. Dentro de `contexto` se añaden `preferencias` y `pendiente_confianza`. Este último contiene opciones, probabilidades, entidades y texto original, o null. `fuente=aclaracion_confianza` identifica una elección explícita. El frontend conserva su `session_id`. Las sesiones siguen siendo temporales y se aíslan entre sí.

## Limitaciones
Las reglas no resuelven todas las paráfrasis, pronombres o cambios de tema. No se desarrolla todavía un recomendador personalizado por personaje/distancia/estilo/pista; se guardan las preferencias y se advierte la limitación en la respuesta. F2P no permite deducir el inventario del usuario: el catálogo no identifica cartas realmente gratuitas. Sin SSR sí excluye las cartas SSR de las recomendaciones. Las preferencias se conservan dentro del tema de recomendaciones; un cambio de tema aceptado las limpia, salvo saludos, consultas fuera de dominio, desconocidas y solicitudes de ampliación. Las entidades activas del proyecto pueden seguir disponibles para referencias posteriores. No se ajustan los umbrales ni se vuelve a entrenar el modelo. No hay persistencia tras reiniciar el servidor.

## Ejecución
```powershell
python -m src.chat_console --modelo v3
python tests/test_context.py
python tests/test_confidence.py
python tests/run_conversation_tests.py --modelo v3
$env:UMABOT_MODELO = "v3"
python tests/test_api.py
```
