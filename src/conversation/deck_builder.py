"""Etapa 11: construye un mazo orientativo de seis cartas por roles.

Utiliza exclusivamente el catálogo local, los objetivos de estadísticas del personaje
 y las restricciones vigentes. No estima probabilidades de victoria ni inventarios.
"""
from collections import Counter
from .card_recommender import ordenar

ROLES = ("Speed", "Stamina", "Power", "Wit", "Guts", "Pal")


def necesidades(kb, personaje, pref=None, escenario=None):
    """Calcula seis cupos por rol con objetivos registrados y distancia solicitada."""
    pref = pref or {}
    # Cuatro pilares de entrenamiento y dos cupos adicionales orientativos.
    cupos = {"Speed": 1, "Stamina": 1, "Power": 1, "Wit": 1, "Guts": 0, "Pal": 0}
    ficha = kb.personajes.get(personaje, {}) if personaje else {}
    metas = {rol: int(ficha.get(col) or 0) for rol, col in (
        ("Speed", "spd_goal"), ("Stamina", "sta_goal"),
        ("Power", "pow_goal"), ("Wit", "wit_goal"), ("Guts", "gut_goal"))}
    # En carreras largas resulta razonable reforzar Stamina, pero no imponer
    # un objetivo numérico diferente al que proporciona Characters.
    distancia = pref.get('distancia')
    candidatos = ["Speed", "Stamina", "Power", "Wit", "Guts"]
    for _ in range(2):
        def prioridad(rol):
            adicional = 500 if distancia == 'larga' and rol == 'Stamina' else 0
            return ((metas[rol] + adicional) / (cupos[rol] + 1), -candidatos.index(rol))
        elegido = max(candidatos, key=prioridad)
        cupos[elegido] += 1
    # Pal es opción de apoyo solicitada explícitamente, no una obligación universal.
    if pref.get('stat') == 'Pal' or pref.get('rol_pal'):
        reemplazable = max((r for r in candidatos if cupos[r] > 1), key=lambda r: cupos[r], default=None)
        if reemplazable:
            cupos[reemplazable] -= 1
            cupos['Pal'] = 1
    return {r: n for r, n in cupos.items() if n}


def construir_mazo(kb, escenario=None, rareza=None, personaje=None, pref=None, stat=None):
    """Selecciona cartas distintas para cada cupo, sin relajar las restricciones."""
    pref = pref or {}
    plan = necesidades(kb, personaje, pref, escenario)
    candidatas = ordenar(kb, escenario, None, rareza, personaje, pref)
    if stat:
        # Una estadística indicada se trata como prioridad, no como filtro de
        # un único rol: un mazo de una sola estadística no sería equilibrado.
        if stat in plan:
            otro = max((r for r in plan if r != stat and plan[r] > 1), key=lambda r: plan[r], default=None)
            if otro:
                plan[otro] -= 1
                plan[stat] += 1
                if plan[otro] == 0:
                    del plan[otro]
    seleccion, faltantes = [], []
    usados = set()
    for rol, cantidad in plan.items():
        elegibles = [f for f in candidatas if kb.cartas[f['id']]['stat'] == rol and f['id'] not in usados]
        for fila in elegibles[:cantidad]:
            seleccion.append({'rol': rol, **fila})
            usados.add(fila['id'])
        if len(elegibles) < cantidad:
            faltantes.append({'rol': rol, 'cantidad': cantidad-len(elegibles)})
    return {'cartas': seleccion, 'roles': plan, 'faltantes': faltantes,
            'candidatas': len(candidatas), 'completo': len(seleccion) == 6 and not faltantes}


def explicar_mazo(kb, resultado, personaje=None, escenario=None, pref=None):
    """Redacta un resultado transparente, con roles, restricciones y vacantes."""
    pref = pref or {}
    nombre = kb.nombre_personaje(personaje) if personaje else 'el personaje que elijas'
    partes = [f'Mazo orientativo de 6 espacios para {nombre} ({len(resultado["cartas"])} seleccionadas).',
             'Distribución de roles: ' + ', '.join(f'{r} ×{n}' for r, n in resultado['roles'].items()) + '.']
    for indice, fila in enumerate(resultado['cartas'], 1):
        partes.append(f'{indice}. [{fila["rol"]}] {kb.etiqueta_carta(fila["id"])}: '
                      + ', '.join(fila['razones'][:2]) + '.')
    if resultado['faltantes']:
        partes.append('No pude completar los seis espacios sin romper tus restricciones: ' +
                      ', '.join(f'{e["cantidad"]} de {e["rol"]}' for e in resultado['faltantes']) + '.')
    partes.append('Selección heurística basada en la base local; no garantiza un mazo óptimo, '
                  'no conoce las cartas que posees y los objetivos registrados no están desglosados por escenario.')
    return '\n'.join(partes)
