
import joblib

RUTA_MODELO = "artifacts/mejor_modelo.joblib"


def cargar_modelo():
    try:
        modelo = joblib.load(RUTA_MODELO)
        print("Modelo cargado correctamente.")
        return modelo

    except FileNotFoundError:
        print("No se encontró el modelo.")
        print("Primero debes ejecutar: python -m src.models.train")
        return None


def predecir_intencion(modelo, texto):
    prediccion = modelo.predict([texto])
    return prediccion[0]


def iniciar_chat():
    modelo = cargar_modelo()

    if modelo is None:
        return

    print("\n===================================")
    print("   UMA MUSUME - PRUEBA DE NLP")
    print("===================================")
    print("Escribe una pregunta sobre el juego.")
    print("Escribe 'salir' para terminar.\n")

    while True:

        mensaje = input("Usuario: ").strip()

        if mensaje.lower() == "salir":
            print("Finalizando prueba...")
            break

        if not mensaje:
            print("Escribe una pregunta válida.\n")
            continue

        intencion = predecir_intencion(modelo, mensaje)

        print(f"Intención detectada: {intencion}\n")


if __name__ == "__main__":
    iniciar_chat()
