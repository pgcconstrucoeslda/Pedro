"""Leitura genérica de Mapas de Quantidades (xls/xlsx/csv).

Cada folha do Excel é percorrida à procura da linha de cabeçalho (Art.º /
Descrição / Qtd. / Un.). As linhas com quantidade são convertidas em itens:

* ``artigo``   - número do artigo (herdado do último artigo quando a linha é uma sub-linha);
* ``local``    - texto da sub-linha (ex.: "Piso 1", "I.S. Serviço"); vazio se a
                 quantidade está na própria linha do artigo;
* ``descricao``- descrição do artigo;
* ``quantidade``, ``unidade``;
* ``ref``      - folha!linha do Excel (rastreabilidade).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RE_ART = re.compile(r"^\s*\d+(\.\d+)*\.?\s*$")
UNIDADES = {"m2": "m²", "m²": "m²", "m3": "m³", "m³": "m³", "ml": "ml", "m": "ml", "un": "un", "un.": "un",
            "uni": "un", "und": "un", "vg": "vg", "vg.": "vg", "kg": "kg", "cj": "cj", "conj": "cj", "pç": "un", "l": "l"}


def _norm_unit(u) -> str:
    u = str(u or "").strip().lower().replace(" ", "")
    return UNIDADES.get(u, u)


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_header(df: pd.DataFrame):
    for i in range(min(len(df), 30)):
        row = [str(x).strip().lower() for x in df.iloc[i].tolist()]
        c_art = next((j for j, x in enumerate(row) if x.startswith("art") or x in ("item", "ref", "ref.", "nº", "n.º")), None)
        c_desc = next((j for j, x in enumerate(row) if x.startswith("descri") or x.startswith("design")), None)
        c_qtd = next((j for j, x in enumerate(row) if x.startswith("qt") or x.startswith("quant")), None)
        if c_desc is not None and c_qtd is not None:
            c_un = next((j for j, x in enumerate(row) if x in ("un", "un.", "unid", "unid.", "unidade", "und")), None)
            return i, c_art, c_desc, c_qtd, c_un
    return None


def ler_mq(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    path = Path(path)
    avisos: list[str] = []
    if path.suffix.lower() == ".csv":
        sheets = {"CSV": pd.read_csv(path, header=None, dtype=object)}
    else:
        engine = "xlrd" if path.suffix.lower() == ".xls" else None
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, engine=engine)
    itens = []
    for nome, df in sheets.items():
        df = df.dropna(how="all").reset_index(drop=True) if False else df
        h = _find_header(df)
        if h is None:
            continue
        i0, c_art, c_desc, c_qtd, c_un = h
        art_atual, desc_atual = "", ""
        for i in range(i0 + 1, len(df)):
            row = df.iloc[i].tolist()
            art = str(row[c_art]).strip() if c_art is not None and pd.notna(row[c_art]) else ""
            desc = " ".join(str(row[c_desc]).split()) if pd.notna(row[c_desc]) else ""
            qtd = _num(row[c_qtd]) if c_qtd < len(row) else None
            # unidade: coluna própria ou primeira célula de texto à direita da quantidade
            un = ""
            if c_un is not None and pd.notna(row[c_un]):
                un = row[c_un]
            else:
                for j in range(c_qtd + 1, min(c_qtd + 3, len(row))):
                    if pd.notna(row[j]) and str(row[j]).strip() and _num(row[j]) is None:
                        un = row[j]
                        break
            if art and RE_ART.match(art):
                art_atual, desc_atual = art.rstrip("."), desc
            if qtd is None:
                continue
            local = "" if art and RE_ART.match(art) else desc
            itens.append(dict(
                capitulo=nome, artigo=art_atual, local=local, descricao=desc_atual,
                quantidade=qtd, unidade=_norm_unit(un), ref=f"{nome}!{i + 1}",
            ))
    mq = pd.DataFrame(itens, columns=["capitulo", "artigo", "local", "descricao", "quantidade", "unidade", "ref"])
    mq.insert(0, "id", [f"{a}|{l}" if l else a for a, l in zip(mq.artigo, mq.local)])
    avisos += verificar_mq(mq)
    return mq, avisos


def verificar_mq(mq: pd.DataFrame) -> list[str]:
    """Verificações formais do MQ (independentes do desenho)."""
    out = []
    dup = mq[mq.id.duplicated(keep=False)]
    for i in dup.id.unique():
        refs = ", ".join(dup[dup.id == i].ref)
        out.append(f"Item duplicado '{i}' ({refs}).")
    for _, r in mq[mq.unidade == ""].iterrows():
        out.append(f"Item '{r.id}' sem unidade ({r.ref}).")
    # numeração do artigo incoerente com a numeração do capítulo (ex.: folha '2_Paredes' com artigos 3.x)
    desfas = []
    for cap, g in mq.groupby("capitulo"):
        m = re.match(r"^\s*(\d+)", str(cap))
        pref = {a.split(".")[0] for a in g.artigo if a}
        if m and pref and m.group(1) not in pref:
            desfas.append(f"'{cap}' -> {'/'.join(sorted(pref))}.x")
    if desfas:
        out.append(f"Numeração dos artigos não coincide com o nº do capítulo em {len(desfas)} capítulos: " + "; ".join(desfas))
    return out
