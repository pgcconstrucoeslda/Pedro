"""Níveis dos pisos e pé-direito a partir das cotas do desenho.

Método (cada valor fica com a evidência que o originou):

1. **Cotas de nível** - textos/atributos numéricos (ex.: ``85.81``, ``cs 82.63``,
   ``C.S.82.63``) em layers/blocos de cotas altimétricas.
2. **Nível de cada planta** - nas folhas de planta, a cota mais frequente entre as
   que estão junto às etiquetas dos compartimentos (as cotas de soleira "cs" e as
   de zonas exteriores ficam com menor prioridade).
3. **Altura entre pisos** - diferença para o piso seguinte (último piso: até à
   cota mais alta dos cortes, ex.: cobertura).
4. **Pé-direito livre** - nos cortes/alçados, cotas dimensionais verticais que
   arrancam do nível do pavimento (a posição vertical é calibrada pelas marcas de
   nível do próprio corte). Escolhe-se a maior que cabe na altura entre pisos
   menos a laje mínima. Se não houver, estima-se: altura entre pisos − laje.
"""
from __future__ import annotations

import re

import pandas as pd

RE_COTA = re.compile(r"^\s*(c\.?\s*s\.?\s*)?([+-]?\d{1,4}[.,]\d{2,3})\s*$", re.I)
RE_CTX = re.compile(r"cota|n[ií]vel|level|altim|elev", re.I)
RE_EXCL = re.compile(r"perfil|topo|terreno|node|existente|curva", re.I)
RE_PLANTA = re.compile(r"piso|r/c|cave|s[oó]t[aã]o|andar", re.I)
RE_CORTE = re.compile(r"corte|al[çc]ado", re.I)

LAJE_MIN = 0.30      # laje + pavimento + teto mínimos: o pé-direito tem de caber em H − 0,30
LAJE_ESTIMADA = 0.35  # usada quando não há cota de pé-direito nos cortes


def marcas_nivel(res) -> pd.DataFrame:
    e = res.entidades
    t = e[e.tipo.isin(["TEXT", "MTEXT", "ATTRIB"])].copy()
    if t.empty:
        return pd.DataFrame(columns=["handle", "folha", "layer", "x", "y", "cota", "soleira"])
    ctx = t.layer.str.contains(RE_CTX) | t.bloco.str.contains(RE_CTX) | t.tag.fillna("").str.contains(RE_CTX)
    excl = t.layer.str.contains(RE_EXCL) | t.bloco.str.contains(RE_EXCL)
    t = t[ctx & ~excl]
    m = t.texto.str.extract(RE_COTA)
    t = t[m[1].notna()].copy()
    m = m[m[1].notna()]
    t["cota"] = m[1].str.replace(",", ".").astype(float)
    t["soleira"] = m[0].notna()
    return t[["handle", "folha", "layer", "x", "y", "cota", "soleira"]]


def calcular_niveis(res, laje_estimada: float = LAJE_ESTIMADA):
    marcas = marcas_nivel(res)
    f = res.fator
    folhas = {fo.id: fo for fo in res.folhas}
    comps = res.compartimentos
    niveis = []
    for fid, fo in folhas.items():
        if not RE_PLANTA.search(f"{fo.nivel} {fo.nome}") or RE_CORTE.search(fo.nome):
            continue
        mk = marcas[(marcas.folha == fid)]
        if mk.empty:
            continue
        c = comps[comps.folha == fid] if not comps.empty else comps
        cand = mk[~mk.soleira]
        metodo = "cota mais frequente na planta"
        if not c.empty and not cand.empty:
            d = cand.apply(lambda r: (((c.x - r.x) ** 2 + (c.y - r.y) ** 2) ** 0.5).min() * f, axis=1)
            junto = cand[d <= 6.0]
            if not junto.empty:
                cand, metodo = junto, "cota junto aos compartimentos"
        if cand.empty:
            cand, metodo = mk, "cota de soleira"
        cota = cand.cota.round(2).mode().max()
        niveis.append(dict(folha=fid, nivel=fo.nivel or fo.nome, cota=float(cota), metodo=metodo,
                           evidencia=", ".join(cand[cand.cota.round(2) == cota].handle.astype(str).head(5))))
    nv = pd.DataFrame(niveis, columns=["folha", "nivel", "cota", "metodo", "evidencia"])
    if nv.empty:
        return nv, pd.DataFrame(columns=["folha", "nivel", "cota", "altura_pisos", "pe_direito", "metodo", "evidencia"])
    nv = nv.sort_values("cota").reset_index(drop=True)

    # cota de topo (cobertura) a partir das marcas dos cortes
    cortes = [fid for fid, fo in folhas.items() if RE_CORTE.search(f"{fo.nome} {fo.nivel}")]
    mc = marcas[marcas.folha.isin(cortes)]
    cotas_pisos = list(nv.cota)
    alturas = []
    for i, c in enumerate(cotas_pisos):
        if i + 1 < len(cotas_pisos):
            alturas.append(round(cotas_pisos[i + 1] - c, 3))
        else:
            acima = mc[(mc.cota > c + 2.2) & (mc.cota < c + 6.0)].cota
            alturas.append(round(acima.max() - c, 3) if not acima.empty else None)
    nv["altura_pisos"] = alturas

    # pé-direito a partir das cotas verticais dos cortes
    dims = res.cotas_dim
    dims = dims[dims.vertical & dims.folha.isin(cortes)] if not dims.empty else dims
    pds = []
    for _, r in nv.iterrows():
        H = r.altura_pisos
        cand = []
        if H and not dims.empty and not mc.empty:
            for _, d in dims.iterrows():
                if not 2.0 <= d.valor <= H - LAJE_MIN + 0.005:
                    continue
                viz = mc[mc.folha == d.folha].copy()
                if viz.empty:
                    continue
                viz["dx"] = (viz.x - d.x).abs()
                viz = viz.nsmallest(6, "dx")
                off = (viz.y * f - viz.cota).median()  # calibração vertical do corte
                base = d.y_baixo * f - off
                if abs(base - r.cota) <= 0.15:  # o símbolo de cota fica ~0,1 m acima da linha
                    cand.append((round(d.valor, 2), d.handle))
        if cand:
            pd_val = max(v for v, _ in cand)
            pds.append((pd_val, "cota vertical no corte a partir do pavimento",
                        ", ".join(str(h) for v, h in cand if v == pd_val)))
        elif H:
            pds.append((round(H - laje_estimada, 2), f"estimado: altura entre pisos − {laje_estimada:.2f} m (laje)", ""))
        else:
            pds.append((None, "sem dados", ""))
    nv["pe_direito"] = [p[0] for p in pds]
    nv["metodo_pd"] = [p[1] for p in pds]
    nv["evidencia_pd"] = [p[2] for p in pds]
    return nv[["folha", "nivel", "cota", "metodo", "evidencia"]], nv[
        ["folha", "nivel", "cota", "altura_pisos", "pe_direito", "metodo_pd", "evidencia_pd"]]


def pd_por_folha(res, padrao: float) -> dict[str, float]:
    """{folha: pé-direito} com fallback para o valor por defeito."""
    out: dict[str, float] = {}
    pdf = getattr(res, "pe_direito", None)
    if pdf is not None and not pdf.empty:
        for _, r in pdf.iterrows():
            if pd.notna(r.pe_direito):
                out[r.folha] = float(r.pe_direito)
    return out
