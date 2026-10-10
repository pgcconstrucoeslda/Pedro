"""Deteção de vãos (portas e janelas) por compartimento.

Para cada lado do polígono de um compartimento procuram-se, nos layers de vãos
(portas/janelas/caixilharia), os elementos encostados a esse lado:

* **portas** - arcos de abertura (raio 0,5-1,3 m) com o centro junto ao lado; a
  largura é o raio e o vão vai do centro até ao ponto do arco que está sobre a parede;
* **janelas/vãos** - linhas paralelas ao lado, a menos de 0,45 m; a largura é a
  projeção (unida) dessas linhas sobre o lado.

A altura não se lê em planta: é preenchida com valores por defeito (editáveis)
e, quando o MQ indica dimensões (ex.: "2.50x0.80"), pode ser ajustada.
Cada vão guarda os *handles* das entidades que o originaram.
"""
from __future__ import annotations

import pandas as pd
from ezdxf.math import Vec2, is_point_in_polygon_2d

DIST_MAX = 0.45   # m - distância máxima do elemento ao lado do compartimento
GAP = 0.10        # m - junção de troços
L_MIN, L_MAX = 0.45, 6.5  # m - largura admissível de um vão

COLS = ["id", "folha", "compartimento", "handle_poligono", "lado", "tipo", "largura", "altura", "area",
        "espessura_parede", "handle_parede", "x", "y", "handles"]


def _merge(iv, gap):
    iv = sorted(iv)
    out = []
    for a, b, hs in iv:
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
            out[-1][2] |= hs
        else:
            out.append([a, b, set(hs)])
    return out


def detetar_vaos(res) -> pd.DataFrame:
    f = res.fator
    comps = res.compartimentos
    if comps.empty or not res.poligonos or not (res.segs_vaos or res.arcos_vaos):
        return pd.DataFrame(columns=COLS)
    dmax, gap = DIST_MAX / f, GAP / f
    segs = [(h, a, b) for h, a, b in res.segs_vaos if (b - a).magnitude > 1e-9]
    arcs = [a for a in res.arcos_vaos if 0.5 / f <= a[2] <= 1.3 / f]
    paredes = [(r.handle, r.espessura, res.poligonos.get(r.handle)) for r in res.paredes.itertuples()
               if res.poligonos.get(r.handle)]
    rows = []
    for c in comps.itertuples():
        verts = res.poligonos.get(c.handle_poligono)
        if not verts:
            continue
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        x0, x1, y0, y1 = min(xs) - dmax, max(xs) + dmax, min(ys) - dmax, max(ys) + dmax

        def perto(p):
            return x0 <= p.x <= x1 and y0 <= p.y <= y1

        sg = [s for s in segs if perto(s[1]) or perto(s[2])]
        ac = [a for a in arcs if perto(a[1])]
        n = len(verts)
        lados = []
        for i in range(n):
            p, q = verts[i], verts[(i + 1) % n]
            L = (q - p).magnitude
            if L * f < 0.4:
                continue
            u = (q - p) / L
            lados.append((i, p, u, Vec2(-u.y, u.x), L))
        # portas: cada arco é atribuído a um só lado (o mais próximo do centro) - evita contar
        # duas vezes as portas de canto
        cand_portas: dict = {}
        for i, p, u, nr, L in lados:
            for h, cen, r, ps, pe in ac:
                dist = abs((cen - p).dot(nr))
                if dist > dmax:
                    continue
                tc = (cen - p).dot(u)
                ends = [e for e in (ps, pe) if abs((e - p).dot(nr)) <= dmax]
                if not ends:
                    continue
                te = (ends[0] - p).dot(u)
                a_, b_ = min(tc, te), max(tc, te)
                # a abertura tem de caber no lado (exclui portas de paredes alinhadas vizinhas)
                if a_ < -gap or b_ > L + gap:
                    continue
                if h not in cand_portas or dist < cand_portas[h][0]:
                    cand_portas[h] = (dist, i, max(a_, 0), min(b_, L))
        for i, p, u, nr, L in lados:
            portas = [(a_, b_, {h}) for h, (_, li, a_, b_) in cand_portas.items() if li == i]
            janelas = []
            for h, a, b in sg:
                w = b - a
                if abs(u.x * w.y - u.y * w.x) / w.magnitude > 0.15:
                    continue
                mid = (a + b) / 2
                if abs((mid - p).dot(nr)) > dmax:
                    continue
                ta, tb = sorted(((a - p).dot(u), (b - p).dot(u)))
                ta, tb = max(ta, 0), min(tb, L)
                if tb - ta < 0.05 / f:
                    continue
                janelas.append((ta, tb, {h}))
            portas = _merge(portas, gap)
            # troços de janela que coincidem com portas pertencem à porta
            janelas = [j for j in _merge(janelas, gap)
                       if not any(j[0] < pb + gap and j[1] > pa - gap for pa, pb, _ in portas)]
            for tipo, lst in (("porta", portas), ("janela/vão", janelas)):
                for a_, b_, hs in lst:
                    larg = (b_ - a_) * f
                    if not L_MIN <= larg <= L_MAX:
                        continue
                    mid = p + u * ((a_ + b_) / 2)
                    # parede onde está o vão: ponto ligeiramente fora do compartimento
                    fora = mid + nr * (0.10 / f)
                    if is_point_in_polygon_2d(fora, verts) > 0:
                        fora = mid - nr * (0.10 / f)
                    esp, hp = None, ""
                    for hw, e, pv in paredes:
                        if is_point_in_polygon_2d(fora, pv) >= 0:
                            esp, hp = e, hw
                            break
                    rows.append(dict(folha=c.folha, compartimento=c.compartimento, handle_poligono=c.handle_poligono,
                                     lado=i + 1, tipo=tipo, largura=round(larg, 2), altura=None, area=None,
                                     espessura_parede=esp, handle_parede=hp, x=mid.x, y=mid.y,
                                     handles=", ".join(sorted(map(str, hs))[:6])))
    df = pd.DataFrame(rows, columns=COLS)
    df["id"] = [f"V{i + 1:03d}" for i in range(len(df))]
    return deduplicar(df, f)


