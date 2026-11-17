"""Mantiene el historial y el estado temporal de una conversación.

Guarda lo necesario para entender preguntas de seguimiento: personaje, carta y escenario
activos, tema actual (intención + parámetros), nivel de detalle ya entregado, aclaración
pendiente y variantes de respuesta usadas (para no repetir)."""

from __future__ import annotations

from collections import deque
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
        """Inicializa el contexto y limita el historial al número de turnos indicado."""
        self.max_turnos = max_turnos
        self.reset()

    def reset(self) -> None:
        """Limpia el historial, los temas activos y el resto del estado conversacional."""
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

    def actualizar_slots(self, valores: Dict[str, Optional[str]]) -> None:
        """Actualiza los slots conocidos con los valores no vacíos proporcionados."""
        for s, v in valores.items():
            if s in SLOTS and v:
                self.slots[s] = v

    def set_tema(self, intencion: str, **params) -> None:
        """Registra el tema y sus parámetros; reinicia el detalle si el tema cambió."""
        nuevo = {"intent": intencion, **params}
        if nuevo != self.tema:
            self.nivel_detalle = 0  # tema distinto: se reinicia la profundidad
        self.tema = nuevo

    def pedir_aclaracion(self, intencion: str, slot: str) -> None:
        """Guarda la intención y el dato que falta para resolver una aclaración."""
        self.pendiente = {"intent": intencion, "slot": slot}

    def limpiar_pendiente(self) -> None:
        """Borra cualquier aclaración que estuviera pendiente."""
        self.pendiente = None

    def registrar_turno(self, turno: Turno) -> None:
        """Añade un turno al historial y actualiza la última intención registrada."""
        self.historial.append(turno)
        self.ultima_intencion = turno.intencion
        self.turnos += 1

    def snapshot(self) -> Dict[str, Any]:
        """Crea una copia resumida del contexto para incluirla en la respuesta."""
        return {"slots": dict(self.slots), "tema": self.tema, "nivel_detalle": self.nivel_detalle,
                "pendiente": self.pendiente, "ultima_intencion": self.ultima_intencion, "turnos": self.turnos}
