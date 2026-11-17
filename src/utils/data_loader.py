"""Carga y valida datasets CSV con las columnas texto e intencion requeridas."""
from pathlib import Path
import pandas as pd


def cargar_dataset(ruta):
    """Lee un CSV, valida sus columnas y devuelve filas limpias y no vacías."""
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    faltantes = {"texto", "intencion"} - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en {ruta}: {sorted(faltantes)}")
    df = df[["texto", "intencion"]].dropna().copy()
    for col in ("texto", "intencion"):
        df[col] = df[col].astype(str).str.strip()
    df = df[(df["texto"] != "") & (df["intencion"] != "")]
    if df.empty:
        raise ValueError(f"Dataset vacío: {ruta}")
    return df.reset_index(drop=True)
