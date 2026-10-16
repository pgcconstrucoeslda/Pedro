"""Extrai medições rastreáveis de um DXF (convertido do DWG pelo CADCraft).

Para cada entidade do espaço modelo: tipo, layer, cor, padrão/bloco, comprimento (m), área (m2),
posição e handle CAD. Deteta a legenda do desenho (amostra + texto à direita) e classifica cada
entidade com a descrição da legenda cuja amostra tem a mesma "chave" (tipo+layer+padrão+cor).

Uso: python3 extrair.py ficheiro.dxf  -> imprime JSON
"""
import json, math, re, sys, collections
import ezdxf
from ezdxf import path as P
from shapely.geometry import Polygon
from shapely.ops import unary_union

UNIDADES = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}


def cor(e, doc):
    tc = e.dxf.get('true_color', None)
    if tc is not None:
        return '#%06X' % tc
    aci = e.dxf.get('color', 256)
    if aci == 256:  # ByLayer
        try:
            lay = doc.layers.get(e.dxf.layer)
            if lay.dxf.get('true_color', None) is not None:
                return '#%06X' % lay.dxf.true_color
            aci = abs(lay.dxf.color)
        except Exception:
            return 'ByLayer'
    return 'ACI%d' % aci


def familia_bloco(nome):
    # Revit: "Família - Tipo-<id>-<vista>" -> "Família - Tipo"
    n = re.sub(r'-(V\d+|\d{4,})-.*$', '', nome)
    return n.strip()


def comprimento(e):
    t = e.dxftype()
    try:
        if t == 'LINE':
            return (e.dxf.end - e.dxf.start).magnitude
        if t == 'ARC':
            a = (e.dxf.end_angle - e.dxf.start_angle) % 360
            return math.radians(a) * e.dxf.radius
        if t == 'CIRCLE':
            return 2 * math.pi * e.dxf.radius
        if t in ('LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ELLIPSE'):
            pts = list(P.make_path(e).flattening(0.001 if t != 'SPLINE' else 0.01))
            return sum((pts[i + 1] - pts[i]).magnitude for i in range(len(pts) - 1))
    except Exception:
        return 0.0
    return 0.0


def area_hatch(h):
    """Área com regra par-ímpar (ilhas descontadas)."""
    geo = None
    try:
        for p in P.from_hatch(h):
            v = [(q.x, q.y) for q in p.flattening(0.01)]
            if len(v) < 3:
                continue
            pg = Polygon(v).buffer(0)
            geo = pg if geo is None else geo.symmetric_difference(pg)
    except Exception:
        return 0.0
    return geo.area if geo is not None else 0.0


def area_poly_fechada(e):
    try:
        if e.dxftype() == 'LWPOLYLINE' and e.closed:
            v = [(x, y) for x, y, *_ in e.get_points()]
            return Polygon(v).buffer(0).area if len(v) > 2 else 0.0
    except Exception:
        pass
    return 0.0


def bbox(e):
    try:
        from ezdxf import bbox as B
        b = B.extents([e], fast=True)
        if b.has_data:
            return (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)
    except Exception:
        pass
    return None


def texto(e):
    try:
        if e.dxftype() == 'MTEXT':
            return e.plain_text().replace('\n', ' ').strip(), e.dxf.char_height, e.dxf.insert
        return e.dxf.text.strip(), e.dxf.height, e.dxf.insert
    except Exception:
        return '', 0, None


def chave(e, doc):
    t = e.dxftype()
    if t == 'HATCH':
        return 'HATCH|%s|%s|%s' % (e.dxf.layer, e.dxf.pattern_name, cor(e, doc))
    if t == 'INSERT':
        return 'BLOCO|%s' % familia_bloco(e.dxf.name)
    if t in ('LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE', 'SPLINE', 'ELLIPSE'):
        return 'LINHA|%s|%s' % (e.dxf.layer, cor(e, doc))
    return None


