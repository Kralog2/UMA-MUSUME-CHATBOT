"""Ejecuta una consola interactiva para predecir intenciones con el modelo."""

from src.models.predictor_adapter import construir_predictor

if __name__ == "__main__":
    p=construir_predictor()
    print("Predicción de intenciones (escribe salir para terminar)")
    while True:
        texto=input("Tú: ").strip()
        if texto.lower()=="salir": break
        if texto:
            intencion, confianza=p(texto)
            print(f"{intencion} ({confianza:.3f})")
