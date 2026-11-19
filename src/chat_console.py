"""Consola del chatbot completo: python -m src.chat_console"""
from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor
from pathlib import Path
import argparse

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description="Chatbot Uma Musume")
    parser.add_argument("--modelo", choices=["original", "reforzado", "v3"], default="original")
    args=parser.parse_args()
    ruta=ROOT/"artifacts"/{"original":"mejor_modelo.joblib","reforzado":"modelo_reforzado_etapa3.joblib","v3":"modelo_v3.joblib"}[args.modelo]
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
