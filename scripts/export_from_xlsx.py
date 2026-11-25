"""Exporta la fuente Excel vigente y valida la semántica de disponibilidad F2P.

Uso:  python scripts/export_from_xlsx.py [ruta/a/DBC.xlsx]

Genera los CSV y JSON en data/game y data/raw; preserva la trazabilidad.
Etapa 10: verifica f2p=1/0/vacío sin inferir falsos y su fuente."""

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
UMBRAL_CONFIANZA = 0.30


def norm(t):
    """Normaliza texto para comprobar duplicados y coincidencias."""
    t = unicodedata.normalize("NFKD", str(t).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def limpiar(df):
    """Limpia columnas de Excel sin eliminar datos significativos."""
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed")]].copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.apply(lambda col: col.map(lambda v: v.strip() if isinstance(v, str) else v))
    return df[~(df == "").all(axis=1)].reset_index(drop=True)


def main(xlsx):
    """Valida y exporta la base de conocimiento y los datasets etiquetados."""
    hojas = {k: limpiar(v) for k, v in pd.read_excel(xlsx, sheet_name=None, dtype=str, keep_default_na=False).items()}
    out = RAIZ / "data" / "game"
    efecto = "CardsEffects" if "CardsEffects" in hojas else "CardsEffect"
    resp = {}
    r = hojas["Responses"].copy(); r["variante"] = r["variante"].astype(int)
    for clave, g in r.sort_values(["intencion", "variante"]).groupby("intencion", sort=False):
        resp[clave] = g["respuesta"].tolist()
    intents = {"umbral_confianza": UMBRAL_CONFIANZA, "intenciones": hojas["Intents"].to_dict("records")}

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
    if any(not norm(t) for t in list(tr.texto)+list(te.texto)): errores.append("textos vacíos")
    ntr, nte = tr["texto"].map(norm), te["texto"].map(norm)
    if ntr.duplicated().any(): errores.append("duplicados en train")
    if nte.duplicated().any(): errores.append("duplicados en test")
    if set(ntr) & set(nte): errores.append("fuga: textos en train y test")
    if set(tr["intencion"]) - ids or set(te["intencion"]) - ids: errores.append("etiquetas que no están en Intents")
    ce, ca = hojas[efecto], hojas["Cards"]
    if not {"f2p", "f2p_fuente"}.issubset(ca.columns):
        errores.append("Cards debe incluir f2p y f2p_fuente")
    else:
        invalidos = ca[~ca["f2p"].isin(("", "0", "1"))]
        if len(invalidos): errores.append("f2p solo admite 1, 0 o vacío (desconocido)")
        sin_fuente = ca[(ca["f2p"] == "1") & (ca["f2p_fuente"] == "")]
        if len(sin_fuente): errores.append("todas las cartas f2p=1 necesitan fuente")
    sr = hojas["Knowledge"]
    sr = sr[(sr["category"] == "rareza") & (sr["name"] == "SR")]
    if len(sr) and any(p in norm(sr.iloc[0]["synonym"]).split()
                       for p in ("f2p", "gratis", "gratuita")):
        errores.append("sinónimos SR contienen conceptos de gratuidad")
    if set(ce["card_id"]) - set(ca["card_id"]): errores.append("CardsEffect con card_id inexistente")
    print(f"intenciones={len(ids)} train={len(tr)} test={len(te)} cartas={len(ca)} personajes={len(hojas['Characters'])}")
    print("VALIDACIÓN OK" if not errores else "ERRORES:\n - " + "\n - ".join(errores))
    if errores:
        return 1
    for hoja, archivo in [("Characters", "characters.csv"), ("Knowledge", "knowledge.csv"), ("Cards", "cards.csv"), (efecto, "cards_effects.csv"), ("DataTrain", "train.csv"), ("DataTest", "test.csv")]:
        destino = RAIZ / "data" / "raw" if hoja in ("DataTrain", "DataTest") else out
        destino.mkdir(parents=True, exist_ok=True)
        hojas[hoja].to_csv(destino / archivo, index=False, encoding="utf-8")
    (out / "responses.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "intents.json").write_text(json.dumps(intents, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "data" / "source" / "DBCv4_etapa10.xlsx"))
