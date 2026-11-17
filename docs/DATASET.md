# Documentación de datos y diseño conversacional

Fuente: `data/source/DBC.xlsx`.  
Hojas → archivos:
+ Characters → characters.csv
+ Knowledge → knowledge.csv
+ Cards → cards.csv,
+ CardsEffect → cards_effects.csv
+ DataTrain → train.csv
+ DataTest → test.csv
+ Responses → responses.json
+ Intents → intents.json.

## Resumen (validado por scripts/export_from_xlsx.py)
- 17 intenciones (mín. 10). Entrenamiento: 366 ejemplos, 21–25 por intención (mín. 20). Prueba: 70 ejemplos (mín. 50).
- Sin duplicados (texto normalizado) ni textos repetidos entre train y test.
- Todas las intenciones tienen ≥3 variantes de respuesta; hay además respuestas internas (fallback, aclarar personaje, etc.).
- Base de datos: 32 personajes, 33 cartas de soporte (R/SR/SSR), 53 filas de efectos por límite (0LB/2LB/3LB/MLB), 40 filas de conocimiento.

## Intenciones
Ver `data/intents.json` (descripción, ejemplo, uso de contexto, acción del gestor y categorías de Knowledge).
No son clases del clasificador: **reinicio** (regla), **desconocido** (confianza < umbral) y las aclaraciones.

## Pendiente para el reporte (que debe completar el equipo)
- Procedencia de los ejemplos (manual / herramienta generativa revisada) y procedimiento de construcción.
- Fuente de los datos del juego (wiki, fecha de consulta) y de las notas de cartas (columna **note**).
