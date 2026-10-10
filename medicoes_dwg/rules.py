"""Regras de medição: ligam um item do MQ a uma medição no desenho.

Cada regra é uma linha de tabela (editável na aplicação e exportável para Excel):

=============  ===============================================================
coluna         significado
=============  ===============================================================
regra          identificador (R001, R002, ...)
ativo          True/False
item_mq        id do item do MQ (``artigo`` ou ``artigo|local``)
grupo          itens com o mesmo grupo são comparados em conjunto (soma do MQ
               contra uma única medição), ex.: portas normais + corta-fogo
fonte          tipo de medição (ver ``FONTES``)
folhas         regex sobre id/nome/nível da folha (vazio = todas)
layers         regex sobre o nome do layer (vazio = todos)
filtro         regex sobre nome do compartimento / bloco / texto
excluir        regex de exclusão (compartimento / bloco / texto)
esp_min/max    espessura de parede em m (só fontes de paredes)
fator          número ou expressão com PD (pé-direito), ex.: "PD", "0.5", "PD-0.10"
deducao        valor a deduzir (ex.: vãos), na unidade final
confianca      alta / média / baixa (sugestões automáticas)
notas          justificação / pressupostos
=============  ===============================================================
"""
from __future__ import annotations

import re

import pandas as pd

from .extractor import Resultado, norm

FONTES = {
    "AREA_COMPART": ("Área de compartimentos (etiqueta)", "m²"),
    "AREA_COMPART_GEOM": ("Área de compartimentos (geometria)", "m²"),
    "PERIM_COMPART": ("Perímetro de compartimentos", "ml"),
    "PAREDES_COMPART": ("Paredes de compartimentos = perímetro × fator − dedução", "m²"),
    "COMPRIMENTO_LAYER": ("Comprimento de linhas/polilinhas no layer", "ml"),
    "EIXO_LAYER": ("Comprimento de eixo (fechadas: perímetro/2)", "ml"),
    "AREA_LAYER": ("Área de tramas/polilinhas fechadas no layer", "m²"),
    "CONTAGEM_BLOCOS": ("Contagem de blocos", "un"),
    "CONTAGEM_TEXTOS": ("Contagem de textos", "un"),
    "COMPRIMENTO_PAREDES": ("Comprimento de paredes (tramas)", "ml"),
    "AREA_PAREDES": ("Área de paredes = comprimento × fator − dedução", "m²"),
    "VALOR_MANUAL": ("Valor manual (no campo fator)", ""),
}

COLUNAS = ["regra", "ativo", "item_mq", "grupo", "fonte", "folhas", "layers", "filtro", "excluir",
           "esp_min", "esp_max", "fator", "deducao", "confianca", "notas"]

RE_FATOR = re.compile(r"^[\d\s.+\-*/()PD]*$")


def regras_vazias() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUNAS)


def avaliar_fator(fator, pe_direito: float) -> float:
    if fator is None or (isinstance(fator, float) and pd.isna(fator)) or str(fator).strip() == "":
        return 1.0
    s = str(fator).replace(",", ".").upper().strip()
    if not RE_FATOR.match(s):
        raise ValueError(f"fator inválido: {fator!r}")
    return float(eval(s.replace("PD", f"({pe_direito})"), {"__builtins__": {}}, {}))


def _rx(v) -> re.Pattern | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    return re.compile(str(v), re.I)


def _match_nome(rx: re.Pattern | None, nome: str) -> bool:
    return rx is None or bool(rx.search(nome) or rx.search(norm(nome)))


def _folhas_sel(res: Resultado, rx) -> set[str]:
    if rx is None:
        return {f.id for f in res.folhas} | {""}
    return {f.id for f in res.folhas if rx.search(f.id) or rx.search(f.nome) or rx.search(f.nivel or "")}


def _usa_pd(fator) -> bool:
    return "PD" in str(fator or "").upper()


