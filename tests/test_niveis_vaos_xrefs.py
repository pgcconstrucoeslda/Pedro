"""Testes com desenhos sintéticos: níveis/pé-direito, vãos, xrefs e projetistas."""
import ezdxf
import pandas as pd
import pytest

from medicoes_dwg.compare import comparar
from medicoes_dwg.extractor import extrair
from medicoes_dwg.projetistas import Registo
from medicoes_dwg.rules import COLUNAS


def _rect(msp, x0, y0, x1, y1, layer="0"):
    msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})


def _projeto(tmp_path, layout_block="LayoutXYZ"):
    doc = ezdxf.new()
    doc.blocks.new(layout_block)
    msp = doc.modelspace()
    folhas = [("Planta do Piso 1", 0), ("Planta do Piso 2", -40), ("Cortes", -80)]
    for titulo, y0 in folhas:
        _rect(msp, 0, y0, 60, y0 + 30, "Layout folha")
        msp.add_text(titulo, height=0.5, dxfattribs={"layer": "Titulos", "insert": (45, y0 + 1)})
    for y0, cota in ((0, "100.00"), (-40, "103.00")):
        # sala 4 x 3 = 12 m2
        _rect(msp, 5, y0 + 5, 9, y0 + 8, "AREAS")
        msp.add_text("Sala", height=0.2, dxfattribs={"insert": (6.5, y0 + 6.8)})
        msp.add_text("12.00m²", height=0.2, dxfattribs={"insert": (6.5, y0 + 6.5)})
        msp.add_text(cota, height=0.2, dxfattribs={"layer": "Cotas_Altimetricas", "insert": (7, y0 + 6)})
        # porta 0,80 no lado de baixo (arco com centro sobre a parede)
        msp.add_arc((6, y0 + 5), 0.8, 0, 90, dxfattribs={"layer": "PortasJanelas"})
        # janela 1,50 no lado de cima (duas linhas paralelas na espessura da parede)
        for dy in (0.05, 0.15):
            msp.add_line((6.5, y0 + 8 + dy), (8, y0 + 8 + dy), dxfattribs={"layer": "PortasJanelas"})
    # corte: marcas de nível e cota vertical de 2,70 a partir do pavimento do piso 1
    for cota, y in (("100.00", -70.0), ("103.00", -67.0), ("106.00", -64.0)):
        msp.add_text(cota, height=0.2, dxfattribs={"layer": "Cotas_Altimetricas", "insert": (20, y)})
    msp.add_linear_dim(base=(22, -68), p1=(21, -70), p2=(21, -67.3), angle=90).render()
    msp.add_linear_dim(base=(23, -68), p1=(21, -67), p2=(21, -64.3), angle=90).render()
    path = tmp_path / "projeto.dxf"
    doc.saveas(path)
    return path


def test_niveis_e_pe_direito(tmp_path):
    res = extrair(str(_projeto(tmp_path)))
    pdf = res.pe_direito.set_index("nivel")
    assert pdf.loc["Piso 1", "cota"] == pytest.approx(100.0)
    assert pdf.loc["Piso 2", "cota"] == pytest.approx(103.0)
    assert pdf.loc["Piso 1", "altura_pisos"] == pytest.approx(3.0)
    assert pdf.loc["Piso 1", "pe_direito"] == pytest.approx(2.70)
    assert "corte" in pdf.loc["Piso 1", "metodo_pd"]


def test_vaos_e_deducao(tmp_path):
    res = extrair(str(_projeto(tmp_path)))
    v = res.vaos[res.vaos.folha == "F01"].sort_values("largura")
    assert list(v.tipo) == ["porta", "janela/vão"]
    assert list(v.largura) == pytest.approx([0.80, 1.50], abs=0.02)

    mq = pd.DataFrame(dict(id=["9.1|Sala"], capitulo=["9_Pinturas"], artigo=["9.1"], local=["Sala"],
                           descricao=["Pintura de paredes"], quantidade=[30.0], unidade=["m²"], ref=["x!1"]))
    regra = dict.fromkeys(COLUNAS, "")
    regra.update(regra="R001", ativo=True, item_mq="9.1|Sala", fonte="PAREDES_COMPART", folhas="^F01$",
                 filtro="^sala$", fator="PD", deducao=0.0)
    regras = pd.DataFrame([regra], columns=COLUNAS)
    comp, det, _ = comparar(mq, regras, res, alt_porta=2.0, alt_janela=1.0)
    # perímetro 14 m × PD 2,70 − porta 0,80×2,00 − janela 1,50×1,00
    assert comp.qtd_dwg.iloc[0] == pytest.approx(14 * 2.70 - 1.6 - 1.5, abs=0.05)
    assert (det.valor < 0).sum() == 2
    comp2, _, _ = comparar(mq, regras, res, deduzir_vaos=False)
    assert comp2.qtd_dwg.iloc[0] == pytest.approx(14 * 2.70, abs=0.05)


def test_xrefs(tmp_path):
    x = ezdxf.new()
    x.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "TUBOS"})
    xp = tmp_path / "XREF-REDE.dxf"
    x.saveas(xp)
    doc = ezdxf.new()
    doc.add_xref_def(filename="..\\xrefs\\XREF-REDE.dwg", name="XREF-REDE")
    doc.modelspace().add_blockref("XREF-REDE", (100, 50))
    doc.modelspace().add_line((0, 0), (1, 1))
    mp = tmp_path / "folha.dxf"
    doc.saveas(mp)

    sem = extrair(str(mp))
    assert any("Xref em falta" in a for a in sem.avisos)
    assert sem.xrefs[0]["estado"] == "EM FALTA"

    com = extrair(str(mp), xrefs={"XREF-REDE": str(xp)})
    t = com.entidades[com.entidades.layer == "XREF-REDE|TUBOS"]
    assert len(t) == 1
    assert t.comprimento.iloc[0] == pytest.approx(10.0)
    assert t.x.iloc[0] == pytest.approx(105.0)


def test_registo_projetistas(tmp_path):
    reg = Registo(tmp_path / "perfis.json")
    r1 = extrair(str(_projeto(tmp_path, "LayoutXYZ")))
    p1, novo1 = reg.identificar(r1, "0001-ARQ-01.dwg")
    p2, novo2 = reg.identificar(r1, "0001-ARQ-02.dwg")
    assert novo1 and not novo2 and p1["id"] == p2["id"]
    assert p1["gabinete"] == "XYZ"
    assert "rodape" not in p1["layers_conhecidos"] and "vaos" in p1["layers_conhecidos"]
    reg.ensinar_bloco(p1["id"], "lavatorio", "A$C0BD9282B")
    assert Registo(tmp_path / "perfis.json").get(p1["id"])["blocos_conhecidos"]["lavatorio"] == ["A$C0BD9282B"]
    alvo = reg.associar_documento("mq.xls", {"ultimo_a_guardar": "Fulano | XYZ & Associados"})
    assert alvo["nome"] == "XYZ & Associados"
