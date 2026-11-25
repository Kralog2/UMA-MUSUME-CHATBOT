# UMA MUSUME ChatBot v4.0 — plan incremental

## Estado actual: etapas 7–10 completadas
- Se integró el frontend Streamlit del equipo en `frontend/app_frontend.py`.
- Se conservó el avatar incrustado y se incluyó `frontend/avatar.png` como recurso separado.
- Se agregó `frontend/requirements.txt` sin alterar las dependencias del backend.
- Consola y API arrancan con el modelo `v3` si no se especifica otro; se conservan opciones históricas.
- Se agregaron pruebas de contrato `tests/test_integracion_frontend.py`.

**La Etapa 8 corrige los defectos 1–4; la 9 aborda los defectos 5–9 y la 10 atiende los defectos 16–19 y 21.** El supuesto de exclusión de cartas del propio personaje (20) queda pendiente de verificación. Las etapas 11–13 están pendientes. Consulta [`ETAPA_10_DATOS_F2P.md`](ETAPA_10_DATOS_F2P.md).

## Hoja de ruta
| Etapa | Objetivo | Problemas |
| --- | --- | --- |
| 7 | Integrar Streamlit, unificar modelo y establecer pruebas de contrato | 22, 23 y base para 24 |
| 8 | Corregir filtros, contaminación de entidades y estado por personaje | 1, 2, 3, 4 |
| 9 | Seguimientos, rarezas, negación y sustituciones | 5, 6, 7, 8, 9 |
| 10 | Revisar datos de cartas y recomendador de F2P | 16, 17, 18, 19, 20, 21 |
| 11 | Armado real de mazos por roles y objetivos de stats | 10, 14, 15 |
| 12 | Mejorar NLP y confianza con pruebas fuera de muestra | 11, 12, 13 |
| 13 | Evaluación de regresión de extremo a extremo y cierre v4.0 | 24 y cobertura de todos |

## Ejecución local (dos terminales)
1. Instalar el backend: `python -m pip install -r requirements.txt`.
2. Instalar frontend: `python -m pip install -r frontend/requirements.txt`.
3. Terminal 1: `python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000`.
4. Terminal 2: `python -m streamlit run frontend/app_frontend.py`.
5. Verificar: abrir la dirección que muestre Streamlit (normalmente `http://localhost:8501`) y comprobar `/api/health` en puerto 8000.

En una máquina distinta, el `API_URL` de `frontend/app_frontend.py` debe apuntar al backend correcto. `127.0.0.1` solo funciona si ambos procesos se ejecutan en el mismo equipo. No expongas el backend sin autenticación y medidas de seguridad adicionales.

## Verificación
- `python -m unittest discover -s tests -p 'test_integracion_frontend.py'`
- `python tests/test_api.py`
- `python tests/run_conversation_tests.py --modelo v3`

La interfaz original utiliza selectores CSS de Streamlit que podrían requerir ajuste después de actualizar esa biblioteca. No se verificó el renderizado visual en navegador en esta integración inicial.