def _deducoes_vaos(vaos: pd.DataFrame | None, mask) -> pd.DataFrame:
    if vaos is None or vaos.empty:
        return pd.DataFrame()
    v = vaos[mask(vaos)]
    v = v[v.area.notna() & (v.area > 0)]
    if v.empty:
        return pd.DataFrame()
    cod = v.get("codigo_mq", pd.Series("", index=v.index)).fillna("")
    return pd.DataFrame({
        "handle": v.handles, "folha": v.folha, "layer": "(vão)",
        "descricao": "dedução " + v.id + " " + v.tipo + " " + v.largura.map("{:.2f}".format) + "x"
                     + v.altura.map("{:.2f}".format) + " " + cod + " - " + v.compartimento,
        "valor": -v.area,
    })


def aplicar_regra(regra: dict, res: Resultado, pe_direito: float, vaos: pd.DataFrame | None = None,
                  deduzir_vaos: bool = True, pd_folhas: dict | None = None) -> tuple[float | None, pd.DataFrame, str]:
    """Devolve (valor, detalhe, erro). O detalhe lista as entidades que contribuem.

    ``pd_folhas``: pé-direito por folha (lido dos cortes); o fator "PD" usa o da folha
    de cada elemento e, na falta, ``pe_direito``. Com ``deduzir_vaos`` as áreas de
    paredes calculadas com PD descontam os vãos detetados (linhas negativas no detalhe).
    """
    fonte = regra.get("fonte")
    pd_folhas = pd_folhas or {}
    try:
        fator = avaliar_fator(regra.get("fator"), pe_direito)
        ded = float(regra.get("deducao") or 0)
        rx_f, rx_l = _rx(regra.get("filtro")), _rx(regra.get("layers"))
        rx_x = _rx(regra.get("excluir"))
        folhas = _folhas_sel(res, _rx(regra.get("folhas")))
    except (re.error, ValueError) as ex:
        return None, pd.DataFrame(), str(ex)

    def fator_folha(fid):
        return avaliar_fator(regra.get("fator"), pd_folhas.get(fid, pe_direito))

    det = pd.DataFrame()
    if fonte == "VALOR_MANUAL":
        return fator - ded, det, ""

    if fonte in ("AREA_COMPART", "AREA_COMPART_GEOM", "PERIM_COMPART", "PAREDES_COMPART"):
        c = res.compartimentos
        if c.empty:
            return None, det, "sem compartimentos no desenho"
        sel = c[c.folha.isin(folhas) & c.compartimento.apply(lambda n: _match_nome(rx_f, n))]
        if rx_x is not None:
            sel = sel[~sel.compartimento.apply(lambda n: _match_nome(rx_x, n))]
        if sel.empty:
            return 0.0, det, "nenhum compartimento corresponde ao filtro"
        if fonte == "AREA_COMPART":
            col = "area_etiqueta"
        elif fonte == "AREA_COMPART_GEOM":
            col = "area_geometria"
        else:
            col = "perimetro"
        falta = sel[sel[col].isna()]
        det = pd.DataFrame({
            "handle": sel.handle_etiqueta if col == "area_etiqueta" else sel.handle_poligono,
            "folha": sel.folha, "layer": sel.layer_poligono, "descricao": sel.compartimento,
            "valor": sel[col],
        })
        err = f"{len(falta)} compartimento(s) sem polígono: " + ", ".join(falta.compartimento) if len(falta) else ""
        if fonte == "PAREDES_COMPART":
            fs = sel.folha.map(fator_folha)
            det["valor"] = sel[col].fillna(0) * fs
            det["descricao"] = sel.compartimento + " (" + sel[col].round(2).astype(str) + " m × " + fs.round(2).astype(str) + ")"
            if deduzir_vaos and _usa_pd(regra.get("fator")):
                hs = set(sel.handle_poligono)
                dd = _deducoes_vaos(vaos, lambda v: v.handle_poligono.isin(hs))
                det = pd.concat([det, dd], ignore_index=True)
            return float(det.valor.sum()) - ded, det, err
        val = float(sel[col].fillna(0).sum())
        return val * fator - ded, det, err

    if fonte in ("COMPRIMENTO_PAREDES", "AREA_PAREDES"):
        p = res.paredes
        if p.empty:
            return None, det, "sem tramas de paredes detetadas"
        sel = p[p.folha.isin(folhas)]
        if rx_l is not None:
            sel = sel[sel.layer.str.contains(rx_l)]
        lo = regra.get("esp_min")
        hi = regra.get("esp_max")
        if lo not in (None, "") and not pd.isna(lo):
            sel = sel[sel.espessura >= float(lo)]
        if hi not in (None, "") and not pd.isna(hi):
            sel = sel[sel.espessura <= float(hi)]
        det = pd.DataFrame({"handle": sel.handle, "folha": sel.folha, "layer": sel.layer,
                            "descricao": "parede e=" + sel.espessura.round(3).astype(str), "valor": sel.comprimento})
        if fonte == "AREA_PAREDES":
            fs = sel.folha.map(fator_folha)
            det["valor"] = sel.comprimento * fs
            if deduzir_vaos and _usa_pd(regra.get("fator")):
                hs = set(sel.handle)
                # cada vão é descontado uma vez (pode aparecer nos dois compartimentos que separa)
                vv = vaos.drop_duplicates(subset=["handles"]) if vaos is not None and not vaos.empty else vaos
                dd = _deducoes_vaos(vv, lambda v: v.handle_parede.isin(hs))
                det = pd.concat([det, dd], ignore_index=True)
            return float(det.valor.sum()) - ded, det, ""
        return float(sel.comprimento.sum()) * fator - ded, det, ""

    e = res.entidades
    sel = e[e.folha.isin(folhas)]
    if rx_l is not None:
        sel = sel[sel.layer.str.contains(rx_l)]
    if fonte == "CONTAGEM_BLOCOS":
        sel = sel[sel.tipo == "INSERT"]
        if rx_f is not None:
            sel = sel[sel.bloco.str.contains(rx_f)]
        if rx_x is not None:
            sel = sel[~sel.bloco.str.contains(rx_x)]
        sel = sel.assign(valor=1.0, descricao=sel.bloco)
    elif fonte == "CONTAGEM_TEXTOS":
        sel = sel[sel.tipo.isin(["TEXT", "MTEXT"])]
        if rx_f is not None:
            sel = sel[sel.texto.str.contains(rx_f)]
        if rx_x is not None:
            sel = sel[~sel.texto.str.contains(rx_x)]
        sel = sel.assign(valor=1.0, descricao=sel.texto)
    elif fonte == "COMPRIMENTO_LAYER":
        sel = sel[sel.comprimento > 0]
        sel = sel.assign(valor=sel.comprimento, descricao=sel.tipo)
    elif fonte == "EIXO_LAYER":
        sel = sel[sel.comprimento > 0]
        sel = sel.assign(valor=sel.comprimento.where(~sel.fechado, sel.comprimento / 2), descricao=sel.tipo)
    elif fonte == "AREA_LAYER":
        sel = sel[sel.area > 0]
        sel = sel.assign(valor=sel.area, descricao=sel.tipo + " " + sel.bloco.fillna(""))
    else:
        return None, det, f"fonte desconhecida: {fonte}"
    det = sel[["handle", "folha", "layer", "descricao", "valor"]].copy()
    det["valor"] = det["valor"] * fator
    return float(sel.valor.sum()) * fator - ded, det, ""


