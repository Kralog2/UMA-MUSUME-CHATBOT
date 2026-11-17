"""Inicia una conversación interactiva con el chatbot desde la terminal.

Permite seleccionar el modelo, enviar mensajes, reiniciar el diálogo y salir.
"""
from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor
from pathlib import Path
import argparse

ROOT=Path(__file__).resolve().parents[1]

def main():
    """Configura el modelo seleccionado y procesa los mensajes de la consola."""
    parser=argparse.ArgumentParser(description="Chatbot Uma Musume")
    parser.add_argument("--modelo", choices=["original", "reforzado"], default="original")
    args=parser.parse_args()
    ruta=ROOT/"artifacts"/("modelo_reforzado_etapa3.joblib" if args.modelo=="reforzado" else "mejor_modelo.joblib")
    dm=DialogueManager(construir_predictor(ruta), ROOT/"data/game")
    print("Asistente Uma Musume | salir: cerrar | /reiniciar: nueva conversación")
    while True:
        try:
            mensaje=input("Tú: ").strip()
        except (KeyboardInterrupt,EOFError):
            print("\nFin.")
            break
        if mensaje.lower()=="salir": break
        if mensaje.lower()=="/reiniciar":
            dm.reiniciar()
            print("Bot: conversación reiniciada.")
            continue
        r=dm.responder(mensaje)
        print(f"Bot: {r['respuesta']}   [{r['intencion']} / {r['confianza']:.2f} / {r['fuente']}]")

if __name__=="__main__":main()
