"""API HTTP del chatbot Uma Musume.

Ejecutar desde la raíz del proyecto:
    python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000

Cada sesión posee su propio DialogueManager (estado conversacional aislado).
El predictor entrenado se carga una sola vez y se comparte en memoria.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATHS = {
    "v3": ROOT / "artifacts" / "modelo_v3.joblib",
    "original": ROOT / "artifacts" / "mejor_modelo.joblib",
    "reforzado": ROOT / "artifacts" / "modelo_reforzado_etapa3.joblib",
}
MODEL_NAME = os.getenv("UMABOT_MODELO", "v3").strip().lower()
if MODEL_NAME not in MODEL_PATHS:
    raise ValueError("UMABOT_MODELO debe ser 'original', 'reforzado' o 'v3'")

# Configuración para una demostración local; no es un almacén persistente ni distribuido.
SESSION_TTL_SECONDS = 30 * 60
MAX_SESSIONS = 300
MAX_MESSAGE_CHARS = 2000


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mensaje: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: UUID
    respuesta: str
    intencion: str
    confianza: float
    entidades: dict[str, Any]
    fuente: str
    contexto: dict[str, Any]
    diagnostico_confianza: dict[str, Any] | None = None


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID


class ResetResponse(BaseModel):
    session_id: UUID
    mensaje: str


@dataclass
class Session:
    manager: DialogueManager
    last_active: float = field(default_factory=time.monotonic)
    lock: Any = field(default_factory=threading.RLock)


class SessionRegistry:
    def __init__(self, predictor):
        """Inicializa los componentes y el estado necesarios para operar."""
        self.predictor = predictor
        self.sessions: dict[UUID, Session] = {}
        self.lock = threading.RLock()

    def _remove_expired(self, now: float) -> None:
        # Solo se ejecuta cuando self.lock está tomado.
        """Elimina sesiones inactivas cuando sus bloqueos permiten hacerlo."""
        for sid, item in list(self.sessions.items()):
            if now - item.last_active > SESSION_TTL_SECONDS and item.lock.acquire(blocking=False):
                try:
                    if now - item.last_active > SESSION_TTL_SECONDS:
                        del self.sessions[sid]
                finally:
                    item.lock.release()

    def resolve(self, session_id: UUID | None) -> tuple[UUID, Session]:
        """Recupera una sesión válida o crea una nueva con contexto aislado."""
        with self.lock:
            now = time.monotonic()
            self._remove_expired(now)
            if session_id is not None:
                item = self.sessions.get(session_id)
                if item is None:
                    raise HTTPException(status_code=404, detail="Sesión inexistente o expirada; inicia un nuevo chat")
                return session_id, item
            if len(self.sessions) >= MAX_SESSIONS:
                raise HTTPException(status_code=503, detail="Límite de sesiones alcanzado; vuelve a intentar después")
            sid = uuid4()
            item = Session(DialogueManager(self.predictor, ROOT / "data" / "game"))
            self.sessions[sid] = item
            return sid, item

    def reply(self, session_id: UUID | None, mensaje: str) -> dict[str, Any]:
        """Procesa un mensaje bajo el bloqueo de su sesión."""
        sid, item = self.resolve(session_id)
        with item.lock:
            item.last_active = time.monotonic()
            result = item.manager.responder(mensaje)
            item.last_active = time.monotonic()
            return {"session_id": sid, **result}

    def reset(self, session_id: UUID) -> dict[str, Any]:
        """Reinicia el contexto de la sesión solicitada."""
        _, item = self.resolve(session_id)
        with item.lock:
            item.manager.reiniciar()
            item.last_active = time.monotonic()
        return {"session_id": session_id, "mensaje": "Contexto de conversación reiniciado"}


def build_app() -> FastAPI:
    """Construye FastAPI y configura sus rutas y CORS."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Carga el predictor al arrancar y libera el registro al apagar."""
        app.state.registry = SessionRegistry(construir_predictor(MODEL_PATHS[MODEL_NAME]))
        yield
        app.state.registry = None

    api = FastAPI(
        title="Uma Musume Chatbot API",
        description="API de clasificación y conversación del proyecto académico.",
        version="1.0.0",
        lifespan=lifespan,
    )
    # Por seguridad, el navegador solo permite los orígenes indicados.
    # Ejemplo: UMABOT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    origins = [x.strip() for x in os.getenv(
        "UMABOT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if x.strip()]
    api.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_credentials=False, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])

    @api.get("/api/health")
    def health():
        """Expone el estado del servicio y el modelo activo."""
        return {"estado": "ok", "modelo": MODEL_NAME, "version": "1.0.0"}

    @api.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, request: Request):
        """Valida el mensaje y devuelve la respuesta de la sesión."""
        if not body.mensaje.strip():
            raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío")
        return request.app.state.registry.reply(body.session_id, body.mensaje)

    @api.post("/api/reset", response_model=ResetResponse)
    def reset(body: ResetRequest, request: Request):
        """Reinicia el contexto de la sesión solicitada."""
        return request.app.state.registry.reset(body.session_id)

    return api


app = build_app()
