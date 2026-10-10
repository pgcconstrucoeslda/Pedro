"""Aplicação web: Medições DWG x MQ e compatibilização de projeto.

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
from medicoes_dwg.converter import find_converter
from medicoes_dwg.mq_parser import ler_mq
from medicoes_dwg.projetistas import PAPEIS_BLOCO, Registo, metadados_ficheiro
from medicoes_dwg.projeto import carregar, verificar_compatibilizacao, verificar_integridade
from medicoes_dwg.relatorio_docx import gerar_docx
from medicoes_dwg.report import FILL, gerar_relatorio
from medicoes_dwg.rules import COLUNAS, FONTES, regras_vazias, sugerir_regras
from medicoes_dwg.vaos import aplicar_alturas, associar_mq, mapa_vaos_mq

st.set_page_config(page_title="Medições DWG x MQ", page_icon="📐", layout="wide")
GRAV = {"Alta": "FFC7CE", "Média": "FFEB9C", "Baixa": "DDEBF7", "Info": "F2F2F2", "OK": "C6EFCE"}


def _cor(mapa):
    return lambda v: f"background-color: #{mapa[v]}" if v in mapa else ""


@st.cache_resource(show_spinner=False, max_entries=3)
def _analisar(digest: str, ficheiros: tuple, ignorar: str, perfis_path: str, mq_digest: str):
    tmp = Path(tempfile.mkdtemp(prefix="prj_"))
    lista = []
    for nome, data in ficheiros:
        p = tmp / nome
        p.write_bytes(data)
        lista.append((nome, str(p)))
    mq = st.session_state.get("mq")
    bar = st.progress(0.0, text="A preparar…")
    prj = carregar(lista, Registo(perfis_path), layers_ignorar=ignorar, mq=mq,
                   progress=lambda v, m="": bar.progress(min(v, 1.0), text=m or "…"))
    bar.empty()
    return prj


@st.cache_data(show_spinner=False, max_entries=8)
def _ler_mq(digest: str, nome: str, data: bytes):
    p = Path(tempfile.mkdtemp(prefix="mq_")) / nome
    p.write_bytes(data)
    mq, av = ler_mq(p)
    return mq, av, metadados_ficheiro(p)


def _dg(*blobs) -> str:
    h = hashlib.sha1()
    for b in blobs:
        h.update(b if isinstance(b, bytes) else str(b).encode())
    return h.hexdigest()


# ---------------------------------------------------------------- barra lateral
st.sidebar.title("📐 Medições DWG x MQ")
conv = find_converter()
st.sidebar.caption(f"Conversor DWG: **{conv[0] if conv else 'não instalado (use DXF)'}**")
f_des = st.sidebar.file_uploader("Desenhos do projeto (DWG/DXF) – inclua as xrefs", type=["dwg", "dxf"],
                                 accept_multiple_files=True)
f_mq = st.sidebar.file_uploader("Mapa de quantidades (xls, xlsx, csv)", type=["xls", "xlsx", "csv"])
with st.sidebar.expander("Parâmetros", expanded=False):
    pe_direito = st.number_input("Pé-direito por defeito [m]", 2.0, 6.0, 2.50, 0.05,
                                 help="Usado só quando o pé-direito não é lido dos cortes.")
    usar_pd = st.checkbox("Usar pé-direito lido dos cortes (por piso)", value=True)
    deduzir = st.checkbox("Deduzir vãos às áreas de paredes", value=True)
    alt_porta = st.number_input("Altura de portas por defeito [m]", 1.8, 3.5, 2.10, 0.05)
    alt_janela = st.number_input("Altura de janelas/vãos por defeito [m]", 0.5, 3.5, 2.10, 0.05)
    tol_ok = st.number_input("Tolerância OK [%]", 0.0, 50.0, 3.0, 0.5)
    tol_al = st.number_input("Tolerância ALERTA [%]", 0.0, 100.0, 10.0, 0.5)
    ignorar = st.text_input("Layers a ignorar (regex)", "", help="Ex.: veget|arvore|topo")
    perfis_path = st.text_input("Ficheiro do registo de projetistas", str(Registo().caminho))

ss = st.session_state
for k, v in {"mq": None, "mq_av": [], "mq_meta": {}, "regras_base": None, "regras": None, "sug_av": []}.items():
    ss.setdefault(k, v)
if f_mq is not None:
    d = f_mq.getvalue()
    ss.mq, ss.mq_av, ss.mq_meta = _ler_mq(_dg(d), f_mq.name, d)
mq = ss.mq

prj = None
if f_des:
    fich = tuple((f.name, f.getvalue()) for f in f_des)
    mqd = _dg(f_mq.getvalue()) if f_mq is not None else ""
    prj = _analisar(_dg(*[n for n, _ in fich], *[b for _, b in fich], ignorar, mqd), fich, ignorar, perfis_path, mqd)
reg = Registo(perfis_path)
if prj is not None and mq is not None and ss.mq_meta:
    reg.associar_documento(f_mq.name, ss.mq_meta)

if prj is None:
    st.title("Medições automáticas e compatibilização de projeto")
    st.markdown("""
