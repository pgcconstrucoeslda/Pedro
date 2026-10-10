"""Linha de comandos.

Um desenho:   python -m medicoes_dwg.cli desenho.dwg --mq mapa.xls -o relatorio.xlsx
Projeto:      python -m medicoes_dwg.cli arq.dwg est-*.dwg ihd-*.dwg XREF-*.dwg --mq mapa.xls \\
                  -o relatorio.xlsx --docx incompatibilidades.docx
O desenho de medição é o de arquitetura com mais compartimentos (ou --principal).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .compare import comparar
from .mq_parser import ler_mq
from .projetistas import Registo, metadados_ficheiro
from .projeto import carregar
from .relatorio_docx import gerar_docx
from .report import gerar_relatorio
from .rules import COLUNAS, sugerir_regras


def main(argv=None):
    ap = argparse.ArgumentParser(description="Medições DWG x Mapa de Quantidades e compatibilização")
    ap.add_argument("desenhos", nargs="+", help="DWG/DXF do projeto (inclua as xrefs, se as tiver)")
    ap.add_argument("--mq", help="mapa de quantidades (xls/xlsx/csv)")
    ap.add_argument("-o", "--saida", default="relatorio_medicoes.xlsx")
    ap.add_argument("--docx", help="relatório Word de incompatibilidades")
    ap.add_argument("--regras", help="Excel de regras (se omitido, usa sugestões automáticas)")
    ap.add_argument("--principal", help="nome do desenho usado nas medições")
    ap.add_argument("--perfis", help="ficheiro JSON do registo de projetistas")
    ap.add_argument("--pe-direito", type=float, default=2.50, help="pé-direito por defeito (se não for lido dos cortes)")
    ap.add_argument("--alt-porta", type=float, default=2.10)
    ap.add_argument("--alt-janela", type=float, default=2.10)
    ap.add_argument("--sem-deducao-vaos", action="store_true")
    ap.add_argument("--tol-ok", type=float, default=3.0)
    ap.add_argument("--tol-alerta", type=float, default=10.0)
    a = ap.parse_args(argv)

    mq, mq_av, meta = None, [], {}
    if a.mq:
        mq, mq_av = ler_mq(a.mq)
        meta = metadados_ficheiro(a.mq)
        print(f"MQ: {len(mq)} itens")
    reg = Registo(a.perfis)
    prj = carregar([(Path(f).name, f) for f in a.desenhos], reg, mq=mq,
                   progress=lambda p, m="": print(f"  [{p:4.0%}] {m}") if m else None)
    if a.mq and meta:
        reg.associar_documento(a.mq, meta)
    print(prj.tabela()[["desenho", "especialidade", "projetista", "entidades", "compartimentos", "xrefs_em_falta"]].to_string())
    d = next((x for x in prj.desenhos if a.principal and a.principal in x.ficheiro), None) or prj.principal()
    res = d.res
    print(f"Desenho de medição: {d.ficheiro}")
    if not res.pe_direito.empty:
        print(res.pe_direito[["nivel", "cota", "altura_pisos", "pe_direito", "metodo_pd"]].to_string())

    comp = det = rr = None
    regras = pd.DataFrame(columns=COLUNAS)
    av = []
    if mq is not None:
        if a.regras:
            regras = pd.read_excel(a.regras).reindex(columns=COLUNAS)
        else:
            perfil = reg.get(d.perfil_id)
            regras, av = sugerir_regras(mq, res, a.pe_direito, perfil=perfil)
        comp, det, rr = comparar(mq, regras, res, a.pe_direito, a.tol_ok / 100, a.tol_alerta / 100,
                                 deduzir_vaos=not a.sem_deducao_vaos, alt_porta=a.alt_porta, alt_janela=a.alt_janela)
        print(comp.estado.value_counts().to_string())
    else:
        comp = pd.DataFrame(columns=["id", "artigo", "local", "descricao", "unidade", "qtd_mq", "grupo", "qtd_mq_comparada",
                                     "qtd_dwg", "desvio", "desvio_pct", "estado", "regras", "observacoes", "ref_mq"])
        det = pd.DataFrame(columns=["regra", "item_mq", "handle", "folha", "layer", "descricao", "valor"])
        rr = pd.DataFrame()
    params = {"Desenho de medição": d.ficheiro, "Mapa de quantidades": Path(a.mq).name if a.mq else "",
              "Unidade do desenho": res.unidade, "Pé-direito por defeito (m)": a.pe_direito,
              "Dedução de vãos": "não" if a.sem_deducao_vaos else "sim",
              "Tolerância OK (%)": a.tol_ok, "Tolerância ALERTA (%)": a.tol_alerta}
    from .vaos import aplicar_alturas, associar_mq, mapa_vaos_mq
    vaos = res.vaos
    if mq is not None and vaos is not None and not vaos.empty:
        vaos = aplicar_alturas(associar_mq(vaos, mapa_vaos_mq(mq)), a.alt_porta, a.alt_janela)
    res.vaos = vaos
    Path(a.saida).write_bytes(gerar_relatorio(comp, det, regras, rr, res, mq_av, av, params, prj=prj, vaos=vaos,
                                              perfis=reg.perfis))
    print(f"Relatório Excel: {a.saida}")
    if a.docx:
        Path(a.docx).write_bytes(gerar_docx(prj, comp, mq_av, reg.perfis, params, regras=regras))
        print(f"Relatório Word: {a.docx}")


if __name__ == "__main__":
    main()
