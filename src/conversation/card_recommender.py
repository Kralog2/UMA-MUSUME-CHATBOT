"""Etapa 10: recomienda cartas con disponibilidad F2P estructurada y verificable.

Separa rareza de accesibilidad, prioriza disponibilidad documentada cuando
el usuario pide F2P y mantiene compatibilidad, bonos y procedencia del dato.
Una disponibilidad vacía significa DESCONOCIDA; no equivale a 0.
"""

MAPAS = {'distancia': {'media':'medium','larga':'long','sprint':'sprint','mile':'mile'},
         'estilo': {'front runner':'front','pace chaser':'pace','late surger':'late','end closer':'end'},
         'pista': {'turf':'turf','dirt':'dirt'}}
COLUMNAS = {'distancia':'distance','estilo':'style','pista':'track'}


def objetivos(kb, personaje, pref):
    """Prioriza valores explícitos; si faltan, recupera todas las mejores aptitudes del personaje."""
    res = {}
    ficha = kb.personajes.get(personaje, {})
    for campo, mapa in MAPAS.items():
        valor = pref.get(campo)
        if valor in mapa:
            res[campo] = ({mapa[valor]}, True)
        elif ficha:
            cols = set(mapa.values())
            mejor = min('SABCDEFG'.index(ficha[c]) for c in cols)
            res[campo] = ({c for c in cols if 'SABCDEFG'.index(ficha[c]) == mejor}, False)
    return res


def ordenar(kb, escenario=None, stat=None, rareza=None, personaje=None, pref=None):
    """Aplica restricciones de catálogo y ordena por evidencia de compatibilidad y bonos MLB disponibles."""
    pref = pref or {}
    metas = objetivos(kb, personaje, pref)
    ficha = kb.personajes.get(personaje, {})
    filas = []
    for cid, c in kb.cartas.items():
        if escenario and c['scenario'] not in (escenario, 'both'): continue
        if stat and c['stat'].lower() != stat.lower(): continue
        if rareza and c['rarity'] != rareza: continue
        if pref.get('sin_ssr') and c['rarity'] == 'SSR': continue
        if ficha and kb.nombre_personaje(personaje).casefold() == c['card'].split(' (')[0].casefold(): continue
        razones, puntos, incompatible = [], 0, False
        for campo, (valores, explicito) in metas.items():
            tags = set(c[COLUMNAS[campo]].split('|'))
            if 'any' in tags:
                puntos += 1
                razones.append(f'{campo}: uso general (any)')
            elif tags & valores:
                puntos += 4 if explicito else 2
                razones.append(f'{campo} compatible ({", ".join(sorted(tags & valores))})')
            elif explicito:
                incompatible = True
                break
            else:
                puntos -= 2
                razones.append(f'{campo} especializado fuera de sus mejores aptitudes')
        if incompatible: continue
        efectos = kb.efectos.get(cid, {})
        lb, e = kb.efecto(cid, 'MLB') if efectos else ('sin datos', {})
        bonos = sum(int(e.get(k) or 0) for k in ('training_eff_pct','friendship_bonus_pct','race_bonus_pct'))
        # No interpretar una nota libre como la clasificación de accesibilidad.
        # Los campos proceden del Excel y pueden registrar disponibilidad desconocida.
        f2p_estado = c.get('f2p', '').strip()
        f2p_evidencia = f2p_estado == '1'
        if pref.get('f2p') and f2p_evidencia:
            razones.append('disponibilidad F2P documentada en el catálogo')
        elif pref.get('f2p') and not f2p_estado:
            razones.append('disponibilidad F2P no documentada')
        if not razones: razones.append('opción general del catálogo')
        filas.append(dict(id=cid, puntos=puntos, bonos=bonos, lb=lb, efecto=e,
                          razones=razones, f2p=f2p_evidencia, f2p_estado=f2p_estado,
                          f2p_fuente=c.get('f2p_fuente', '')))
    # Preferencia F2P: la accesibilidad documentada gana al puntaje.
    # Sin preferencia: compatibilidad > bonos > rareza > identificador estable.
    orden_rareza = {'SSR': 0, 'SR': 1, 'R': 2}
    def clave_orden(fila):
        """Ordena primero F2P si se pidió; deja disponibilidad desconocida detrás."""
        c = kb.cartas[fila['id']]
        prioridad_f2p = -int(fila['f2p']) if pref.get('f2p') else 0
        return (prioridad_f2p, -fila['puntos'], -fila['bonos'],
                orden_rareza.get(c['rarity'], 9), fila['id'])
    return sorted(filas, key=clave_orden)


def describir(kb, fila):
    """Explica la compatibilidad y muestra bonos registrados, indicando el límite de la carta."""
    c = kb.cartas[fila['id']]
    e = fila['efecto']
    texto = kb.etiqueta_carta(fila['id']) + ': ' + '; '.join(fila['razones'])
    if e:
        texto += f". En {fila['lb']}: entrenamiento {e['training_eff_pct']}%, amistad {e['friendship_bonus_pct']}%, carrera {e['race_bonus_pct']}%"
    texto += ". Escenario: " + {'both':'URA Finale y Unity Cup','ura_finale':'URA Finale','unity_cup':'Unity Cup'}.get(c['scenario'],c['scenario'])
    if fila.get('f2p') and fila.get('f2p_fuente'):
        texto += f". Evidencia F2P registrada: {fila['f2p_fuente']}"
    if c['skill']: texto += f". Habilidad registrada: {c['skill']}"
    return texto + '.'
