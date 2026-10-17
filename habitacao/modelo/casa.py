"""Modelo 3D da habitação (cave + R/C + 1º piso + cobertura em telha a 2 águas).

Coordenadas em metros: X = largura (0 = face exterior da empena esquerda, 7.24 = direita),
Y = profundidade (0 = fachada traseira, ~12 = fachada principal / rua), Z = cota (0 = piso da cave).
Medidas lidas das plantas e alçados (PDF, escala 1:100 → 117,6 px/m a 300 dpi).
"""
import math
import bpy
import materiais as MT

Z = {'cave': 0.0, 'rc': 3.0, 'p1': 6.0}
PD = 2.60          # pé-direito livre (escolha do cliente)
ANDAR = 3.0        # piso a piso (alçados)
M = {}


# ------------------------------------------------------------------ primitivas
def box(name, x0, x1, y0, y1, z0, z1, mat, col=None):
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def cyl(name, x, y, z0, z1, r, mat, seg=24, col=None):
    v, f = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append((x + r * math.cos(a), y + r * math.sin(a), z0))
        v.append((x + r * math.cos(a), y + r * math.sin(a), z1))
    for i in range(seg):
        j = (i + 1) % seg
        f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    f.append(tuple(2 * i for i in range(seg))[::-1])
    f.append(tuple(2 * i + 1 for i in range(seg)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


# ------------------------------------------------------------------ paredes e vãos
_jit_n = [0]


def _jit():
    _jit_n[0] += 1
    return 0.0001 + (_jit_n[0] * 0.000137) % 0.0014


def parede(name, x0, x1, y0, y1, z0, h, vaos=(), mat=None, col=None):
    """Parede retangular com vãos (a, b, peitoril, verga) ao longo do eixo maior.
    Peitoril/verga relativos a z0. Suporta vãos sobrepostos em planta a alturas diferentes."""
    mat = mat or M['parede']
    longo_x = (x1 - x0) >= (y1 - y0)
    a0, a1 = (x0, x1) if longo_x else (y0, y1)
    cortes = sorted({a0, a1} | {max(a0, min(a1, v)) for va in vaos for v in va[:2]})
    k = 0
    for s0, s1 in zip(cortes, cortes[1:]):
        if s1 - s0 < 1e-4:
            continue
        m = (s0 + s1) / 2
        furos = sorted((v[2], v[3]) for v in vaos if v[0] <= m <= v[1])
        z = 0.0
        pecas = []
        for (zs, zt) in furos:
            if zs > z:
                pecas.append((z, zs))
            z = max(z, zt)
        if z < h:
            pecas.append((z, h))
        for (za, zb) in pecas:
            if zb - za < 1e-4:
                continue
            # expansão mínima e distinta por peça: evita faces coincidentes entre paredes sobrepostas
            e = _jit()
            if longo_x:
                box(f'{name}_{k}', s0 - e, s1 + e, y0 - e, y1 + e, z0 + za, z0 + zb, mat, col)
            else:
                box(f'{name}_{k}', x0 - e, x1 + e, s0 - e, s1 + e, z0 + za, z0 + zb, mat, col)
            k += 1


def janela(name, x0, x1, y0, y1, zb, zt, col=None, porta=False, folhas=None):
    """Caixilharia antracite + vidro, ao centro da espessura da parede."""
    c, g = M['caixilho'], M['vidro']
    longo_x = (x1 - x0) >= (y1 - y0)
    e = 0.06  # perfil
    if longo_x:
        ym = (y0 + y1) / 2
        p = lambda s0, s1, z0, z1, n: box(n, s0, s1, ym - 0.035, ym + 0.035, z0, z1, c, col)
        gl = lambda s0, s1, z0, z1, n: box(n, s0, s1, ym - 0.004, ym + 0.004, z0, z1, g, col)
        a0, a1 = x0, x1
    else:
        xm = (x0 + x1) / 2
        p = lambda s0, s1, z0, z1, n: box(n, xm - 0.035, xm + 0.035, s0, s1, z0, z1, c, col)
        gl = lambda s0, s1, z0, z1, n: box(n, xm - 0.004, xm + 0.004, s0, s1, z0, z1, g, col)
        a0, a1 = y0, y1
    p(a0, a0 + e, zb, zt, name + '_fe')
    p(a1 - e, a1, zb, zt, name + '_fd')
    p(a0, a1, zt - e, zt, name + '_fs')
    p(a0, a1, zb, zb + (0.02 if porta else e), name + '_fi')
    n = folhas or (2 if (a1 - a0) > 1.1 else 1)
    w = (a1 - a0) / n
    for i in range(1, n):
        p(a0 + i * w - e / 2, a0 + i * w + e / 2, zb, zt, f'{name}_m{i}')
    gl(a0 + e, a1 - e, zb + e, zt - e, name + '_v')
    # peitoril interior (pedra clara) quando não é porta
    if not porta:
        if longo_x:
            box(name + '_peit', a0, a1, min(y0, y1) - 0.02, max(y0, y1) + 0.02, zb - 0.03, zb, M['branco_lacado'], col)
        else:
            box(name + '_peit', min(x0, x1) - 0.02, max(x0, x1) + 0.02, a0, a1, zb - 0.03, zb, M['branco_lacado'], col)


def porta_int(name, x0, x1, y0, y1, z0, h=2.05, col=None, aberta=0.0):
    """Porta interior lacada branca (aro + folha). aberta: 0 fechada."""
    longo_x = (x1 - x0) >= (y1 - y0)
    m = M['porta']
    if longo_x:
        box(name + '_ae', x0, x0 + 0.04, y0 - 0.01, y1 + 0.01, z0, z0 + h, m, col)
        box(name + '_ad', x1 - 0.04, x1, y0 - 0.01, y1 + 0.01, z0, z0 + h, m, col)
        box(name + '_as', x0, x1, y0 - 0.01, y1 + 0.01, z0 + h - 0.04, z0 + h, m, col)
        ym = (y0 + y1) / 2
        box(name + '_folha', x0 + 0.04, x1 - 0.04, ym - 0.02, ym + 0.02, z0 + 0.01, z0 + h - 0.04, m, col)
        cyl(name + '_puxador', x1 - 0.12, ym - 0.05, z0 + 1.03, z0 + 1.05, 0.012, M['cromado'], col=col)
        cyl(name + '_puxador2', x1 - 0.12, ym + 0.05, z0 + 1.03, z0 + 1.05, 0.012, M['cromado'], col=col)
    else:
        box(name + '_ae', x0 - 0.01, x1 + 0.01, y0, y0 + 0.04, z0, z0 + h, m, col)
        box(name + '_ad', x0 - 0.01, x1 + 0.01, y1 - 0.04, y1, z0, z0 + h, m, col)
        box(name + '_as', x0 - 0.01, x1 + 0.01, y0, y1, z0 + h - 0.04, z0 + h, m, col)
        xm = (x0 + x1) / 2
        box(name + '_folha', xm - 0.02, xm + 0.02, y0 + 0.04, y1 - 0.04, z0 + 0.01, z0 + h - 0.04, m, col)
        cyl(name + '_puxador', xm - 0.05, y1 - 0.12, z0 + 1.03, z0 + 1.05, 0.012, M['cromado'], col=col)
        cyl(name + '_puxador2', xm + 0.05, y1 - 0.12, z0 + 1.03, z0 + 1.05, 0.012, M['cromado'], col=col)


# ------------------------------------------------------------------ escada em U
def escada(z0, col):
    """Escada em U entre z0 e z0+3.0: lanço A (metade esquerda) sobe da frente para trás,
    patamar junto à fachada traseira, lanço B (metade direita) sobe de trás para a frente."""
    oak, wh = M['madeira'], M['branco_lacado']
    nA, nB = 9, 9
    hA = 1.5 / nA
    yA0, yA1 = 3.50, 1.20
    tA = (yA0 - yA1) / nA
    for i in range(nA):
        ztop = z0 + (i + 1) * hA
        yy1 = yA0 - i * tA
        yy0 = yA0 - (i + 1) * tA
        box(f'esc_A_{z0}_{i}', 0.20, 1.38, yy0, yy1, ztop - hA - 0.15, ztop - 0.03, wh, col)
        box(f'esc_A_{z0}_{i}_cob', 0.20, 1.38, yy0 - 0.02, yy1, ztop - 0.03, ztop, oak, col)
    box(f'esc_pat_{z0}', 0.20, 2.82, 0.20, 1.20, z0 + 1.5 - 0.20, z0 + 1.5 - 0.03, wh, col)
    box(f'esc_pat_{z0}_cob', 0.20, 2.82, 0.20, 1.20, z0 + 1.5 - 0.03, z0 + 1.5, oak, col)
    yB0, yB1 = 1.20, 2.75
    tB = (yB1 - yB0) / nB
    for i in range(nB):
        ztop = z0 + 1.5 + (i + 1) * hA
        yy0 = yB0 + i * tB
        yy1 = yB0 + (i + 1) * tB
        box(f'esc_B_{z0}_{i}', 1.52, 2.82, yy0, yy1, ztop - hA - 0.15, ztop - 0.03, wh, col)
        box(f'esc_B_{z0}_{i}_cob', 1.52, 2.82, yy0, yy1 + 0.02, ztop - 0.03, ztop, oak, col)
    # parede central entre lanços (núcleo)
    box(f'esc_nucleo_{z0}', 1.38, 1.52, 1.20, 3.50, z0, z0 + ANDAR, M['parede'], col)
    # corrimão em madeira na parede central
    box(f'esc_corr_{z0}', 1.36, 1.38, 1.20, 3.50, z0 + 0.95, z0 + 2.45, oak, col).rotation_euler = (0, 0, 0)


# ------------------------------------------------------------------ revestimentos
def pavimento(name, x0, x1, y0, y1, z0, mat, col, dz=0.010):
    box(name, x0, x1, y0, y1, z0, z0 + dz, mat, col)


def revest_parede(name, x0, x1, y0, y1, z0, h, mat, vaos_por_lado, col):
    """Pele de revestimento (cerâmica) nas 4 faces interiores de um compartimento.
    vaos_por_lado: dict {'S','N','O','E': [(a,b,peit,verga)]} (S = y0, N = y1, O = x0, E = x1)."""
    t = 0.008
    parede(name + '_S', x0, x1, y0, y0 + t, z0, h, vaos_por_lado.get('S', []), mat, col)
    parede(name + '_N', x0, x1, y1 - t, y1, z0, h, vaos_por_lado.get('N', []), mat, col)
    parede(name + '_O', x0, x0 + t, y0 + t, y1 - t, z0, h, vaos_por_lado.get('O', []), mat, col)
    parede(name + '_E', x1 - t, x1, y0 + t, y1 - t, z0, h, vaos_por_lado.get('E', []), mat, col)


def rodape(x0, x1, y0, y1, z0, col, excl=()):
    """Rodapé lacado branco 7 cm no perímetro do compartimento (sem vãos excluídos)."""
    w = M['branco_lacado']
    for (a0, a1, yy) in ((x0, x1, y0), (x0, x1, y1 - 0.012)):
        box(f'rod_{x0:.2f}_{yy:.2f}', a0, a1, yy, yy + 0.012, z0, z0 + 0.07, w, col)
    for (b0, b1, xx) in ((y0, y1, x0), (y0, y1, x1 - 0.012)):
        box(f'rod_{xx:.2f}_{y0:.2f}', xx, xx + 0.012, b0, b1, z0, z0 + 0.07, w, col)


def luz_teto(name, x, y, z0, energia=60, tam=0.35, cor=(1.0, 0.86, 0.70), col=None, candeeiro=True):
    zc = z0 + PD
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energia
    ld.size = tam
    ld.color = cor
    ob = bpy.data.objects.new(name, ld)
    ob.location = (x, y, zc - 0.03)
    (col or bpy.context.scene.collection).objects.link(ob)
    if candeeiro:
        cyl(name + '_aro', x, y, zc - 0.03, zc, 0.09, M['branco_lacado'], col=col)
        cyl(name + '_dif', x, y, zc - 0.035, zc - 0.03, 0.075, M['luz'], col=col)
    return ob


# ------------------------------------------------------------------ mobiliário (eixos alinhados)
def movel(x0, x1, y0, y1, z0, z1, mat, nome, col):
    return box(nome, x0, x1, y0, y1, z0, z1, mat, col)


def cama(nome, x0, x1, y0, y1, z0, cabeceira, col, larg_almofadas=2):
    """Cama: cabeceira em 'N','S','E','O'."""
    mad, len_, man = M['madeira'], M['lencol'], M['manta']
    box(nome + '_estr', x0, x1, y0, y1, z0, z0 + 0.30, mad, col)
    box(nome + '_colchao', x0 + 0.02, x1 - 0.02, y0 + 0.02, y1 - 0.02, z0 + 0.30, z0 + 0.52, len_, col)
    # manta na metade dos pés
    if cabeceira in ('N', 'S'):
        L = y1 - y0
        if cabeceira == 'N':
            box(nome + '_manta', x0, x1, y0 - 0.01, y0 + L * 0.35, z0 + 0.50, z0 + 0.55, man, col)
            box(nome + '_cab', x0 - 0.05, x1 + 0.05, y1, y1 + 0.06, z0, z0 + 1.10, M['sofa'], col)
            yp0, yp1 = y1 - 0.45, y1 - 0.08
        else:
            box(nome + '_manta', x0, x1, y1 - L * 0.35, y1 + 0.01, z0 + 0.50, z0 + 0.55, man, col)
            box(nome + '_cab', x0 - 0.05, x1 + 0.05, y0 - 0.06, y0, z0, z0 + 1.10, M['sofa'], col)
            yp0, yp1 = y0 + 0.08, y0 + 0.45
        w = (x1 - x0 - 0.12) / larg_almofadas
        for i in range(larg_almofadas):
            box(f'{nome}_alm{i}', x0 + 0.06 + i * w + 0.02, x0 + 0.06 + (i + 1) * w - 0.02, yp0, yp1, z0 + 0.52, z0 + 0.66, len_, col)
    else:
        L = x1 - x0
        if cabeceira == 'E':
            box(nome + '_manta', x0 - 0.01, x0 + L * 0.35, y0, y1, z0 + 0.50, z0 + 0.55, man, col)
            box(nome + '_cab', x1, x1 + 0.06, y0 - 0.05, y1 + 0.05, z0, z0 + 1.10, M['sofa'], col)
            xp0, xp1 = x1 - 0.45, x1 - 0.08
        else:
            box(nome + '_manta', x1 - L * 0.35, x1 + 0.01, y0, y1, z0 + 0.50, z0 + 0.55, man, col)
            box(nome + '_cab', x0 - 0.06, x0, y0 - 0.05, y1 + 0.05, z0, z0 + 1.10, M['sofa'], col)
            xp0, xp1 = x0 + 0.08, x0 + 0.45
        w = (y1 - y0 - 0.12) / larg_almofadas
        for i in range(larg_almofadas):
            box(f'{nome}_alm{i}', xp0, xp1, y0 + 0.06 + i * w + 0.02, y0 + 0.06 + (i + 1) * w - 0.02, z0 + 0.52, z0 + 0.66, len_, col)


def mesa_cabeceira(nome, x, y, z0, col, cand=True):
    box(nome, x - 0.22, x + 0.22, y - 0.20, y + 0.20, z0, z0 + 0.50, M['branco_lacado'], col)
    if cand:
        cyl(nome + '_pe', x, y, z0 + 0.50, z0 + 0.82, 0.015, M['madeira'], col=col)
        cyl(nome + '_abaj', x, y, z0 + 0.78, z0 + 0.98, 0.12, M['cortina'], col=col)
        ld = bpy.data.lights.new(nome + '_luz', 'POINT'); ld.energy = 8; ld.color = (1, 0.8, 0.6); ld.shadow_soft_size = 0.08
        ob = bpy.data.objects.new(nome + '_luz', ld); ob.location = (x, y, z0 + 0.88); col.objects.link(ob)


def roupeiro(nome, x0, x1, y0, y1, z0, frente, col, h=2.4):
    box(nome, x0, x1, y0, y1, z0, z0 + h, M['branco_lacado'], col)
    # juntas das portas (frisos escuros)
    n = max(2, round(((x1 - x0) if frente in ('N', 'S') else (y1 - y0)) / 0.5))
    for i in range(1, n):
        if frente in ('N', 'S'):
            xx = x0 + i * (x1 - x0) / n
            yy = y1 if frente == 'N' else y0
            box(f'{nome}_j{i}', xx - 0.003, xx + 0.003, yy - 0.002, yy + 0.002, z0 + 0.05, z0 + h - 0.02, M['preto'], col)
        else:
            yy = y0 + i * (y1 - y0) / n
            xx = x1 if frente == 'E' else x0
            box(f'{nome}_j{i}', xx - 0.002, xx + 0.002, yy - 0.003, yy + 0.003, z0 + 0.05, z0 + h - 0.02, M['preto'], col)


def sanita(nome, x, y, z0, costas, col):
    """Sanita suspensa simplificada; costas = lado da parede ('N','S','E','O')."""
    l = M['loica']
    d = {'N': (0, -1), 'S': (0, 1), 'E': (-1, 0), 'O': (1, 0)}[costas]
    # tanque/caixa embutida e bacia
    cx, cy = x + d[0] * 0.30, y + d[1] * 0.30
    cyl(nome + '_bacia', cx, cy, z0 + 0.25, z0 + 0.42, 0.19, l, col=col)
    if costas in ('N', 'S'):
        box(nome + '_tras', x - 0.18, x + 0.18, min(y, y + d[1] * 0.20), max(y, y + d[1] * 0.20), z0 + 0.25, z0 + 0.42, l, col)
        box(nome + '_tampo', cx - 0.18, cx + 0.18, cy - 0.20, cy + 0.20, z0 + 0.42, z0 + 0.44, l, col)
    else:
        box(nome + '_tras', min(x, x + d[0] * 0.20), max(x, x + d[0] * 0.20), y - 0.18, y + 0.18, z0 + 0.25, z0 + 0.42, l, col)
        box(nome + '_tampo', cx - 0.20, cx + 0.20, cy - 0.18, cy + 0.18, z0 + 0.42, z0 + 0.44, l, col)


def lavatorio(nome, x0, x1, y0, y1, z0, parede_lado, col, espelho=True):
    """Móvel suspenso com lavatório + espelho; parede_lado: lado da parede."""
    box(nome + '_movel', x0, x1, y0, y1, z0 + 0.40, z0 + 0.85, M['madeira'], col)
    box(nome + '_tampo', x0 - 0.01, x1 + 0.01, y0 - 0.01, y1 + 0.01, z0 + 0.85, z0 + 0.87, M['loica'], col)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cyl(nome + '_cuba', cx, cy, z0 + 0.87, z0 + 0.99, 0.19, M['loica'], col=col)
    cyl(nome + '_cuba_int', cx, cy, z0 + 0.90, z0 + 0.995, 0.16, M['preto'], col=col) if False else None
    if espelho:
        if parede_lado == 'N':
            box(nome + '_esp', x0, x1, y1 + 0.0, y1 + 0.01, z0 + 1.05, z0 + 1.85, M['espelho'], col)
            cyl(nome + '_torn', cx, y1 - 0.06, z0 + 0.87, z0 + 1.10, 0.012, M['cromado'], col=col)
        elif parede_lado == 'S':
            box(nome + '_esp', x0, x1, y0 - 0.01, y0, z0 + 1.05, z0 + 1.85, M['espelho'], col)
            cyl(nome + '_torn', cx, y0 + 0.06, z0 + 0.87, z0 + 1.10, 0.012, M['cromado'], col=col)
        elif parede_lado == 'E':
            box(nome + '_esp', x1, x1 + 0.01, y0, y1, z0 + 1.05, z0 + 1.85, M['espelho'], col)
            cyl(nome + '_torn', x1 - 0.06, cy, z0 + 0.87, z0 + 1.10, 0.012, M['cromado'], col=col)
        else:
            box(nome + '_esp', x0 - 0.01, x0, y0, y1, z0 + 1.05, z0 + 1.85, M['espelho'], col)
            cyl(nome + '_torn', x0 + 0.06, cy, z0 + 0.87, z0 + 1.10, 0.012, M['cromado'], col=col)


def duche(nome, x0, x1, y0, y1, z0, lado_vidro, col):
    box(nome + '_base', x0, x1, y0, y1, z0, z0 + 0.04, M['loica'], col)
    g = M['vidro']
    if lado_vidro == 'S':
        box(nome + '_vidro', x0, x1 - 0.3, y0, y0 + 0.01, z0 + 0.04, z0 + 2.0, g, col)
    elif lado_vidro == 'N':
        box(nome + '_vidro', x0, x1 - 0.3, y1 - 0.01, y1, z0 + 0.04, z0 + 2.0, g, col)
    elif lado_vidro == 'E':
        box(nome + '_vidro', x1 - 0.01, x1, y0, y1 - 0.3, z0 + 0.04, z0 + 2.0, g, col)
    else:
        box(nome + '_vidro', x0, x0 + 0.01, y0, y1 - 0.3, z0 + 0.04, z0 + 2.0, g, col)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cyl(nome + '_chuv', cx, cy, z0 + 2.08, z0 + 2.10, 0.12, M['cromado'], col=col)


def banheira(nome, x0, x1, y0, y1, z0, col):
    box(nome + '_ext', x0, x1, y0, y1, z0, z0 + 0.55, M['loica'], col)
    box(nome + '_int', x0 + 0.06, x1 - 0.06, y0 + 0.06, y1 - 0.06, z0 + 0.20, z0 + 0.551, M['branco_lacado'], col)


def sofa(nome, x0, x1, y0, y1, z0, costas, col):
    s, a = M['sofa'], M['almofada_azul']
    box(nome + '_base', x0, x1, y0, y1, z0 + 0.10, z0 + 0.42, s, col)
    if costas == 'E':
        box(nome + '_costas', x1 - 0.20, x1, y0, y1, z0 + 0.42, z0 + 0.80, s, col)
        box(nome + '_br1', x0, x1, y0, y0 + 0.18, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_br2', x0, x1, y1 - 0.18, y1, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_alm', x1 - 0.32, x1 - 0.20, y0 + 0.30, y0 + 0.75, z0 + 0.42, z0 + 0.80, a, col)
        box(nome + '_alm2', x1 - 0.32, x1 - 0.20, y1 - 0.75, y1 - 0.30, z0 + 0.42, z0 + 0.80, M['manta'], col)
    elif costas == 'O':
        box(nome + '_costas', x0, x0 + 0.20, y0, y1, z0 + 0.42, z0 + 0.80, s, col)
        box(nome + '_br1', x0, x1, y0, y0 + 0.18, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_br2', x0, x1, y1 - 0.18, y1, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_alm', x0 + 0.20, x0 + 0.32, y0 + 0.30, y0 + 0.75, z0 + 0.42, z0 + 0.80, a, col)
    elif costas == 'N':
        box(nome + '_costas', x0, x1, y1 - 0.20, y1, z0 + 0.42, z0 + 0.80, s, col)
        box(nome + '_br1', x0, x0 + 0.18, y0, y1, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_br2', x1 - 0.18, x1, y0, y1, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_alm', x0 + 0.30, x0 + 0.75, y1 - 0.32, y1 - 0.20, z0 + 0.42, z0 + 0.80, a, col)
    else:
        box(nome + '_costas', x0, x1, y0, y0 + 0.20, z0 + 0.42, z0 + 0.80, s, col)
        box(nome + '_br1', x0, x0 + 0.18, y0, y1, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_br2', x1 - 0.18, x1, y0, y1, z0 + 0.42, z0 + 0.62, s, col)
        box(nome + '_alm', x0 + 0.30, x0 + 0.75, y0 + 0.20, y0 + 0.32, z0 + 0.42, z0 + 0.80, a, col)
    for (xx, yy) in ((x0 + 0.06, y0 + 0.06), (x1 - 0.06, y0 + 0.06), (x0 + 0.06, y1 - 0.06), (x1 - 0.06, y1 - 0.06)):
        cyl(nome + '_pe', xx, yy, z0, z0 + 0.10, 0.02, M['madeira'], 8, col)


def mesa(nome, x0, x1, y0, y1, z0, col, h=0.75, tampo=None):
    t = tampo or M['madeira']
    box(nome + '_tampo', x0, x1, y0, y1, z0 + h - 0.04, z0 + h, t, col)
    for (xx, yy) in ((x0 + 0.06, y0 + 0.06), (x1 - 0.06, y0 + 0.06), (x0 + 0.06, y1 - 0.06), (x1 - 0.06, y1 - 0.06)):
        box(nome + '_pe', xx - 0.025, xx + 0.025, yy - 0.025, yy + 0.025, z0, z0 + h - 0.04, M['madeira'], col)


def cadeira(nome, x, y, z0, frente, col):
    m = M['madeira']
    box(nome + '_ass', x - 0.22, x + 0.22, y - 0.22, y + 0.22, z0 + 0.43, z0 + 0.47, m, col)
    for (dx, dy) in ((-0.19, -0.19), (0.19, -0.19), (-0.19, 0.19), (0.19, 0.19)):
        box(nome + '_pe', x + dx - 0.015, x + dx + 0.015, y + dy - 0.015, y + dy + 0.015, z0, z0 + 0.43, m, col)
    d = {'N': (0, -0.21), 'S': (0, 0.21), 'E': (-0.21, 0), 'O': (0.21, 0)}[frente]
    if frente in ('N', 'S'):
        box(nome + '_cost', x - 0.22, x + 0.22, y + d[1] - 0.015, y + d[1] + 0.015, z0 + 0.47, z0 + 0.85, m, col)
    else:
        box(nome + '_cost', x + d[0] - 0.015, x + d[0] + 0.015, y - 0.22, y + 0.22, z0 + 0.47, z0 + 0.85, m, col)


def planta(nome, x, y, z0, col, h=1.1):
    cyl(nome + '_vaso', x, y, z0, z0 + 0.35, 0.17, M['vaso'], col=col)
    for i, (dx, dy, hh, r) in enumerate(((0, 0, h, 0.22), (0.08, 0.05, h * 0.8, 0.18), (-0.07, -0.06, h * 0.7, 0.17))):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=(x + dx, y + dy, z0 + hh))
        o = bpy.context.active_object; o.name = f'{nome}_folh{i}'; o.data.materials.append(M['planta'])
        o.scale = (1, 1, 1.4)
        bpy.ops.object.shade_smooth()
        for c in o.users_collection:
            c.objects.unlink(o)
        col.objects.link(o)
    cyl(nome + '_caule', x, y, z0 + 0.35, z0 + h * 0.7, 0.012, M['madeira'], 6, col)


def quadro(nome, x0, x1, y0, y1, z0, z1, mat, col):
    box(nome + '_mold', x0, x1, y0, y1, z0, z1, M['preto'], col)
    if (x1 - x0) > (y1 - y0):
        yy = (y0 + y1) / 2
        box(nome, x0 + 0.03, x1 - 0.03, min(y0, y1) - 0.002, max(y0, y1) + 0.002, z0 + 0.03, z1 - 0.03, mat, col)
    else:
        box(nome, min(x0, x1) - 0.002, max(x0, x1) + 0.002, y0 + 0.03, y1 - 0.03, z0 + 0.03, z1 - 0.03, mat, col)


def tapete(nome, x0, x1, y0, y1, z0, col):
    box(nome, x0, x1, y0, y1, z0 + 0.010, z0 + 0.022, M['tapete'], col)


def cortina(nome, x0, x1, y0, y1, z0, col):
    box(nome, x0, x1, y0, y1, z0 + 0.02, z0 + PD - 0.05, M['cortina'], col)


# ================================================================== construção
def construir():
    global M
    M = MT.todos()
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    cE = coll('Estrutura')
    cX = coll('Exterior')
    cC, cR, cP = coll('Cave'), coll('RC'), coll('P1')

    # ---------------- lajes (pavimento estrutural + teto do piso inferior)
    t = M['teto']
    # laje do R/C (z 2.6–3.0) — vazio da escada em x0.2–2.82 (esq. y0.2–3.6; dir. y0.2–2.75)
    for z in (Z['rc'], Z['p1']):
        box(f'laje_{z}_a', 2.82, 7.24, 0.0, 12.16, z - 0.40, z, t, cE)
        box(f'laje_{z}_b', 0.0, 2.82, 3.60, 11.55 if z == Z['rc'] else 10.69, z - 0.40, z, t, cE)
        box(f'laje_{z}_c', 1.38, 2.82, 2.75, 3.60, z - 0.40, z, t, cE)
    box('laje_cave', 0.0, 7.24, 0.0, 12.13, -0.30, 0.0, t, cE)
    box('laje_cobertura', 0.0, 7.24, 0.0, 11.16, Z['p1'] + PD, Z['p1'] + PD + 0.30, t, cE)
    box('laje_terraco_rc', 3.48, 7.24, 11.16, 12.16, Z['p1'] - 0.40, Z['p1'] - 0.0, t, cE)

    # ---------------- CAVE (z0 = 0)
    z0 = Z['cave']
    H = ANDAR
    parede('C_emp_esq', 0.0, 0.2, 0.0, 11.2, z0, H, col=cC)
    parede('C_emp_dir', 7.04, 7.24, 0.1, 12.13, z0, H, col=cC)
    parede('C_tras_esq', 0.0, 2.98, 0.0, 0.2, z0, H, [(1.0, 2.0, 0.9, 1.5), (1.0001, 2.0, 2.15, H)], col=cC) if False else \
        parede('C_tras_esq', 0.0, 2.98, 0.0, 0.2, z0, H, [(1.0, 2.0, 0.9, 1.5), (1.0, 2.0, 2.15, 3.0)], col=cC)
    parede('C_tras_dir', 2.98, 7.24, 0.1, 0.3, z0, H, [(3.2, 5.7, 0.0, 2.3), (6.21, 6.82, 1.05, 1.95)], col=cC)
    parede('C_fr1', 0.2, 2.98, 11.0, 11.2, z0, H, col=cC)
    parede('C_fr2', 2.98, 3.18, 11.0, 11.7, z0, H, col=cC)
    parede('C_fr3', 3.18, 5.24, 11.5, 11.7, z0, H, col=cC)
    parede('C_fr4', 5.24, 5.44, 11.5, 12.13, z0, H, col=cC)
    parede('C_fr5', 5.44, 7.04, 11.93, 12.13, z0, H, col=cC)
    parede('C_escada', 2.78, 2.98, 0.2, 5.32, z0, H, [(3.96, 4.81, 0.0, 2.05)], col=cC)
    parede('C_atrio', 0.2, 2.78, 5.11, 5.32, z0, H, col=cC)
    janela('C_jan_esc', 1.0, 2.0, 0.0, 0.2, z0 + 0.9, z0 + 1.5, cC)
    janela('C_jan_lav', 6.21, 6.82, 0.1, 0.3, z0 + 1.05, z0 + 1.95, cC)
    # portão seccionado (2,50 x 2,30) para o quintal
    box('C_portao', 3.2, 5.7, 0.17, 0.21, z0, z0 + 2.3, M['caixilho'], cC)
    for i in range(1, 5):
        box(f'C_portao_j{i}', 3.2, 5.7, 0.215, 0.22, z0 + i * 0.46 - 0.005, z0 + i * 0.46 + 0.005, M['preto'], cC)
    porta_int('C_porta_atrio', 2.78, 2.98, 3.96, 4.81, z0, col=cC)
    pavimento('C_pav', 0.2, 7.04, 0.2, 12.0, z0, M['cer_cave'], cC)
    escada(z0, cE)
    # mobiliário: carro, estantes, lavandaria, bancada
    # arrumos: estantes extra e caixas no lugar do carro (garagem/arrumos)
    for i, yy in enumerate((2.0, 3.4)):
        for k in range(5):
            box(f'estante_t{i}_{k}', 6.62, 7.02, yy, yy + 1.3, z0 + 0.05 + k * 0.45, z0 + 0.08 + k * 0.45, M['madeira'], cC)
        box(f'estante_t{i}_lat', 6.62, 7.02, yy, yy + 0.03, z0, z0 + 1.9, M['madeira'], cC)
        box(f'estante_t{i}_lat2', 6.62, 7.02, yy + 1.27, yy + 1.3, z0, z0 + 1.9, M['madeira'], cC)
    for k, (xx, yy, hh) in enumerate(((3.6, 1.0, 0.4), (3.6, 1.0 + 0.45, 0.35), (4.1, 1.0, 0.5))):
        box(f'caixa_chao{k}', xx, xx + 0.45, yy, yy + 0.40, z0, z0 + hh, M['vaso'], cC)
    box('bicicleta_quadro', 5.6, 6.4, 1.2, 1.25, z0 + 0.35, z0 + 0.95, M['preto'], cC)
    cyl('bic_roda1', 5.65, 1.22, z0, z0 + 0.05, 0.0, M['preto'], 3, cC) if False else None
    for i, yy in enumerate((6.2, 7.6, 9.0)):
        box(f'estante_{i}', 6.60, 7.02, yy, yy + 1.3, z0, z0 + 2.0, M['madeira'], cC) if False else None
        for k in range(5):
            box(f'estante_{i}_{k}', 6.62, 7.02, yy, yy + 1.3, z0 + 0.05 + k * 0.45, z0 + 0.08 + k * 0.45, M['madeira'], cC)
        box(f'estante_{i}_lat', 6.62, 7.02, yy, yy + 0.03, z0, z0 + 1.9, M['madeira'], cC)
        box(f'estante_{i}_lat2', 6.62, 7.02, yy + 1.27, yy + 1.3, z0, z0 + 1.9, M['madeira'], cC)
        for k in range(4):
            box(f'caixa_{i}_{k}', 6.66, 6.98, yy + 0.1 + k * 0.28, yy + 0.32 + k * 0.28, z0 + 0.08 + (k % 3) * 0.45, z0 + 0.30 + (k % 3) * 0.45, M['vaso'], cC)
    # lavandaria junto à parede esquerda
    box('maq_lavar', 0.25, 0.85, 6.0, 6.6, z0, z0 + 0.85, M['branco_lacado'], cC)
    cyl('maq_lavar_porta', 0.86, 6.3, z0 + 0.3, z0 + 0.3, 0.0, M['cromado'], 3, cC)
    box('maq_lavar_vigia', 0.85, 0.87, 6.12, 6.48, z0 + 0.2, z0 + 0.56, M['vidro'], cC)
    box('maq_secar', 0.25, 0.85, 6.65, 7.25, z0, z0 + 0.85, M['branco_lacado'], cC)
    box('maq_secar_vigia', 0.85, 0.87, 6.77, 7.13, z0 + 0.2, z0 + 0.56, M['vidro'], cC)
    box('tanque', 0.25, 0.85, 7.35, 8.05, z0 + 0.0, z0 + 0.90, M['loica'], cC)
    box('lav_armario', 0.22, 0.55, 6.0, 8.05, z0 + 1.45, z0 + 2.2, M['branco_lacado'], cC)
    box('bancada_trab', 0.9, 2.7, 10.4, 10.98, z0 + 0.85, z0 + 0.9, M['madeira'], cC)
    box('bancada_trab_base', 0.9, 2.7, 10.4, 10.98, z0, z0 + 0.85, M['branco_lacado'], cC)
    box('bicicleta_parede', 3.4, 5.0, 11.45, 11.5, z0 + 1.0, z0 + 1.7, M['preto'], cC)
    for (x, y) in ((1.5, 4.3), (4.5, 3.0), (4.5, 8.0), (2.0, 8.5)):
        luz_teto(f'C_luz_{x}_{y}', x, y, z0, 45, 0.6, (1.0, 0.95, 0.88), cC, candeeiro=False)
        box(f'C_led_{x}_{y}', x - 0.6, x + 0.6, y - 0.06, y + 0.06, z0 + PD - 0.03, z0 + PD, M['luz'], cC)

    # ---------------- RÉS-DO-CHÃO (z0 = 3)
    z0 = Z['rc']
    parede('R_emp_esq', 0.0, 0.2, 0.0, 10.69, z0, H, col=cR)
    parede('R_emp_dir', 7.04, 7.24, 0.1, 12.16, z0, H, col=cR)
    parede('R_tras_esq', 0.0, 2.93, 0.0, 0.2, z0, H, [(1.0, 2.0, 0.0, 1.25)], col=cR)
    parede('R_tras_dir', 2.93, 7.24, 0.1, 0.3, z0, H, [(4.22, 5.71, 1.2, 2.2)], col=cR)
    parede('R_fr_hall', 0.2, 2.82, 10.49, 10.69, z0, H, [(0.6, 2.5, 0.0, 2.1)], col=cR)
    parede('R_fr_lado', 2.82, 2.93, 10.49, 11.71, z0, H, col=cR)
    parede('R_fr_sala', 2.93, 5.07, 11.51, 11.71, z0, H, [(3.21, 4.97, 0.0, 2.1)], col=cR)
    parede('R_fr_deg', 5.07, 5.27, 11.51, 12.16, z0, H, col=cR)
    parede('R_fr_pedra', 5.27, 7.04, 11.96, 12.16, z0, H, col=cR)
    parede('R_esc_coz', 2.82, 2.93, 0.2, 3.60, z0, H, col=cR)
    parede('R_central', 2.82, 2.93, 3.60, 10.49, z0, H, [(4.30, 5.20, 0.0, 2.10)], col=cR)
    parede('R_desp_s', 0.2, 1.41, 4.85, 4.92, z0, H, [(0.40, 1.20, 0.0, 2.05)], col=cR)
    parede('R_div', 1.41, 1.61, 4.85, 8.37, z0, H, [(7.00, 7.75, 0.0, 2.05)], col=cR)
    parede('R_desp_n', 0.2, 1.41, 6.00, 6.16, z0, H, col=cR)
    parede('R_hall_s', 0.2, 2.82, 8.37, 8.58, z0, H, [(1.78, 2.62, 0.0, 2.05)], col=cR)
    janela('R_jan_coz', 4.22, 5.71, 0.1, 0.3, z0 + 1.2, z0 + 2.2, cR)
    janela('R_jan_sala', 3.21, 4.97, 11.51, 11.71, z0 + 0.0, z0 + 2.1, cR, porta=True, folhas=2)
    janela('esc_jan_inf', 1.0, 2.0, 0.0, 0.2, 2.15, 4.25, cE, porta=True, folhas=1)
    # porta de entrada (folha 0,90 antracite + painéis laterais em vidro)
    janela('R_entrada_lat', 0.6, 2.5, 10.49, 10.69, z0, z0 + 2.1, cR, porta=True, folhas=3)
    box('R_porta_entrada', 1.13, 1.97, 10.57, 10.61, z0 + 0.02, z0 + 2.04, M['caixilho'], cR)
    box('R_puxador_ent', 1.18, 1.21, 10.50, 10.57, z0 + 0.8, z0 + 1.6, M['inox'], cR)
    porta_int('R_p_desp', 0.40, 1.20, 4.85, 4.92, z0, col=cR)
    porta_int('R_p_wc', 1.41, 1.61, 7.00, 7.75, z0, col=cR)
    porta_int('R_p_hall', 1.78, 2.62, 8.37, 8.58, z0, col=cR)
    # pavimentos
    pavimento('R_pav_coz', 2.93, 7.04, 0.30, 4.16, z0, M['cer_coz'], cR)
    pavimento('R_pav_sala', 2.93, 7.04, 4.16, 11.51, z0, M['soalho'], cR)
    pavimento('R_pav_sala2', 5.07, 7.04, 11.5, 11.96, z0, M['soalho'], cR)
    pavimento('R_pav_corr', 0.2, 2.82, 3.60, 10.49, z0, M['soalho'], cR)
    pavimento('R_pav_desp', 0.2, 1.41, 4.92, 6.00, z0, M['cer_wc_chao'], cR, 0.012)
    pavimento('R_pav_wc', 0.2, 1.41, 6.16, 8.37, z0, M['cer_wc_chao'], cR, 0.012)
    pavimento('R_pav_patamar', 0.2, 2.82, 3.4, 3.6, z0, M['soalho'], cR)
    revest_parede('R_wc_rev', 0.2, 1.41, 6.16, 8.37, z0 + 0.012, PD, M['cer_wc_parede'], {'E': [(7.00, 7.75, 0, 2.05)]}, cR)
    # cozinha branca, bancada em madeira (L: parede traseira + parede direita) e mesa de refeições
    zc = z0
    box('coz_base_tras', 2.95, 6.44, 0.30, 0.90, zc + 0.10, zc + 0.88, M['branco_lacado'], cR)
    box('coz_rodape_tras', 2.97, 6.44, 0.33, 0.85, zc, zc + 0.10, M['preto'], cR)
    box('coz_tampo_tras', 2.95, 6.44, 0.30, 0.92, zc + 0.88, zc + 0.92, M['madeira'], cR)
    box('coz_base_dir', 6.44, 7.04, 0.30, 3.40, zc + 0.10, zc + 0.88, M['branco_lacado'], cR)
    box('coz_tampo_dir', 6.42, 7.04, 0.30, 3.40, zc + 0.88, zc + 0.92, M['madeira'], cR)
    box('coz_coluna', 2.95, 3.65, 0.30, 0.95, zc, zc + 2.35, M['branco_lacado'], cR)
    box('coz_forno', 3.02, 3.58, 0.94, 0.96, zc + 0.95, zc + 1.55, M['preto'], cR)
    box('coz_lava', 4.60, 5.30, 0.42, 0.80, zc + 0.80, zc + 0.921, M['inox'], cR)
    cyl('coz_torn', 4.95, 0.38, zc + 0.92, zc + 1.20, 0.015, M['cromado'], col=cR)
    box('coz_placa', 6.50, 7.00, 1.30, 1.90, zc + 0.92, zc + 0.93, M['preto'], cR)
    box('coz_exaustor', 6.55, 7.04, 1.25, 1.95, zc + 1.65, zc + 1.80, M['inox'], cR)
    box('coz_sup_dir', 6.70, 7.04, 2.05, 3.40, zc + 1.50, zc + 2.30, M['branco_lacado'], cR)
    box('coz_sup_tras', 5.85, 6.44, 0.30, 0.65, zc + 1.50, zc + 2.30, M['branco_lacado'], cR)
    box('coz_sup_tras2', 3.65, 4.15, 0.30, 0.65, zc + 1.50, zc + 2.30, M['branco_lacado'], cR)
    box('coz_azulejo_tras', 3.65, 6.44, 0.31, 0.312, zc + 0.92, zc + 1.50, M['azulejo_coz'], cR)
    box('coz_azulejo_dir', 7.028, 7.03, 0.30, 3.40, zc + 0.92, zc + 1.50, M['azulejo_coz'], cR)
    box('coz_frigorifico', 6.40, 7.04, 3.40, 4.10, zc, zc + 2.0, M['inox'], cR)
    for i in range(1, 7):
        xx = 2.95 + i * 0.5
        if xx < 6.44:
            box(f'coz_junta{i}', xx - 0.002, xx + 0.002, 0.899, 0.902, zc + 0.12, zc + 0.86, M['preto'], cR)
    mesa('R_mesa_ref', 3.90, 5.50, 2.10, 3.00, z0, cR)
    for i, xx in enumerate((4.25, 5.15)):
        cadeira(f'R_cad_n{i}', xx, 1.82, z0, 'S', cR)
        cadeira(f'R_cad_s{i}', xx, 3.28, z0, 'N', cR)
    cyl('R_pendente_fio', 4.70, 2.55, z0 + 1.55, z0 + PD, 0.004, M['preto'], 6, cR)
    cyl('R_pendente', 4.70, 2.55, z0 + 1.45, z0 + 1.60, 0.20, M['preto'], 32, cR)
    ld = bpy.data.lights.new('R_pend_luz', 'POINT'); ld.energy = 40; ld.color = (1, 0.82, 0.62); ld.shadow_soft_size = 0.1
    ob = bpy.data.objects.new('R_pend_luz', ld); ob.location = (4.70, 2.55, z0 + 1.42); cR.objects.link(ob)
    luz_teto('R_luz_coz', 5.2, 1.2, z0, 50, 0.4, col=cR)
    # sala: sofá encostado à empena direita, TV na parede central, tapete, mesa de centro
    tapete('R_tapete', 4.10, 6.10, 7.10, 9.90, z0, cR)
    sofa('R_sofa', 6.10, 7.00, 7.30, 9.70, z0, 'E', cR)
    mesa('R_mesa_centro', 4.80, 5.60, 8.05, 8.95, z0, cR, h=0.40)
    box('R_movel_tv', 2.93, 3.38, 7.4, 9.6, z0 + 0.15, z0 + 0.55, M['madeira'], cR)
    box('R_tv', 2.95, 2.98, 7.85, 9.15, z0 + 1.00, z0 + 1.72, M['preto'], cR)
    box('R_poltrona', 3.4, 4.2, 10.5, 11.3, z0 + 0.10, z0 + 0.42, M['manta'], cR)
    box('R_poltrona_c', 3.4, 4.2, 11.1, 11.3, z0 + 0.42, z0 + 0.85, M['manta'], cR) if False else None
    planta('R_planta', 6.65, 11.55, z0, cR, 1.3)
    planta('R_planta2', 3.25, 6.95, z0, cR, 1.0)
    cyl('R_cand_pe', 6.75, 10.20, z0, z0 + 1.55, 0.012, M['preto'], 8, cR)
    cyl('R_cand_abaj', 6.75, 10.20, z0 + 1.50, z0 + 1.75, 0.18, M['cortina'], 24, cR)
    ld = bpy.data.lights.new('R_cand_luz', 'POINT'); ld.energy = 25; ld.color = (1, 0.8, 0.6)
    ob = bpy.data.objects.new('R_cand_luz', ld); ob.location = (6.75, 10.2, z0 + 1.62); cR.objects.link(ob)
    quadro('R_quadro', 7.03, 7.04, 7.9, 9.1, z0 + 1.15, z0 + 1.85, M['quadro1'], cR)
    cortina('R_cort1', 3.05, 3.35, 11.40, 11.48, z0, cR)
    cortina('R_cort2', 4.85, 5.06, 11.40, 11.48, z0, cR)
    box('R_aparador', 3.0, 3.42, 5.4, 6.6, z0, z0 + 0.80, M['branco_lacado'], cR)
    luz_teto('R_luz_sala1', 5.0, 6.0, z0, 50, 0.4, col=cR)
    luz_teto('R_luz_sala2', 5.0, 9.5, z0, 50, 0.4, col=cR)
    # hall de entrada / corredor / despensa / WC social
    box('R_hall_consola', 0.22, 0.55, 8.9, 10.1, z0 + 0.75, z0 + 0.79, M['madeira'], cR)
    box('R_hall_sapateira', 0.22, 0.55, 8.9, 10.1, z0 + 0.10, z0 + 0.60, M['branco_lacado'], cR)
    box('R_hall_espelho', 0.20, 0.21, 9.1, 9.9, z0 + 1.1, z0 + 2.0, M['espelho'], cR)
    for k in range(4):
        cyl(f'R_cabide{k}', 2.70, 8.80 + k * 0.25, z0 + 1.65, z0 + 1.67, 0.02, M['preto'], 8, cR)
    planta('R_hall_planta', 2.55, 10.25, z0, cR, 0.9)
    quadro('R_corr_quadro', 2.81, 2.82, 6.2, 7.4, z0 + 1.2, z0 + 1.9, M['quadro2'], cR)
    for k in range(5):
        box(f'R_desp_prat{k}', 0.22, 0.55, 5.0, 5.95, z0 + 0.3 + k * 0.42, z0 + 0.33 + k * 0.42, M['madeira'], cR)
        box(f'R_desp_prat_b{k}', 0.55, 1.39, 5.62, 5.98, z0 + 0.3 + k * 0.42, z0 + 0.33 + k * 0.42, M['madeira'], cR)
        for j in range(3):
            box(f'R_desp_fr{k}{j}', 0.26 + j * 0.0, 0.48, 5.1 + j * 0.28, 5.3 + j * 0.28, z0 + 0.33 + k * 0.42, z0 + 0.53 + k * 0.42, M['vaso' if (k + j) % 2 else 'quadro2'], cR)
    sanita('R_wc_san', 0.20, 7.70, z0, 'O', cR)
    lavatorio('R_wc_lav', 0.21, 0.66, 6.30, 6.95, z0, 'O', cR)
    luz_teto('R_luz_hall', 1.5, 9.5, z0, 40, 0.3, col=cR)
    luz_teto('R_luz_corr', 2.2, 6.0, z0, 30, 0.3, col=cR)
    luz_teto('R_luz_desp', 0.8, 5.45, z0, 15, 0.25, col=cR)
    luz_teto('R_luz_wc', 0.8, 7.25, z0, 25, 0.25, col=cR)
    luz_teto('R_luz_esc', 1.5, 2.0, z0, 30, 0.3, col=cR)

    # ---------------- 1º PISO (z0 = 6)
    z0 = Z['p1']
    Hp = PD + 0.30
    parede('P_emp_esq', 0.0, 0.2, 0.0, 10.69, z0, Hp, col=cP)
    parede('P_emp_dir', 7.04, 7.24, 0.1, 11.16, z0, Hp, col=cP)
    parede('P_tras_esq', 0.0, 2.93, 0.0, 0.2, z0, Hp, [(1.0, 2.0, 0.14, 2.24)], col=cP)
    parede('P_tras_dir', 2.93, 7.24, 0.1, 0.31, z0, Hp, [(4.07, 5.57, 1.2, 2.2)], col=cP)
    parede('P_fr_esq', 0.2, 3.71, 10.49, 10.69, z0, Hp, [(1.75, 2.65, 1.0, 2.0)], col=cP)
    parede('P_fr_deg', 3.48, 3.71, 10.69, 11.16, z0, Hp, col=cP)
    parede('P_fr_dir', 3.71, 7.04, 10.96, 11.16, z0, Hp, [(4.07, 4.97, 1.0, 2.0)], col=cP)
    box('P_roupeiro_esc', 2.91, 3.50, 0.31, 2.71, z0, z0 + PD, M['branco_lacado'], cP)
    parede('P_q1_o', 3.50, 3.56, 0.31, 2.71, z0, Hp, col=cP)
    parede('P_wc1_n', 1.41, 3.56, 2.71, 2.84, z0, Hp, col=cP)
    parede('P_wc1_o', 1.41, 1.59, 2.84, 5.25, z0, Hp, col=cP)
    parede('P_wc1_e', 3.42, 3.56, 2.84, 5.14, z0, Hp, [(3.35, 4.25, 0.0, 2.05)], col=cP)
    parede('P_wc1_s', 1.41, 3.56, 5.14, 5.25, z0, Hp, col=cP)
    parede('P_vest_s', 3.56, 4.74, 5.14, 5.25, z0, Hp, [(3.71, 4.60, 0.0, 2.05)], col=cP)
    parede('P_q1_s', 4.74, 7.04, 4.33, 4.42, z0, Hp, col=cP)
    parede('P_wc2_o', 4.74, 4.84, 4.33, 6.77, z0, Hp, [(5.56, 6.45, 0.0, 2.05)], col=cP)
    parede('P_hall_s', 2.56, 7.04, 6.77, 6.86, z0, Hp, [(2.62, 3.38, 0.0, 2.05), (3.80, 4.60, 0.0, 2.05)], col=cP)
    parede('P_q2_n', 0.2, 2.56, 6.16, 6.27, z0, Hp, col=cP)
    parede('P_q2_deg', 2.46, 2.56, 6.16, 6.86, z0, Hp, col=cP)
    parede('P_q2q3', 3.48, 3.71, 6.86, 10.96, z0, Hp, col=cP)
    # guardas da caixa de escada
    box('P_guarda1', 1.38, 1.52, 2.75, 3.60, z0, z0 + 1.0, M['parede'], cP)
    box('P_guarda2', 0.2, 1.38, 3.58, 3.62, z0, z0 + 1.0, M['vidro'], cP)
    box('P_guarda2_c', 0.2, 1.38, 3.57, 3.63, z0 + 0.98, z0 + 1.02, M['madeira'], cP)
    janela('P_jan_esc', 1.0, 2.0, 0.0, 0.2, z0 + 0.14, z0 + 2.24, cP, porta=True, folhas=1)
    janela('P_jan_q1', 4.07, 5.57, 0.1, 0.31, z0 + 1.2, z0 + 2.2, cP)
    janela('P_jan_q2', 1.75, 2.65, 10.49, 10.69, z0 + 1.0, z0 + 2.0, cP)
    janela('P_jan_q3', 4.07, 4.97, 10.96, 11.16, z0 + 1.0, z0 + 2.0, cP)
    porta_int('P_p_wc1', 3.42, 3.56, 3.35, 4.25, z0, col=cP)
    porta_int('P_p_q1', 3.71, 4.60, 5.14, 5.25, z0, col=cP)
    porta_int('P_p_wc2', 4.74, 4.84, 5.56, 6.45, z0, col=cP)
    porta_int('P_p_q2', 2.62, 3.38, 6.77, 6.86, z0, col=cP)
    porta_int('P_p_q3', 3.80, 4.60, 6.77, 6.86, z0, col=cP)
    # pavimentos
    pavimento('P_pav_q1', 3.56, 7.04, 0.31, 4.33, z0, M['soalho_x'], cP)
    pavimento('P_pav_vest', 3.56, 4.74, 4.33, 5.14, z0, M['soalho_x'], cP)
    pavimento('P_pav_hall', 2.56, 4.74, 5.25, 6.77, z0, M['soalho'], cP)
    pavimento('P_pav_hall2', 0.2, 2.56, 3.60, 6.16, z0, M['soalho'], cP)
    pavimento('P_pav_hall3', 1.38, 1.41, 2.75, 3.60, z0, M['soalho'], cP)
    pavimento('P_pav_q2', 0.2, 3.48, 6.27, 10.49, z0, M['soalho'], cP)
    pavimento('P_pav_q3', 3.71, 7.04, 6.86, 10.96, z0, M['soalho'], cP)
    pavimento('P_pav_wc1', 1.59, 3.42, 2.84, 5.14, z0, M['cer_wc_chao'], cP, 0.012)
    pavimento('P_pav_wc2', 4.84, 7.04, 4.42, 6.77, z0, M['cer_wc_chao'], cP, 0.012)
    revest_parede('P_wc1_rev', 1.59, 3.42, 2.84, 5.14, z0 + 0.012, PD, M['cer_wc_parede'], {'E': [(3.35, 4.25, 0, 2.05)]}, cP)
    revest_parede('P_wc2_rev', 4.84, 7.04, 4.42, 6.77, z0 + 0.012, PD, M['cer_wc_parede'], {'O': [(5.56, 6.45, 0, 2.05)]}, cP)
    # Quarto 1 (traseiras): cama de casal com cabeceira na empena direita, roupeiro na parede esq.
    cama('P_q1_cama', 4.95, 6.95, 1.20, 2.80, z0, 'E', cP)
    mesa_cabeceira('P_q1_mc1', 6.80, 0.85, z0, cP)
    mesa_cabeceira('P_q1_mc2', 6.80, 3.15, z0, cP)
    roupeiro('P_q1_roup', 3.56, 4.16, 0.40, 2.60, z0, 'E', cP)
    tapete('P_q1_tap', 4.4, 5.2, 1.0, 3.0, z0, cP)
    quadro('P_q1_quadro', 7.03, 7.04, 1.4, 2.6, z0 + 1.3, z0 + 1.9, M['quadro1'], cP)
    planta('P_q1_planta', 4.40, 3.95, z0, cP, 0.9)
    luz_teto('P_luz_q1', 5.3, 2.2, z0, 50, 0.4, col=cP)
    # Quarto 2 (frente esq.): cama de solteiro, secretária sob a janela, roupeiro existente
    roupeiro('P_q2_roup', 0.55, 2.46, 6.27, 6.87, z0, 'S', cP)
    cama('P_q2_cama', 0.22, 1.22, 7.4, 9.4, z0, 'O', cP, 1)
    mesa_cabeceira('P_q2_mc', 0.45, 9.75, z0, cP)
    mesa('P_q2_secret', 1.75, 2.95, 9.85, 10.45, z0, cP)
    cadeira('P_q2_cad', 2.35, 9.55, z0, 'N', cP)
    box('P_q2_estante', 3.05, 3.46, 7.2, 8.6, z0, z0 + 1.8, M['madeira'], cP)
    tapete('P_q2_tap', 1.4, 2.8, 7.6, 9.2, z0, cP)
    luz_teto('P_luz_q2', 1.8, 8.4, z0, 45, 0.4, col=cP)
    cortina('P_q2_cort', 1.55, 1.73, 10.40, 10.47, z0, cP)
    # Quarto 3 (frente dir.): cama de casal, cabeceira na empena direita
    cama('P_q3_cama', 5.0, 7.0, 7.6, 9.2, z0, 'E', cP)
    mesa_cabeceira('P_q3_mc1', 6.80, 7.25, z0, cP)
    mesa_cabeceira('P_q3_mc2', 6.80, 9.55, z0, cP)
    roupeiro('P_q3_roup', 3.71, 4.31, 7.6, 9.8, z0, 'E', cP)
    tapete('P_q3_tap', 4.5, 5.3, 7.4, 9.4, z0, cP)
    box('P_q3_comoda', 5.6, 6.9, 10.45, 10.94, z0, z0 + 0.8, M['madeira'], cP)
    quadro('P_q3_quadro', 7.03, 7.04, 7.8, 9.0, z0 + 1.3, z0 + 1.9, M['quadro2'], cP)
    luz_teto('P_luz_q3', 5.2, 8.9, z0, 50, 0.4, col=cP)
    cortina('P_q3_cort', 3.85, 4.05, 10.87, 10.94, z0, cP)
    # WC 1 (suite Q1): base de duche junto à fachada? (parede norte = escada) — duche no canto NO
    duche('P_wc1_duche', 1.60, 2.55, 2.85, 3.75, z0 + 0.012, 'N', cP)
    sanita('P_wc1_san', 1.59, 4.60, z0 + 0.012, 'O', cP)
    lavatorio('P_wc1_lav', 2.70, 3.40, 4.62, 5.13, z0 + 0.012, 'N', cP)
    luz_teto('P_luz_wc1', 2.5, 4.0, z0, 30, 0.3, col=cP)
    # WC 2: banheira na empena direita, sanita e lavatório
    banheira('P_wc2_banh', 6.30, 7.03, 4.45, 6.15, z0 + 0.012, cP)
    sanita('P_wc2_san', 4.84, 4.95, z0 + 0.012, 'O', cP) if False else sanita('P_wc2_san', 5.40, 4.43, z0 + 0.012, 'S', cP)
    lavatorio('P_wc2_lav', 4.85, 5.35, 6.18, 6.76, z0 + 0.012, 'N', cP)
    luz_teto('P_luz_wc2', 5.9, 5.6, z0, 30, 0.3, col=cP)
    # Hall do 1º piso
    quadro('P_hall_quadro', 4.73, 4.74, 5.5, 6.3, z0 + 1.2, z0 + 1.8, M['quadro2'], cP) if False else None
    planta('P_hall_planta', 0.45, 5.85, z0, cP, 1.0)
    box('P_hall_banco', 0.22, 0.60, 4.3, 5.3, z0, z0 + 0.45, M['madeira'], cP)
    luz_teto('P_luz_hall', 2.0, 5.0, z0, 35, 0.3, col=cP)
    luz_teto('P_luz_hall2', 3.6, 6.0, z0, 25, 0.3, col=cP)

    # ---------------- EXTERIOR: fachadas, cobertura, vizinhos, terreno
    cap, gran = M['capoto'], M['granito']
    # pele de capoto nas fachadas (traseira e principal)
    parede('cap_tras_esq', 0.0, 2.98, -0.06, 0.0, 0.0, 8.9, [(1.0, 2.0, 0.9, 1.5), (1.0, 2.0, 2.15, 4.25), (1.0, 2.0, 6.14, 8.24)], cap, cX)
    parede('cap_tras_dir', 2.98, 7.24, 0.04, 0.1, 0.0, 8.9, [(3.2, 5.7, 0.0, 2.3), (6.21, 6.82, 1.05, 1.95), (4.22, 5.71, 4.2, 5.2), (4.07, 5.57, 7.2, 8.2)], cap, cX)
    parede('cap_fr_hall', 0.2, 2.82, 10.69, 10.75, 3.0, 5.9, [(0.6, 2.5, 0.0, 2.1), (1.75, 2.65, 4.0, 5.0)], cap, cX)
    parede('cap_fr_p1b', 2.82, 3.71, 10.69, 10.75, 6.0, 2.9, [], cap, cX)
    parede('cap_fr_q3', 3.71, 7.24, 11.16, 11.22, 6.0, 2.9, [(4.07, 4.97, 1.0, 2.0)], cap, cX)
    parede('cap_fr_sala', 2.82, 5.07, 11.71, 11.77, 3.0, 3.0, [(3.21, 4.97, 0.0, 2.1)], cap, cX)
    box('pedra_fr', 5.07, 7.24, 12.16, 12.24, 3.0, 6.0, gran, cX)
    # cobertura em telha a 2 águas (cumeeira paralela à rua, ~35 %)
    yc, ze, inc = 5.58, Z['p1'] + PD + 0.30, 0.35
    zr = ze + yc * inc
    import bmesh
    for nome, ya, yb in (('telhado_tras', -0.45, yc), ('telhado_frente', 11.61, yc)):
        za = ze - 0.45 * inc
        me = bpy.data.meshes.new(nome)
        v = [(-0.0, ya, za), (7.24, ya, za), (7.24, yb, zr), (0.0, yb, zr),
             (-0.0, ya, za + 0.12), (7.24, ya, za + 0.12), (7.24, yb, zr + 0.12), (0.0, yb, zr + 0.12)]
        f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        me.from_pydata(v, [], f)
        ob = bpy.data.objects.new(nome, me); ob.data.materials.append(M['telha']); cX.objects.link(ob)
    for xx, nm in ((0.0, 'emp_esq'), (7.04, 'emp_dir')):
        me = bpy.data.meshes.new('oitao_' + nm)
        v = [(xx, 0.0, ze), (xx, 11.16, ze), (xx, yc, zr), (xx + 0.2, 0.0, ze), (xx + 0.2, 11.16, ze), (xx + 0.2, yc, zr)]
        f = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
        me.from_pydata(v, [], f)
        ob = bpy.data.objects.new('oitao_' + nm, me); ob.data.materials.append(M['parede']); cX.objects.link(ob)
    box('cumeeira', 0.0, 7.24, yc - 0.12, yc + 0.12, zr + 0.08, zr + 0.18, M['telha'], cX)
    # vizinhos (moradias em banda)
    box('viz_esq', -9.0, 0.0, 0.0, 10.2, -0.3, 9.0, M['reboco_viz'], cX)
    box('viz_dir', 7.24, 16.0, 1.0, 12.9, -0.3, 9.0, M['reboco_viz'], cX)
    box('viz_esq_tel', -9.0, 0.0, -0.3, 10.5, 9.0, 9.2, M['telha'], cX)
    box('viz_dir_tel', 7.24, 16.0, 0.7, 13.2, 9.0, 9.2, M['telha'], cX)
    # terreno: quintal (traseiras, cota da cave) e rua (frente, cota do R/C)
    box('quintal_relva', -9.0, 16.0, -14.0, -2.5, -0.05, 0.0, M['relva'], cX)
    box('quintal_patio', -9.0, 16.0, -2.5, 0.0, -0.05, 0.0, M['calcada'], cX)
    box('muro_fundo', -9.0, 16.0, -14.2, -14.0, 0.0, 1.8, M['reboco_viz'], cX)
    box('rua_passeio', -9.0, 16.0, 11.2, 14.0, 2.85, 3.0, M['calcada'], cX)
    box('rua', -30.0, 40.0, 14.0, 22.0, 2.7, 2.85, M['preto'], cX)
    box('frente_casas', -30.0, 40.0, 24.0, 25.0, 2.7, 10.0, M['reboco_viz'], cX)
    box('entrada_patamar', 0.2, 2.82, 10.69, 11.55, 2.85, 3.0, M['granito'], cX)
    box('terraco_sala', 2.82, 5.07, 11.71, 12.16, 2.85, 3.0, M['granito'], cX)
    return M


def luz_natural(sol_elev=38, sol_rot=200, forca_ceu=1.0, forca_sol=3.5):
    sc = bpy.context.scene
    w = bpy.data.worlds.new('Ceu')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    sky = nt.nodes.new('ShaderNodeTexSky')
    for tipo in ('MULTIPLE_SCATTERING', 'NISHITA', 'HOSEK_WILKIE'):
        try:
            sky.sky_type = tipo
            break
        except Exception:
            continue
    try:
        sky.sun_disc = False
        sky.sun_elevation = math.radians(sol_elev)
        sky.sun_rotation = math.radians(sol_rot)
    except Exception:
        pass
    bg.inputs['Strength'].default_value = forca_ceu
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    ld = bpy.data.lights.new('Sol', 'SUN')
    ld.energy = forca_sol
    ld.angle = math.radians(0.6)
    ld.color = (1.0, 0.95, 0.88)
    ob = bpy.data.objects.new('Sol', ld)
    # direção: sol vindo da frente/esquerda (fachada principal), elevação sol_elev
    ob.rotation_euler = (math.radians(90 - sol_elev), 0, math.radians(sol_rot))
    sc.collection.objects.link(ob)
