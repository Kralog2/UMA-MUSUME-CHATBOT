"""Consola del chatbot completo: python -m src.chat_console"""
from src.conversation.dialogue_manager import DialogueManager
from src.models.predictor_adapter import construir_predictor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    dm=DialogueManager(construir_predictor(), ROOT/"data/game")
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
