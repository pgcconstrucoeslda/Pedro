"""Uso: python -m medicoes_dwg.cli DESENHO.dwg|dxf MQ.xls[x] [-o relatorio.xlsx] [--regras regras.xlsx]"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .compare import comparar
from .converter import dwg_to_dxf
from .extractor import extrair
from .mq_parser import ler_mq
from .report import gerar_relatorio
from .rules import COLUNAS, sugerir_regras


def main(argv=None):
    ap = argparse.ArgumentParser(description="Medições DWG x Mapa de Quantidades")
    ap.add_argument("desenho")
    ap.add_argument("mq")
    ap.add_argument("-o", "--saida", default="relatorio_medicoes.xlsx")
    ap.add_argument("--regras", help="Excel de regras (se omitido, usa sugestões automáticas)")
    ap.add_argument("--pe-direito", type=float, default=2.50)
    ap.add_argument("--unidade", choices=["m", "cm", "mm"])
    ap.add_argument("--tol-ok", type=float, default=3.0)
    ap.add_argument("--tol-alerta", type=float, default=10.0)
    a = ap.parse_args(argv)

    dxf = Path(a.desenho)
    if dxf.suffix.lower() == ".dwg":
        print("A converter DWG -> DXF ...")
        dxf = dwg_to_dxf(dxf)
    print("A extrair geometria ...")
    res = extrair(str(dxf), unidade=a.unidade)
    print(f"  {len(res.entidades)} entidades, {len(res.folhas)} folhas, {len(res.compartimentos)} compartimentos")
    mq, mq_av = ler_mq(a.mq)
    print(f"  {len(mq)} itens no MQ")
    if a.regras:
        regras = pd.read_excel(a.regras)[COLUNAS]
        av = []
    else:
        regras, av = sugerir_regras(mq, res, a.pe_direito)
        print(f"  {len(regras)} regras sugeridas")
    comp, det, rr = comparar(mq, regras, res, a.pe_direito, a.tol_ok / 100, a.tol_alerta / 100)
    params = {"Desenho": Path(a.desenho).name, "Mapa de quantidades": Path(a.mq).name,
              "Unidade do desenho": res.unidade, "Pé-direito (PD) m": a.pe_direito,
              "Tolerância OK (%)": a.tol_ok, "Tolerância ALERTA (%)": a.tol_alerta}
    Path(a.saida).write_bytes(gerar_relatorio(comp, det, regras, rr, res, mq_av, av, params))
    print(comp.estado.value_counts().to_string())
    print(f"Relatório: {a.saida}")


if __name__ == "__main__":
    main()