# ---------------------------------------------------------------- sugestões

# palavra-chave na descrição/local (normalizada) -> (fonte, layers, filtro, fator, notas)
# palavra-chave (texto normalizado) -> unidade, fonte, layers, filtro, fator, excluir-se, notas
DICIONARIO = [
    (r"rodap", "ml", "COMPRIMENTO_LAYER", r"rodap|skirt", "", "1", "", "Linhas no layer de rodapés"),
    (r"guarda", "ml", "COMPRIMENTO_LAYER", r"guard|railing", "", "0.5", "",
     "Guarda desenhada a 2 linhas (espessura do vidro): comprimento/2 - confirmar no desenho"),
    (r"sanita", "un", "CONTAGEM_BLOCOS", "", r"sanit|sant|toilet|^wc", "1", "", "Blocos de sanitas"),
    (r"autoclismo|geberit", "un", "CONTAGEM_BLOCOS", "", r"sanit|sant|toilet|^wc", "1", "", "1 por sanita"),
    (r"lavatorio", "un", "CONTAGEM_BLOCOS", "", r"lavat|basin|lav", "1", "", "Blocos de lavatórios"),
    (r"banheira", "un", "CONTAGEM_BLOCOS", "", r"banheir|bath", "1", "", "Blocos de banheiras"),
    (r"baseduche", "un", "CONTAGEM_BLOCOS", "", r"duche|shower", "1", "", "Blocos de bases de duche"),
    (r"portasdebatente|portadebatente|portainterior|portasinteriores", "un", "CONTAGEM_BLOCOS", "",
     r"porta|door", "1", r"armario|movel|roupeiro|cozinha", "Blocos de portas interiores"),
    (r"degrau", "un", "CONTAGEM_TEXTOS", r"legend|escada|stair", r"^\d{1,2}$", "1", r"soleira",
     "Numeração dos degraus (só numa planta, para não duplicar)"),
    (r"muro", "ml", "COMPRIMENTO_LAYER", r"muro|wall", "", "0.5", "", "Muros a 2 linhas: comprimento/2 (todos os muros!)"),
]

