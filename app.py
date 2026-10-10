"""Aplicação web: Medições DWG x Mapa de Quantidades.

Executar:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from medicoes_dwg.compare import comparar
from medicoes_dwg.converter import ConversionError, dwg_to_dxf, find_converter
from medicoes_dwg.extractor import extrair
from medicoes_dwg.mq_parser import ler_mq
from medicoes_dwg.report import FILL, gerar_relatorio
from medicoes_dwg.rules import COLUNAS, FONTES, regras_vazias, sugerir_regras

st.set_page_config(page_title="Medições DWG x MQ", page_icon="📐", layout="wide")


# ---------------------------------------------------------------- cache

@st.cache_resource(show_spinner=False, max_entries=4)
def _extrair_cached(digest: str, nome: str, data: bytes, unidade: str | None, ignorar: str):
    tmp = Path(tempfile.mkdtemp(prefix="med_"))
    src = tmp / nome
    src.write_bytes(data)
    dxf = dwg_to_dxf(src, tmp) if src.suffix.lower() == ".dwg" else src
    return extrair(str(dxf), unidade=unidade, layers_ignorar=ignorar)


@st.cache_data(show_spinner=False, max_entries=8)
def _ler_mq_cached(digest: str, nome: str, data: bytes):
    tmp = Path(tempfile.mkdtemp(prefix="mq_")) / nome
    tmp.write_bytes(data)
    return ler_mq(tmp)


def _digest(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def _cor_estado(v):
    c = FILL.get(v)
    return f"background-color: #{c}" if c else ""


# ---------------------------------------------------------------- barra lateral

st.sidebar.title("📐 Medições DWG x MQ")
conv = find_converter()
st.sidebar.caption(f"Conversor DWG: **{conv[0] if conv else 'não instalado (use DXF)'}**")

f_dwg = st.sidebar.file_uploader("Desenho (DWG ou DXF)", type=["dwg", "dxf"])
f_mq = st.sidebar.file_uploader("Mapa de quantidades (xls, xlsx, csv)", type=["xls", "xlsx", "csv"])

with st.sidebar.expander("Parâmetros", expanded=True):
    unidade_sel = st.selectbox("Unidade do desenho", ["auto", "m", "cm", "mm"], index=0,
                               help="O cabeçalho do DWG ($INSUNITS) é muitas vezes incoerente; 'auto' confirma pela dimensão do desenho.")
    pe_direito = st.number_input("Pé-direito (PD) [m]", 2.0, 6.0, 2.50, 0.05,
                                 help="Usado nas regras com fator 'PD' (áreas de paredes).")
    tol_ok = st.number_input("Tolerância OK [%]", 0.0, 50.0, 3.0, 0.5)
    tol_al = st.number_input("Tolerância ALERTA [%]", 0.0, 100.0, 10.0, 0.5)
    ignorar = st.text_input("Layers a ignorar (regex)", "",
                            help="Ex.: veget|arvore|topo  - acelera ficheiros com muita vegetação/topografia.")

ss = st.session_state
for k, v in {"res": None, "mq": None, "mq_av": [], "regras": None, "regras_base": None, "sug_av": []}.items():
    ss.setdefault(k, v)

if f_dwg is not None:
    data = f_dwg.getvalue()
    try:
        with st.spinner("A ler o desenho (conversão + extração)…"):
            ss.res = _extrair_cached(_digest(data), f_dwg.name, data,
                                     None if unidade_sel == "auto" else unidade_sel, ignorar)
    except ConversionError as ex:
        st.error(str(ex))
        ss.res = None
if f_mq is not None:
    data = f_mq.getvalue()
    ss.mq, ss.mq_av = _ler_mq_cached(_digest(data), f_mq.name, data)

res, mq = ss.res, ss.mq

if res is None and mq is None:
    st.title("Medições automáticas DWG x Mapa de Quantidades")
    st.markdown(
        """
**Fluxo de trabalho (cada etapa é validável):**

