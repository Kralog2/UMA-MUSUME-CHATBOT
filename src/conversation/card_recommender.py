"""Ordena cartas según DBCv3, preferencias y aptitudes; explica los criterios sin inferir inventario."""

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
        f2p_evidencia = bool(pref.get('f2p') and any('f2p' in r.get('note','').lower() for r in efectos.values()))
        if f2p_evidencia:
            razones.append('descrita como opción F2P en DBCv3')
        if not razones: razones.append('opción general del catálogo')
        filas.append(dict(id=cid, puntos=puntos, bonos=bonos, lb=lb, efecto=e, razones=razones, f2p=f2p_evidencia))
    return sorted(filas, key=lambda r: (-r['puntos'], -int(r['f2p']), -r['bonos'], r['id']))


def describir(kb, fila):
    """Explica la compatibilidad y muestra bonos registrados, indicando el límite de la carta."""
    c = kb.cartas[fila['id']]
    e = fila['efecto']
    texto = kb.etiqueta_carta(fila['id']) + ': ' + '; '.join(fila['razones'])
    if e:
        texto += f". En {fila['lb']}: entrenamiento {e['training_eff_pct']}%, amistad {e['friendship_bonus_pct']}%, carrera {e['race_bonus_pct']}%"
    texto += ". Escenario: " + {'both':'URA Finale y Unity Cup','ura_finale':'URA Finale','unity_cup':'Unity Cup'}.get(c['scenario'],c['scenario'])
    if c['skill']: texto += f". Habilidad registrada: {c['skill']}"
    return texto + '.'
