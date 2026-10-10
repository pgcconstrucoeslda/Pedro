"""Extração geométrica de um DXF.

Produz tabelas rastreáveis (cada linha tem o *handle* da entidade no desenho):

* ``folhas``        - folhas/desenhos detetados (molduras ou layouts);
* ``entidades``     - todas as entidades do espaço modelo com comprimento/área;
* ``compartimentos``- etiquetas "nome + área m²" e o polígono que as contém;
* ``paredes``       - paredes estimadas a partir das tramas (comprimento e espessura).

Todas as medidas são devolvidas em metros (m, m²) aplicando o fator de escala
das unidades do desenho.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

import ezdxf
import ezdxf.path
import pandas as pd
from ezdxf import bbox, recover
from ezdxf.math import Vec2, area as poly_area, is_point_in_polygon_2d

FLAT = 0.01  # tolerância de discretização de arcos (unidades do desenho)

RE_AREA = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*m\s*(?:²|2|\^2)\s*$", re.I)
RE_TITULO = re.compile(
    r"^\s*(planta|cortes?|al[çc]ados?|pormenor|implanta|cobertura|piso|cave|r/?c|r[ée]s)", re.I
)
RE_NUM_FOLHA = re.compile(r"^\s*[A-Z]{0,3}\.?\s?\d{1,3}\s*$")

UNIT_FACTORS = {"m": 1.0, "cm": 0.01, "mm": 0.001}


def norm(txt: str) -> str:
    """Normaliza texto para comparação (sem acentos, pontuação, espaços, minúsculas)."""
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", txt.lower())


@dataclass
class Folha:
    id: str
    nome: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    origem: str  # moldura | layout | modelo
    nivel: str = ""  # alias editável (ex.: "Piso 1")

    def contem(self, x: float, y: float) -> bool:
        return self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax


@dataclass
class Resultado:
    ficheiro: str
    unidade: str
    fator: float
    folhas: list[Folha]
    entidades: pd.DataFrame
    compartimentos: pd.DataFrame
    paredes: pd.DataFrame
    avisos: list[str] = field(default_factory=list)

    def folhas_df(self) -> pd.DataFrame:
        return pd.DataFrame([f.__dict__ for f in self.folhas])

    def layers_df(self) -> pd.DataFrame:
        e = self.entidades
        if e.empty:
            return pd.DataFrame()
        g = e.groupby("layer").agg(
            entidades=("handle", "count"),
            linhas=("tipo", lambda s: int(s.isin(["LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE"]).sum())),
            tramas=("tipo", lambda s: int((s == "HATCH").sum())),
            blocos=("tipo", lambda s: int((s == "INSERT").sum())),
            textos=("tipo", lambda s: int(s.isin(["TEXT", "MTEXT"]).sum())),
            comprimento_m=("comprimento", "sum"),
            area_m2=("area", "sum"),
        )
        return g.reset_index().sort_values("entidades", ascending=False)


# ---------------------------------------------------------------- geometria

def _text_of(e) -> str:
    if e.dxftype() == "MTEXT":
        return " ".join(e.plain_text().split())
    return " ".join(str(e.dxf.text).split())


def _text_height(e) -> float:
    if e.dxftype() == "MTEXT":
        return float(e.dxf.get("char_height", 0) or 0)
    return float(e.dxf.get("height", 0) or 0)


def _polyline_vertices(e) -> tuple[list[Vec2], bool]:
    """Vértices (discretizados se houver arcos) e se é fechada."""
    if e.dxftype() == "LWPOLYLINE":
        closed = bool(e.closed)
        pts = list(e.get_points("xyb"))
        if all(abs(b) < 1e-9 for _, _, b in pts):
            v = [Vec2(x, y) for x, y, _ in pts]
            if not closed and len(v) >= 4 and v[0].isclose(v[-1], abs_tol=1e-6):
                v, closed = v[:-1], True  # fechada "à mão" (último vértice = primeiro)
            return v, closed
    else:  # POLYLINE 2D
        closed = bool(e.is_closed)
    try:
        p = ezdxf.path.make_path(e)
        verts = [Vec2(v) for v in p.flattening(FLAT)]
    except Exception:
        return [], closed
    if closed and len(verts) > 1 and verts[0].isclose(verts[-1]):
        verts = verts[:-1]
    return verts, closed


def _length(verts: list[Vec2], closed: bool) -> float:
    if len(verts) < 2:
        return 0.0
    s = sum((b - a).magnitude for a, b in zip(verts, verts[1:]))
    if closed:
        s += (verts[0] - verts[-1]).magnitude
    return s


def _hatch_polys(e) -> list[tuple[list[Vec2], bool]]:
    """Polígonos de contorno da trama: (vértices, é_exterior)."""
    out = []
    ocs = e.ocs()
    elev = e.dxf.elevation.z if e.dxf.hasattr("elevation") else 0
    for bp in e.paths:
        try:
            p = ezdxf.path.from_hatch_boundary_path(bp, ocs, elev)
            verts = [Vec2(v) for v in p.flattening(FLAT)]
        except Exception:
            continue
        if len(verts) >= 3:
            flags = getattr(bp, "path_type_flags", 0)
            out.append((verts, bool(flags & 1) or bool(flags & 16)))
    return out


def _hatch_area_perim(polys) -> tuple[float, float, list[Vec2] | None]:
    if not polys:
        return 0.0, 0.0, None
    areas = [(abs(poly_area(v)), v, ext) for v, ext in polys]
    areas.sort(key=lambda t: -t[0])
    if any(ext for _, _, ext in areas) and not all(ext for _, _, ext in areas):
        a = sum(a for a, _, ext in areas if ext) - sum(a for a, _, ext in areas if not ext)
    elif len(areas) > 1 and all(ext for _, _, ext in areas):
        a = sum(a for a, _, _ in areas)  # várias regiões independentes
    else:
        a = areas[0][0] - sum(a for a, _, _ in areas[1:])
    per = sum(_length(v, True) for v, _ in polys)
    return max(a, 0.0), per, areas[0][1]


# ---------------------------------------------------------------- folhas

def _rects_modelspace(msp, minlen: float) -> list[tuple[float, float, float, float]]:
    """Retângulos alinhados com os eixos (molduras de folha) no espaço modelo."""
    tol = max(minlen * 0.002, 1e-6)
    hs, vs, rects = [], [], []
    for e in msp.query("LINE LWPOLYLINE"):
        if e.dxftype() == "LINE":
            segs = [(Vec2(e.dxf.start), Vec2(e.dxf.end))]
        else:
            pts = [Vec2(x, y) for x, y in e.get_points("xy")]
            if e.closed and len(pts) in (4, 5):
                xs = [p.x for p in pts]
                ys = [p.y for p in pts]
                w, h = max(xs) - min(xs), max(ys) - min(ys)
                axis = all(abs(a.x - b.x) < tol or abs(a.y - b.y) < tol for a, b in zip(pts, pts[1:] + pts[:1]))
                if axis and w >= minlen and h >= minlen * 0.3:
                    rects.append((min(xs), min(ys), max(xs), max(ys)))
                    continue
            segs = list(zip(pts, pts[1:] + ([pts[0]] if e.closed else [])))
        for a, b in segs:
            if abs(a.y - b.y) < tol and abs(a.x - b.x) >= minlen:
                hs.append((min(a.x, b.x), max(a.x, b.x), a.y))
            elif abs(a.x - b.x) < tol and abs(a.y - b.y) >= minlen * 0.3:
                vs.append((min(a.y, b.y), max(a.y, b.y), a.x))
    if len(hs) < 400:
        for i, (x0, x1, ya) in enumerate(hs):
            for x0b, x1b, yb in hs[i + 1:]:
                if abs(x0 - x0b) > tol * 10 or abs(x1 - x1b) > tol * 10 or abs(ya - yb) < minlen * 0.3:
                    continue
                y0, y1 = min(ya, yb), max(ya, yb)
                left = any(abs(x - x0) < tol * 10 and v0 <= y0 + tol * 10 and v1 >= y1 - tol * 10 for v0, v1, x in vs)
                right = any(abs(x - x1) < tol * 10 and v0 <= y0 + tol * 10 and v1 >= y1 - tol * 10 for v0, v1, x in vs)
                if left and right:
                    rects.append((x0, y0, x1, y1))
    rects = sorted(set(rects), key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
    t = tol * 10

    def inside(r, k):
        return k[0] - t <= r[0] and k[1] - t <= r[1] and k[2] + t >= r[2] and k[3] + t >= r[3] and r != k

    def overlap(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    # 1) descartar "contentores" (ex.: limite geral que engloba várias folhas)
    def contentor(k):
        filhos = [r for r in rects if inside(r, k)]
        return any(not overlap(a, b) for i, a in enumerate(filhos) for b in filhos[i + 1:])

    rects = [k for k in rects if not contentor(k)]
    # 2) das molduras encaixadas (exterior/interior) manter a exterior
    keep: list[tuple[float, float, float, float]] = []
    for r in rects:
        if not any(inside(r, k) for k in keep):
            keep.append(r)
    # 3) se ainda houver sobreposições parciais, manter a maior
    final: list[tuple[float, float, float, float]] = []
    for r in keep:
        if not any(overlap(r, k) for k in final):
            final.append(r)
    return final


def _sheets_from_layouts(doc) -> list[Folha]:
    out = []
    for lay in doc.layouts:
        if lay.name.lower() == "model":
            continue
        vps = [v for v in lay.query("VIEWPORT") if v.dxf.get("id", 2) != 1]
        for i, v in enumerate(vps):
            h = v.dxf.get("view_height", 0)
            if not h or not v.dxf.get("height"):
                continue
            w = h * v.dxf.width / v.dxf.height
            c = v.dxf.view_center_point
            fid = f"{lay.name}" + (f"-{i + 1}" if len(vps) > 1 else "")
            out.append(Folha(fid, fid, c.x - w / 2, c.y - h / 2, c.x + w / 2, c.y + h / 2, "layout"))
    return out


def detetar_folhas(doc, extents) -> list[Folha]:
    msp = doc.modelspace()
    size = max(extents.size.x, extents.size.y) if extents.has_data else 0
    folhas: list[Folha] = []
    if size > 0:
        rects = _rects_modelspace(msp, minlen=size * 0.08)
        # descartar retângulos minúsculos face ao maior
        if rects:
            amax = max((r[2] - r[0]) * (r[3] - r[1]) for r in rects)
            rects = [r for r in rects if (r[2] - r[0]) * (r[3] - r[1]) >= amax * 0.2]
        if len(rects) >= 2:
            rects.sort(key=lambda r: (-round(r[3], 0), r[0]))
            folhas = [Folha(f"F{i + 1:02d}", f"Folha {i + 1}", *r, origem="moldura") for i, r in enumerate(rects)]
    if not folhas:
        folhas = _sheets_from_layouts(doc)
    if not folhas and extents.has_data:
        folhas = [Folha("F01", "Modelo", extents.extmin.x, extents.extmin.y, extents.extmax.x, extents.extmax.y, "modelo")]
    return folhas


def _nomear_folhas(folhas: list[Folha], textos: pd.DataFrame) -> None:
    cand = textos[textos.texto.str.match(RE_TITULO) & (textos.texto.str.len() <= 120) & (textos.folha != "")]
    # o layer dos títulos é o que tem um título candidato em mais folhas
    layer_tit = None
    if not cand.empty:
        cont = cand.groupby("layer").folha.nunique()
        if cont.max() >= max(2, len(folhas) // 2):
            layer_tit = cont.idxmax()
    for f in folhas:
        c = cand[cand.folha == f.id]
        if layer_tit is not None and (c.layer == layer_tit).any():
            c = c[c.layer == layer_tit]
        if not c.empty:
            top_h = c.altura.max()
            f.nome = c[c.altura >= top_h * 0.8].sort_values("y").iloc[0].texto
        f.nivel = sugerir_nivel(f.nome)


def sugerir_nivel(nome: str) -> str:
    n = nome.lower()
    m = re.search(r"piso\s*(-?\d+)", n)
    if m:
        return f"Piso {m.group(1)}"
    if re.search(r"\br[ée]s[\s-]*d[oe]|\br/c\b|t[ée]rreo", n):
        return "R/C"
    if "cave" in n:
        return "Cave"
    if "cobertura" in n:
        return "Cobertura"
    if "implanta" in n:
        return "Implantação"
    if re.search(r"corte|al[çc]ado", n):
        return "Cortes/Alçados"
    return ""


# ---------------------------------------------------------------- unidades

def adivinhar_unidade(doc, extents) -> tuple[str, str]:
    """Devolve (unidade, justificação). O $INSUNITS é muitas vezes incoerente,
    por isso confirma-se pela dimensão do desenho."""
    ins = doc.header.get("$INSUNITS", 0)
    hdr = {4: "mm", 5: "cm", 6: "m"}.get(ins)
    size = max(extents.size.x, extents.size.y) if extents.has_data else 0
    if size > 20000:
        geo = "mm"
    elif size > 2000:
        geo = "cm"
    else:
        geo = "m"
    if hdr and hdr != geo:
        return geo, f"Cabeçalho indica '{hdr}' mas a dimensão do desenho ({size:.0f} un.) sugere '{geo}'. Usado '{geo}' - confirme."
    return geo, f"Unidade '{geo}' (dimensão do desenho {size:.0f} un.)."


# ---------------------------------------------------------------- dynamic blocks

def _nomes_blocos_efetivos(doc) -> dict[str, str]:
    """Mapeia blocos anónimos (*U..) para o nome do bloco dinâmico original."""
    out = {}
    for blk in doc.blocks:
        if not blk.name.startswith("*U"):
            continue
        br = blk.block_record
        try:
            if br.has_xdata("AcDbBlockRepBTag"):
                tags = br.get_xdata("AcDbBlockRepBTag")
                h = next((t.value for t in tags if t.code == 1005), None)
                src = doc.entitydb.get(h) if h else None
                if src is not None:
                    out[blk.name] = src.dxf.name
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- principal

def _ler(dxf_path: str):
    try:
        return ezdxf.readfile(dxf_path), []
    except Exception:
        doc, auditor = recover.readfile(dxf_path)
        return doc, [f"Ficheiro com {len(auditor.errors)} erros de estrutura (recuperado)."] if auditor.has_errors else []


_CENTROS_BLOCOS: dict = {}


def _medir(e, t: str):
    """Mede uma entidade sem recorrer a bounding boxes (mais rápido).

    Devolve (cx, cy, comprimento, area, perimetro, fechado, vertices) ou None.
    """
    if t == "LINE":
        a, b = Vec2(e.dxf.start), Vec2(e.dxf.end)
        c = (a + b) / 2
        return c.x, c.y, (b - a).magnitude, 0.0, 0.0, False, None
    if t == "LWPOLYLINE" or (t == "POLYLINE" and e.is_2d_polyline):
        v, fechado = _polyline_vertices(e)
        if not v:
            return None
        comp = _length(v, fechado)
        xs = [p.x for p in v]
        ys = [p.y for p in v]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        if fechado and len(v) >= 3:
            return cx, cy, comp, abs(poly_area(v)), comp, True, v
        return cx, cy, comp, 0.0, 0.0, False, None
    if t == "ARC":
        span = (e.dxf.end_angle - e.dxf.start_angle) % 360 or 360
        c = e.dxf.center
        return c.x, c.y, math.radians(span) * e.dxf.radius, 0.0, 0.0, False, None
    if t == "CIRCLE":
        c, r = e.dxf.center, e.dxf.radius
        return c.x, c.y, 2 * math.pi * r, math.pi * r * r, 2 * math.pi * r, True, None
    if t in ("SPLINE", "ELLIPSE"):
        v = [Vec2(x) for x in ezdxf.path.make_path(e).flattening(FLAT)]
        if not v:
            return None
        xs = [p.x for p in v]
        ys = [p.y for p in v]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, _length(v, False), 0.0, 0.0, False, None
    if t == "HATCH":
        area, per, outer = _hatch_area_perim(_hatch_polys(e))
        if outer is None:
            return None
        xs = [p.x for p in outer]
        ys = [p.y for p in outer]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0, area, per, True, outer
    if t in ("TEXT", "MTEXT"):
        p = e.dxf.insert
        return p.x, p.y, 0.0, 0.0, 0.0, False, None
    if t == "INSERT":
        # o ponto de inserção pode estar longe da geometria (ponto base deslocado):
        # usa-se o centro da geometria do bloco, calculado uma vez por definição
        nome = e.dxf.name
        if nome not in _CENTROS_BLOCOS:
            c = None
            try:
                blk = e.doc.blocks.get(nome)
                b = bbox.extents(blk, fast=True) if blk is not None else None
                if b is not None and b.has_data:
                    c = b.center
            except Exception:
                pass
            _CENTROS_BLOCOS[nome] = c
        c = _CENTROS_BLOCOS[nome]
        if c is not None:
            try:
                w = e.matrix44().transform(c)
                return w.x, w.y, 0.0, 0.0, 0.0, False, None
            except Exception:
                pass
        p = e.dxf.insert
        return p.x, p.y, 0.0, 0.0, 0.0, False, None
    b = bbox.extents([e], fast=True)
    if not b.has_data:
        return None
    return b.center.x, b.center.y, 0.0, 0.0, 0.0, False, None


def extrair(dxf_path: str, unidade: str | None = None, layers_ignorar: str = "", progress=None) -> Resultado:
    doc, avisos = _ler(dxf_path)
    _CENTROS_BLOCOS.clear()
    msp = doc.modelspace()
    re_ign = re.compile(layers_ignorar, re.I) if layers_ignorar else None
    efetivos = _nomes_blocos_efetivos(doc)

    rows = []
    polys = []  # (handle, layer, tipo, area, perimetro, vertices) em unidades do desenho
    ents = [e for e in msp if not (re_ign and re_ign.search(e.dxf.layer))]
    n = len(ents)
    for i, e in enumerate(ents):
        if progress and i % 5000 == 0:
            progress(0.9 * i / max(n, 1))
        t = e.dxftype()
        try:
            m = _medir(e, t)
        except Exception as ex:  # entidade problemática: regista e continua
            avisos.append(f"Entidade {e.dxf.handle} ({t}) ignorada: {ex}")
            continue
        if m is None:
            continue
        cx, cy, comp, area, per, fechado, verts = m
        bloco = texto = ""
        altura = 0.0
        if t == "INSERT":
            bloco = efetivos.get(e.dxf.name, e.dxf.name)
        elif t == "HATCH":
            bloco = e.dxf.get("pattern_name", "")
        elif t in ("TEXT", "MTEXT"):
            texto = _text_of(e)
            altura = _text_height(e)
        rows.append((e.dxf.handle, e.dxf.layer, t, bloco, texto, altura, fechado, comp, area, per, cx, cy))
        if verts is not None and area > 0:
            polys.append((e.dxf.handle, e.dxf.layer, t, area, per, verts))

    df = pd.DataFrame(rows, columns=["handle", "layer", "tipo", "bloco", "texto", "altura", "fechado",
                                     "comprimento", "area", "perimetro", "x", "y"])
    # extensão "robusta" (ignora 0,5 % de pontos extremos/perdidos)
    ext = bbox.BoundingBox()
    if not df.empty:
        qx = df.x.quantile([0.005, 0.995]).tolist()
        qy = df.y.quantile([0.005, 0.995]).tolist()
        ext = bbox.BoundingBox([(qx[0], qy[0]), (qx[1], qy[1])])
    if unidade is None:
        unidade, msg = adivinhar_unidade(doc, ext)
        avisos.append(msg)
    f = UNIT_FACTORS[unidade]
    f2 = f * f

    folhas = detetar_folhas(doc, ext)
    df.insert(1, "folha", "")
    for fo in folhas:  # a primeira folha que contém o ponto ganha
        m = (df.folha == "") & df.x.between(fo.xmin, fo.xmax) & df.y.between(fo.ymin, fo.ymax)
        df.loc[m, "folha"] = fo.id
    for c in ("comprimento", "perimetro", "altura"):
        df[c] = df[c] * f
    df["area"] = df["area"] * f2

    folha_por_handle = dict(zip(df.handle, df.folha))
    polys = [(folha_por_handle.get(h, ""), h, lay, tp, a * f2, p * f, v) for h, lay, tp, a, p, v in polys]

    textos = df[df.tipo.isin(["TEXT", "MTEXT"])]
    _nomear_folhas(folhas, textos)

    comps = _compartimentos(textos, polys, f)
    paredes = _paredes(df)
    if not comps.empty and comps.area_geometria.notna().any():
        ok = comps.dropna(subset=["area_geometria"])
        ratio = (ok.area_geometria / ok.area_etiqueta).median()
        if not 0.8 <= ratio <= 1.25:
            avisos.append(
                f"As áreas geométricas são {ratio:.3g}x as etiquetas: provável unidade errada (atual '{unidade}')."
            )
    if progress:
        progress(1.0)
    return Resultado(str(dxf_path), unidade, f, folhas, df, comps, paredes, avisos)


def _compartimentos(textos: pd.DataFrame, polys, f: float) -> pd.DataFrame:
    rows = []
    if textos.empty:
        return pd.DataFrame(columns=["folha", "compartimento", "area_etiqueta", "area_geometria",
                                     "perimetro", "desvio_%", "handle_etiqueta", "handle_poligono", "layer_poligono"])
    areas = textos[textos.texto.str.match(RE_AREA)]
    outros = textos[~textos.texto.str.match(RE_AREA) & (textos.texto.str.len().between(2, 60))
                    & ~textos.texto.str.fullmatch(r"[\d.,\s]+")]
    by_folha_polys: dict[str, list] = {}
    for p in polys:
        by_folha_polys.setdefault(p[0], []).append(p)
    for _, a in areas.iterrows():
        val = float(RE_AREA.match(a.texto).group(1).replace(",", "."))
        h = a.altura or 0.2
        o = outros[outros.folha == a.folha]
        nome = ""
        if not o.empty:
            d = ((o.x - a.x) ** 2 + (o.y - a.y) ** 2) ** 0.5 * f
            j = d.idxmin()
            if d[j] <= max(6 * h, 0.8):
                nome = o.loc[j, "texto"]
        # polígono mais pequeno que contém a etiqueta e tem área compatível
        best = None
        pt = Vec2(a.x, a.y)
        for fo, hd, lay, tp, ar, per, verts in by_folha_polys.get(a.folha, []):
            if ar < val * 0.6 or ar > val * 1.6:
                continue
            if is_point_in_polygon_2d(pt, verts) >= 0:
                if best is None or abs(ar - val) < abs(best[1] - val):
                    best = (hd, ar, per, lay)
        rows.append(dict(
            folha=a.folha, compartimento=nome or "(sem nome)", area_etiqueta=val,
            area_geometria=round(best[1], 3) if best else None,
            perimetro=round(best[2], 3) if best else None,
            **{"desvio_%": round((best[1] - val) / val * 100, 1) if best and val else None},
            handle_etiqueta=a.handle, handle_poligono=best[0] if best else "",
            layer_poligono=best[3] if best else "",
        ))
    return pd.DataFrame(rows)


RE_PAREDE_DEFAULT = r"parede|wall|alvenaria"


def _paredes(df: pd.DataFrame, layers_regex: str = RE_PAREDE_DEFAULT) -> pd.DataFrame:
    """Estima comprimento e espessura de paredes a partir das tramas.

    Para uma faixa de espessura constante t e comprimento L: A = L·t e P ≈ 2(L+t),
    logo L = (P/2 + sqrt((P/2)² - 4A)) / 2 e t = A/L.
    """
    h = df[(df.tipo == "HATCH") & df.layer.str.contains(layers_regex, case=False, regex=True) & (df.area > 0)]
    rows = []
    for _, r in h.iterrows():
        sp = r.perimetro / 2
        disc = sp * sp - 4 * r.area
        L = (sp + math.sqrt(max(disc, 0))) / 2
        t = r.area / L if L else 0
        rows.append(dict(handle=r.handle, folha=r.folha, layer=r.layer, padrao=r.bloco,
                         area_planta=round(r.area, 4), comprimento=round(L, 3), espessura=round(t, 3)))
    return pd.DataFrame(rows, columns=["handle", "folha", "layer", "padrao", "area_planta", "comprimento", "espessura"])
