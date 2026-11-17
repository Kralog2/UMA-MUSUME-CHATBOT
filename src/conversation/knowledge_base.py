"""Carga y consulta el conocimiento del juego y extrae entidades de mensajes.

Lee personajes, cartas, efectos y conocimiento desde los CSV exportados de
DBC.xlsx; también normaliza texto y construye patrones para reconocer nombres.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

ORDEN_APT = "SABCDEFG"  
ORDEN_RAREZA = {"SSR": 0, "SR": 1, "R": 2}
ESCENARIOS = {"ura_finale": "URA Finale", "unity_cup": "Unity Cup", "both": "ambos escenarios"}
CATEGORIAS_APT = {
    "pista": [("turf", "Turf (pasto)"), ("dirt", "Dirt (tierra)")],
    "distancia": [("sprint", "Sprint"), ("mile", "Mile"), ("medium", "Media"), ("long", "Larga")],
    "estilo": [("front", "Front Runner"), ("pace", "Pace Chaser"), ("late", "Late Surger"), ("end", "End Closer")],
}

_BLOQUEO = {"super", "smart", "grass", "black", "nature", "special", "silence", "wonder",
            "sunday", "marvelous", "motion"}


def normalizar(texto: str) -> str:
    """Convierte texto a minúsculas sin acentos ni puntuación y normaliza espacios."""
    t = unicodedata.normalize("NFKD", str(texto).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", t)).strip()


def _slug(t: str) -> str:
    """Crea una clave normalizada para buscar nombres de personajes."""
    return normalizar(t).replace(" ", "_")


def _alias_nombres(nombres: Dict[str, str]) -> Dict[str, set]:
    """nombre completo + tokens (>=5 letras) que identifican a una sola entrada."""
    toks: Dict[str, set] = {}
    for clave, nombre in nombres.items():
        for tk in normalizar(nombre).split():
            toks.setdefault(tk, set()).add(clave)
    res = {}
    for clave, nombre in nombres.items():
        a = {normalizar(nombre)}
        a |= {tk for tk in normalizar(nombre).split()
              if len(tk) >= 5 and tk not in _BLOQUEO and toks[tk] == {clave}}
        res[clave] = a
    return res


class KnowledgeBase:
    def __init__(self, directorio: Union[str, Path]):
        """Carga los CSV del directorio y prepara índices y patrones de búsqueda."""
        d = Path(directorio)
        leer = lambda n: pd.read_csv(d / n, dtype=str, keep_default_na=False).to_dict("records")
        self.personajes: Dict[str, dict] = {_slug(r["name"]): r for r in leer("characters.csv")}
        self.cartas: Dict[str, dict] = {r["card_id"]: r for r in leer("cards.csv")}
        self.efectos: Dict[str, Dict[str, dict]] = {}
        for r in leer("cards_effects.csv"):
            self.efectos.setdefault(r["card_id"], {})[r["limit_break"]] = r
        self.conocimiento: Dict[str, Dict[str, dict]] = {}
        for r in leer("knowledge.csv"):
            self.conocimiento.setdefault(r["category"], {})[r["name"]] = r
        self._patrones: List[Tuple[str, str, re.Pattern, str]] = []
        self._grupos_carta: Dict[str, List[str]] = {}
        self._construir_patrones()

    # Patrones

    def _add(self, clave, valor, alias):
        """Compila y registra un alias para la categoría y el valor indicados."""
        a = normalizar(alias)
        if a:
            palabras = [re.escape(w) + ("(?:e?s)?" if len(w) >= 4 else "") for w in a.split()]
            self._patrones.append((clave, valor, re.compile(r"\b" + " ".join(palabras) + r"\b"), a))

    def _construir_patrones(self):
        """Genera patrones para el conocimiento, personajes y cartas cargados."""
        for cat, filas in self.conocimiento.items():
            for nombre, f in filas.items():
                alias = [s for s in f["synonym"].split("|")]
                if cat not in ("habilidad", "carta", "rareza"):
                    alias.append(nombre)
                for a in alias:
                    self._add("k_" + cat, nombre, a)
        for clave, aliases in _alias_nombres({k: v["name"] for k, v in self.personajes.items()}).items():
            for a in aliases:
                self._add("personaje", clave, a)
        cortos: Dict[str, str] = {}
        for cid, c in self.cartas.items():
            corto = c["card"].split(" (")[0]
            self._grupos_carta.setdefault(corto, []).append(cid)
            cortos[corto] = corto
        for corto, aliases in _alias_nombres(cortos).items():
            for a in aliases:
                self._add("card", corto, a)

    # Entidades

    def extraer_entidades(self, texto: str) -> Dict[str, str]:
        """Detecta las entidades mencionadas y resuelve las cartas por rareza."""
        norm = normalizar(texto)
        mejor: Dict[str, tuple] = {}
        for clave, valor, rx, alias in self._patrones:
            m = rx.search(norm)
            if m:
                cand = (m.start(), -len(alias), valor)
                if clave not in mejor or cand[:2] < mejor[clave][:2]:
                    mejor[clave] = cand
        ent = {c: v[2] for c, v in mejor.items()}
        if "card" in ent:
            ent["card"] = self._resolver_carta(ent["card"], ent.get("k_rareza"))
        return ent

    def quitar_entidades(self, texto: str) -> str:
        """Retira del texto los alias reconocidos y devuelve el contenido restante."""
        norm = normalizar(texto)
        for _, _, rx, _ in sorted(self._patrones, key=lambda p: -len(p[3])):  # alias largos primero
            norm = rx.sub(" ", norm)
        return re.sub(r"\s+", " ", norm).strip()

    def _resolver_carta(self, corto: str, rareza: Optional[str]) -> str:
        """Elige la carta del grupo solicitado, priorizando la rareza indicada."""
        ids = sorted(self._grupos_carta[corto], key=lambda i: ORDEN_RAREZA.get(self.cartas[i]["rarity"], 9))
        for i in ids:
            if rareza and self.cartas[i]["rarity"] == rareza:
                return i
        return ids[0]

    # Conocimiento

    def fila(self, categoria: str, nombre: str) -> Optional[dict]:
        """Devuelve el registro de conocimiento de una categoría y nombre."""
        return self.conocimiento.get(categoria, {}).get(nombre)

    def filas(self, categoria: str) -> List[dict]:
        """Devuelve todos los registros disponibles para una categoría."""
        return list(self.conocimiento.get(categoria, {}).values())

    # Personajes

    def nombre_personaje(self, clave: str) -> str:
        """Obtiene el nombre visible del personaje identificado por su clave."""
        return self.personajes[clave]["name"]

    def aptitudes(self, clave: str, categoria: str, letras: str = "SA") -> List[str]:
        """Lista las opciones de la categoría cuya aptitud coincide con las letras."""
        p = self.personajes[clave]
        return [etq for col, etq in CATEGORIAS_APT[categoria] if p[col] in letras]

    def mejor_aptitud(self, clave: str, categoria: str) -> Tuple[str, List[str]]:
        """Devuelve la mejor calificación del personaje y las opciones que la tienen."""
        p = self.personajes[clave]
        letra = min((p[col] for col, _ in CATEGORIAS_APT[categoria]), key=ORDEN_APT.index)
        return letra, [etq for col, etq in CATEGORIAS_APT[categoria] if p[col] == letra]

    def crecimiento(self, clave: str) -> str:
        """Resume los porcentajes de crecimiento de estadísticas del personaje."""
        p = self.personajes[clave]
        partes = [f"{n} +{p[c]}%" for n, c in [("Speed", "spd_growth"), ("Stamina", "sta_growth"), ("Power", "pow_growth"),
                                               ("Guts", "gut_growth"), ("Wit", "wit_growth")] if p[c] not in ("", "0")]
        return " y ".join(partes) if partes else "ningún stat en particular"

    def objetivos(self, clave: str) -> str:
        """Resume los objetivos de estadísticas del personaje para el entrenamiento."""
        p = self.personajes[clave]
        mas = lambda v: "+" if v not in ("", "0") else ""
        return (f"Speed {p['spd_goal']}{mas(p['spd_goal_plus'])}, Stamina {p['sta_goal']}, Power {p['pow_goal']}, "
                f"Guts {p['gut_goal']}, Wit {p['wit_goal']}{mas(p['wit_goal_plus'])}")

    def principiantes(self) -> List[str]:
        """Lista los nombres de personajes recomendados para principiantes."""
        return [p["name"] for p in self.personajes.values() if p["recommended_beginner"] == "1"]

    # Cartas
    
    def nombre_carta(self, card_id: str) -> str:
        """Devuelve el nombre completo de una carta por su identificador."""
        return self.cartas[card_id]["card"]

    def etiqueta_carta(self, card_id: str) -> str:
        """Devuelve una etiqueta breve con nombre, rareza y estadística de la carta."""
        c = self.cartas[card_id]
        return f"{c['card'].split(' (')[0]} ({c['rarity']} {c['stat']})"

    def efecto(self, card_id: str, lb: Optional[str]) -> Tuple[str, dict]:
        """Obtiene el efecto del límite pedido, usando MLB o el mayor disponible como alternativa."""
        ef = self.efectos.get(card_id, {})
        if lb in ef:
            return lb, ef[lb]
        if "MLB" in ef:
            return "MLB", ef["MLB"]
        k = max(ef, key=lambda x: int(ef[x]["level"]))
        return k, ef[k]

    def recomendar_cartas(self, escenario: Optional[str], stat: Optional[str], rareza: Optional[str]) -> List[str]:
        """Filtra y ordena cartas compatibles con el escenario, estadística y rareza."""
        res = []
        for cid, c in self.cartas.items():
            if escenario and c["scenario"] not in (escenario, "both"):
                continue
            if stat and c["stat"].lower() != stat.lower():
                continue
            if rareza and c["rarity"] != rareza:
                continue
            _, e = self.efecto(cid, "MLB")
            puntaje = sum(int(e[k] or 0) for k in ("training_eff_pct", "friendship_bonus_pct", "race_bonus_pct"))
            res.append((ORDEN_RAREZA.get(c["rarity"], 9), -puntaje, c["card"], cid))
        return [r[3] for r in sorted(res)]
