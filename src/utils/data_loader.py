
import pandas as pd


def cargar_dataset(ruta):
    """
    Carga un archivo CSV y verifica su estructura.
    """

    try:
        datos = pd.read_csv(ruta)

        # Comprobar que existan las columnas necesarias
        columnas_requeridas = ["texto", "intencion"]

        for columna in columnas_requeridas:
            if columna not in datos.columns:
                raise ValueError(
                    f"Falta la columna requerida: {columna}"
                )

        # Eliminar filas sin información
        datos = datos.dropna(
            subset=["texto", "intencion"]
        ).copy()

        # Convertir valores a texto y eliminar espacios
        datos["texto"] = datos["texto"].astype(str).str.strip()
        datos["intencion"] = (
            datos["intencion"].astype(str).str.strip()
        )

        # Eliminar mensajes vacíos
        datos = datos[
            (datos["texto"] != "") &
            (datos["intencion"] != "")
        ]

        return datos

    except FileNotFoundError:
        print(f"No se encontró el archivo: {ruta}")
        return None

    except Exception as error:
        print(f"Error al cargar el dataset: {error}")
        return None


def explorar_dataset(datos):
    """
    Muestra información general del dataset.
    """

    if datos is None:
        return

    print("\n========== INFORMACIÓN DEL DATASET ==========")

    print(f"Total de ejemplos: {len(datos)}")

    print(
        f"Total de intenciones: "
        f"{datos['intencion'].nunique()}"
    )

    print("\nEjemplos por intención:")

    print(
        datos["intencion"].value_counts().sort_index()
    )

    print("\nEjemplos del dataset:")

    print(datos.head())


if __name__ == "__main__":

    datos = cargar_dataset("data/raw/train.csv")

    explorar_dataset(datos)
