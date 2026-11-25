"""Gestor de diálogo, contexto y recomendaciones del chatbot.

Etapa 12: adapta confianza V4 y permite continuidad contextual comprobable.
Etapa 11: incorpora mazos orientativos y la intención objetivos_stats.

Etapas 8–10: valida filtros, preserva el estado, separa F2P de rareza y distingue continuaciones,
negaciones parciales de SSR y solicitudes de alternativas trazables.

Flujo por mensaje:
  1) Recibe el texto
  2) Extrae entidades (personaje, carta, escenario)
  3) Obtiene la intención del clasificador entrenado
  4) Consulta el contexto 
  5) Elige respuesta/acción
  6) Devuelve la respuesta 
  7) Actualiza el contexto"""

from __future__ import annotations

from copy import deepcopy
import json
import random
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .confidence_manager import ConfidenceManager
from .card_recommender import ordenar, describir, objetivos
from .deck_builder import construir_mazo, explicar_mazo
from .context_resolver import ETIQUETAS, elegir_opcion, preferencias, seguimiento, analizar_ssr
from .context_manager import ContextManager, Turno
from .knowledge_base import ESCENARIOS, KnowledgeBase, normalizar

Predictor = Callable[[str], Tuple[str, float]]

ENTIDAD_REPETIBLE = {
    "info_personaje": ["personaje"], "distancia_pista_recomendada": ["personaje"],
    "uma_facil_entrenar": ["personaje"], "info_carta": ["card"],
    "cartas_recomendadas": ["k_escenario"], "mejor_escenario": ["k_escenario"],
    "stats_funcion": ["k_stat"], "objetivos_stats": ["personaje", "k_escenario"], "herencias": ["k_herencia"], "habilidades_comprar": ["k_habilidad"],
    "recompensas_items": ["k_item"], "distancias_aptitudes": ["k_distancia", "k_pista", "k_estilo"],
}
_STOP = {"y", "e", "de", "del", "el", "la", "los", "las", "a", "que", "tal", "pero", "ahora", "entonces",
         "tambien", "con", "sobre", "para", "en", "pues", "oye", "ahi", "ese", "esa"}
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
        """Inicializa los componentes y el estado necesarios para operar."""
        d = Path(directorio_datos)
        self.predictor = predictor
        if umbral is None and getattr(predictor, 'politica_v4', False):
            politica = predictor.configuracion_confianza
            self.gestor_confianza = ConfidenceManager(
                minimo=politica['minimo'],
                margen_minimo=politica['margen_minimo'],
                minimo_aclaracion=politica['minimo_aclaracion'])
        elif getattr(predictor, 'politica_v3', False) and umbral is None:
            self.gestor_confianza = ConfidenceManager()
        else:
            self.gestor_confianza = None
        self.diagnostico = None
        self.kb = KnowledgeBase(d)
        self.resp: Dict[str, Any] = json.loads((d / "responses_extra.json").read_text(encoding="utf-8"))
        self.resp.update(json.loads((d / "responses.json").read_text(encoding="utf-8")))  # la hoja manda
        meta = json.loads((d / "intents.json").read_text(encoding="utf-8"))
        self.umbral = umbral if umbral is not None else meta["umbral_confianza"]
        self.ctx = ContextManager()
        self._rng = random.Random(seed)
        self._norm = ""
        self._texto = ""
        self._recomendacion_sin_resultados = False

    # API
    def reiniciar(self) -> None:
        """Botón/comando de nueva conversación (lo usa la interfaz)."""
        self.ctx.reset()
        self.diagnostico = None

    def responder(self, mensaje: str) -> Dict[str, Any]:
        """Procesa un turno, aplica reglas contextuales y evalúa la confianza antes de responder."""
        self.diagnostico = None
        self._recomendacion_sin_resultados = False
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

        # 2) Resolver una elección de intención sin volver a clasificar el ordinal.
        pc = ctx.pendiente_confianza
        ctx.pendiente_confianza = None
        if pc:
            elegida = elegir_opcion(texto, pc["opciones"])
            if elegida:
                intent, fuente = elegida, "aclaracion_confianza"
                conf = pc["probabilidades"][elegida]
                ent = dict(pc["entidades"])
                self._texto, self._norm = pc["texto"], normalizar(pc["texto"])
            elif self._norm in ("si", "no", "no se", "cualquiera"):
                ctx.pendiente_confianza = pc
                respuesta = "Elige la opción 1 o 2, o escribe una pregunta nueva."
                ctx.registrar_turno(Turno(texto, "desconocido", 0.0, respuesta, {}))
                return self._salida(respuesta, "desconocido", 0.0, {}, "confianza_ambigua")

        # 3) Contestar una aclaración pendiente

        pend = ctx.pendiente
        ctx.aclaracion_previa = pend["intent"] if pend else None
        ctx.limpiar_pendiente()
        if intent is None and pend and pend["slot"] in ent and self._solo_entidad(texto):
            intent, fuente = pend["intent"], "aclaracion"

        # Reglas de seguimiento que solo tienen sentido con contexto

        tema_intent = (ctx.tema or {}).get("intent")
        if intent is None and tema_intent in ("cartas_recomendadas", "mejor_escenario", "objetivos_stats") and _RX_OTRO_ESC.search(self._norm):
            intent, fuente = "pedir_mas_detalle", "regla"          
        elif intent is None and tema_intent == "info_carta" and (
                _RX_LB.search(self._norm) or _RX_MLB.search(self._norm) or _RX_SIN_LB.search(self._norm)):
            intent, fuente = "info_carta", "regla"                 

        # Etapa 9: aclarar inventario parcial sin establecer una exclusión SSR falsa.
        estado_ssr = analizar_ssr(texto)
        if intent is None and tema_intent == "cartas_recomendadas" and estado_ssr["parcial"]:
            respuesta = ("Entiendo que tienes algunas SSR, pero no todas. "
                         "¿Cuáles te faltan? Puedo mostrar alternativas SR por rol, "
                         "sin suponer cuáles cartas posees.")
            ctx.registrar_turno(Turno(texto, "aclaracion_inventario", 1.0, respuesta, dict(ent)))
            return self._salida(respuesta, "aclaracion_inventario", 1.0, ent, "contexto")
        if intent is None and tema_intent == "cartas_recomendadas" and (
                estado_ssr["sustituciones"] or estado_ssr["faltan_especificas"]):
            intent, fuente = "sustituciones_cartas", "contexto"

        # Una petición explícita de ficha de personaje no es una continuación.
        if intent is None and ent.get("personaje") and re.match(
                r"^(?:hablame|cuentame|dime) (?:de|sobre)\b", self._norm) and not re.search(
                r"\b(?:cartas?|soportes?|mazo|deck)\b", self._norm):
            intent, fuente = "info_personaje", "regla"

        # Etapa 12: si se preguntan aptitudes de alguien que figura solo como
        # carta de soporte, informar esa limitación en lugar de escoger un tema
        # ambiguo. No se infiere que la carta sea un personaje entrenable.
        if intent is None and ent.get('card') and not ent.get('personaje') and re.search(
                r'\b(?:que|cuales) aptitudes (?:tiene|posee)\b', self._norm):
            intent, conf, fuente = 'info_personaje', 1.0, 'regla_catalogo'

        # Etapa 11: las continuaciones explícitas de cartas deben operar también
        # con el modelo exploratorio V4, cuya política de confianza está pendiente.
        if intent is None and (self.gestor_confianza or tema_intent == 'cartas_recomendadas'):
            continuacion = seguimiento(texto, ent, ctx, self._solo_entidad(texto))
            if continuacion:
                intent, fuente = continuacion, "contexto"

        # Etapa 11: órdenes explícitas reconocibles por reglas antes del SVM.
        # «Mazo» no es una estadística ni un simple listado top-N.
        pide_mazo = bool(re.search(r"\b(?:mazo|deck|build|armame|armar un mazo)\b", self._norm))
        pide_objetivos = bool(re.search(
            r"\b(?:objetivos? (?:de )?(?:stats?|estadisticas?)|"
            r"(?:stats?|estadisticas?) (?:ideales?|objetivo|recomendad[ao]s?|metas?)|"
            r"(?:cuanto|cuanta|cuantos) (?:speed|stamina|power|guts|wit) (?:necesito|debo)|"
            r"(?:meta|valores? objetivo|cantidades? recomendadas?|numeros? objetivo) (?:de|para) (?:speed|stamina|power|guts|wit)|"
            r"(?:guia|metas?) de (?:estadisticas?|stats?)|"
            r"stats? (?:con los que|con que) (?:debo|deberia) terminar)\b",
            self._norm))
        if intent is None and tema_intent == 'objetivos_stats' and ent.get('k_escenario') and len(self._norm.split()) <= 12:
            intent, conf, fuente = 'objetivos_stats', 1.0, 'contexto'
        if intent is None and pide_objetivos:
            intent, conf, fuente = "objetivos_stats", 1.0, "regla_objetivos"
        elif intent is None and pide_mazo:
            intent, conf, fuente = "cartas_recomendadas", 1.0, "regla_mazo"

        # 4) Clasificador entrenado

        if intent is None:
            candidatos = self.predictor.top_k(texto) if self.gestor_confianza else None
            intent, conf = candidatos[0] if candidatos else self.predictor(texto)
            tema_intent = (ctx.tema or {}).get("intent")
            claves = ENTIDAD_REPETIBLE.get(tema_intent or "", [])
            if claves and any(k in ent for k in claves) and self._solo_entidad(texto):
                intent, conf, fuente = tema_intent, 1.0, "contexto"   
            elif candidatos:
                self.diagnostico = self.gestor_confianza.evaluar(candidatos)
                # Etapa 12: recuperar tema anterior SOLO con evidencia de continuación,
                # entre las dos primeras clases y sin una nueva entidad de personaje.
                # No forzar una etiqueta basándonos únicamente en su probabilidad.
                indices = dict(candidatos[:2])
                marcador = bool(re.match(r'^(?:y|para|pero|entonces|respecto a|sobre eso)\b', self._norm))
                misma_entidad = (not ent.get('personaje') or
                                 ent['personaje'] == ctx.slots.get('personaje'))
                continuar = (self.diagnostico['accion'] == 'aclarar' and
                             tema_intent in indices and tema_intent in ENTIDAD_REPETIBLE and
                             len(self._norm.split()) <= 12 and marcador and misma_entidad and
                             not re.search(r'\b(?:hablame|cuentame|dime|explicame)\b',self._norm))
                if continuar:
                    intent, conf, fuente = tema_intent, indices[tema_intent], 'contexto_confianza'
                    self.diagnostico['accion'] = 'aceptar_contexto'
                    self.diagnostico['motivo'] = 'continuidad con tema previo y top-2'
                if self.diagnostico['accion'] not in ('aceptar', 'aceptar_contexto'):
                    # No contaminar slots ni tema con una clasificación incierta.
                    if self.diagnostico["accion"] == "aclarar" and ctx.desconocidos_seguidos >= 1 and not ent:
                        # Dos mensajes consecutivos sin información reconocible:
                        # ofrecer ayuda en vez de repetir alternativas al azar.
                        respuesta = self._h_desconocido(ent)
                        fuente = "ayuda_contextual"
                    elif self.diagnostico["accion"] == "aclarar":
                        respuesta = self._pregunta_confianza(candidatos)
                        opciones = [i for i, _ in candidatos[:2]]
                        if all(i in ETIQUETAS for i in opciones):
                            ctx.pendiente_confianza = {"opciones": opciones,
                                "probabilidades": dict(candidatos[:2]), "entidades": dict(ent), "texto": texto}
                        ctx.desconocidos_seguidos = 0
                        fuente = "confianza_ambigua"
                    else:
                        respuesta = self._h_desconocido(ent)
                        fuente = "umbral"
                    ctx.registrar_turno(Turno(texto, "desconocido", float(conf), respuesta, dict(ent)))
                    return self._salida(respuesta, "desconocido", conf, ent, fuente)
            elif conf < self.umbral:
                intent, fuente = "desconocido", "umbral"

        # Preparar una copia para deshacer cambios si la recomendación queda vacía.
        estado_previo = deepcopy((ctx.slots, ctx.tema, ctx.preferencias, ctx.nivel_detalle))
        if intent not in ("desconocido", "fuera_dominio", "saludo", "despedida"):
            ctx.actualizar_slots({"personaje": ent.get("personaje"), "card": ent.get("card"),
                                  "escenario": self._clave_escenario(ent.get("k_escenario"))})
        if intent != "desconocido":
            ctx.desconocidos_seguidos = 0
        if intent not in ("cartas_recomendadas", "sustituciones_cartas", "pedir_mas_detalle", "saludo", "fuera_dominio", "desconocido"):
            ctx.preferencias.clear()
        manejador = getattr(self, f"_h_{intent}", self._h_desconocido)
        respuesta = manejador(ent)
        if self._recomendacion_sin_resultados:
            # Una consulta fallida no debe reemplazar el último contexto confirmado.
            ctx.slots, ctx.tema, ctx.preferencias, ctx.nivel_detalle = estado_previo
        if intent not in _TERMINALES:
            ctx.registrar_turno(Turno(texto, intent, float(conf), respuesta, dict(ent)))
        return self._salida(respuesta, intent, conf, ent, fuente)

    # Utilidades

    def _salida(self, respuesta, intent, conf, ent, fuente):
        """Construye la respuesta estructurada con contexto y diagnóstico."""
        return {"respuesta": respuesta, "intencion": intent, "confianza": round(float(conf), 3),
                "entidades": ent, "fuente": fuente, "contexto": self.ctx.snapshot(), "diagnostico_confianza": self.diagnostico}

    def _pregunta_confianza(self, candidatos):
        """Formula una aclaración con las alternativas plausibles, sin afirmar que son correctas."""
        opciones = [ETIQUETAS[i] for i, _ in candidatos[:2] if i in ETIQUETAS]
        if len(opciones) == 2:
            return f"No estoy seguro de haber entendido. ¿Te refieres a 1) {opciones[0]} o 2) {opciones[1]}? Escribe 1 o 2, o reformula tu pregunta."
        return "No estoy seguro de haber entendido. ¿Puedes concretar tu pregunta sobre Uma Musume?"

    def _elegir(self, clave: str, **fmt) -> str:
        """Elige una variante distinta de la última usada para esa clave."""
        opciones = self.resp[clave]
        ultimo = self.ctx.ultima_variante.get(clave)
        idx = [i for i in range(len(opciones)) if i != ultimo] or list(range(len(opciones)))
        i = self._rng.choice(idx)
        self.ctx.ultima_variante[clave] = i
        return opciones[i].format(**fmt)

    def _solo_entidad(self, texto: str) -> bool:
        """Comprueba si el mensaje contiene únicamente entidades y palabras auxiliares."""
        return not (set(self.kb.quitar_entidades(texto).split()) - _STOP)

    @staticmethod
    def _clave_escenario(nombre: Optional[str]) -> Optional[str]:
        """Convierte el nombre de escenario a su clave interna."""
        return {v: k for k, v in ESCENARIOS.items()}.get(nombre) if nombre else None

    @staticmethod
    def _unir(items: List[str]) -> str:
        """Une las aptitudes disponibles o señala su ausencia."""
        return ", ".join(items) if items else "ninguna con A"

    def _texto_fila(self, fila: dict) -> str:
        """Formatea la descripción y detalle de un registro."""
        nombre = fila["name"][0].upper() + fila["name"][1:]
        t = f"{nombre}: {fila['description']}"
        t += "." if not t.endswith(".") else ""
        if fila["detail"]:
            t += " " + fila["detail"] + ("." if not fila["detail"].endswith(".") else "")
        return t

    def _filas_mencionadas(self, ent, categorias: List[str]) -> List[dict]:
        """Recupera registros asociados a las entidades detectadas."""
        out = []
        for cat in categorias:
            nombre = ent.get("k_" + cat)
            f = self.kb.fila(cat, nombre) if nombre else None
            if f:
                out.append(f)
        return out

    def _respuesta_conocimiento(self, filas: List[dict]) -> str:
        """Compone una respuesta a partir de registros de conocimiento."""
        return self._elegir("_knowledge", texto=" ".join(self._texto_fila(f) for f in filas))

    def _aclarar(self, intent: str, slot: str = "personaje") -> str:
        """Registra y solicita un dato necesario para responder."""
        self.ctx.pedir_aclaracion(intent, slot)
        if slot == "card":
            ej = [self.kb.etiqueta_carta(c) for c in list(self.kb.cartas)[:4]]
            return self._elegir("_aclarar_carta", lista=", ".join(ej))
        return self._elegir("_aclarar_personaje")

    # Manejadores

    def _h_saludo(self, ent):
        """Devuelve un saludo."""
        return self._elegir("saludo")
    def _h_fuera_dominio(self, ent):
        """Informa que el tema está fuera del ámbito del chatbot."""
        respuesta = self._elegir("fuera_dominio")
        return respuesta if "umamusume" in normalizar(respuesta) else respuesta + " Mi ámbito es Umamusume."

    def _h_despedida(self, ent):
        """Responde la despedida y limpia el contexto."""
        r = self._elegir("despedida")
        self.ctx.reset()
        return r

    def _h_desconocido(self, ent):
        """Solicita reformular o presenta ejemplos después de varios fallos."""
        self.ctx.desconocidos_seguidos += 1
        if self.ctx.desconocidos_seguidos >= 2:
            self.ctx.desconocidos_seguidos = 0
            return self._elegir("_ayuda")
        return self._elegir("_fallback")

    def _h_stats_funcion(self, ent):
        """Explica estadísticas y guarda el tema."""
        stat = ent.get("k_stat")
        self.ctx.set_tema("stats_funcion", stat=stat)
        if stat:
            return self._respuesta_conocimiento([self.kb.fila("stat", stat)])
        return self._elegir("stats_funcion")

    def _h_objetivos_stats(self, ent):
        """Muestra las metas registradas de un personaje, sin inventar cifras por escenario."""
        personaje = ent.get('personaje') or self.ctx.slots.get('personaje')
        if not personaje:
            return self._aclarar('objetivos_stats')
        escenario = self._clave_escenario(ent.get('k_escenario')) or self.ctx.slots.get('escenario')
        self.ctx.set_tema('objetivos_stats', personaje=personaje, escenario=escenario)
        nombre = self.kb.nombre_personaje(personaje)
        texto = f'Objetivos generales registrados para {nombre}: {self.kb.objetivos(personaje)}.'
        if escenario:
            texto += f' Escenario consultado: {ESCENARIOS.get(escenario, escenario)}.'
        return (texto + ' Estos objetivos provienen de Characters y no están diferenciados '
                'por escenario; no son valores mínimos universales para ganar.')

    def _h_cartas_soporte(self, ent):
        """Explica cartas de soporte y sus categorías."""
        filas = self._filas_mencionadas(ent, ["carta", "rareza"])
        self.ctx.set_tema("cartas_soporte", carta=ent.get("k_carta"), rareza=ent.get("k_rareza"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("cartas_soporte")

    @staticmethod
    def _estadistica_carta(ent: Dict[str, str]) -> Optional[str]:
        """Acepta únicamente estadísticas válidas, nunca conceptos como «mazo»."""
        estadisticas_validas = {"Speed", "Stamina", "Power", "Guts", "Wit", "Pal"}
        concepto = ent.get("k_carta", "")
        if concepto.endswith("(carta)"):
            candidata = concepto.split(" (", 1)[0].capitalize()
            if candidata in estadisticas_validas:
                return candidata
        explicita = ent.get("k_stat", "").capitalize()
        return explicita if explicita in estadisticas_validas else None

    def _continuidad_cartas(self, ent: Dict[str, str]) -> bool:
        """Solo hereda filtros cuando continúa el mismo personaje y la misma intención."""
        anterior = self.ctx.tema or {}
        return anterior.get("intent") == "cartas_recomendadas" and (
            not ent.get("personaje") or ent["personaje"] == anterior.get("personaje")
        )

    def _filtros_cartas(self, ent) -> Dict[str, Optional[str]]:
        """Resuelve filtros válidos, sin heredar restricciones de otro personaje."""
        continuidad = self._continuidad_cartas(ent)
        anterior = self.ctx.tema or {}
        pref_nuevas = preferencias(self._texto, ent)
        stat = self._estadistica_carta(ent)
        if continuidad and not stat:
            stat = anterior.get("stat")
        # Un cambio de personaje no debe mantener el escenario de una búsqueda previa.
        escenario_explicito = self._clave_escenario(ent.get("k_escenario"))
        esc = escenario_explicito or (self.ctx.slots["escenario"] if continuidad else None)
        rareza = pref_nuevas.get("rareza", anterior.get("rareza") if continuidad else None)
        # Los sinónimos F2P de la base de conocimiento no significan «solo SR».
        if not self.gestor_confianza and "rareza" not in pref_nuevas:
            entidad_rareza = ent.get("k_rareza")
            if entidad_rareza and not pref_nuevas.get("f2p"):
                rareza = entidad_rareza
        if pref_nuevas.get("sin_ssr") and rareza == "SSR":
            rareza = None
        return {"escenario": esc, "stat": stat, "rareza": rareza}

    def _h_sustituciones_cartas(self, ent):
        """Propone SR por rol como alternativas ilustrativas a SSR, sin inventar inventario.

        La correspondencia compara la estadística principal y compatibilidad; no
        afirma equivalencia de habilidades, costos ni propiedad de las cartas.
        """
        tema = self.ctx.tema or {}
        if tema.get("intent") != "cartas_recomendadas":
            return "Primero dime para qué personaje necesitas cartas y después te propongo alternativas SR."
        pref = dict(self.ctx.preferencias)
        pref.pop("sin_ssr", None)
        pref.pop("rareza", None)
        personaje = tema.get("personaje")
        escenario = tema.get("escenario")
        stat = tema.get("stat")
        ssr = ordenar(self.kb, escenario, stat, "SSR", personaje, pref)
        sr = ordenar(self.kb, escenario, stat, "SR", personaje, pref)
        parejas = []
        for origen in ssr:
            rol = self.kb.cartas[origen["id"]]["stat"]
            alternativa = next((c for c in sr if self.kb.cartas[c["id"]]["stat"] == rol), None)
            if alternativa and (rol, alternativa["id"]) not in {(r, a) for r, a, _ in parejas}:
                parejas.append((rol, alternativa["id"], origen["id"]))
            if len(parejas) >= 4:
                break
        if not parejas:
            return "No encontré parejas SSR/SR del mismo rol con tus filtros actuales. Puedes indicar qué carta necesitas sustituir o cambiar las restricciones."
        partes = ["Alternativas SR orientativas por el mismo rol (no equivalencias exactas):"]
        for rol, alternativa, origen in parejas:
            partes.append(f"• {self.kb.etiqueta_carta(origen)} → {self.kb.etiqueta_carta(alternativa)} ({rol}).")
        partes.append("No conozco cuáles SSR tienes; si me dices las que te faltan, puedo acotar la búsqueda. No cambié tus preferencias guardadas.")
        return "\n".join(partes)

    def _h_cartas_recomendadas(self, ent):
        """Calcula primero la recomendación y confirma el contexto solo si es válida."""
        continuidad = self._continuidad_cartas(ent)
        f = self._filtros_cartas(ent)
        nuevas = preferencias(self._texto, ent)
        pref = dict(self.ctx.preferencias) if continuidad else {}
        pref.update(nuevas)
        if nuevas.get("rareza") == "SSR":
            pref["sin_ssr"] = False
        if pref.get("sin_ssr") and f["rareza"] == "SSR":
            f["rareza"] = None
        # El personaje del contexto puede usarse aunque el tema anterior no fuera de cartas.
        # No se heredan por ello los filtros de una recomendación anterior.
        personaje = ent.get("personaje") or self.ctx.slots["personaje"]
        filas = ordenar(self.kb, f["escenario"], f["stat"], f["rareza"], personaje, pref)
        if not filas:
            self._recomendacion_sin_resultados = True
            filtros = [f"{clave}={valor}" for clave, valor in f.items() if valor]
            filtros.extend(f"{clave}={valor}" for clave, valor in pref.items() if valor is not None)
            descripcion = ", ".join(filtros) if filtros else "ninguno"
            return ("No encontré cartas con estos filtros: " + descripcion +
                    ". No cambié tus preferencias anteriores. Puedes ajustar las restricciones.")
        self.ctx.preferencias = pref
        # Conservar modo mazo en seguimientos; cambiar de personaje crea una búsqueda nueva.
        solicita_lista = bool(re.search(r"\b(?:mejores cartas|recomiendame cartas|lista de cartas|cartas recomendadas)\b", self._norm))
        modo = ("mazo" if re.search(r"\b(?:mazo|deck|build|armame)\b", self._norm)
                else None if solicita_lista
                else (self.ctx.tema or {}).get("modo") if continuidad else None)
        self.ctx.set_tema("cartas_recomendadas", **f, personaje=personaje, modo=modo)
        if modo == "mazo":
            resultado = construir_mazo(self.kb, f['escenario'], f['rareza'], personaje, pref, f['stat'])
            return explicar_mazo(self.kb, resultado, personaje, f['escenario'], pref)
        return self._pagina_cartas(self.ctx.tema, 0)

    def _pagina_cartas(self, tema, pagina):
        """Presenta una página estable de recomendaciones y explica sus restricciones."""
        personaje = tema.get("personaje")
        pref = self.ctx.preferencias
        filas = ordenar(self.kb, tema.get("escenario"), tema.get("stat"), tema.get("rareza"), personaje, pref)
        seleccion = filas[pagina * _TAM_PAGINA:(pagina + 1) * _TAM_PAGINA]
        if not seleccion:
            if pagina:
                return None
            criterios = [f"{k}={v}" for k, v in tema.items()
                         if k in ("escenario", "stat", "rareza", "personaje") and v]
            criterios += [f"{k}={v}" for k, v in pref.items() if v is not None]
            return ("No encontré cartas con estos filtros: " + (", ".join(criterios) or "ninguno") +
                    ". Puedes cambiar distancia, estilo, pista, rareza o escenario. "
                    "No se han relajado tus restricciones.")
        titulo = "Otras opciones" if pagina else "Cartas recomendadas"
        titulo += " para " + self.kb.nombre_personaje(personaje) if personaje else " del catálogo"
        titulo += " — " + (ESCENARIOS[tema["escenario"]] if tema.get("escenario") else "sin escenario específico")
        metas = objetivos(self.kb, personaje, pref)
        filtros = [f"{k}: {', '.join(sorted(v))} ({'solicitado' if exp else 'inferido por aptitudes'})" for k, (v, exp) in metas.items()]
        if tema.get("stat"): filtros.append("stat: " + tema["stat"])
        if tema.get("rareza"): filtros.append("rareza: " + tema["rareza"])
        if pref.get("sin_ssr"): filtros.append("sin SSR")
        if pref.get("f2p"): filtros.append("preferencia F2P (prioridad, no exclusión)")
        partes = [titulo + "."]
        if filtros: partes.append("Criterios: " + "; ".join(filtros) + ".")
        if personaje:
            ficha = self.kb.personajes[personaje]
            bajas = [f"{k} {x.upper()} (aptitud {ficha[x]})" for k,(v,exp) in metas.items() if exp for x in v if ficha[x] not in ("S", "A")]
            if bajas: partes.append("Atención: " + ", ".join(bajas) + "; la preferencia explícita se conserva.")
        partes.extend(f"{pagina * _TAM_PAGINA + i}. {describir(self.kb, fila)}" for i, fila in enumerate(seleccion, 1))
        partes.append("Orden orientativo por compatibilidad y bonos registrados; no es un mazo optimizado. Los bonos corresponden al límite indicado, no necesariamente al nivel que posees.")
        if pref.get("f2p"):
            con_evidencia = sum(1 for r in filas if r.get("f2p"))
            partes.append(f"F2P: {con_evidencia} de {len(filas)} candidatas cuentan con evidencia de gratuidad en el catálogo; "
                          "aparecen primero. Las demás tienen disponibilidad desconocida, no necesariamente son de pago. "
                          "No conozco tu inventario ni la disponibilidad actual del juego.")
        partes.append(f"Mostrando {pagina * _TAM_PAGINA + 1}–{pagina * _TAM_PAGINA + len(seleccion)} de {len(filas)}.")
        if (pagina+1)*_TAM_PAGINA < len(filas): partes.append("Puedes pedir más opciones.")
        return "\n".join(partes)

    def _h_distancias_aptitudes(self, ent):
        """Explica aptitudes de pista, distancia y estilo."""
        self.ctx.set_tema("distancias_aptitudes")
        m = _RX_LETRA.search(self._texto)
        if m and not self._filas_mencionadas(ent, ["distancia", "pista", "estilo"]):
            letra = m.group(1)
            return self._elegir("_aptitud_letra", letra=letra, significado=_SIGNIFICADO_LETRA[letra])
        filas = self._filas_mencionadas(ent, ["aptitud", "distancia", "pista", "estilo"])
        return self._respuesta_conocimiento(filas) if filas else self._elegir("distancias_aptitudes")

    def _h_distancia_pista_recomendada(self, ent):
        """Consulta aptitudes para recomendar pistas y distancias."""
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
        """Construye la ficha del personaje o solicita su nombre."""
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
        """Consulta personajes recomendados para principiantes."""
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
        """Explica objetos y recompensas."""
        filas = self._filas_mencionadas(ent, ["item"])
        self.ctx.set_tema("recompensas_items", item=ent.get("k_item"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("recompensas_items")

    def _h_mejor_escenario(self, ent):
        """Explica o recomienda escenarios."""
        filas = self._filas_mencionadas(ent, ["escenario"])
        if filas:
            self.ctx.set_tema("mejor_escenario", escenario=ent["k_escenario"])
            return self._respuesta_conocimiento(filas)
        self.ctx.actualizar_slots({"escenario": "ura_finale"})  
        self.ctx.set_tema("mejor_escenario")
        return self._elegir("mejor_escenario")

    def _h_herencias(self, ent):
        """Explica los conceptos de herencia."""
        filas = self._filas_mencionadas(ent, ["herencia"])
        self.ctx.set_tema("herencias", color=ent.get("k_herencia"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("herencias")

    def _h_habilidades_comprar(self, ent):
        """Explica las habilidades y sus categorías."""
        filas = self._filas_mencionadas(ent, ["habilidad"])
        self.ctx.set_tema("habilidades_comprar", tipo=ent.get("k_habilidad"))
        return self._respuesta_conocimiento(filas) if filas else self._elegir("habilidades_comprar")

    def _h_subir_nivel(self, ent):
        """Explica la progresión de nivel."""
        self.ctx.set_tema("subir_nivel")
        return self._elegir("subir_nivel")

    def _h_info_carta(self, ent):
        """Consulta los efectos y límites de una carta."""
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
        """Construye una etiqueta legible del tema activo."""
        i = t["intent"]
        if i == "objetivos_stats": return "los objetivos de estadísticas del personaje"
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
        """Recupera información adicional o pagina recomendaciones."""
        i, kb = t["intent"], self.kb
        todas = lambda cat: " ".join(f"{f['name'][0].upper() + f['name'][1:]}: {f['detail']}." for f in kb.filas(cat) if f["detail"])
        if i == "cartas_recomendadas":
            if t.get('modo') == 'mazo':
                return 'Este mazo ya contiene sus seis espacios posibles. Cambia distancia, escenario o rareza para generar otra propuesta.'
            return self._pagina_cartas(t, nivel + 1)
        if i == "objetivos_stats":
            return 'Las metas proceden de Characters; no se dispone de objetivos específicos por escenario.'
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
        """Amplía el tema activo o resuelve un cambio de escenario."""
        ctx = self.ctx
        t = ctx.tema
        if not t:
            return self._aclarar_tema()
        if t["intent"] in ("cartas_recomendadas", "mejor_escenario") and (
                ent.get("k_escenario") or _RX_OTRO_ESC.search(self._norm)):
            if not ent.get("k_escenario") and not ctx.slots["escenario"]:
                return "¿Te refieres a URA Finale o Unity Cup? Indica el escenario para continuar."
            if not ent.get("k_escenario"):
                otro = "unity_cup" if ctx.slots["escenario"] == "ura_finale" else "ura_finale"
                ent = dict(ent, k_escenario=ESCENARIOS[otro]); ctx.slots["escenario"] = otro
            return getattr(self, "_h_" + t["intent"])(ent)
        texto = self._detalle(t, ctx.nivel_detalle)
        if texto is None:
            return ("No quedan más cartas que cumplan tus filtros. Puedes cambiar alguno para ampliar la búsqueda."
                    if t["intent"] == "cartas_recomendadas" else self._elegir("_sin_mas_detalle"))
        ctx.nivel_detalle += 1
        return self._elegir("pedir_mas_detalle", tema=self._etiqueta_tema(t)).rstrip() + " " + texto

    def _aclarar_tema(self):
        """Solicita un tema cuando falta contexto."""
        return self._elegir("_aclarar_tema")
