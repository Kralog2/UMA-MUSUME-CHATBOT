
from src.preprocessing.text_preprocessor import crear_vectorizador

mensajes = [
    "¿Para qué sirve la velocidad?",
    "¿Cómo aumento mi velocidad?",
    "¿Qué cartas de soporte necesito?",
    "¿Cómo mejoro mis cartas de soporte?"
]

vectorizador = crear_vectorizador()

matriz = vectorizador.fit_transform(mensajes)

print("Palabras identificadas:")
print(vectorizador.get_feature_names_out())

print("\nDimensiones de la matriz:")
print(matriz.shape)

print("\nRepresentación numérica:")
print(matriz.toarray())
