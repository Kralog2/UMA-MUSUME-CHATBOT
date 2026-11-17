# Chatbot Uma Musume — integración NLP + conversación

Integración del gestor de diálogo del equipo con el clasificador TF-IDF + SVM calibrado.

## Python 3.11 / Windows (PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.models.train
python -m src.chat_console
```

Si ya existe el modelo en `artifacts/mejor_modelo.joblib`, omite el entrenamiento.
Ejecutar desde la raíz del repositorio. Las dependencias pueden instalarse en un entorno virtual.

## Prueba de integración
```powershell
python tests/run_conversation_tests.py
```
Este test utiliza **el clasificador SVM real**, no el provisional. Sus resultados pueden diferir de los 34/34 del compañero.

## Estructura
- `src/models/train.py`: validación cruzada del SVM y calibración interna, guarda el modelo.
- `src/models/predictor_adapter.py`: API `(intencion, confianza)` compatible con DialogueManager.
- `src/conversation/`: gestor, contexto y base de conocimientos originales del compañero.
- `data/game/`: bases de conocimiento y plantillas de respuesta.
- `data/raw/`: dataset de entrenamiento 425 y test 136 usados en nuestra parte.
- `data/legacy/`: archivos train/test originales del compañero, preservados para trazabilidad.
- `data/source/DBC.xlsx`: Excel de origen de la rama del compañero.
- `data/processed/`: métricas, errores y confusión de integración.

## Consideraciones
- El conjunto test 136 ya había sido usado para evaluar el modelo anterior; la nueva medición **no es una prueba final virgen**.
- El modelo calibrado no garantiza rechazo correcto de mensajes ajenos al juego; hay que probar ese comportamiento en casos de conversación reales.
- El umbral de confianza del gestor proviene de `data/game/intents.json`. Debe ajustarse con validación, no usando test repetidamente.
- `joblib.load` solo debe abrir modelos producidos por nuestro equipo en un entorno confiable.
- Antes de conectar el frontend es necesario conservar un `DialogueManager` por sesión de usuario (no un único contexto compartido).
- No se ha modificado la lógica del gestor; únicamente imports y rutas de los datos.

## Resultados medidos en esta integración
- **34/34** turnos de pruebas conversacionales originales correctos usando el nuevo SVM calibrado.
- Sobre los 136 ejemplos del conjunto ya utilizado previamente: **accuracy 0.8971**, **macro F1 0.8961**.
- Validación cruzada del SVM *sin calibrar* sobre los 425 datos de entrenamiento: **macro F1 0.6975** (cifra distinta y no directamente comparable con el test).
- Ejemplos manuales: "¿Qué son las support cards?" → `cartas_soporte`; "¿Cómo se hace arroz blanco?" → `desconocido` mediante umbral; "¿Quién descubrió América?" → `fuera_dominio`.
- Estas observaciones **no constituyen una validación independiente de generalización**; hacen falta nuevos ejemplos de evaluación separados de entrenamiento/selección de umbrales.

## Próxima etapa
1. Analizar errores/near-duplicados y evaluar frases nuevas sin tocar test antiguo.
2. Afinar el rechazo `fuera_dominio` frente a `desconocido` con validación.
3. Crear API por sesión para frontend y tests de integración HTTP.
4. Completar notebook de comparación de dos clasificadores y documentación de procedencia.
