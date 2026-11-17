"""Exporta DBC.xlsx (fuente de verdad editable) a los archivos que usa el chatbot.

Uso:  python scripts/export_from_xlsx.py [ruta/a/DBC.xlsx]

Genera en data/: characters.csv, knowledge.csv, cards.csv, cards_effects.csv, train.csv, test.csv, responses.json, intents.json  y valida los requisitos del 
proyecto (>=10 intenciones, >=20 ejemplos por intención, >=50 de prueba, sin duplicados ni fuga train/test, >=3 variantes de respuesta)."""

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
UMBRAL_CONFIANZA = 0.30


def norm(t):
    """Normaliza texto para detectar duplicados y fugas entre conjuntos."""
    t = unicodedata.normalize("NFKD", str(t).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def limpiar(df):
    """Elimina columnas y filas vacías y limpia espacios en los datos de una hoja."""
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]].copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.apply(lambda col: col.map(lambda v: v.strip() if isinstance(v, str) else v))
    return df[~(df == "").all(axis=1)].reset_index(drop=True)


def main(xlsx):
    """Exporta las hojas del libro, genera JSON y valida los datos requeridos."""
    hojas = {k: limpiar(v) for k, v in pd.read_excel(xlsx, sheet_name=None, dtype=str, keep_default_na=False).items()}
    out = RAIZ / "data"
    for hoja, archivo in [("Characters", "characters.csv"), ("Knowledge", "knowledge.csv"), ("Cards", "cards.csv"),
                          ("CardsEffect", "cards_effects.csv"), ("DataTrain", "train.csv"), ("DataTest", "test.csv")]:
        hojas[hoja].to_csv(out / archivo, index=False, encoding="utf-8")

    resp = {}
    r = hojas["Responses"].copy(); r["variante"] = r["variante"].astype(int)
    for clave, g in r.sort_values(["intencion", "variante"]).groupby("intencion", sort=False):
        resp[clave] = g["respuesta"].tolist()
    (out / "responses.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    intents = {"umbral_confianza": UMBRAL_CONFIANZA, "intenciones": hojas["Intents"].to_dict("records")}
    (out / "intents.json").write_text(json.dumps(intents, ensure_ascii=False, indent=2), encoding="utf-8")

    # Validaciones

    tr, te = hojas["DataTrain"], hojas["DataTest"]
    errores = []
    ids = set(hojas["Intents"]["intencion"])
    if len(ids) < 10: errores.append("menos de 10 intenciones")
    cuenta = tr["intencion"].value_counts()
    for i in ids:
        if cuenta.get(i, 0) < 20: errores.append(f"{i}: {cuenta.get(i, 0)} ejemplos (<20)")
        if len(resp.get(i, [])) < 3: errores.append(f"{i}: menos de 3 variantes de respuesta")
    if len(tr) < 200: errores.append("train < 200")
    if len(te) < 50: errores.append("test < 50")
    ntr, nte = tr["texto"].map(norm), te["texto"].map(norm)
    if ntr.duplicated().any(): errores.append("duplicados en train")
    if nte.duplicated().any(): errores.append("duplicados en test")
    if set(ntr) & set(nte): errores.append("fuga: textos en train y test")
    if set(tr["intencion"]) - ids or set(te["intencion"]) - ids: errores.append("etiquetas que no están en Intents")
    ce, ca = hojas["CardsEffect"], hojas["Cards"]
    if set(ce["card_id"]) - set(ca["card_id"]): errores.append("CardsEffect con card_id inexistente")
    print(f"intenciones={len(ids)} train={len(tr)} test={len(te)} cartas={len(ca)} personajes={len(hojas['Characters'])}")
    print("VALIDACIÓN OK" if not errores else "ERRORES:\n - " + "\n - ".join(errores))
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "data" / "source" / "DBC.xlsx"))