**Fluxo (cada etapa é validável):**
0. **Projeto** – peças, especialidades, projetistas, xrefs em falta, incompatibilidades.
1. **Desenho** – desenho de medição (arquitetura), folhas, unidade, layers.
2. **Compartimentos** – etiquetas de área vs polígonos.
3. **Níveis e vãos** – pé-direito lido dos cortes; vãos detetados (alturas editáveis).
4. **Mapa de Quantidades** – leitura e verificações formais.
5. **Regras** – ligação artigo do MQ ↔ medição (sugestões afinadas pelo perfil do projetista).
6. **Comparação** – desvios com semáforo e rastreabilidade.
7. **Relatórios** – Excel (medições) e Word (incompatibilidades / pedidos de esclarecimento).
""")
    st.stop()

nomes = [d.ficheiro for d in prj.desenhos]
principal = prj.principal()
sel_nome = st.sidebar.selectbox("Desenho de medição", nomes, index=nomes.index(principal.ficheiro) if principal else 0)
des = next(d for d in prj.desenhos if d.ficheiro == sel_nome)
res = des.res
perfil = reg.get(des.perfil_id)

# vãos (associados ao MQ, alturas por defeito) - editáveis no separador 3
vaos_base = res.vaos
if mq is not None and vaos_base is not None and not vaos_base.empty:
    vaos_base = associar_mq(vaos_base, mapa_vaos_mq(mq))
vaos_base = aplicar_alturas(vaos_base, alt_porta, alt_janela) if vaos_base is not None and not vaos_base.empty else vaos_base

tabs = st.tabs(["0 · Projeto", "1 · Desenho", "2 · Compartimentos", "3 · Níveis e vãos", "4 · Mapa de Quantidades",
                "5 · Regras", "6 · Comparação", "7 · Relatórios"])

# ---------------------------------------------------------------- 0 projeto
with tabs[0]:
    if mq is not None:  # refazer verificações com o MQ atual
        prj.issues = []
        verificar_integridade(prj)
        verificar_compatibilizacao(prj, mq=mq)
    iss = prj.issues_df()
    c = st.columns(5)
    for col, g in zip(c, ["Alta", "Média", "Baixa", "Info", "OK"]):
        col.metric(g, int((iss.gravidade == g).sum()) if not iss.empty else 0)
    st.subheader("Peças analisadas")
    st.dataframe(prj.tabela(), hide_index=True, use_container_width=True)
    st.subheader("Integridade e incompatibilidades")
    cat = st.multiselect("Categorias", sorted(iss.categoria.unique()) if not iss.empty else [],
                         default=sorted(iss.categoria.unique()) if not iss.empty else [])
    st.dataframe(iss[iss.categoria.isin(cat)].style.map(_cor(GRAV), subset=["gravidade"]),
                 hide_index=True, use_container_width=True, height=420)
    st.subheader("Projetistas")
    if reg.perfis:
        st.dataframe(pd.DataFrame([{
            "id": p["id"], "nome": p["nome"], "evidência": p.get("evidencia_gabinete", ""),
            "especialidades": ", ".join(p["especialidades"]), "autores": ", ".join(p["autores"]),
            "assinatura": ", ".join(p["blocos_legenda"][:3] + p["prefixos_layers"][:3]),
            "layers conhecidos": "; ".join(f"{k}: {', '.join(v[:3])}" for k, v in p["layers_conhecidos"].items()),
            "blocos conhecidos": "; ".join(f"{k}: {', '.join(v[:3])}" for k, v in p["blocos_conhecidos"].items()),
            "documentos": len(p["projetos"])} for p in reg.perfis]), hide_index=True, use_container_width=True)
        with st.expander("Dar nome a um perfil (quando o gabinete for conhecido)"):
            c1, c2, c3 = st.columns([1, 3, 1])
            pid_n = c1.selectbox("Perfil ", [p["id"] for p in reg.perfis], key="ren_pid")
            novo_nome = c2.text_input("Nome do gabinete/projetista", reg.get(pid_n)["nome"], key="ren_nome")
            if c3.button("Guardar nome"):
                reg.get(pid_n).update(nome=novo_nome, gabinete=novo_nome, evidencia_gabinete="indicado pelo utilizador")
                reg.guardar()
                st.success("Nome guardado.")
        with st.expander("Ensinar um bloco ao perfil do projetista (ex.: A$C0BD9282B = lavatório)"):
            c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
            pid = c1.selectbox("Perfil", [p["id"] for p in reg.perfis],
                               index=[p["id"] for p in reg.perfis].index(des.perfil_id) if des.perfil_id in [p["id"] for p in reg.perfis] else 0)
            papel = c2.selectbox("Papel", list(PAPEIS_BLOCO))
            blocos = sorted(res.entidades[res.entidades.tipo == "INSERT"].bloco.unique())
            bloco = c3.selectbox("Bloco", blocos)
            if c4.button("Guardar"):
                reg.ensinar_bloco(pid, papel, bloco)
                st.success(f"'{bloco}' guardado como {papel} no perfil {pid}. Reaplique as sugestões de regras.")

# ---------------------------------------------------------------- 1 desenho
with tabs[1]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entidades", f"{len(res.entidades):,}".replace(",", " "))
    c2.metric("Folhas", len(res.folhas))
    c3.metric("Compartimentos", len(res.compartimentos))
    c4.metric("Unidade", res.unidade)
    for a in [a for a in res.avisos if "ignorada" not in a][:15]:
        st.warning(a)
    if res.xrefs:
        st.subheader("Referências externas (xrefs)")
        st.dataframe(pd.DataFrame(res.xrefs), hide_index=True, use_container_width=True)
    st.subheader("Folhas detetadas")
    ed = st.data_editor(res.folhas_df(), hide_index=True, disabled=["id", "xmin", "ymin", "xmax", "ymax", "origem"],
                        key=f"ed_folhas_{sel_nome}", use_container_width=True)
    for f, (_, row) in zip(res.folhas, ed.iterrows()):
        f.nome, f.nivel = row["nome"], row["nivel"]
    st.subheader("Layers")
    st.dataframe(res.layers_df().round(2), hide_index=True, use_container_width=True, height=300)
    st.subheader("Blocos por folha")
    if not res.entidades.empty:
        blk = (res.entidades[res.entidades.tipo == "INSERT"].groupby(["folha", "bloco"]).size()
               .reset_index(name="n").sort_values(["folha", "n"], ascending=[True, False]))
        st.dataframe(blk, hide_index=True, use_container_width=True, height=260)

# ---------------------------------------------------------------- 2 compartimentos
with tabs[2]:
    if res.compartimentos.empty:
        st.info("Sem etiquetas de compartimentos (texto 'NN.NN m²') neste desenho.")
    else:
        c = res.compartimentos.drop(columns=["x", "y"], errors="ignore")
        st.dataframe(c.style.map(lambda v: "background-color:#FFC7CE" if pd.notna(v) and abs(v) > 5 else "",
                                 subset=["desvio_%"]), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 3 níveis e vãos
with tabs[3]:
    st.subheader("Níveis e pé-direito")
    if res.pe_direito is None or res.pe_direito.empty:
        st.info("Sem cotas de nível suficientes: é usado o pé-direito por defeito.")
    else:
        st.caption("O pé-direito é lido das cotas verticais dos cortes que arrancam do pavimento; pode corrigi-lo aqui.")
        pdf = st.data_editor(res.pe_direito, hide_index=True, disabled=["folha", "nivel", "cota", "metodo_pd", "evidencia_pd"],
                             key=f"ed_pd_{sel_nome}", use_container_width=True)
        res.pe_direito = pdf
    st.subheader("Vãos detetados")
    if vaos_base is None or vaos_base.empty:
        st.info("Sem vãos detetados (layers de portas/janelas junto aos compartimentos).")
        vaos_edit = vaos_base
    else:
        st.caption("Largura medida em planta; altura do mapa de vãos do MQ (por largura) ou por defeito. "
                   "Edite alturas/tipos ou apague linhas de falsos vãos.")
        vaos_edit = st.data_editor(vaos_base.drop(columns=["x", "y"]), hide_index=True, num_rows="dynamic",
                                   key=f"ed_vaos_{sel_nome}", use_container_width=True, height=420,
                                   column_config={"tipo": st.column_config.SelectboxColumn(options=["porta", "janela/vão"])})
        vaos_edit = vaos_edit.merge(vaos_base[["id", "x", "y"]], on="id", how="left")
        vaos_edit["area"] = (vaos_edit.largura * vaos_edit.altura).round(3)
        st.metric("Área total de vãos (m²)", f"{vaos_edit.area.sum():.2f}")

# ---------------------------------------------------------------- 4 MQ
with tabs[4]:
    if mq is None:
        st.info("Carregue o mapa de quantidades.")
    else:
        if ss.mq_meta:
            st.caption("Metadados: " + " · ".join(f"{k}: {v}" for k, v in ss.mq_meta.items()))
        for a in ss.mq_av:
            st.warning(a)
        st.dataframe(mq, hide_index=True, use_container_width=True, height=460)
        st.subheader("Mapa de vãos lido do MQ")
        st.dataframe(mapa_vaos_mq(mq), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 5 regras
with tabs[5]:
    if mq is None:
        st.info("Carregue o MQ.")
    else:
        b1, b2, b3 = st.columns([1, 1, 2])
        chave = f"{sel_nome}"
        if b1.button("🔄 Sugerir regras automaticamente", use_container_width=True) or ss.get("regras_chave") != chave:
            ss.regras_base, ss.sug_av = sugerir_regras(mq, res, pe_direito, perfil=perfil)
            ss.regras_chave = chave
            ss.pop("ed_regras", None)
        up = b3.file_uploader("Importar regras (xlsx)", type=["xlsx"], label_visibility="collapsed")
        if up is not None and b2.button("Usar regras importadas", use_container_width=True):
            ss.regras_base = pd.read_excel(up).reindex(columns=COLUNAS)
            ss.pop("ed_regras", None)
        if perfil:
            st.caption(f"Sugestões afinadas com o perfil **{perfil['id']} – {perfil['nome']}**.")
        for a in ss.sug_av:
            st.warning(a)
        with st.expander("Fontes de medição"):
            st.table(pd.DataFrame([(k, v[0], v[1]) for k, v in FONTES.items()], columns=["fonte", "descrição", "unidade"]))
            st.markdown("- `fator` aceita `PD` (pé-direito **do piso** do elemento). Com `PD`, os vãos são deduzidos.\n"
                        "- `grupo`: itens comparados pela soma das quantidades do MQ.")
        ss.regras = st.data_editor(
            ss.regras_base if ss.regras_base is not None else regras_vazias(), num_rows="dynamic", hide_index=True,
            use_container_width=True, height=480, key="ed_regras",
            column_config={"ativo": st.column_config.CheckboxColumn(default=True),
                           "item_mq": st.column_config.SelectboxColumn(options=list(mq.id), width="large"),
                           "fonte": st.column_config.SelectboxColumn(options=list(FONTES)),
                           "confianca": st.column_config.SelectboxColumn(options=["alta", "média", "baixa"])})
        buf = io.BytesIO()
        ss.regras.to_excel(buf, index=False)
        st.download_button("⬇️ Exportar regras (xlsx)", buf.getvalue(), "regras_medicao.xlsx")

# ---------------------------------------------------------------- 6 comparação
comp = det = rr = None
regras = None
if mq is not None and ss.regras is not None:
    regras = ss.regras.copy()
    regras["regra"] = [r if isinstance(r, str) and r else f"R{i + 1:03d}" for i, r in enumerate(regras.regra)]
    comp, det, rr = comparar(mq, regras, res, pe_direito, tol_ok / 100, tol_al / 100, vaos=vaos_edit,
                             deduzir_vaos=deduzir, usar_pd_desenho=usar_pd, alt_porta=alt_porta, alt_janela=alt_janela)
with tabs[6]:
    if comp is None:
        st.info("Carregue o MQ e reveja as regras.")
    else:
        cnt = comp.estado.value_counts()
        for col, s in zip(st.columns(6), ["OK", "ALERTA", "CRÍTICO", "NÃO MEDIDO", "SEM REGRA", "N/A"]):
            col.metric(s, int(cnt.get(s, 0)))
        view = comp[comp.regras != ""] if st.toggle("Mostrar só itens com regra", value=True) else comp
        show = ["id", "unidade", "qtd_mq", "grupo", "qtd_mq_comparada", "qtd_dwg", "desvio", "desvio_pct", "estado",
                "regras", "observacoes", "ref_mq"]
        st.dataframe(view[show].style.map(_cor(FILL), subset=["estado"]), hide_index=True, use_container_width=True, height=480)
        it = st.selectbox("Rastreabilidade – entidades e deduções do item", [""] + list(view[view.regras != ""].id))
        if it:
            st.dataframe(det[det.item_mq == it], hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 7 relatórios
with tabs[7]:
    params = {"Desenho de medição": sel_nome, "Mapa de quantidades": f_mq.name if f_mq else "",
              "Unidade do desenho": res.unidade, "Pé-direito por defeito (m)": pe_direito,
              "Pé-direito dos cortes": "sim" if usar_pd else "não", "Dedução de vãos": "sim" if deduzir else "não",
              "Tolerância OK (%)": tol_ok, "Tolerância ALERTA (%)": tol_al}
    if comp is None:
        comp = pd.DataFrame(columns=["id", "artigo", "local", "descricao", "unidade", "qtd_mq", "grupo", "qtd_mq_comparada",
                                     "qtd_dwg", "desvio", "desvio_pct", "estado", "regras", "observacoes", "ref_mq"])
        det = pd.DataFrame(columns=["regra", "item_mq", "handle", "folha", "layer", "descricao", "valor"])
        rr, regras = pd.DataFrame(), regras_vazias()
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Relatório Excel (medições)", gerar_relatorio(
        comp, det, regras, rr, res, ss.mq_av, ss.sug_av, params, prj=prj, vaos=vaos_edit, perfis=reg.perfis),
        "relatorio_medicoes.xlsx", type="primary", use_container_width=True)
    c2.download_button("⬇️ Relatório Word (incompatibilidades)", gerar_docx(prj, comp, ss.mq_av, reg.perfis, params, regras=regras),
                       "relatorio_compatibilizacao.docx", use_container_width=True)
    c3.download_button("⬇️ Registo de projetistas (JSON)", reg.to_json(), "projetistas.json", use_container_width=True)
