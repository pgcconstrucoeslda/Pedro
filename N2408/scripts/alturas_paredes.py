"""Atribui a cada linha de acabamento de parede a altura do teto do compartimento (legenda dos tetos).

Para cada par (planta de paredes, planta de tetos) do mesmo piso:
1. Desvio entre as duas plantas = moda dos deslocamentos entre blocos iguais (portas, louças).
2. Polígonos dos tetos (hatches com descrição) deslocados para as coordenadas da planta de paredes.
3. Cada linha de acabamento: ponto médio deslocado 8 cm para cada lado (a linha está na face da parede);
   o lado que cai dentro de um teto dá a altura ("ALTURA: 260cm" na legenda).
Saída: json/alturas/<parede>.json  {handle: {altura_m, handle_teto, teto, lado_cm}}
"""
import json, math, re, collections, sys
import ezdxf
from ezdxf import path as P
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree

RAIZ = '/home/user/Pedro/N2408'
PARES = [('3-05', '3-10'), ('3-06', '3-11'), ('3-07', '3-12'), ('3-08', '3-13')]


def desvio(jp, jt):
    a = collections.defaultdict(list); b = collections.defaultdict(list)
    for d, m in ((jp, a), (jt, b)):
        for e in d['entidades']:
            if e['tipo'] == 'INSERT' and e['x'] is not None and not e['legenda']:
                m[e['padrao_bloco']].append((e['x'], e['y']))
    c = collections.Counter()
    for k in a:
        if k in b and len(a[k]) <= 20 and len(b[k]) <= 20:
            for p in a[k]:
                for q in b[k]:
                    c[(round(q[0] - p[0], 1), round(q[1] - p[1], 1))] += 1
    (dx, dy), n = c.most_common(1)[0]
    return dx, dy, n, sum(c.values())


def altura(desc):
    m = re.search(r'ALTURA:\s*(\d{3})\s*cm', desc or '')
    return int(m.group(1)) / 100 if m else None


for par, tet in PARES:
    jp = json.load(open(f'{RAIZ}/json/ARQ/03-Acabamentos/Paredes/{par}.json'))
    jt = json.load(open(f'{RAIZ}/json/ARQ/03-Acabamentos/Tetos/{tet}.json'))
    dx, dy, n, tot = desvio(jp, jt)
    st = jt['escala_m']
    info_t = {e['handle']: e for e in jt['entidades']}
    doc_t = ezdxf.readfile(f'{RAIZ}/dxf/ARQ/03-Acabamentos/Tetos/{tet}.dxf')
    polys, meta = [], []
    for h in doc_t.modelspace().query('HATCH'):
        r = info_t.get(h.dxf.handle)
        if not r or r['legenda'] or not r['descricao']:
            continue
        geo = None
        for p in P.from_hatch(h):
            v = [(q.x * st - dx, q.y * st - dy) for q in p.flattening(0.01)]
            if len(v) > 2:
                pg = Polygon(v).buffer(0)
                geo = pg if geo is None else geo.symmetric_difference(pg)
        if geo is not None and not geo.is_empty:
            polys.append(geo); meta.append((h.dxf.handle, r['descricao'], altura(r['descricao'])))
    arv = STRtree(polys)

    sp = jp['escala_m']
    info_p = {e['handle']: e for e in jp['entidades']}
    doc_p = ezdxf.readfile(f'{RAIZ}/dxf/ARQ/03-Acabamentos/Paredes/{par}.dxf')
    out = {}
    stats = collections.Counter()
    for e in doc_p.modelspace():
        r = info_p.get(e.dxf.handle)
        if not r or r['legenda'] or not r['descricao'] or r['tipo'] == 'HATCH' or r['tipo'] == 'INSERT':
            continue
        try:
            pts = [(q.x * sp, q.y * sp) for q in P.make_path(e).flattening(0.01)]
        except Exception:
            continue
        if len(pts) < 2:
            continue
        # segmento mais comprido da entidade
        i = max(range(len(pts) - 1), key=lambda k: math.dist(pts[k], pts[k + 1]))
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        L = math.dist((x1, y1), (x2, y2)) or 1
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        nx, ny = -(y2 - y1) / L, (x2 - x1) / L
        res = None
        for off in (0.08, 0.20, 0.40):
            achados = []
            for sgn in (1, -1):
                pt = Point(mx + sgn * off * nx, my + sgn * off * ny)
                for idx in arv.query(pt):
                    if polys[idx].contains(pt):
                        achados.append((idx, sgn)); break
            if achados:
                # preferir o teto com altura definida
                achados.sort(key=lambda t: meta[t[0]][2] is None)
                idx, sgn = achados[0]
                res = {'altura_m': meta[idx][2], 'handle_teto': meta[idx][0], 'teto': meta[idx][1][:120], 'lado_cm': int(off * 100)}
                break
        if res is None:
            res = {'altura_m': None, 'handle_teto': None, 'teto': 'sem teto encontrado', 'lado_cm': None}
            stats['sem teto'] += 1
        elif res['altura_m'] is None:
            stats['teto sem altura'] += 1
        else:
            stats['ok'] += 1
        out[e.dxf.handle] = res
    import os
    os.makedirs(f'{RAIZ}/json/alturas', exist_ok=True)
    json.dump({'desvio_m': [dx, dy], 'votos': [n, tot], 'linhas': out}, open(f'{RAIZ}/json/alturas/{par}.json', 'w'), ensure_ascii=False)
    print(par, tet, 'desvio', (dx, dy), f'{n}/{tot} votos', dict(stats))
