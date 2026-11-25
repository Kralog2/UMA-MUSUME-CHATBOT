# Etapa 10 — Datos estructurados y recomendaciones F2P

## Objetivo
Resolver los problemas 16 a 21 señalados por el equipo: clasificación F2P basada en texto libre, confusión F2P/SR, ordenamiento inadecuado, rareza como desempate, restricciones no transparentes y revisión de la exclusión de cartas del mismo personaje.

## Fuente y procedencia
- Base anterior conservada: `data/source/DBCv3.xlsx`.
- Nueva fuente activa: `data/source/DBCv4_etapa10.xlsx`, derivada de DBCv3.
- La hoja `Cards` incorpora `f2p` y `f2p_fuente`. `1` significa **evidencia positiva documentada en las notas de DBCv3**, `0` una negativa documentada y una celda vacía significa **desconocido**. No se han asignado valores `0` porque el catálogo no justifica ninguna negativa categórica.
- Se identificaron seis cartas con evidencia explícita en las notas existentes: Narita Brian SSR, Mejiro McQueen SSR, Daiwa Scarlet SR, Haru Urara SSR, Riko Kashimoto R y Aoi Kiryuin SR. `f2p_fuente` reproduce la nota correspondiente. Esto **no verifica** su disponibilidad actual en el juego.
- Se quitaron de los sinónimos `rareza=SR` las referencias `f2p`, `free to play`, `gratis`, `gratuita`, `económica` y `sin ssr`, pues no representan rareza.
- Los ejemplos de entrenamiento/prueba y el modelo V3 NO se modificaron ni reentrenaron.

## Algoritmo y decisiones
1. `KnowledgeBase` carga el estado y fuente por carta.
2. `ordenar()` mantiene filtros explícitos de personaje, escenario, estadística y rareza; `sin_ssr` excluye SSR aunque se pidan opciones F2P.
3. Sin preferencia F2P: ordena por compatibilidad, bonos, rareza (SSR, SR, R) y `card_id`.
4. Con preferencia F2P: coloca primero las cartas con `f2p=1`, después aplica compatibilidad, bonos y rareza, y finalmente añade cartas de disponibilidad desconocida. La preferencia F2P **no es un filtro obligatorio** y no convierte F2P en SR.
5. La respuesta indica el número de candidatas con evidencia positiva, explicita los filtros y avisa que no se conoce el inventario del usuario.
6. Si no hay resultados, enumera los filtros aplicados y no los relaja automáticamente. Las consultas fallidas no confirman un tema inválido.

## Consideraciones
- La preferencia F2P prioriza accesibilidad documentada incluso cuando la carta es menos compatible; es una decisión de producto que se deberá validar con usuarios. Los casos sin evidencia permanecen disponibles como alternativa.
- **No se eliminó** la exclusión de la carta del mismo personaje que se entrena. El equipo pidió verificar si es una regla del juego; hasta contar con una fuente contrastada, se conserva el comportamiento anterior. Su comprobación se mantiene como tarea pendiente.
- No se implementó un armador de mazos por roles ni un inventario; corresponden a la Etapa 11.
- El campo `f2p` no significa precio, propiedad ni disponibilidad actual, únicamente respaldo textual en DBCv3.

## Archivos
### Nuevos
- `data/source/DBCv4_etapa10.xlsx`: fuente editable con dos columnas en `Cards` y sinónimos corregidos.
- `tests/test_etapa10_f2p.py`: diez pruebas de estructura, compatibilidad, F2P, rareza y exportación.
- `docs/ETAPA_10_DATOS_F2P.md`: documentación técnica.
- `data/processed/etapa10/pruebas.txt`: evidencia de ejecución.

### Modificados
- `data/game/cards.csv`, `data/game/knowledge.csv`: exportados desde el nuevo Excel.
- `src/conversation/card_recommender.py`: prioridad F2P, desempate por rareza y explicación de evidencia.
- `src/conversation/knowledge_base.py`: aclaración de carga y docstrings.
- `src/conversation/dialogue_manager.py`: mensajes de filtros y nueva política F2P.
- `scripts/export_from_xlsx.py`: valida datos estructurados y usa la fuente v4 de esta etapa por defecto.
- `tests/test_recommendations.py`: actualiza una expectativa histórica basada en notas libres al contrato estructurado actual.
- `README.md`, `docs/VERSION_4_0_PLAN.md`: avance y ejecución.

## Pruebas
Desde la raíz:

```powershell
python scripts/export_from_xlsx.py
python tests/test_etapa10_f2p.py
python -m unittest discover -s tests -p "test_*.py"
python tests/run_conversation_tests.py --modelo v3
python tests/test_api.py
```

Las pruebas de esta etapa evalúan el funcionamiento y regresiones. No demuestran que la disponibilidad F2P declarada en el Excel siga vigente en la versión actual del juego.