PAREDES_ESP = [
    (r"blocotermico25|bloco.*25|tijolo.*(25|30)", 0.22, 0.32, "Paredes exteriores e≈0,25-0,30"),
    (r"tijolo.*(11|15)|bloco.*15", 0.12, 0.20, "Paredes e≈0,15"),
    (r"tijolo.*7|tijolosimples", 0.06, 0.11, "Paredes e≈0,07-0,10"),
]

# medições que, repetidas em vários itens do mesmo artigo, devem ser comparadas em grupo
SOMAR_EM_GRUPO = {r"portasdebatente|portadebatente|portainterior|portasinteriores", r"muro"}

RE_PAREDES_CAP = re.compile(r"parede|revestimento.*parede|pintura.*parede", re.I)
RE_TECTO = re.compile(r"tect|teto", re.I)


def _nivel_de_local(local: str, res: Resultado) -> list[str]:
    """Folhas cujo nome/nível corresponde ao texto do local (ex.: 'Piso 1')."""
    n = norm(local)
    if not n:
        return []
    out = []
    for f in res.folhas:
        nomes = {norm(f.nivel), norm(f.nome)}
        if any(x and (n == x or (len(n) >= 4 and n in x)) for x in nomes):
            out.append(f.id)
    return out


PAPEL_DICIONARIO = {  # palavra-chave -> (tipo, papel no perfil do projetista)
    r"rodap": ("layer", "rodape"), r"guarda": ("layer", "guardas"), r"muro": ("layer", "muros"),
    r"sanita": ("bloco", "sanita"), r"autoclismo|geberit": ("bloco", "sanita"), r"lavatorio": ("bloco", "lavatorio"),
    r"banheira": ("bloco", "banheira"), r"baseduche": ("bloco", "duche"),
    r"portasdebatente|portadebatente|portainterior|portasinteriores": ("bloco", "porta"),
}


def _exato(nomes: list[str]) -> str:
    return "^(?:" + "|".join(re.escape(n) for n in nomes) + ")$"


