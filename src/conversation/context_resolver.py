"""Etapa 9: reconoce continuaciones, rarezas y negaciones del lenguaje cotidiano.

Separa restricciones explícitas de inventario desconocido; no modifica el SVM.
Todas las funciones devuelven valores nuevos, sin alterar el contexto recibido.
"""
import re
from .knowledge_base import normalizar

ETIQUETAS = {
    'cartas_recomendadas': 'recomendaciones de cartas', 'cartas_soporte': 'cómo funcionan las cartas de soporte',
    'info_carta': 'información de una carta concreta', 'info_personaje': 'información de un personaje',
    'distancia_pista_recomendada': 'la pista o distancia adecuada para una uma', 'distancias_aptitudes': 'las aptitudes',
    'subir_nivel': 'subir de nivel', 'herencias': 'las herencias', 'mejor_escenario': 'los escenarios',
    'habilidades_comprar': 'las habilidades', 'stats_funcion': 'las estadísticas', 'recompensas_items': 'los objetos',
    'uma_facil_entrenar': 'umas para principiantes', 'pedir_mas_detalle': 'ampliar el tema anterior',
}


# Los cuantificadores «todas»/«algunas» no equivalen a «ninguna».
_NEGACION_TOTAL = re.compile(
    r"\b(?:sin ssr|no (?:tengo|tener|uso|cuento con)(?: [a-z0-9]+){0,4} (?:ninguna? (?:carta )?)?ssr)\b"
)
_NEGACION_PARCIAL = re.compile(
    r"\b(?:no (?:tengo|cuento con|poseo) (?:todas|cada una|las suficientes)(?: (?:las|de|cartas|carta|de soporte)){0,4} ssr|"
    r"(?:me faltan|no tengo algunas de) (?:las |cartas )*ssr)\b"
)
_PEDIR_SUSTITUTOS = re.compile(
    r"\b(?:sustitu(?:ir|yo|yas|ye|yen|ciones?)|sustitutas?|reemplaz(?:ar|o|os|os?)|"
    r"cambiar(?:las|los)?|alternativas?|por cuales (?:las|los) cambio|cuales uso)\b"
)


def analizar_ssr(texto):
    """Distingue ausencia total de SSR, posesión parcial y petición de alternativas.

    No inventa cuáles SSR posee el usuario; interpreta «no todas» como inventario parcial.
    """
    norm = normalizar(texto)
    parcial = bool(_NEGACION_PARCIAL.search(norm))
    # «sin SSR» y «ninguna SSR» sí son restricciones globales.
    total = bool(re.search(r"\b(?:sin ssr|no (?:tengo|uso|poseo|cuento con) (?:(?:ninguna? (?:carta )?|cualquier ))?ssr)\b", norm)) and not parcial
    # «no tengo las SSR» expresa ausencia de las SSR aludidas, no de todas las del juego.
    faltan_especificas = bool(re.search(r"\bno tengo (?:las |esas |estas )ssr\b", norm))
    pide_alternativas = bool(_PEDIR_SUSTITUTOS.search(norm)) or bool(re.search(
        r"\b(?:cuales? (?:cartas? )?sr (?:uso|utilizo|recomiendas)|que (?:cartas? )?sr (?:uso|utilizo))\b", norm))
    return {
        "parcial": parcial,
        "sin_ssr": total,
        "faltan_especificas": faltan_especificas,
        "sustituciones": pide_alternativas and (bool(re.search(r"\bssr\b", norm)) or parcial or faltan_especificas),
    }


def preferencias(texto, ent):
    """Extrae restricciones positivas sin convertir F2P ni ausencia parcial en rareza SR."""
    norm = normalizar(texto)
    valores = {k: ent['k_' + k] for k in ('distancia', 'pista', 'estilo', 'stat') if 'k_' + k in ent}
    if re.search(r'\b(f2p|free to play|free 2 play|gratis|gratuitas?|economicas?)\b', norm):
        valores['f2p'] = True
    if re.search(r'\b(?:no soy f2p|sin restriccion de presupuesto)\b', norm):
        valores['f2p'] = False
    estado = analizar_ssr(texto)
    if estado['sin_ssr']:
        valores['sin_ssr'] = True
    if re.search(r'\b(?:con ssr|si tengo ssr|tambien ssr)\b', norm):
        valores['sin_ssr'] = False
    # «SSR ... SR» pide alternativas SR; la primera mención no es un filtro.
    sustitucion_sr = bool(re.search(r'\b(?:sr|rar(eza)? sr)\b', norm) and
                          (estado['sustituciones'] or estado['faltan_especificas']))
    if sustitucion_sr:
        valores['rareza'] = 'SR'
    elif not (estado['parcial'] or estado['faltan_especificas'] or estado['sustituciones'] or estado['sin_ssr']):
        rarezas = re.findall(r'\b(ssr|sr|carta r|rareza r)\b', norm)
        if len(set(rarezas)) == 1 and rarezas:
            valores['rareza'] = rarezas[0].split()[-1].upper()
    if re.search(r'\b(?:cualquier rareza|todas las rarezas)\b', norm):
        valores['rareza'] = None
        valores['sin_ssr'] = False
    return valores


def elegir_opcion(texto, opciones):
    """Reconoce una elección explícita por número, ordinal o etiqueta; no interpreta un sí ambiguo."""
    norm = normalizar(texto)
    for idx, opcion in enumerate(opciones):
        ordinal = ('primera', 'segunda')[idx]
        if norm in {str(idx + 1), 'opcion ' + str(idx + 1), 'la ' + ordinal, ordinal, normalizar(ETIQUETAS[opcion]), normalizar(opcion)}:
            return opcion
    return None


def seguimiento(texto, ent, ctx, solo_entidad):
    """Reconoce mensajes breves que modifican cartas sin secuestrar consultas nuevas.

    Verbos como «háblame» abren una petición distinta. La longitud limita los
    seguimientos con escenario/rareza; el resto va al clasificador habitual.
    """
    norm = normalizar(texto)
    tema = (ctx.tema or {}).get('intent')
    if not tema:
        return None
    if re.fullmatch(r'(?:y )?(?:explicame mas|cuentame mas|dame mas opciones|que mas|mas detalles|continua)', norm):
        return 'pedir_mas_detalle'
    if tema == 'cartas_recomendadas':
        if re.fullmatch(r'(?:y )?(?:para )?(?:ella|el|esa uma|ese personaje)', norm):
            return tema
        tokens = norm.split()
        # Un cambio de escenario debe conservar filtros y entrar al recomendador.
        escenario = bool(ent.get('k_escenario')) or bool(re.search(r'\b(?:otro escenario|ura final|unity cup)\b', norm))
        rareza = bool(re.search(r'\b(?:ssr|sr|rareza)\b', norm))
        pref = preferencias(texto, ent)
        es_peticion_nueva = bool(re.match(r'^(?:hablame|cuentame|dime|explicame)\b', norm))
        if len(tokens) <= 14 and not es_peticion_nueva and (escenario or rareza or pref):
            return tema
        if ent.get('personaje') and solo_entidad and not es_peticion_nueva:
            return tema
    if tema in ('info_personaje', 'distancia_pista_recomendada') and re.fullmatch(
            r'(?:y )?(?:en )?que (?:distancia|pista|estilo)(?: le conviene(?: correr)?| tiene| usa)?', norm):
        return 'distancia_pista_recomendada'
    return None