1. **Desenho** – carregue o DWG/DXF; confirme folhas, unidade e layers.
2. **Compartimentos** – etiquetas de área vs polígonos (verificação do próprio desenho).
3. **Mapa de Quantidades** – leitura e verificações formais do MQ.
4. **Regras** – ligação artigo do MQ ↔ medição no desenho (sugestão automática + edição).
5. **Comparação** – desvios com semáforo e relatório Excel rastreável (handles das entidades).
"""
    )
    st.stop()

tabs = st.tabs(["1 · Desenho", "2 · Compartimentos", "3 · Mapa de Quantidades", "4 · Regras", "5 · Comparação"])

# ---------------------------------------------------------------- 1 desenho
with tabs[0]:
    if res is None:
        st.info("Carregue um desenho.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entidades", f"{len(res.entidades):,}".replace(",", " "))
        c2.metric("Folhas", len(res.folhas))
        c3.metric("Compartimentos", len(res.compartimentos))
        c4.metric("Unidade", res.unidade)
        for a in res.avisos[:20]:
            st.warning(a)
        st.subheader("Folhas detetadas")
        st.caption("Pode corrigir o **nome** e o **nível** (ex.: 'Piso 1', 'R/C'). O nível é usado nas regras e na "
                   "ligação aos locais do MQ.")
        fdf = res.folhas_df()
        ed = st.data_editor(fdf, hide_index=True, disabled=["id", "xmin", "ymin", "xmax", "ymax", "origem"],
                            key="ed_folhas", use_container_width=True)
        for f, (_, row) in zip(res.folhas, ed.iterrows()):
            f.nome, f.nivel = row["nome"], row["nivel"]
        st.subheader("Layers")
        st.dataframe(res.layers_df().round(2), hide_index=True, use_container_width=True, height=350)
        st.subheader("Blocos por folha")
        blk = (res.entidades[res.entidades.tipo == "INSERT"].groupby(["folha", "bloco"]).size()
               .reset_index(name="n").sort_values(["folha", "n"], ascending=[True, False]))
        st.dataframe(blk, hide_index=True, use_container_width=True, height=300)

# ---------------------------------------------------------------- 2 compartimentos
with tabs[1]:
    if res is None or res.compartimentos.empty:
        st.info("Sem etiquetas de compartimentos (texto 'NN.NN m²') no desenho.")
    else:
        c = res.compartimentos.copy()
        nomes = {f.id: f"{f.id} · {f.nome}" for f in res.folhas}
        c.insert(1, "folha_nome", c.folha.map(nomes))
        st.caption("Área da etiqueta vs área do polígono que a contém. Desvios > 5 % indicam etiqueta "
                   "desatualizada ou polígono incorreto – **verificar no desenho** (handle).")
        st.dataframe(
            c.style.map(lambda v: "background-color:#FFC7CE" if pd.notna(v) and abs(v) > 5 else "", subset=["desvio_%"]),
            hide_index=True, use_container_width=True)
        tot = c.groupby("folha_nome").area_etiqueta.sum().reset_index()
        st.dataframe(tot.rename(columns={"area_etiqueta": "Σ área etiquetas (m²)"}), hide_index=True)

# ---------------------------------------------------------------- 3 MQ
with tabs[2]:
    if mq is None:
        st.info("Carregue o mapa de quantidades.")
    else:
        st.metric("Itens com quantidade", len(mq))
        for a in ss.mq_av:
            st.warning(a)
        st.dataframe(mq, hide_index=True, use_container_width=True, height=500)

# ---------------------------------------------------------------- 4 regras
with tabs[3]:
    if res is None or mq is None:
        st.info("Carregue o desenho e o MQ.")
    else:
        b1, b2, b3 = st.columns([1, 1, 2])
        # o editor trabalha sobre uma base fixa (regras_base); as edições ficam no estado do widget
        if b1.button("🔄 Sugerir regras automaticamente", use_container_width=True) or ss.get("regras_base") is None:
            ss.regras_base, ss.sug_av = sugerir_regras(mq, res, pe_direito)
            ss.pop("ed_regras", None)
        up = b3.file_uploader("Importar regras (xlsx)", type=["xlsx"], label_visibility="collapsed")
        if up is not None and b2.button("Usar regras importadas", use_container_width=True):
            ss.regras_base = pd.read_excel(up).reindex(columns=COLUNAS)
            ss.pop("ed_regras", None)
        for a in ss.sug_av:
            st.warning(a)
        with st.expander("Fontes de medição disponíveis"):
            st.table(pd.DataFrame([(k, v[0], v[1]) for k, v in FONTES.items()], columns=["fonte", "descrição", "unidade"]))
            st.markdown("- **folhas / layers / filtro / excluir** são expressões regulares (ex.: `^F02$`, `rodap|skirt`).\n"
                        "- **fator** aceita números ou `PD` (pé-direito), ex.: `PD`, `0.5`, `PD-0.10`.\n"
                        "- **grupo**: itens com o mesmo grupo são comparados pela soma das quantidades do MQ.")
        regras = ss.regras_base if ss.regras_base is not None else regras_vazias()
        ss.regras = st.data_editor(
            regras, num_rows="dynamic", hide_index=True, use_container_width=True, height=520, key="ed_regras",
            column_config={
                "ativo": st.column_config.CheckboxColumn(default=True),
                "item_mq": st.column_config.SelectboxColumn(options=list(mq.id), width="large"),
                "fonte": st.column_config.SelectboxColumn(options=list(FONTES)),
                "confianca": st.column_config.SelectboxColumn(options=["alta", "média", "baixa"]),
                "esp_min": st.column_config.NumberColumn(format="%.2f"),
                "esp_max": st.column_config.NumberColumn(format="%.2f"),
                "deducao": st.column_config.NumberColumn(format="%.2f"),
            })
        buf = io.BytesIO()
        ss.regras.to_excel(buf, index=False)
        st.download_button("⬇️ Exportar regras (xlsx)", buf.getvalue(), "regras_medicao.xlsx")

# ---------------------------------------------------------------- 5 comparação
with tabs[4]:
    if res is None or mq is None or ss.regras is None:
        st.info("Carregue o desenho e o MQ e reveja as regras.")
    else:
        regras = ss.regras.copy()
        regras["regra"] = [r if isinstance(r, str) and r else f"R{i + 1:03d}" for i, r in enumerate(regras.regra)]
        comp, det, rr = comparar(mq, regras, res, pe_direito, tol_ok / 100, tol_al / 100)
        cnt = comp.estado.value_counts()
        cols = st.columns(6)
        for col, s in zip(cols, ["OK", "ALERTA", "CRÍTICO", "NÃO MEDIDO", "SEM REGRA", "N/A"]):
            col.metric(s, int(cnt.get(s, 0)))
        so_regras = st.toggle("Mostrar só itens com regra", value=True)
        view = comp[comp.regras != ""] if so_regras else comp
        show = ["id", "unidade", "qtd_mq", "grupo", "qtd_mq_comparada", "qtd_dwg", "desvio", "desvio_pct", "estado",
                "regras", "observacoes", "ref_mq"]
        st.dataframe(view[show].style.map(_cor_estado, subset=["estado"]).format(
            {"qtd_mq": "{:.2f}", "qtd_mq_comparada": "{:.2f}", "qtd_dwg": "{:.2f}", "desvio": "{:+.2f}",
             "desvio_pct": "{:+.1f}"}, na_rep=""), hide_index=True, use_container_width=True, height=520)

        st.subheader("Rastreabilidade")
        sel = st.selectbox("Ver entidades medidas para o item", [""] + list(view[view.regras != ""].id))
        if sel:
            d = det[det.item_mq == sel]
            st.caption("Use o **handle** no AutoCAD (comando `_SELECT` + LISP `(handent \"<handle>\")`) para localizar a entidade.")
            st.dataframe(d, hide_index=True, use_container_width=True)

        params = {"Desenho": f_dwg.name if f_dwg else "", "Mapa de quantidades": f_mq.name if f_mq else "",
                  "Unidade do desenho": res.unidade, "Pé-direito (PD) m": pe_direito,
                  "Tolerância OK (%)": tol_ok, "Tolerância ALERTA (%)": tol_al}
        xls = gerar_relatorio(comp, det, regras, rr, res, ss.mq_av, ss.sug_av, params)
        st.download_button("⬇️ Descarregar relatório Excel", xls, "relatorio_medicoes.xlsx", type="primary")