def sugerir_regras(mq: pd.DataFrame, res: Resultado, pe_direito: float = 2.50,
                   perfil: dict | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Sugere regras. Com ``perfil`` (projetista) usa os layers/blocos que esse gabinete
    usa para cada papel (aprendidos de projetos anteriores ou ensinados na aplicação)."""
    regras, avisos = [], []
    comps = res.compartimentos
    nomes = sorted({c for c in comps.compartimento if c and c != "(sem nome)"}, key=lambda s: -len(norm(s))) if not comps.empty else []
    plantas = [f.id for f in res.folhas if re.search(r"piso|r/c|cave|planta", f"{f.nome} {f.nivel}", re.I)
               and not re.search(r"implanta|cobertura", f.nome, re.I)]
    rx_plantas = "^(?:" + "|".join(plantas) + ")$" if plantas else ""

    def add(item, fonte, conf, notas, folhas="", layers="", filtro="", excluir="", fator="1", esp=(None, None), grupo=""):
        regras.append(dict(regra="", ativo=True, item_mq=item, grupo=grupo, fonte=fonte, folhas=folhas, layers=layers,
                           filtro=filtro, excluir=excluir, esp_min=esp[0], esp_max=esp[1], fator=fator,
                           deducao=0.0, confianca=conf, notas=notas))

    for _, it in mq.iterrows():
        if it.unidade not in ("m²", "ml", "un"):
            continue
        local, desc = str(it.local), str(it.descricao)
        nl, nd = norm(local), norm(desc)
        is_paredes = bool(RE_PAREDES_CAP.search(desc) or RE_PAREDES_CAP.search(str(it.capitulo))) \
            and not RE_TECTO.search(local + desc[:60])
        fol_local = _nivel_de_local(local, res) if nl else []
        feito = False

        # 1) compartimento citado no local (confiança alta) ou na descrição (baixa)
        alvo = nl if nl else nd
        comp = next((c for c in nomes if len(norm(c)) >= 3 and norm(c) in alvo), None)
        if comp and it.unidade == "m²":
            filtro = "^" + re.escape(norm(comp)) + "$"
            if is_paredes:
                add(it.id, "PAREDES_COMPART", "média" if nl and "parede" not in str(it.capitulo).lower() else "baixa",
                    f"Perímetro de '{comp}' × PD do piso (lido dos cortes) − vãos detetados", filtro=filtro, fator="PD")
            else:
                add(it.id, "AREA_COMPART", "alta" if nl else "baixa",
                    f"Área do compartimento '{comp}'" + ("" if nl else " (citado na descrição - confirmar)"), filtro=filtro)
            feito = True

        # 2) palavra-chave do dicionário (no local, se existir; senão na descrição)
        if not feito:
            for kw, un, fonte, layers, filtro, fator, excl, notas in DICIONARIO:
                if un != it.unidade or not re.search(kw, alvo) or (excl and re.search(excl, alvo)):
                    continue
                if kw == "muro":
                    folhas = "implanta"
                elif kw == "degrau" and plantas:
                    folhas = f"^{plantas[0]}$"
                else:
                    folhas = rx_plantas
                grupo = f"G{it.artigo}" if kw in SOMAR_EM_GRUPO else ""
                if perfil and kw in PAPEL_DICIONARIO:
                    tipo_p, papel = PAPEL_DICIONARIO[kw]
                    conhecidos = perfil.get("layers_conhecidos" if tipo_p == "layer" else "blocos_conhecidos", {}).get(papel)
                    if conhecidos:
                        if tipo_p == "layer":
                            layers = _exato(conhecidos)
                        else:
                            filtro = _exato(conhecidos)
                        notas += f" [perfil {perfil['id']}]"
                add(it.id, fonte, "média" if kw != "muro" else "baixa", notas, folhas=folhas, layers=layers,
                    filtro=filtro, fator=fator, grupo=grupo)
                feito = True
                break

        # 3) paredes por espessura (só quando o local corresponde a uma planta, ou não há local)
        if not feito and it.unidade == "m²" and is_paredes and (fol_local or not nl):
            for kw, lo, hi, notas in PAREDES_ESP:
                if re.search(kw, nd):
                    add(it.id, "AREA_PAREDES", "baixa", f"{notas} × PD do piso (estimativa a partir das tramas) − vãos detetados",
                        folhas="^(?:" + "|".join(fol_local) + ")$" if fol_local else rx_plantas, fator="PD", esp=(lo, hi))
                    feito = True
                    break

        # 4) local = piso -> soma de compartimentos dessa planta (pavimentos/tectos)
        if not feito and it.unidade == "m²" and fol_local and not is_paredes:
            add(it.id, "AREA_COMPART", "baixa", "Soma de todos os compartimentos da planta - rever exclusões",
                folhas="^(?:" + "|".join(fol_local) + ")$")

    df = pd.DataFrame(regras, columns=COLUNAS)
    df["regra"] = [f"R{i + 1:03d}" for i in range(len(df))]

    # incoerência: dois locais diferentes do mesmo artigo apontam para a mesma planta
    if not mq.empty:
        for art, g in mq[mq.local != ""].groupby("artigo"):
            mapa = {}
            for loc in g.local:
                for fid in _nivel_de_local(loc, res):
                    mapa.setdefault(fid, set()).add(loc)
            for fid, locs in mapa.items():
                if len(locs) > 1:
                    nome = next(f.nome for f in res.folhas if f.id == fid)
                    avisos.append(f"Art. {art}: os locais {sorted(locs)} correspondem à mesma planta '{nome}' - "
                                  "nomenclatura de pisos do MQ diferente da do desenho.")
    return df, avisos
