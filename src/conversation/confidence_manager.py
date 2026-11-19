"""Decide si aceptar, aclarar o rechazar una clasificación usando probabilidades V3.
No interpreta el contexto ni modifica el modelo; la decisión es consumida por el diálogo.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceManager:
    # Política seleccionada con predicciones fuera de partición (etapa 5.1).
    minimo: float = 0.45
    margen_minimo: float = 0.20
    minimo_aclaracion: float = 0.25

    def evaluar(self, candidatos):
        """Calcula la diferencia entre las dos primeras clases y devuelve una decisión."""
        (primera, p1), (_, p2) = candidatos[:2]
        margen = p1 - p2
        if p1 >= self.minimo and margen >= self.margen_minimo:
            accion = 'aceptar'
        elif p1 >= self.minimo_aclaracion:
            accion = 'aclarar'
        else:
            accion = 'reformular'
        return {'accion': accion, 'margen': margen, 'candidatos': [
            {'intencion': i, 'probabilidad': p} for i, p in candidatos[:3]]}
