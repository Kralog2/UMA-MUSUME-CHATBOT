"""Ejecuta y valida los casos conversacionales definidos en conversation_tests.json.

Comprueba intenciones, contenido de respuestas, contexto y fuente de respuesta.
"""

import json
import sys
import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.conversation.dialogue_manager import DialogueManager
from src.conversation.knowledge_base import normalizar
from src.models.predictor_adapter import construir_predictor


def main():
    """Corre todos los pasos de conversación y devuelve el número de fallos."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", choices=["original", "reforzado"], default="original")
    args = parser.parse_args()
    ruta = RAIZ / "artifacts" / ("modelo_reforzado_etapa3.joblib" if args.modelo == "reforzado" else "mejor_modelo.joblib")
    dm = DialogueManager(construir_predictor(ruta), RAIZ / "data" / "game", seed=0)
    casos = json.load(open(RAIZ / "tests" / "conversation_tests.json", encoding="utf-8"))
    fallos = pasos = 0
    for caso in casos:
        dm.reiniciar()
        print(f"\n== {caso['nombre']}")
        for paso in caso["pasos"]:
            r = dm.responder(paso["usuario"])
            resp, errores = normalizar(r["respuesta"]), []
            if r["intencion"] != paso["intencion"]:
                errores.append(f"intención {r['intencion']} != {paso['intencion']}")
            claves = [normalizar(c) for c in paso.get("contiene", [])]
            if claves and not (any(c in resp for c in claves) if paso.get("alguna") else all(c in resp for c in claves)):
                errores.append(f"falta contenido {paso['contiene']}")
            for c in paso.get("no_contiene", []):
                if normalizar(c) in resp:
                    errores.append(f"no debía contener '{c}'")
            for k, v in paso.get("slots", {}).items():
                if r["contexto"]["slots"].get(k) != v:
                    errores.append(f"slot {k}={r['contexto']['slots'].get(k)} != {v}")
            if "fuente" in paso and r["fuente"] != paso["fuente"]:
                errores.append(f"fuente {r['fuente']} != {paso['fuente']}")
            pasos += 1; fallos += bool(errores)
            print(f"  [{'OK ' if not errores else 'ERR'}] Tú: {paso['usuario']}\n Bot: {r['respuesta']}  ({r['intencion']}, {r['confianza']}, {r['fuente']})")
            for e in errores:
                print(f"        -> {e}")
    print(f"\nResultado: {pasos - fallos}/{pasos} pasos correctos" + ("  ✔ TODAS LAS PRUEBAS PASARON" if not fallos else ""))
    return fallos


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