def extrair(fn):
    doc = ezdxf.readfile(fn)
    msp = doc.modelspace()
    u = doc.header.get('$INSUNITS', 6)
    s = UNIDADES.get(u, 1.0)
    ents, textos = [], []
    vistos = set()
    for e in msp:
        t = e.dxftype()
        if t in ('TEXT', 'MTEXT'):
            tx, hh, ins = texto(e)
            if tx and ins is not None:
                textos.append({'t': tx, 'h': hh, 'x': ins.x, 'y': ins.y, 'handle': e.dxf.handle})
            continue
        k = chave(e, doc)
        if not k:
            continue
        if t == 'LINE':  # remove segmentos duplicados (exportações Revit)
            a, b = e.dxf.start, e.dxf.end
            sig = (k, tuple(sorted([(round(a.x, 4), round(a.y, 4)), (round(b.x, 4), round(b.y, 4))])))
            if sig in vistos:
                continue
            vistos.add(sig)
        bb = bbox(e)
        r = {'handle': e.dxf.handle, 'tipo': t, 'layer': e.dxf.layer, 'cor': cor(e, doc), 'chave': k,
             'padrao_bloco': e.dxf.get('pattern_name', '') if t == 'HATCH' else (familia_bloco(e.dxf.name) if t == 'INSERT' else ''),
             'comp_m': 0.0, 'area_m2': 0.0, 'bb': bb}
        if t == 'HATCH':
            r['area_m2'] = area_hatch(e) * s * s
        elif t == 'INSERT':
            pass
        else:
            r['comp_m'] = comprimento(e) * s
            r['area_m2'] = area_poly_fechada(e) * s * s
        ents.append(r)

    # ---- legenda: amostra à esquerda de um texto, na mesma linha, em coluna alinhada ----
    PRIO = {'HATCH': 0, 'INSERT': 1}
    por_texto = {}
    NEUTRAS = {'ACI0', 'ACI7', 'ACI8', 'ACI250', 'ACI251', 'ByLayer', '#777777', '#FFFFFF', '#000000', '#808080'}
    for r in ents:
        bb = r['bb']
        if not bb or (r['chave'].startswith('LINHA') and r['cor'] in NEUTRAS):
            continue
        w, hgt = bb[2] - bb[0], bb[3] - bb[1]
        cy = (bb[1] + bb[3]) / 2
        melhor = None
        for tx in textos:
            h = tx['h'] or 1
            if max(w, hgt) > 40 * h or max(w, hgt) < 0.5 * h:
                continue
            gap = tx['x'] - bb[2]
            ty = tx['y'] - h / 2  # MTEXT ancorado em cima
            if -0.5 * h <= gap <= 6 * h and abs(ty - cy) <= max(hgt / 2, h) + h:
                d = gap + abs(ty - cy)
                if melhor is None or d < melhor[0]:
                    melhor = (d, tx)
        if melhor:
            tx = melhor[1]
            pr = (PRIO.get(r['tipo'], 2), -(w * hgt))
            atual = por_texto.get(tx['handle'])
            if atual is None or pr < atual[0]:
                por_texto[tx['handle']] = (pr, r, tx)
    cand = [(r, tx) for _, r, tx in por_texto.values()]
    # coluna alinhada: >=3 amostras com o mesmo x mínimo
    col = collections.defaultdict(list)
    for r, tx in cand:
        col[round(r['bb'][0] / max(tx['h'], 1e-9) / 2)].append((r, tx))

    def coluna_valida(g):
        """Legenda verdadeira: amostras com espaçamento regular, tamanhos parecidos e chaves distintas."""
        if len(g) < 3:
            return False
        g = sorted(g, key=lambda it: -(it[0]['bb'][1] + it[0]['bb'][3]))
        cys = [(it[0]['bb'][1] + it[0]['bb'][3]) / 2 for it in g]
        gaps = sorted(cys[i] - cys[i + 1] for i in range(len(cys) - 1))
        med = gaps[len(gaps) // 2]
        if med <= 0:
            return False
        regulares = sum(1 for x in gaps if 0.5 * med <= x <= 3.5 * med) / len(gaps)
        chaves = len({it[0]['chave'] for it in g}) / len(g)
        ws = sorted(it[0]['bb'][2] - it[0]['bb'][0] for it in g)
        wmed = ws[len(ws) // 2]
        tam = sum(1 for x in ws if 0.6 * wmed <= x <= 1.6 * wmed) / len(ws)
        return regulares >= 0.7 and chaves >= 0.7 and tam >= 0.7

    validas = {k: sorted(g, key=lambda it: -(it[0]['bb'][1] + it[0]['bb'][3])) for k, g in col.items() if coluna_valida(g)}
    legenda = {}
    amostras = set()

    def sobrepoe(a, b):
        return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]

    hatch_bbs = [r['bb'] for g in validas.values() for r, _ in g if r['tipo'] == 'HATCH']
    colunas_x = sorted({min(r['bb'][0] for r, _ in g) for g in validas.values()})
    for grupo in validas.values():
        cys = [(r['bb'][1] + r['bb'][3]) / 2 for r, _ in grupo]
        gaps = sorted(cys[i] - cys[i + 1] for i in range(len(cys) - 1))
        passo = gaps[len(gaps) // 2]
        for r, tx in grupo:
            if r['tipo'] != 'HATCH' and any(sobrepoe(r['bb'], hb) for hb in hatch_bbs):
                amostras.add(r['handle'])  # contorno da caixa de uma amostra de hatch
                continue
            amostras.add(r['handle'])
            h = tx['h'] or 1
            bb = r['bb']
            cy = (bb[1] + bb[3]) / 2
            # todos os textos da mesma entrada da legenda (faixa = metade do passo entre linhas),
            # até à coluna de legenda seguinte
            x_fim = min([c for c in colunas_x if c > bb[2]] + [tx['x'] + 60 * h])
            faixa = max(0.5 * passo, 0.6 * h)
            linhas = [t for t in textos if tx['x'] - 0.5 * h <= t['x'] < x_fim
                      and abs((t['y'] - (t['h'] or h) / 2) - cy) < faixa]
            if tx not in linhas:
                linhas.append(tx)
            desc = ' '.join(t['t'] for t in sorted(linhas, key=lambda t: (-round(t['y'] / h * 2), t['x'])))
            desc = re.sub(r'\s+', ' ', desc).strip().replace('A LTURA', 'ALTURA')
            legenda.setdefault(r['chave'], {'descricao': desc, 'handle_texto': tx['handle'], 'handle_amostra': r['handle']})
    # amostras (contorno da caixa) que ficaram fora: linhas neutras sobrepostas a uma amostra
    amostra_bbs = [e['bb'] for e in ents if e['handle'] in amostras and e['bb']]
    for r in ents:
        if r['handle'] in amostras or not r['bb'] or r['tipo'] == 'HATCH':
            continue
        b = r['bb']
        for a in amostra_bbs:
            tol = 0.05 * max(a[2] - a[0], a[3] - a[1])
            if a[0] - tol <= b[0] and b[2] <= a[2] + tol and a[1] - tol <= b[1] and b[3] <= a[3] + tol:
                amostras.add(r['handle']); break

    # cor -> descrição, só quando a cor é única na legenda e não é cinzenta/neutra
    def cinzento(c):
        if not c.startswith('#'):
            return c in NEUTRAS or c.startswith('ACI25') or c in ('ACI8', 'ACI9')
        r_, g_, b_ = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        return max(r_, g_, b_) - min(r_, g_, b_) < 24
    descs_cor = collections.defaultdict(set)
    for k, v in legenda.items():
        descs_cor[k.split('|')[-1]].add(v['descricao'])
    por_cor = {c: next(iter(d)) for c, d in descs_cor.items() if len(d) == 1 and not cinzento(c)}

    for r in ents:
        r['legenda'] = r['handle'] in amostras
        if r['chave'] in legenda:
            r['descricao'], r['match'] = legenda[r['chave']]['descricao'], 'chave'
        elif not r['chave'].startswith('BLOCO') and r['cor'] in por_cor:
            r['descricao'], r['match'] = por_cor[r['cor']], 'cor'
        else:
            r['descricao'], r['match'] = '', ''
        bb = r.pop('bb')
        r['x'], r['y'] = ((bb[0] + bb[2]) / 2 * s, (bb[1] + bb[3]) / 2 * s) if bb else (None, None)
    return {'ficheiro': fn, 'unidades': u, 'escala_m': s, 'legenda': legenda, 'entidades': ents,
            'textos': [{'t': t['t'], 'x': t['x'] * s, 'y': t['y'] * s, 'handle': t['handle']} for t in textos]}


if __name__ == '__main__':
    print(json.dumps(extrair(sys.argv[1]), ensure_ascii=False))
