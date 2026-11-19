"""Resuelve continuaciones breves y elecciones explícitas sin alterar el clasificador.
Las preferencias se guardan como datos del diálogo; los filtros nuevos serán usados
por el recomendador en la etapa 5.4.
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


def preferencias(texto, ent):
    """Extrae preferencias explícitas, separando F2P de rareza y evitando deducir inventario."""
    norm = normalizar(texto)
    valores = {k: ent['k_' + k] for k in ('distancia', 'pista', 'estilo', 'stat') if 'k_' + k in ent}
    if re.search(r'\b(f2p|free to play|free 2 play|gratis|gratuitas?|economicas?)\b', norm):
        valores['f2p'] = True
    if re.search(r'\b(?:sin ssr|no tengo ssr)\b', norm):
        valores['sin_ssr'] = True
    if re.search(r'\b(?:con ssr|si tengo ssr|tambien ssr)\b', norm):
        valores['sin_ssr'] = False
    if re.search(r'\b(?:no soy f2p|sin restriccion de presupuesto)\b', norm):
        valores['f2p'] = False
    if re.search(r'\b(?:sr|ssr|carta r|rareza r)\b', norm) and not re.search(r'\b(?:sin ssr|no tengo ssr|con ssr|si tengo ssr|tambien ssr)\b', norm):
        # La rareza explícita tiene prioridad sobre los alias F2P de DBCv3.
        m = re.search(r'\b(ssr|sr|carta r|rareza r)\b', norm)
        valores['rareza'] = m.group(1).split()[-1].upper()
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
    """Detecta continuaciones de forma conservadora para no secuestrar preguntas nuevas."""
    norm = normalizar(texto)
    tema = (ctx.tema or {}).get('intent')
    if not tema:
        return None
    if re.fullmatch(r'(?:y )?(?:explicame mas|cuentame mas|dame mas opciones|que mas|mas detalles|continua)', norm):
        return 'pedir_mas_detalle'
    if tema == 'cartas_recomendadas':
        if re.fullmatch(r'(?:y )?(?:para )?(?:ella|el|esa uma|ese personaje)', norm):
            return tema
        pref = preferencias(texto, ent)
        if pref and (solo_entidad or re.fullmatch(r"(?:y )?para (?:carreras )?(?:largas?|medias?|cortas?|milla)(?: y (?:que sean )?(?:f2p|gratis|economicas))?", norm) or re.fullmatch(r'(?:y )?(?:si )?(?:no tengo ssr|sin ssr|con ssr|si tengo ssr|tambien ssr|cualquier rareza|todas las rarezas|no soy f2p|sin restriccion de presupuesto)', norm)):
            return tema
        if ent.get('personaje') and solo_entidad:
            return tema
    if tema in ('info_personaje', 'distancia_pista_recomendada') and re.fullmatch(r'(?:y )?(?:en )?que (?:distancia|pista|estilo)(?: le conviene(?: correr)?| tiene| usa)?', norm):
        return 'distancia_pista_recomendada'
    return None
