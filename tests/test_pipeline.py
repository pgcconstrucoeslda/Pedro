"""Teste de ponta a ponta com um desenho sintético (sem ficheiros de clientes)."""
import ezdxf
import pandas as pd
import pytest

from medicoes_dwg.compare import comparar
from medicoes_dwg.extractor import extrair
from medicoes_dwg.mq_parser import ler_mq
from medicoes_dwg.rules import sugerir_regras


def _rect(msp, x0, y0, x1, y1, layer, closed=True):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=closed, dxfattribs={"layer": layer})


@pytest.fixture
def ficheiros(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    blk = doc.blocks.new("sanita")
    blk.add_circle((0, 0), 0.2)
    # duas folhas (molduras) com título
    for i, (titulo, y0) in enumerate([("Planta do Piso 1", 0), ("Planta do Piso 2", -40)]):
        _rect(msp, 0, y0, 60, y0 + 30, "Layout folha")
        msp.add_text(titulo, height=0.5, dxfattribs={"layer": "Titulos", "insert": (45, y0 + 1)})
    # Piso 1: sala 5x4 = 20 m2 e IS 2x2 = 4 m2
    _rect(msp, 5, 5, 10, 9, "AREAS")
    msp.add_text("Sala", height=0.2, dxfattribs={"insert": (7, 7.3)})
    msp.add_text("20.00m²", height=0.2, dxfattribs={"insert": (7, 7)})
    _rect(msp, 11, 5, 13, 7, "AREAS")
    msp.add_text("I.S. Serviço", height=0.2, dxfattribs={"insert": (11.5, 6.3)})
    msp.add_text("4.00m²", height=0.2, dxfattribs={"insert": (11.5, 6)})
    msp.add_blockref("sanita", (12, 5.5))
    # rodapé: perímetro da sala (18 m)
    for a, b in [((5, 5), (10, 5)), ((10, 5), (10, 9)), ((10, 9), (5, 9)), ((5, 9), (5, 5))]:
        msp.add_line(a, b, dxfattribs={"layer": "ARQ_rodapé"})
    # parede 6 m x 0,25 m em trama
    h = msp.add_hatch(dxfattribs={"layer": "ARQ_TramaParedes"})
    h.paths.add_polyline_path([(5, 10), (11, 10), (11, 10.25), (5, 10.25)], is_closed=True)
    # Piso 2: quarto 3x4 = 12 m2 (etiqueta com 12.50 -> desvio de etiqueta)
    _rect(msp, 5, -35, 8, -31, "AREAS")
    msp.add_text("Quarto", height=0.2, dxfattribs={"insert": (6, -32.7)})
    msp.add_text("12.50m²", height=0.2, dxfattribs={"insert": (6, -33)})
    msp.add_blockref("sanita", (7, -34))
    dxf = tmp_path / "teste.dxf"
    doc.saveas(dxf)

    mq = pd.DataFrame([
        ["Art.º", "Descrição dos trabalhos", "Qtd.", "Un."],
        ["7.1", "Pavimento flutuante", None, None],
        [None, "Sala", 20, "m2"],
        [None, "Quarto", 12, "m2"],
        ["7.2", "Pavimento na I.S. Serviço", 4.2, "m2"],
        ["11.5", "Rodapés em MDF", 22, "ml"],
        ["13.2", "Sanita suspensa", 2, "un"],
        ["1.1", "Estaleiro", 1, "vg"],
    ])
    xlsx = tmp_path / "mq.xlsx"
    mq.to_excel(xlsx, header=False, index=False, sheet_name="7_Pavimentos")
    return dxf, xlsx


def test_pipeline(ficheiros):
    dxf, xlsx = ficheiros
    res = extrair(str(dxf))
    assert res.unidade == "m"
    assert [f.nivel for f in res.folhas] == ["Piso 1", "Piso 2"]
    comps = res.compartimentos.set_index("compartimento")
    assert comps.loc["Sala", "area_geometria"] == pytest.approx(20.0)
    assert comps.loc["Sala", "perimetro"] == pytest.approx(18.0)
    assert comps.loc["Quarto", "desvio_%"] == pytest.approx(-4.0)
    par = res.paredes.iloc[0]
    assert par.comprimento == pytest.approx(6.0, abs=0.01)
    assert par.espessura == pytest.approx(0.25, abs=0.005)

    mq, avisos = ler_mq(xlsx)
    assert set(mq.id) >= {"7.1|Sala", "7.1|Quarto", "7.2", "11.5", "13.2", "1.1"}
    regras, _ = sugerir_regras(mq, res)
    comp, det, _ = comparar(mq, regras, res)
    c = comp.set_index("id")
    assert c.loc["7.1|Sala", "estado"] == "OK"
    assert c.loc["7.1|Quarto", "qtd_dwg"] == pytest.approx(12.5)
    assert c.loc["7.1|Quarto", "estado"] == "ALERTA"
    assert c.loc["7.2", "qtd_dwg"] == pytest.approx(4.0)
    assert c.loc["11.5", "qtd_dwg"] == pytest.approx(18.0)
    assert c.loc["11.5", "estado"] == "CRÍTICO"
    assert c.loc["13.2", "qtd_dwg"] == 2
    assert c.loc["1.1", "estado"] == "N/A"
    assert not det.empty and det.handle.notna().all()
