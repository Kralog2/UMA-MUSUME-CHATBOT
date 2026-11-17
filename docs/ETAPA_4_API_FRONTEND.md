# Etapa 4 — API HTTP para frontend

Fecha: 17 de noviembre de 2026.

## Objetivo

Ofrecer por HTTP el gestor conversacional y el modelo SVM calibrado construido en las etapas anteriores, conservando **un contexto diferente por sesión** y una única copia del clasificador en memoria.

## Archivos nuevos o modificados

| Acción | Ruta | Descripción |
|---|---|---|
| Nuevo | `src/api/__init__.py` | Paquete de API |
| Nuevo | `src/api/app.py` | Aplicación FastAPI; endpoint, almacenamiento temporal de sesiones, CORS y validaciones |
| Nuevo | `tests/test_api.py` | Pruebas de salud, sesiones independientes, reinicio, validación de entrada, CORS |
| Nuevo | `docs/ETAPA_4_API_FRONTEND.md` | Esta guía y el contrato HTTP |
| Modificado | `requirements.txt` | Agrega FastAPI, Uvicorn y HTTPX para pruebas |
| Modificado | `README.md` | Cómo arrancar y probar la API |

No se tocaron `DialogueManager`, `ContextManager`, la base de conocimiento, el entrenamiento, los datasets ni los artefactos de modelos.

## Instalar y ejecutar (Windows, VS Code/PowerShell)

Desde la carpeta que contiene `src/`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

Documentación interactiva: http://127.0.0.1:8000/docs

Pruebas HTTP: `python tests/test_api.py`

Pruebas de conversación: `python tests/run_conversation_tests.py --modelo reforzado`

## Contrato HTTP

### GET `/api/health`

Respuesta 200:

```json
{"estado":"ok","modelo":"reforzado","version":"1.0.0"}
```

### POST `/api/chat`

Content-Type: `application/json`.

**Primer mensaje** (omitir `session_id`):

```json
{"mensaje":"Háblame de Gold Ship"}
```

Respuesta 200 con esta forma (la intención, confianza, respuesta y valores de contexto reales dependen del contenido):

```json
{
  "session_id": "uuid-generado-por-el-servidor",
  "respuesta": "texto generado por el gestor de diálogo",
  "intencion": "info_personaje",
  "confianza": 0.85,
  "entidades": {},
  "fuente": "clasificador",
  "contexto": {"slots": {"personaje": null,"card": null,"escenario": null},"tema": null,"nivel_detalle": 0,"pendiente": null,"ultima_intencion": null,"turnos": 1}
}
```

**Siguiente mensaje**: reutiliza el `session_id` exacto del primer resultado.

```json
{"session_id":"UUID_RECIBIDO","mensaje":"¿Y sus aptitudes?"}
```

### POST `/api/reset`

```json
{"session_id":"UUID_RECIBIDO"}
```

Respuesta 200:

```json
{"session_id":"UUID_RECIBIDO","mensaje":"Contexto de conversación reiniciado"}
```

## Ejemplo de integración con Next.js o JavaScript

Archivo sugerido del frontend: `lib/umabot.ts`:

```typescript
const API_URL = process.env.NEXT_PUBLIC_UMABOT_API_URL ?? "http://127.0.0.1:8000";

export type ChatReply = {
  session_id: string;
  respuesta: string;
  intencion: string;
  confianza: number;
  entidades: Record<string, unknown>;
  fuente: string;
  contexto: Record<string, unknown>;
};

export async function enviarMensaje(mensaje: string, sessionId: string | null): Promise<ChatReply> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensaje, ...(sessionId ? { session_id: sessionId } : {}) }),
  });
  if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
  return response.json() as Promise<ChatReply>;
}

export async function reiniciarChat(sessionId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
}
```

En `.env.local` del frontend:

```
NEXT_PUBLIC_UMABOT_API_URL=http://127.0.0.1:8000
```

En el componente React guardar `session_id` en estado y actualizarlo tras cada envío. Para **nuevo chat**, llamar a `/api/reset` y limpiar las burbujas locales. Si se recibe un 404 de sesión expirada, limpiar el ID y permitir crear otra conversación con una nueva solicitud.

## Configuración

- `UMABOT_MODELO=reforzado` (predeterminado) u `original`, variable de entorno definida antes de arrancar el servidor.
- `UMABOT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000` (predeterminado). Separar orígenes por coma.
- La API acepta mensajes de hasta 2,000 caracteres; rechaza mensajes en blanco.
- Sesiones en memoria del proceso: 30 min de inactividad, máximo 300 sesiones activas.
- `session_id` es UUID aleatorio. Es una capacidad de acceso, **no una autenticación de usuario**; no publicar datos privados en el contexto.

## Límites de la entrega

Diseñado para **demostración académica local**. El servidor conserva las sesiones solo en RAM, de modo que reiniciarlo borra los contextos. Utilizar **un solo worker** de Uvicorn: con varios procesos las sesiones no se comparten. `--reload` también reinicia la memoria cuando se modifica un archivo. El endpoint no tiene inicio de sesión, control de abuso distribuido ni base de datos de sesiones; antes de exponerlo públicamente se necesitarían HTTPS, límites por cliente, autenticación y un almacén compartido (por ejemplo, Redis). CORS **no sustituye autenticación**. El frontend debe usar la URL de backend alcanzable desde el navegador, no `localhost` si ambos se ejecutan en máquinas diferentes.

No se reentrenó el clasificador ni se empleó el conjunto de evaluación independiente para ajustar el modelo en esta etapa.
