"""Comparação MQ x medições do desenho."""
from __future__ import annotations

import pandas as pd

from .extractor import Resultado
from .rules import FONTES, aplicar_regra

ESTADOS = ["OK", "ALERTA", "CRÍTICO", "NÃO MEDIDO", "SEM REGRA"]


def estado(desvio: float | None, tol_ok: float, tol_alerta: float) -> str:
    if desvio is None or pd.isna(desvio):
        return "NÃO MEDIDO"
    a = abs(desvio)
    if a <= tol_ok:
        return "OK"
    if a <= tol_alerta:
        return "ALERTA"
    return "CRÍTICO"


def comparar(mq: pd.DataFrame, regras: pd.DataFrame, res: Resultado, pe_direito: float = 2.50,
             tol_ok: float = 0.03, tol_alerta: float = 0.10, vaos: pd.DataFrame | None = None,
             deduzir_vaos: bool = True, usar_pd_desenho: bool = True,
             alt_porta: float = 2.10, alt_janela: float = 2.10) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Devolve (comparacao, detalhe, regras_resultado).

    ``vaos``: tabela de vãos (editada pelo utilizador); por defeito usa a detetada no
    desenho, associada ao mapa de vãos do MQ, com alturas por defeito nas restantes.
    """
    from .niveis import pd_por_folha
    from .vaos import aplicar_alturas, associar_mq, mapa_vaos_mq
    if vaos is None:
        vaos = getattr(res, "vaos", None)
        if vaos is not None and not vaos.empty:
            vaos = associar_mq(vaos, mapa_vaos_mq(mq))
    vaos = aplicar_alturas(vaos, alt_porta, alt_janela) if vaos is not None and not vaos.empty else vaos
    pd_folhas = pd_por_folha(res, pe_direito) if usar_pd_desenho else {}
    det_all, rres = [], []
    medido: dict[str, float] = {}
    origem: dict[str, list[str]] = {}
    erros: dict[str, list[str]] = {}
    ativas = regras[regras.ativo.fillna(True).astype(bool)] if not regras.empty else regras
    for _, r in ativas.iterrows():
        val, det, err = aplicar_regra(r.to_dict(), res, pe_direito, vaos, deduzir_vaos, pd_folhas)
        rres.append(dict(regra=r.regra, item_mq=r.item_mq, fonte=r.fonte, valor=val, n_entidades=len(det), erro=err))
        if val is not None:
            medido[r.item_mq] = medido.get(r.item_mq, 0.0) + val
        origem.setdefault(r.item_mq, []).append(r.regra)
        if err:
            erros.setdefault(r.item_mq, []).append(f"{r.regra}: {err}")
        if not det.empty:
            det = det.copy()
            det.insert(0, "regra", r.regra)
            det.insert(1, "item_mq", r.item_mq)
            det_all.append(det)

    # grupos: vários itens do MQ comparados com uma única medição
    grupo_de: dict[str, str] = {}
    if not ativas.empty and "grupo" in ativas:
        for _, r in ativas.iterrows():
            g = str(r.get("grupo") or "").strip()
            if g and g.lower() != "nan":
                grupo_de[r.item_mq] = g
    membros: dict[str, list[str]] = {}
    for i, g in grupo_de.items():
        membros.setdefault(g, []).append(i)
    qtd = dict(zip(mq.id, mq.quantidade))
    val_grupo = {g: next((medido[i] for i in ids if i in medido), None) for g, ids in membros.items()}
    mq_grupo = {g: sum(qtd.get(i, 0) or 0 for i in ids) for g, ids in membros.items()}

    # altura implícita do MQ em artigos de paredes: (quantidade MQ + vãos deduzidos) / perímetro
    alt_impl: dict[str, tuple[float, float]] = {}
    if det_all:
        dd = pd.concat(det_all, ignore_index=True)
        if "base_m" in dd:
            for item, g in dd.groupby("item_mq"):
                base = g.base_m.fillna(0).sum()
                if base > 0:
                    vaos_area = -g[g.valor < 0].valor.sum()
                    pdm = g[g.base_m.fillna(0) > 0]
                    pd_med = (pdm.valor.sum() / base) if not pdm.empty else None
                    alt_impl[item] = (base, vaos_area, pd_med)

    rows = []
    for _, it in mq.iterrows():
        regs = origem.get(it.id, [])
        g = grupo_de.get(it.id, "")
        q_dwg = val_grupo[g] if g else medido.get(it.id)
        q_cmp = mq_grupo[g] if g else it.quantidade
        obs = erros.get(it.id, [])
        if g:
            obs = [f"Grupo {g} ({len(membros[g])} itens): MQ total {q_cmp:g} vs desenho {q_dwg if q_dwg is not None else '-'}"] + obs
        if not regs:
            st, dv = ("SEM REGRA" if it.unidade not in ("vg",) else "N/A"), None
        else:
            dv = (q_dwg - q_cmp) / q_cmp if q_dwg is not None and q_cmp else None
            st = estado(dv, tol_ok, tol_alerta)
            if q_dwg == 0:
                st = "NÃO MEDIDO"
        h_impl = None
        if it.id in alt_impl and not g:
            base, va, pd_med = alt_impl[it.id]
            h_impl = round((it.quantidade + va) / base, 2)
            h_bruta = it.quantidade / base
            obs = obs + [f"Altura implícita no MQ: {h_impl:.2f} m descontando vãos / {h_bruta:.2f} m sem descontar "
                         f"(pé-direito no desenho {pd_med:.2f} m; perímetro {base:.2f} m; vãos {va:.2f} m²)"]
        rows.append(dict(
            altura_implicita_mq=h_impl,
            id=it.id, capitulo=it.capitulo, artigo=it.artigo, local=it.local, descricao=it.descricao,
            unidade=it.unidade, qtd_mq=it.quantidade, grupo=g, qtd_mq_comparada=q_cmp,
            qtd_dwg=None if q_dwg is None else round(q_dwg, 2),
            desvio=None if q_dwg is None else round(q_dwg - q_cmp, 2),
            desvio_pct=None if dv is None else round(dv * 100, 1), estado=st, regras=", ".join(regs),
            observacoes=" | ".join(obs), ref_mq=it.ref,
        ))
    comp = pd.DataFrame(rows)
    # regras que apontam para itens inexistentes no MQ
    orf = set(origem) - set(mq.id)
    for o in sorted(orf):
        comp.loc[len(comp)] = dict(id=o, capitulo="", artigo="", local="", descricao="(item não existe no MQ)",
                                   unidade="", qtd_mq=None, grupo="", qtd_mq_comparada=None, qtd_dwg=round(medido.get(o, 0), 2), desvio=None,
                                   desvio_pct=None, estado="SEM ITEM MQ", regras=", ".join(origem[o]),
                                   observacoes="", ref_mq="")
    det = pd.concat(det_all, ignore_index=True) if det_all else pd.DataFrame(
        columns=["regra", "item_mq", "handle", "folha", "layer", "descricao", "valor"])
    rr = pd.DataFrame(rres)
    if not rr.empty:
        rr["fonte_desc"] = rr.fonte.map(lambda f: FONTES.get(f, ("?", ""))[0])
    return comp, det, rr
