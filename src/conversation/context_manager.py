"""Administrador de contexto conversacional.

Guarda lo necesario para entender preguntas de seguimiento: personaje, carta y escenario
activos, tema actual (intención + parámetros), nivel de detalle ya entregado, aclaración
pendiente y variantes de respuesta usadas (para no repetir)."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

SLOTS = ("personaje", "card", "escenario")


@dataclass
class Turno:
    usuario: str
    intencion: str
    confianza: float
    respuesta: str
    entidades: Dict[str, str] = field(default_factory=dict)


class ContextManager:
    def __init__(self, max_turnos: int = 10):
        """Configura el tamaño del historial e inicializa el estado."""
        self.max_turnos = max_turnos
        self.reset()

    def reset(self) -> None:
        """Elimina TODO el contexto (reinicio de conversación)."""
        self.historial: Deque[Turno] = deque(maxlen=self.max_turnos)
        self.slots: Dict[str, Optional[str]] = {s: None for s in SLOTS}
        self.ultima_intencion: Optional[str] = None
        self.tema: Optional[Dict[str, Any]] = None     
        self.nivel_detalle: int = 0
        self.pendiente: Optional[Dict[str, str]] = None  
        self.aclaracion_previa: Optional[str] = None     
        self.desconocidos_seguidos: int = 0
        self.ultima_variante: Dict[str, int] = {}
        self.turnos: int = 0
        self.preferencias: Dict[str, Any] = {}
        self.pendiente_confianza: Optional[Dict[str, Any]] = None

    def actualizar_slots(self, valores: Dict[str, Optional[str]]) -> None:
        """Conserva las entidades reconocidas hasta que sean reemplazadas."""
        for s, v in valores.items():
            if s in SLOTS and v:
                self.slots[s] = v

    def set_tema(self, intencion: str, **params) -> None:
        """Actualiza el tema y reinicia la paginación si cambian sus parámetros."""
        nuevo = {"intent": intencion, **params}
        if nuevo != self.tema:
            self.nivel_detalle = 0  # tema distinto: se reinicia la profundidad
        self.tema = nuevo

    def pedir_aclaracion(self, intencion: str, slot: str) -> None:
        """Solicita una entidad necesaria para continuar."""
        self.pendiente = {"intent": intencion, "slot": slot}

    def limpiar_pendiente(self) -> None:
        """Cancela la aclaración de entidad."""
        self.pendiente = None

    def registrar_turno(self, turno: Turno) -> None:
        """Registra el turno y actualiza el contador."""
        self.historial.append(turno)
        self.ultima_intencion = turno.intencion
        self.turnos += 1

    def snapshot(self) -> Dict[str, Any]:
        """Devuelve una copia independiente del estado público de la sesión."""
        return deepcopy({"slots": dict(self.slots), "tema": self.tema, "nivel_detalle": self.nivel_detalle,
                "pendiente": self.pendiente, "ultima_intencion": self.ultima_intencion, "turnos": self.turnos,
                "preferencias": self.preferencias, "pendiente_confianza": self.pendiente_confianza})
