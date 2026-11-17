"""Gestor de diálogo

Flujo por mensaje:
  1) Recibe el texto
  2) Extrae entidades (personaje, carta, escenario)
  3) Obtiene la intención del clasificador entrenado
  4) Consulta el contexto 
  5) Elige respuesta/acción
  6) Devuelve la respuesta 
  7) Actualiza el contexto"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .context_manager import ContextManager, Turno
from .knowledge_base import ESCENARIOS, KnowledgeBase, normalizar

Predictor = Callable[[str], Tuple[str, float]]

ENTIDAD_REPETIBLE = {
    "info_personaje": ["personaje"], "distancia_pista_recomendada": ["personaje"],
    "uma_facil_entrenar": ["personaje"], "info_carta": ["card"],
    "cartas_recomendadas": ["k_escenario"], "mejor_escenario": ["k_escenario"],
    "stats_funcion": ["k_stat"], "herencias": ["k_herencia"], "habilidades_comprar": ["k_habilidad"],
    "recompensas_items": ["k_item"], "distancias_aptitudes": ["k_distancia", "k_pista", "k_estilo"],
}
_STOP = {"y", "e", "de", "del", "el", "la", "los", "las", "a", "que", "tal", "pero", "ahora", "entonces",
         "tambien", "con", "sobre", "para", "en", "hablame", "cuentame", "dime", "pues", "oye", "ahi", "ese", "esa"}
_TERMINALES = {"despedida"}
_RX_REINICIO = re.compile(
    r"\b(reinici\w+|resete\w*|reset|nueva conversacion|nuevo chat|empez\w+ (de nuevo|otra vez|de cero|desde cero)|"
    r"empecemos (de nuevo|otra vez|de cero|desde cero)|olvida\w* (todo|lo anterior|lo que hablamos)|"
    r"borra\w* (el )?(contexto|historial)|limpia\w* (el )?(historial|contexto|conversacion))\b")
_RX_LB = re.compile(r"\b([0-4])\s?lb\b")
_RX_MLB = re.compile(r"\b(mlb|limite maximo|limite al maximo|maximo|full limit|max limit)\b")
_RX_SIN_LB = re.compile(r"\b(sin limite|sin romper|sin lb)\b")
_RX_OTRO_ESC = re.compile(r"\b(otro|el otro|el segundo|el primero) escenario\b|\bpara el otro\b")
_RX_LETRA = re.compile(r"(?<![A-Za-zÁ-ú])([A-GS])(?![A-Za-zÁ-ú])")
_SIGNIFICADO_LETRA = {
    "S": "la mejor aptitud posible: rendimiento máximo en esa pista, distancia o estilo",
    "A": "una aptitud muy buena y es la mínima recomendable para competir",
    "B": "una aptitud aceptable, pero por debajo de lo ideal; conviene compensarla con stats altos",
    "C": "una aptitud regular: la uma rinde claramente menos y suele evitarse",
    "D": "una aptitud baja; es mejor elegir otra pista, distancia o estilo",
    "E": "una aptitud baja; es mejor elegir otra pista, distancia o estilo",
    "F": "una aptitud muy mala; conviene evitarla",
    "G": "la peor aptitud: casi no puede competir bien en eso",
}
_ETIQ_CAT = {"pista": "pista", "distancia": "distancia", "estilo": "estilo"}
_TAM_PAGINA = 5


class DialogueManager:
    def __init__(self, predictor: Predictor, directorio_datos: Union[str, Path],
                 umbral: Optional[float] = None, seed: Optional[int] = None):
        """Carga conocimiento y respuestas, configura el predictor y crea el contexto."""
        d = Path(directorio_datos)
        self.predictor = predictor
        self.kb = KnowledgeBase(d)
        self.resp: Dict[str, Any] = json.loads((d / "responses_extra.json").read_text(encoding="utf-8"))
        self.resp.update(json.loads((d / "responses.json").read_text(encoding="utf-8")))  # la hoja manda
        meta = json.loads((d / "intents.json").read_text(encoding="utf-8"))
        self.umbral = umbral if umbral is not None else meta["umbral_confianza"]
        self.ctx = ContextManager()
        self._rng = random.Random(seed)
        self._norm = ""
        self._texto = ""

    # API
    def reiniciar(self) -> None:
        """Reinicia el contexto conversacional para comenzar una conversación nueva."""
        self.ctx.reset()

    def responder(self, mensaje: str) -> Dict[str, Any]:
        """Clasifica y responde al mensaje, actualizando el contexto de la conversación."""
        texto = (mensaje or "").strip()
        if not texto:
            return self._salida(self._elegir("vacio"), "vacio", 1.0, {}, "sistema")
        ctx = self.ctx
        self._texto, self._norm = texto, normalizar(texto)
        ent = self.kb.extraer_entidades(texto)

        # 1) Reinicio

        if _RX_REINICIO.search(self._norm):
            ctx.reset()
            return self._salida(self._elegir("_reinicio"), "reinicio", 1.0, ent, "regla")

        intent, conf, fuente = None, 1.0, "clasificador"

        # 2) Contestar una aclaración pendiente

        pend = ctx.pendiente
        ctx.aclaracion_previa = pend["intent"] if pend else None
        ctx.limpiar_pendiente()
        if pend and pend["slot"] in ent:
            intent, fuente = pend["intent"], "aclaracion"

        # Reglas de seguimiento que solo tienen sentido con contexto

        tema_intent = (ctx.tema or {}).get("intent")
        if intent is None and tema_intent in ("cartas_recomendadas", "mejor_escenario") and _RX_OTRO_ESC.search(self._norm):
            intent, fuente = "pedir_mas_detalle", "regla"          
        elif intent is None and tema_intent == "info_carta" and (
                _RX_LB.search(self._norm) or _RX_MLB.search(self._norm) or _RX_SIN_LB.search(self._norm)):
            intent, fuente = "info_carta", "regla"                 

        # 3) Clasificador entrenado

        if intent is None:
            intent, conf = self.predictor(texto)
            tema_intent = (ctx.tema or {}).get("intent")
            claves = ENTIDAD_REPETIBLE.get(tema_intent or "", [])
            if claves and any(k in ent for k in claves) and self._solo_entidad(texto):
                intent, conf, fuente = tema_intent, 1.0, "contexto"   
            elif conf < self.umbral:
                intent, fuente = "desconocido", "umbral"

        ctx.actualizar_slots({"personaje": ent.get("personaje"), "card": ent.get("card"),
                              "escenario": self._clave_escenario(ent.get("k_escenario"))})
        if intent != "desconocido":
            ctx.desconocidos_seguidos = 0
        manejador = getattr(self, f"_h_{intent}", self._h_desconocido)
        respuesta = manejador(ent)
        if intent not in _TERMINALES:
            ctx.registrar_turno(Turno(texto, intent, float(conf), respuesta, dict(ent)))
        return self._salida(respuesta, intent, conf, ent, fuente)

    # Utilidades

    def _salida(self, respuesta, intent, conf, ent, fuente):
        """Construye la respuesta pública con intención, entidades y contexto actual."""
        return {"respuesta": respuesta, "intencion": intent, "confianza": round(float(conf), 3),
                "entidades": ent, "fuente": fuente, "contexto": self.ctx.snapshot()}

    def _elegir(self, clave: str, **fmt) -> str:
        """Elige una variante de respuesta y la formatea evitando repetir la anterior."""
        opciones = self.resp[clave]
        ultimo = self.ctx.ultima_variante.get(clave)
        idx = [i for i in range(len(opciones)) if i != ultimo] or list(range(len(opciones)))
        i = self._rng.choice(idx)
        self.ctx.ultima_variante[clave] = i
        return opciones[i].format(**fmt)

    def _solo_entidad(self, texto: str) -> bool:
        """Indica si el mensaje contiene solo entidades y palabras de enlace comunes."""
        return not (set(self.kb.quitar_entidades(texto).split()) - _STOP)

    @staticmethod
    def _clave_escenario(nombre: Optional[str]) -> Optional[str]:
        """Convierte el nombre visible de un escenario a su clave interna."""
        return {v: k for k, v in ESCENARIOS.items()}.get(nombre) if nombre else None

    @staticmethod
    def _unir(items: List[str]) -> str:
        """Une opciones en una lista legible o indica que no hay opciones con A."""
        return ", ".join(items) if items else "ninguna con A"

    def _texto_fila(self, fila: dict) -> str:
        """Formatea una fila de conocimiento con su nombre, descripción y detalle."""
        nombre = fila["name"][0].upper() + fila["name"][1:]
        t = f"{nombre}: {fila['description']}"
        t += "." if not t.endswith(".") else ""
        if fila["detail"]:
            t += " " + fila["detail"] + ("." if not fila["detail"].endswith(".") else "")
        return t

    def _filas_mencionadas(self, ent, categorias: List[str]) -> List[dict]:
        """Busca en la base de conocimiento las filas de las entidades detectadas."""
        out = []
        for cat in categorias:
            nombre = ent.get("k_" + cat)
            f = self.kb.fila(cat, nombre) if nombre else None
            if f:
                out.append(f)
        return out

    def _respuesta_conocimiento(self, filas: List[dict]) -> str:
        """Crea una respuesta con el texto de las filas de conocimiento recibidas."""
        return self._elegir("_knowledge", texto=" ".join(self._texto_fila(f) for f in filas))

    def _aclarar(self, intent: str, slot: str = "personaje") -> str:
        """Registra el dato que falta y selecciona una pregunta de aclaración adecuada."""
        self.ctx.pedir_aclaracion(intent, slot)
        if slot == "card":
            ej = [self.kb.etiqueta_carta(c) for c in list(self.kb.cartas)[:4]]
            return self._elegir("_aclarar_carta", lista=", ".join(ej))
        return self._elegir("_aclarar_personaje")

    # Manejadores

    def _h_saludo(self, ent):
        """Devuelve una respuesta de saludo."""
        return self._elegir("saludo")

    def _h_fuera_dominio(self, ent):
        """Responde que la consulta está fuera del dominio del chatbot."""
        return self._elegir("fuera_dominio")

    def _h_despedida(self, ent):
        """Devuelve una despedida y limpia el contexto de la conversación."""
        r = self._elegir("despedida")
        self.ctx.reset()
        return r

    def _h_desconocido(self, ent):
        """Responde a una intención no reconocida y ofrece ayuda tras dos casos seguidos."""
        self.ctx.desconocidos_seguidos += 1
        if self.ctx.desconocidos_seguidos >= 2:
            self.ctx.desconocidos_seguidos = 0
            return self._elegir("_ayuda")
        return self._elegir("_fallback")

    def _h_stats_funcion(self, ent):
        """Explica la estadística mencionada o presenta la respuesta general sobre stats."""
        stat = ent.get("k_stat")
        self.ctx.set_tema("stats_funcion", stat=stat)
        if stat:
            return self._respuesta_conocimiento([self.kb.fila("stat", stat)])
        return self._elegir("stats_funcion")

    def _h_cartas_soporte(self, ent):
        """Explica información general o específica sobre cartas y rarezas."""
        filas = self._filas_mencionadas(ent, ["carta", "rareza"])
        self.ctx.set_tema("cartas_soporte", carta=ent.get("k_carta"), rareza=ent.get("k_rareza"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("cartas_soporte")

    def _filtros_cartas(self, ent) -> Dict[str, Optional[str]]:
        """Combina filtros extraídos del mensaje con el escenario guardado en contexto."""
        stat = None
        if ent.get("k_carta"):
            stat = ent["k_carta"].split(" (")[0]
            stat = stat.capitalize()
        elif ent.get("k_stat"):
            stat = ent["k_stat"].capitalize()
        esc = self._clave_escenario(ent.get("k_escenario")) or self.ctx.slots["escenario"]
        return {"escenario": esc, "stat": stat, "rareza": ent.get("k_rareza")}

    def _h_cartas_recomendadas(self, ent):
        """Recomienda cartas compatibles con los filtros y limita la lista inicial."""
        f = self._filtros_cartas(ent)
        self.ctx.set_tema("cartas_recomendadas", **f)
        ids = self.kb.recomendar_cartas(f["escenario"], f["stat"], f["rareza"])
        if not ids:
            return self._elegir("_cartas_sin_resultados")
        lista = ", ".join(self.kb.etiqueta_carta(i) for i in ids[:_TAM_PAGINA])
        return self._elegir("cartas_recomendadas", escenario=ESCENARIOS.get(f["escenario"] or "both"), lista_cartas=lista)

    def _h_distancias_aptitudes(self, ent):
        """Explica aptitudes mencionadas o interpreta una letra de calificación."""
        self.ctx.set_tema("distancias_aptitudes")
        m = _RX_LETRA.search(self._texto)
        if m and not self._filas_mencionadas(ent, ["distancia", "pista", "estilo"]):
            letra = m.group(1)
            return self._elegir("_aptitud_letra", letra=letra, significado=_SIGNIFICADO_LETRA[letra])
        filas = self._filas_mencionadas(ent, ["aptitud", "distancia", "pista", "estilo"])
        return self._respuesta_conocimiento(filas) if filas else self._elegir("distancias_aptitudes")

    def _h_distancia_pista_recomendada(self, ent):
        """Indica las pistas, distancias y estilos adecuados para el personaje activo."""
        clave = self.ctx.slots["personaje"]
        if not clave:
            if self.ctx.aclaracion_previa == "distancia_pista_recomendada":  
                return self._elegir("distancia_pista_recomendada")
            return self._aclarar("distancia_pista_recomendada")
        self.ctx.set_tema("distancia_pista_recomendada", personaje=clave)
        nombre = self.kb.nombre_personaje(clave)
        cats = [c for c in ("pista", "distancia", "estilo") if "k_" + c in ent] or ["pista", "distancia", "estilo"]
        ok, mal = {}, []
        for c in cats:
            a = self.kb.aptitudes(clave, c)
            if a:
                ok[c] = ", ".join(a)
            else:
                letra, mejores = self.kb.mejor_aptitud(clave, c)
                mal.append(self._elegir("_sin_aptitud_A", personaje=nombre, categoria=_ETIQ_CAT[c],
                                        mejor=f"{', '.join(mejores)} (aptitud {letra})"))
        if len(cats) == 3 and not mal:
            return self._elegir("_distancia_pista_personaje", personaje=nombre, pistas=ok["pista"],
                                distancias=ok["distancia"], estilos=ok["estilo"])
        partes = [f"En {_ETIQ_CAT[c]}, {nombre} tiene aptitud A en {v}." for c, v in ok.items()]
        return " ".join(partes + mal)

    def _h_info_personaje(self, ent):
        """Presenta aptitudes, crecimiento y objetivos del personaje activo."""
        clave = self.ctx.slots["personaje"]
        if not clave:
            if "card" in ent:
                nombre = self.kb.nombre_carta(ent["card"]).split(" (")[0]
                return self._elegir("_sin_ficha", nombre=nombre)
            return self._aclarar("info_personaje")
        self.ctx.set_tema("info_personaje", personaje=clave)
        return self._elegir("info_personaje", personaje=self.kb.nombre_personaje(clave),
                            pistas=self._unir(self.kb.aptitudes(clave, "pista")),
                            distancias=self._unir(self.kb.aptitudes(clave, "distancia")),
                            estilos=self._unir(self.kb.aptitudes(clave, "estilo")),
                            crecimiento=self.kb.crecimiento(clave), objetivos=self.kb.objetivos(clave))

    def _h_uma_facil_entrenar(self, ent):
        """Enumera personajes para principiantes y evalúa uno si fue mencionado."""
        lista = self.kb.principiantes()
        self.ctx.set_tema("uma_facil_entrenar")
        if not lista:
            return self._elegir("_uma_facil_sin_datos")
        clave = ent.get("personaje")
        if clave:
            p = self.kb.personajes[clave]
            datos = dict(personaje=p["name"], a_count=p["a_count"], crecimiento=self.kb.crecimiento(clave),
                         lista_umas=", ".join(lista))
            return self._elegir("_uma_facil_si" if p["recommended_beginner"] == "1" else "_uma_facil_no", **datos)
        return self._elegir("uma_facil_entrenar", lista_umas=", ".join(lista))

    def _h_recompensas_items(self, ent):
        """Explica el objeto de recompensa mencionado o la información general disponible."""
        filas = self._filas_mencionadas(ent, ["item"])
        self.ctx.set_tema("recompensas_items", item=ent.get("k_item"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("recompensas_items")

    def _h_mejor_escenario(self, ent):
        """Explica el escenario mencionado o responde con una comparación general."""
        filas = self._filas_mencionadas(ent, ["escenario"])
        if filas:
            self.ctx.set_tema("mejor_escenario", escenario=ent["k_escenario"])
            return self._respuesta_conocimiento(filas)
        self.ctx.actualizar_slots({"escenario": "ura_finale"})  
        self.ctx.set_tema("mejor_escenario")
        return self._elegir("mejor_escenario")

    def _h_herencias(self, ent):
        """Explica la herencia o el color de herencia detectado en el mensaje."""
        filas = self._filas_mencionadas(ent, ["herencia"])
        self.ctx.set_tema("herencias", color=ent.get("k_herencia"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("herencias")

    def _h_habilidades_comprar(self, ent):
        """Explica la habilidad mencionada o da información general para comprar habilidades."""
        filas = self._filas_mencionadas(ent, ["habilidad"])
        self.ctx.set_tema("habilidades_comprar", tipo=ent.get("k_habilidad"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("habilidades_comprar")

    def _h_subir_nivel(self, ent):
        """Responde a consultas generales sobre cómo subir de nivel."""
        self.ctx.set_tema("subir_nivel")
        return self._elegir("subir_nivel")

    def _h_info_carta(self, ent):
        """Describe una carta y sus efectos para el límite de ruptura solicitado."""
        cid = ent.get("card") or self.ctx.slots["card"]
        if not cid:
            return self._aclarar("info_carta", "card")
        c = self.kb.cartas[cid]
        pedido = None
        if _RX_SIN_LB.search(self._norm): pedido = "0LB"
        elif _RX_MLB.search(self._norm): pedido = "MLB"
        elif _RX_LB.search(self._norm): pedido = _RX_LB.search(self._norm).group(1) + "LB"
        lb, e = self.kb.efecto(cid, pedido)
        self.ctx.set_tema("info_carta", card=cid, lb=lb)
        prefijo = ""
        if pedido and pedido != lb:
            prefijo = self._elegir("_lb_no_disponible", carta=self.kb.etiqueta_carta(cid), pedido=pedido, lb=lb)
        bonos = [b for b in re.split(r"[|,]", e["stat_bonus"]) if b]
        bono = ", ".join(f"+{b.split(':')[1]} {b.split(':')[0].capitalize()}" if ":" in b else b for b in bonos) or "ninguno"
        return prefijo + self._elegir(
            "info_carta", carta=c["card"], rareza=c["rarity"], stat=c["stat"],
            escenario=ESCENARIOS.get(c["scenario"], c["scenario"]),
            habilidad_txt=f"Su habilidad es {c['skill']}. " if c["skill"] else "", lb=lb, nivel=e["level"],
            amistad=e["friendship_bonus_pct"], entrenamiento=e["training_eff_pct"], prioridad=e["specialty_prio"],
            race_bonus=e["race_bonus_pct"], amistad_inicial=e["initial_friendship"], bono_stat=bono, nota=e["note"])

    # Para pedir más detalle

    def _etiqueta_tema(self, t: Dict[str, Any]) -> str:
        """Genera una etiqueta legible para el tema de conversación registrado."""
        i = t["intent"]
        if i == "stats_funcion": return f"la estadística {t['stat'].capitalize()}" if t.get("stat") else "las estadísticas"
        if i in ("info_personaje", "distancia_pista_recomendada"):
            n = self.kb.nombre_personaje(t["personaje"])
            return n if i == "info_personaje" else f"la pista y distancia de {n}"
        if i == "info_carta": return f"la carta {self.kb.nombre_carta(t['card'])}"
        return {"cartas_soporte": "las cartas de soporte", "cartas_recomendadas": "las cartas recomendadas",
                "distancias_aptitudes": "las aptitudes", "recompensas_items": "los objetos de recompensa",
                "mejor_escenario": "los escenarios", "herencias": "la herencia", "habilidades_comprar": "las habilidades",
                "subir_nivel": "subir de nivel", "uma_facil_entrenar": "las umas para principiantes"}.get(i, "ese tema")

    def _detalle(self, t: Dict[str, Any], nivel: int) -> Optional[str]:
        """Obtiene el siguiente detalle disponible para el tema y nivel solicitados."""
        i, kb = t["intent"], self.kb
        todas = lambda cat: " ".join(f"{f['name'][0].upper() + f['name'][1:]}: {f['detail']}." for f in kb.filas(cat) if f["detail"])
        if i == "cartas_recomendadas":  # paginación: cada "más" muestra las siguientes cartas
            ids = kb.recomendar_cartas(t.get("escenario"), t.get("stat"), t.get("rareza"))
            pag = ids[_TAM_PAGINA * (nivel + 1): _TAM_PAGINA * (nivel + 2)]
            return ("Otras opciones: " + ", ".join(kb.etiqueta_carta(c) for c in pag) +
                    ". (Orden: rareza y luego suma de bonos de entrenamiento, amistad y carrera con MLB.)") if pag else None
        if nivel > 0:
            return None
        if i == "stats_funcion":
            if t.get("stat"):
                f = kb.fila("stat", t["stat"]); return (f["detail"] + ".") if f["detail"] else None
            return todas("stat")
        if i == "cartas_soporte":
            fs = [kb.fila("carta", t["carta"])] if t.get("carta") else [kb.fila("rareza", t["rareza"])] if t.get("rareza") else None
            if fs and fs[0] and fs[0]["detail"]: return fs[0]["detail"] + "."
            return " ".join(f"{f['name']}: {f['description']}." for f in kb.filas("rareza"))
        if i == "distancias_aptitudes":
            return (kb.fila("aptitud", "aptitud")["detail"] + ". " + " ".join(
                f"{f['name'][0].upper() + f['name'][1:]}: {f['detail']}." for f in kb.filas("distancia")))
        if i == "distancia_pista_recomendada":
            c = t["personaje"]; return f"Sus objetivos de stats son {kb.objetivos(c)}, y crece en {kb.crecimiento(c)}."
        if i == "recompensas_items": return todas("item")
        if i == "mejor_escenario": return todas("escenario")
        if i == "herencias": return todas("herencia")
        if i == "habilidades_comprar": return todas("habilidad")
        if i == "subir_nivel":
            niveles: Dict[str, Dict[str, List[int]]] = {}
            for cid, efs in kb.efectos.items():
                r = kb.cartas[cid]["rarity"]
                for lb, e in efs.items():
                    niveles.setdefault(r, {}).setdefault(lb, []).append(int(e["level"]))
            partes = []
            for r in sorted(niveles, key=lambda x: {"SSR": 0, "SR": 1, "R": 2}.get(x, 9)):
                lbs = niveles[r]
                if "0LB" in lbs and "MLB" in lbs:
                    partes.append(f"{r}: nivel {min(lbs['0LB'])} sin romper límite (0LB) y hasta {max(lbs['MLB'])} con MLB")
                elif "MLB" in lbs:
                    partes.append(f"{r}: hasta nivel {max(lbs['MLB'])} con MLB")
            return ("Según mi base de datos, " + "; ".join(partes) + ". Romper el límite mejora los bonos de la carta.") if partes else None
        if i == "info_personaje":
            c = t["personaje"]
            sec = {cat: ", ".join(kb.aptitudes(c, cat, "B")) for cat in ("pista", "distancia", "estilo")}
            if not any(sec.values()): return None
            return "Aptitudes secundarias (B): " + "; ".join(f"{_ETIQ_CAT[k]} {v}" for k, v in sec.items() if v) + "."
        if i == "info_carta":
            efs = kb.efectos[t["card"]]
            if len(efs) < 2: return None
            return "Comparación por límite: " + "; ".join(
                f"{lb} (nivel {e['level']}): amistad {e['friendship_bonus_pct']}%, entrenamiento {e['training_eff_pct']}%, "
                f"prioridad {e['specialty_prio']}" for lb, e in efs.items()) + "."
        if i == "uma_facil_entrenar":
            return " ".join(f"{p['name']}: {p['a_count']} aptitudes A, crece en {kb.crecimiento(k)}."
                            for k, p in kb.personajes.items() if p["recommended_beginner"] == "1")
        return None

    def _h_pedir_mas_detalle(self, ent):
        """Resuelve una petición de más detalle, incluida la paginación de resultados."""
        ctx = self.ctx
        t = ctx.tema
        if not t:
            return self._aclarar_tema()
        if t["intent"] in ("cartas_recomendadas", "mejor_escenario") and (
                ent.get("k_escenario") or (_RX_OTRO_ESC.search(self._norm) and ctx.slots["escenario"])):
            if not ent.get("k_escenario"):
                otro = "unity_cup" if ctx.slots["escenario"] == "ura_finale" else "ura_finale"
                ent = dict(ent, k_escenario=ESCENARIOS[otro]); ctx.slots["escenario"] = otro
            return getattr(self, "_h_" + t["intent"])(ent)
        texto = self._detalle(t, ctx.nivel_detalle)
        if texto is None:
            return self._elegir("_sin_mas_detalle")
        ctx.nivel_detalle += 1
        return self._elegir("pedir_mas_detalle", tema=self._etiqueta_tema(t)).rstrip() + " " + texto

    def _aclarar_tema(self):
        """Pide al usuario que indique el tema del que quiere más información."""
        return self._elegir("_aclarar_tema")