def aplicar_alturas(vaos: pd.DataFrame, alt_porta: float, alt_janela: float) -> pd.DataFrame:
    """Preenche alturas em falta e calcula a área de cada vão."""
    if vaos is None or vaos.empty:
        return vaos
    v = vaos.copy()
    falta = v.altura.isna()
    v.loc[falta & (v.tipo == "porta"), "altura"] = alt_porta
    v.loc[falta & (v.tipo != "porta"), "altura"] = alt_janela
    v["area"] = (v.largura * v.altura).round(3)
    return v


# ---------------------------------------------------------------- mapa de vãos do MQ
import re as _re

RE_DIM = _re.compile(r"(\d+[.,]\d+)\s*[xX×]\s*(\d+[.,]\d+)")
RE_COD = _re.compile(r"\b((?:V[eEiI]|P[eEiI]?|J)\s?\d{1,3})\b")


def mapa_vaos_mq(mq: pd.DataFrame) -> pd.DataFrame:
    """Vãos descritos no MQ (ex.: 'Ve03 (1.30x2.50m)', 'Portas de batente 2.50x0.80')."""
    rows = []
    if mq is None or mq.empty:
        return pd.DataFrame(columns=["codigo", "tipo", "largura", "altura", "quantidade", "item_mq"])
    for _, it in mq.iterrows():
        if it.unidade != "un":
            continue
        txt = f"{it.local} {it.descricao if not it.local else ''}"
        if not _re.search(r"\bV[eEiI]?\s?\d|porta|janela|caixilh|v[ãa]o|portão", txt, _re.I):
            continue
        if _re.search(r"arm[áa]rio|m[óo]vel|espelho|duche|tampa", txt, _re.I):
            continue
        dims = [(float(a.replace(",", ".")), float(b.replace(",", "."))) for a, b in RE_DIM.findall(str(it.local or txt))]
        if not dims:
            continue
        cod = RE_COD.search(str(it.local))
        porta = bool(_re.search(r"porta|portão", txt, _re.I)) and not cod
        for a, b in dims:
            # nas portas o MQ indica muitas vezes altura x largura (2.50x0.80, 2.00x4.10):
            # a altura é a dimensão típica de porta (1,90-2,70 m)
            if porta and (1.9 <= a <= 2.7) != (1.9 <= b <= 2.7):
                h, w = (a, b) if 1.9 <= a <= 2.7 else (b, a)
            else:
                w, h = a, b
            rows.append(dict(codigo=cod.group(1).replace(" ", "") if cod else "", tipo="porta" if porta else "janela/vão",
                             largura=w, altura=h, quantidade=it.quantidade, item_mq=it.id))
    return pd.DataFrame(rows, columns=["codigo", "tipo", "largura", "altura", "quantidade", "item_mq"])


def deduplicar(vaos: pd.DataFrame, f: float = 1.0) -> pd.DataFrame:
    """Remove vãos repetidos no mesmo compartimento (ex.: dois arcos da mesma porta)."""
    if vaos.empty:
        return vaos
    keep = []
    for (_, _), g in vaos.groupby(["handle_poligono", "tipo"], sort=False):
        acc = []
        for r in g.sort_values("largura", ascending=False).itertuples():
            if any(((r.x - a.x) ** 2 + (r.y - a.y) ** 2) ** 0.5 * f < max(r.largura, a.largura) * 0.6 for a in acc):
                continue
            acc.append(r)
        keep += [a.Index for a in acc]
    out = vaos.loc[sorted(keep)].reset_index(drop=True)
    out["id"] = [f"V{i + 1:03d}" for i in range(len(out))]
    return out


def associar_mq(vaos: pd.DataFrame, mapa: pd.DataFrame, tol: float = 0.06) -> pd.DataFrame:
    """Atribui a cada vão detetado o vão do MQ com a mesma largura (± tol) e tipo.

    Cada linha do MQ é usada no máximo tantas vezes quanto a sua quantidade (os
    vãos de compartimentos vizinhos que partilham a mesma abertura contam uma vez).
    Daí resultam a altura e o código (ex.: Ve12)."""
    v = vaos.copy()
    if "codigo_mq" not in v:
        v["codigo_mq"] = ""
        v["item_mq"] = ""
    if v.empty or mapa.empty:
        return v
    usos = {i: 0 for i in mapa.index}
    abertura: dict = {}  # posição arredondada -> índice do mapa (mesma abertura vista de dois lados)
    for i, r in v.sort_values("largura", ascending=False).iterrows():
        chave = (round(r.x, 0), round(r.y, 0), r.tipo)
        cand = mapa[((mapa.largura - r.largura).abs() <= tol) & (mapa.tipo == r.tipo)]
        if cand.empty:
            continue
        if chave in abertura:
            j = abertura[chave]
        else:
            livres = [j for j in cand.index if usos[j] < max(int(mapa.at[j, "quantidade"] or 1), 1)]
            pool = livres or list(cand.index)
            j = min(pool, key=lambda j: abs(mapa.at[j, "largura"] - r.largura))
            usos[j] += 1
            abertura[chave] = j
        best = mapa.loc[j]
        if pd.isna(r.altura):
            v.at[i, "altura"] = best.altura
        v.at[i, "codigo_mq"] = best.codigo or "(MQ)"
        v.at[i, "item_mq"] = best.item_mq
    return v
