#!/usr/bin/env python3
"""Gera exemplo/modelo_exemplo.json: moradia fictícia de 2 pisos com parede inclinada.

Serve para testar verificar_modelo.py, build.py e o visualizador sem um projeto real.
Todos os valores são FICTÍCIOS (pranchas de exemplo "EX-xx").
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))

nos, idx = [], {}


def no(x, y, z, limite=False, status="EXTRAIDO", memoria="Exemplo: coordenada fictícia"):
    k = (round(x, 3), round(y, 3), round(z, 3))
    if k in idx:
        n = idx[k]
        if limite:
            n["limite_lote"] = True
        return n["id"]
    n = {"id": f"N-{len(nos)+1:04d}", "x": k[0], "y": k[1], "z": k[2], "status": status,
         "memoria": memoria, "limite_lote": limite}
    nos.append(n)
    idx[k] = n
    return n["id"]


trechos, pontos = [], []
cont = {}


def trecho(sis, dn, pts, pav, status="EXTRAIDO", prancha="EX-HID 02", memoria="", motivo="", embutido="", limite_fim=False):
    pre = {"HID-AF": "HID", "SAN-ESG": "ESG", "SAN-VENT": "VEN", "DRE-PLU": "PLU", "DRE-AC": "DAC"}[sis]
    cont[pre] = cont.get(pre, 0) + 1
    ids = [no(*p, limite=(limite_fim and i == len(pts) - 1)) for i, p in enumerate(pts)]
    trechos.append({"id": f"T-{pre}-{cont[pre]:04d}", "sistema": sis, "dn": dn, "nos": ids, "pav": pav,
                    "status": status, "prancha": prancha, "memoria": memoria or "Traço vetorial da planta registada; Z dos isométricos/notas",
                    "motivo": motivo, "embutido": embutido})


def ponto(pid, tipo, sis, dn, x, y, z, h, pav, amb, prancha, status="EXTRAIDO", motivo="", memoria=""):
    pontos.append({"id": pid, "no": no(x, y, z), "tipo": tipo, "sistema": sis, "dn": dn, "x": x, "y": y, "z": z, "h": h,
                   "pav": pav, "ambiente": amb, "prancha": prancha, "status": status, "motivo": motivo,
                   "memoria": memoria or f"X,Y: planta {prancha} registada sobre ARQ; h={h} do isométrico (fictício)"})


# ---------------------------------------------------------------- arquitetura
EXT = [(0, 0), (10, 0), (10, 5.5), (7.5, 8), (0, 8)]
pav = [
    {"id": "T", "nome": "Térreo", "z_piso": 0.0, "z_forro": 2.70, "z_laje_fundo": 2.90, "z_laje_topo": 3.05, "fonte": "EX-ARQ 05 Corte AA"},
    {"id": "S", "nome": "Superior", "z_piso": 3.10, "z_forro": 5.80, "z_laje_fundo": 6.00, "z_laje_topo": 6.15, "fonte": "EX-ARQ 05 Corte AA"},
    {"id": "C", "nome": "Cobertura", "z_piso": 6.15, "z_forro": None, "z_laje_fundo": None, "z_laje_topo": 6.15, "fonte": "EX-ARQ 05 Corte AA"},
]
paredes = []


def parede(pv, a, b, esp, z0, z1, tipo="parede"):
    paredes.append({"id": f"W-{pv}-{len([w for w in paredes if w['pav']==pv])+1:03d}", "pav": pv, "a": list(a), "b": list(b),
                    "esp": esp, "z0": z0, "z1": z1, "tipo": tipo, "fonte": "EX-ARQ 02 vetor (par paralelo)"})
    return paredes[-1]["id"]


W = {}
for pv, z0, z1 in (("T", 0.0, 2.90), ("S", 3.10, 6.00)):
    for i in range(len(EXT)):
        a, b = EXT[i], EXT[(i + 1) % len(EXT)]
        W[(pv, i)] = parede(pv, a, b, 0.15, z0 if pv == "S" else -0.02, z1)
    W[(pv, "x5")] = parede(pv, (5, 0), (5, 8), 0.13, z0 if pv == "S" else -0.02, z1)
    W[(pv, "y4")] = parede(pv, (5, 4), (10, 4), 0.13, z0 if pv == "S" else -0.02, z1)
parede("T", (-2.5, -3.0), (11.0, -3.0), 0.15, -0.15, 1.80, "muro")

esq = []


def esquadria(ref, tipo, wid, c, larg, alt, peit, zp, status="EXTRAIDO", fonte="EX-ARQ 07 Quadro de esquadrias"):
    esq.append({"id": f"ESQ-{len(esq)+1:02d}", "ref": ref, "tipo": tipo, "parede": wid, "centro": list(c), "largura": larg,
                "altura": alt, "peitoril": peit, "z_piso": zp, "status": status, "fonte": fonte})


esquadria("P01", "porta", W[("T", "x5")], (5, 6.5), 0.70, 2.10, 0, 0.0)
esquadria("P02", "porta", W[("T", "x5")], (5, 2.0), 0.80, 2.10, 0, 0.0)
esquadria("P03", "porta", W[("T", 0)], (2.5, 0), 0.90, 2.10, 0, 0.0)
esquadria("J01", "janela", W[("T", 0)], (8.5, 0), 1.20, 1.00, 1.10, 0.0)
esquadria("J02", "janela", W[("T", 4)], (0, 4.0), 2.00, 1.20, 0.90, 0.0)
esquadria("J03", "janela", W[("T", 3)], (6.5, 8), 0.60, 0.60, 1.60, -0.02)
esquadria("J04", "janela", W[("S", 1)], (10, 2.8), 0.60, 0.60, 1.60, 3.10)
esquadria("J05", "janela", W[("S", 3)], (2.5, 8), 1.50, 1.20, 0.90, 3.10)
esquadria("J06", "janela", W[("S", 2)], (8.75, 6.75), 1.20, 1.20, 0.90, 3.10)
esquadria("P04", "porta", W[("S", "x5")], (5, 6.0), 0.80, 2.10, 0, 3.10)
esquadria("P05", "porta", W[("S", "y4")], (9.0, 4), 0.70, 2.10, 0, 3.10)
esquadria("", "porta", W[("S", 0)], (2.5, 0), 1.00, 2.10, 0, 3.10, status="INFERIDO",
          fonte="Vão sem etiqueta: verga a 2,10 (INFERIDO)")

pisos = [
    {"id": "PS-T-01", "pav": "T", "ambiente": "SALA", "tipo": "piso", "z": 0.0, "esp": 0.10, "poly": [[0, 0], [5, 0], [5, 8], [0, 8]], "fonte": "EX-ARQ 02"},
    {"id": "PS-T-02", "pav": "T", "ambiente": "COZ", "tipo": "piso", "z": 0.0, "esp": 0.10, "poly": [[5, 0], [10, 0], [10, 4], [5, 4]], "fonte": "EX-ARQ 02"},
    {"id": "PS-T-03", "pav": "T", "ambiente": "BWC01", "tipo": "piso", "z": -0.02, "esp": 0.10, "poly": [[5, 4], [10, 4], [10, 5.5], [7.5, 8], [5, 8]], "fonte": "EX-ARQ 02 cota -0,02"},
    {"id": "PS-S-01", "pav": "S", "ambiente": "Q1", "tipo": "piso", "z": 3.10, "esp": 0.20, "poly": [[0, 0], [5, 0], [5, 8], [0, 8]], "fonte": "EX-ARQ 03"},
    {"id": "PS-S-02", "pav": "S", "ambiente": "BWC02", "tipo": "piso", "z": 3.10, "esp": 0.20, "poly": [[5, 0], [10, 0], [10, 4], [5, 4]], "fonte": "EX-ARQ 03"},
    {"id": "PS-S-03", "pav": "S", "ambiente": "Q2", "tipo": "piso", "z": 3.10, "esp": 0.20, "poly": [[5, 4], [10, 4], [10, 5.5], [7.5, 8], [5, 8]], "fonte": "EX-ARQ 03"},
    {"id": "PS-C-01", "pav": "C", "ambiente": "COB", "tipo": "cobertura", "z": 6.15, "esp": 0.15, "poly": [list(p) for p in EXT], "fonte": "EX-ARQ 04"},
]
ambientes = [
    {"id": "SALA", "nome": "Sala", "pav": "T", "pos": [2.5, 4.0]},
    {"id": "COZ", "nome": "Cozinha", "pav": "T", "pos": [7.5, 2.0]},
    {"id": "BWC01", "nome": "Banheiro social", "pav": "T", "pos": [6.8, 6.0]},
    {"id": "Q1", "nome": "Quarto 1", "pav": "S", "pos": [2.5, 4.0]},
    {"id": "BWC02", "nome": "Banheiro suíte", "pav": "S", "pos": [7.5, 2.0]},
    {"id": "Q2", "nome": "Quarto 2", "pav": "S", "pos": [6.8, 6.0]},
    {"id": "COB", "nome": "Cobertura", "pav": "C", "pos": [5.0, 6.5]},
]
niveis = [
    {"pav": "T", "ambiente": "SALA", "tipo": "piso", "z": 0.0, "fonte": "EX-ARQ 02", "status": "EXTRAIDO"},
    {"pav": "T", "ambiente": "BWC01", "tipo": "piso (rebaixado)", "z": -0.02, "fonte": "EX-ARQ 02 cota -0,02", "status": "EXTRAIDO"},
    {"pav": "T", "ambiente": "Exterior", "tipo": "terreno", "z": -0.15, "fonte": "EX-ARQ 01 implantação", "status": "EXTRAIDO"},
    {"pav": "S", "ambiente": "(todos)", "tipo": "piso", "z": 3.10, "fonte": "EX-ARQ 05 Corte AA", "status": "EXTRAIDO"},
    {"pav": "C", "ambiente": "Caixa de água", "tipo": "base", "z": 6.25, "fonte": "EX-HID 04 detalhe 1", "status": "EXTRAIDO"},
]

# ---------------------------------------------------------------- louças (apoio na face + normal)
r2 = 2 ** 0.5
loucas = [
    {"id": "LC-T-BWC01-01", "tipo": "vaso", "pav": "T", "ambiente": "BWC01", "apoio": [5.065, 5.0], "normal": [1, 0], "largura": 0.36, "profundidade": 0.65, "altura": 0.40, "z": -0.02},
    {"id": "LC-T-BWC01-02", "tipo": "bancada_1cuba", "pav": "T", "ambiente": "BWC01", "apoio": [6.5, 4.065], "normal": [0, 1], "largura": 0.60, "profundidade": 0.45, "altura": 0.85, "z": -0.02},
    {"id": "LC-T-BWC01-03", "tipo": "chuveiro", "pav": "T", "ambiente": "BWC01", "apoio": [round(8.75 - 0.0751 / r2, 6), round(6.75 - 0.0751 / r2, 6)], "normal": [-1 / r2, -1 / r2], "largura": 0.90, "profundidade": 0.90, "altura": 2.10, "z": -0.02},
    {"id": "LC-T-COZ-01", "tipo": "bancada_2cubas", "pav": "T", "ambiente": "COZ", "apoio": [7.5, 0.075], "normal": [0, 1], "largura": 1.20, "profundidade": 0.60, "altura": 0.90, "z": 0.0},
    {"id": "LC-T-COZ-02", "tipo": "maquina_lavar", "pav": "T", "ambiente": "COZ", "apoio": [9.3, 0.075], "normal": [0, 1], "largura": 0.60, "profundidade": 0.60, "altura": 0.85, "z": 0.0},
    {"id": "LC-S-BWC02-01", "tipo": "vaso", "pav": "S", "ambiente": "BWC02", "apoio": [5.065, 1.5], "normal": [1, 0], "largura": 0.36, "profundidade": 0.65, "altura": 0.40, "z": 3.10},
    {"id": "LC-S-BWC02-02", "tipo": "bancada_1cuba", "pav": "S", "ambiente": "BWC02", "apoio": [7.0, 3.935], "normal": [0, -1], "largura": 0.80, "profundidade": 0.45, "altura": 0.85, "z": 3.10},
    {"id": "LC-S-BWC02-03", "tipo": "chuveiro", "pav": "S", "ambiente": "BWC02", "apoio": [9.925, 1.0], "normal": [-1, 0], "largura": 0.90, "profundidade": 0.90, "altura": 2.10, "z": 3.10},
]
for l in loucas:
    l.update({"fonte": "EX-ARQ 02/03 desenho vetorial; dimensões usuais de mercado (sem cota)", "status": "EXTRAIDO"})

equip = [
    {"id": "EQ-HD-01", "tipo": "hidrometro", "nome": "Hidrómetro", "centro": [4.0, -2.0, 0.60], "dims": [0.40, 0.20, 0.50], "rot": 0, "sistema": "HID-AF"},
    {"id": "EQ-RI-01", "tipo": "reservatorio_inferior", "nome": "Reservatório inferior", "centro": [8.0, -3.0 + 0.0, -0.80], "dims": [1.50, 1.20, 1.60], "rot": 0, "sistema": "HID-AF"},
    {"id": "EQ-MB-01", "tipo": "motobomba", "nome": "Motobomba", "centro": [6.5, -3.0, 0.25], "dims": [0.50, 0.30, 0.35], "rot": 0, "sistema": "HID-AF"},
    {"id": "EQ-CX-01", "tipo": "caixa_agua", "nome": "Caixa de água 1000 L", "centro": [2.0, 1.5, 6.75], "dims": [1.20, 1.00, 1.00], "rot": 0, "sistema": "HID-AF"},
    {"id": "EQ-CI-01", "tipo": "caixa_inspecao", "nome": "Caixa de inspeção CI-01", "centro": [5.35, -1.30, -0.60], "dims": [0.60, 0.60, 0.60], "rot": 0, "sistema": "SAN-ESG"},
    {"id": "EQ-CG-01", "tipo": "caixa_gordura", "nome": "Caixa de gordura CG-01", "centro": [7.5, -1.0, -0.40], "dims": [0.50, 0.50, 0.60], "rot": 0, "sistema": "SAN-ESG"},
    {"id": "EQ-CA-01", "tipo": "caixa_areia", "nome": "Caixa de areia CA-01", "centro": [-1.5, 3.0, -0.50], "dims": [0.60, 0.60, 0.60], "rot": 0, "sistema": "DRE-PLU"},
]
for e in equip:
    e.update({"fonte": "EX-HID/SAN/DRE detalhes (fictício)", "status": "EXTRAIDO"})

# ---------------------------------------------------------------- água fria
H = "HID-AF"
trecho(H, 25, [(4.0, -3.0, -0.40), (4.0, -2.05, -0.40), (4.0, -2.05, 0.45)], "T", prancha="EX-HID 01", embutido="enterrado")
nos[0]["limite_lote"] = True
trecho(H, 25, [(4.0, -1.95, 0.45), (4.0, -1.95, -0.40), (4.0, -1.5, -0.40)], "T", prancha="EX-HID 01")
trecho(H, 25, [(4.0, -1.5, -0.40), (1.0, -1.5, -0.40), (0.5, -1.5, -0.40), (0.5, 0.3, -0.40), (0.5, 0.3, 7.0), (0.5, 1.5, 7.0), (1.45, 1.5, 7.0)], "T",
       prancha="EX-HID 01", memoria="Alimentação direta da caixa de água (subida); trecho enterrado até ao interior")
trecho(H, 25, [(4.0, -1.5, -0.40), (8.0, -1.5, -0.40), (8.0, -2.45, -0.40)], "T", prancha="EX-HID 01", memoria="Ramal enterrado até ao reservatório inferior (boia)")
trecho(H, 32, [(7.6, -3.0, -1.5), (7.6, -3.0, 0.2), (6.7, -3.0, 0.2)], "T", prancha="EX-HID 04", memoria="Sucção: válvula de pé no reservatório inferior")
trecho(H, 25, [(6.3, -3.0, 0.2), (5.5, -3.0, 0.2), (5.5, -0.3, 0.2), (5.5, -0.3, 6.6), (5.5, 1.5, 6.6), (2.55, 1.5, 6.6)], "T", prancha="EX-HID 04", memoria="Recalque até à caixa de água")
trecho(H, 32, [(2.3, 1.95, 6.35), (2.3, 3.0, 6.35), (5.0, 3.0, 6.35)], "C", prancha="EX-HID 04", memoria="Barrilete")
trecho(H, 32, [(1.45, 1.2, 6.30), (0.3, 1.2, 6.30), (0.3, 3.0, 6.30), (0.3, 3.0, 6.15)], "C", prancha="EX-HID 04", memoria="Limpeza da caixa → ralo da cobertura")
trecho(H, 32, [(1.45, 1.9, 7.10), (0.3, 1.9, 7.10), (0.3, 1.9, 6.30)], "C", prancha="EX-HID 04", memoria="Extravasor → junta à limpeza")
trecho(H, 25, [(5.0, 3.0, 6.35), (5.0, 3.0, 5.00), (5.0, 3.0, 4.30), (5.0, 3.0, 2.80)], "S", prancha="EX-HID 05", memoria="Coluna AF01 (isométrico ISO-01)", embutido="parede")
trecho(H, 25, [(5.0, 3.0, 4.30), (5.0, 1.5, 4.30), (5.0, 1.5, 3.40)], "S", prancha="EX-HID 05", embutido="parede")
trecho(H, 25, [(5.0, 3.0, 4.30), (5.0, 4.0, 4.30), (7.0, 4.0, 4.30), (7.0, 4.0, 3.70)], "S", prancha="EX-HID 05", embutido="parede")
trecho(H, 25, [(5.0, 1.5, 4.30), (5.0, 0.0, 4.30), (10.0, 0.0, 4.30), (10.0, 1.0, 4.30), (10.0, 1.0, 5.30)], "S", prancha="EX-HID 05", embutido="parede")
trecho(H, 25, [(5.0, 3.0, 2.80), (5.0, 4.6, 2.80), (5.0, 4.6, 1.88), (5.0, 4.6, 1.18), (5.0, 5.0, 1.18), (5.0, 5.0, 0.28)], "T",
       status="INFERIDO", prancha="EX-HID 02", motivo="Z do ramal = +2,80 entre forro (+2,70) e fundo da laje (+2,90); cota não indicada",
       memoria="Ramal sobre o forro: Z inferido entre forro e laje", embutido="forro")
trecho(H, 25, [(5.0, 4.6, 1.18), (5.0, 4.0, 1.18), (6.5, 4.0, 1.18), (6.5, 4.0, 0.58)], "T", prancha="EX-HID 02", embutido="parede")
trecho(H, 25, [(5.0, 4.6, 2.80), (8.75, 6.75, 2.80), (8.75, 6.75, 2.18)], "T", prancha="EX-HID 02", embutido="forro")
trecho(H, 25, [(5.0, 3.0, 2.80), (7.5, 3.0, 2.80), (7.5, 0.0, 2.80), (7.5, 0.0, 1.20), (7.5, 0.0, 0.60)], "T", prancha="EX-HID 02", embutido="forro")
trecho(H, 25, [(7.5, 0.0, 1.20), (9.3, 0.0, 1.20), (9.3, 0.0, 0.90)], "T", prancha="EX-HID 02", embutido="parede")
trecho(H, 20, [(1.0, -1.5, -0.40), (1.0, 0.0, -0.40), (1.0, 0.0, 0.60)], "T", status="INFERIDO", prancha="EX-HID 01",
       motivo="Ligação da torneira de jardim não desenhada; traçado deduzido", embutido="enterrado")

ponto("HID-T-BWC01-001", "registo de gaveta", H, 25, 5.0, 4.6, 1.88, 1.90, "T", "BWC01", "EX-HID 02")
ponto("HID-T-BWC01-002", "vaso com caixa acoplada", H, 20, 5.0, 5.0, 0.28, 0.30, "T", "BWC01", "EX-HID 02")
ponto("HID-T-BWC01-003", "lavatório", H, 20, 6.5, 4.0, 0.58, 0.60, "T", "BWC01", "EX-HID 02")
ponto("HID-T-BWC01-004", "chuveiro", H, 25, 8.75, 6.75, 2.18, 2.20, "T", "BWC01", "EX-HID 02")
ponto("HID-T-COZ-001", "pia de cozinha", H, 20, 7.5, 0.0, 0.60, 0.60, "T", "COZ", "EX-HID 02")
ponto("HID-T-COZ-002", "máquina de lavar", H, 20, 9.3, 0.0, 0.90, 0.90, "T", "COZ", "EX-HID 02",
      status="INFERIDO", motivo="Altura não cotada no isométrico: adotado 0,90 (altura usual de mercado)")
ponto("HID-T-EXT-001", "torneira de jardim", H, 20, 1.0, 0.0, 0.60, None, "T", "EXT", "EX-HID 01",
      status="PENDENTE", motivo="Símbolo sem legenda na planta; altura não indicada")
ponto("HID-S-BWC02-001", "registo de gaveta", H, 25, 5.0, 3.0, 5.00, 1.90, "S", "BWC02", "EX-HID 05")
ponto("HID-S-BWC02-002", "vaso com caixa acoplada", H, 20, 5.0, 1.5, 3.40, 0.30, "S", "BWC02", "EX-HID 05")
ponto("HID-S-BWC02-003", "lavatório", H, 20, 7.0, 4.0, 3.70, 0.60, "S", "BWC02", "EX-HID 05")
ponto("HID-S-BWC02-004", "chuveiro", H, 25, 10.0, 1.0, 5.30, 2.20, "S", "BWC02", "EX-HID 05")

# ---------------------------------------------------------------- esgoto
E = "SAN-ESG"
trecho(E, 100, [(5.35, 5.0, -0.02), (5.35, 5.0, -0.35), (5.35, 4.4, -0.360), (5.35, 3.0, -0.383), (5.35, -1.05, -0.45)], "T", prancha="EX-SAN 01",
       memoria="Coletor do BWC01; Z interpolado pelo comprimento entre saída do vaso e CI-01", embutido="enterrado")
trecho(E, 50, [(7.0, 5.5, -0.02), (7.0, 5.5, -0.25), (7.0, 3.0, -0.31), (5.35, 3.0, -0.383)], "T", prancha="EX-SAN 01", embutido="enterrado")
trecho(E, 40, [(6.5, 4.0, 0.50), (6.5, 4.0, -0.20), (7.0, 5.5, -0.25)], "T", prancha="EX-SAN 01")
trecho(E, 100, [(5.35, 1.5, 3.10), (5.35, 1.5, 2.80), (5.0, 0.5, 2.76)], "S", prancha="EX-SAN 02", embutido="forro")
trecho(E, 50, [(8.5, 1.0, 3.10), (8.5, 1.0, 2.88), (5.0, 0.5, 2.80)], "S", prancha="EX-SAN 02", embutido="forro")
trecho(E, 40, [(7.0, 4.0, 3.60), (7.0, 4.0, 2.89), (5.0, 0.5, 2.80)], "S", prancha="EX-SAN 02", embutido="forro")
trecho(E, 100, [(5.0, 0.5, 2.80), (5.0, 0.5, 2.76), (5.0, 0.5, -0.40), (5.25, -1.05, -0.45)], "T", prancha="EX-SAN 03",
       memoria="TQ-01; base do TQ a -0,40 (INFERIDA, ver DIV-001)", embutido="parede")
trecho(E, 50, [(7.5, 0.0, 0.50), (7.5, 0.0, -0.20), (7.5, -0.8, -0.22)], "T", prancha="EX-SAN 01")
trecho(E, 50, [(9.3, 0.0, 0.90), (9.3, 0.0, -0.15), (7.5, 0.0, -0.20)], "T", prancha="EX-SAN 01")
trecho(E, 100, [(7.3, -1.2, -0.45), (5.6, -1.2, -0.50)], "T", prancha="EX-SAN 01", embutido="enterrado")
trecho(E, 100, [(5.35, -1.55, -0.65), (5.35, -3.0, -0.70)], "T", prancha="EX-SAN 01", memoria="Saída para a rede pública", limite_fim=True)
ponto("SAN-T-BWC01-001", "saída de vaso", E, 100, 5.35, 5.0, -0.02, 0.0, "T", "BWC01", "EX-SAN 01")
ponto("SAN-T-BWC01-002", "saída de lavatório", E, 40, 6.5, 4.0, 0.50, 0.52, "T", "BWC01", "EX-SAN 01")
ponto("SAN-T-BWC01-003", "caixa sifonada", E, 50, 7.0, 5.5, -0.02, 0.0, "T", "BWC01", "EX-SAN 01")
ponto("SAN-T-COZ-001", "saída de pia", E, 50, 7.5, 0.0, 0.50, 0.50, "T", "COZ", "EX-SAN 01")
ponto("SAN-T-COZ-002", "saída de máquina de lavar", E, 50, 9.3, 0.0, 0.90, 0.90, "T", "COZ", "EX-SAN 01")
ponto("SAN-S-BWC02-001", "saída de vaso", E, 100, 5.35, 1.5, 3.10, 0.0, "S", "BWC02", "EX-SAN 02")
ponto("SAN-S-BWC02-002", "saída de lavatório", E, 40, 7.0, 4.0, 3.60, 0.50, "S", "BWC02", "EX-SAN 02")
ponto("SAN-S-BWC02-003", "caixa sifonada", E, 50, 8.5, 1.0, 3.10, 0.0, "S", "BWC02", "EX-SAN 02")

V = "SAN-VENT"
trecho(V, 50, [(5.35, 4.4, -0.360), (5.0, 4.4, -0.30), (5.0, 4.4, 6.45)], "T", prancha="EX-SAN 03", memoria="Coluna de ventilação CV-01 até 0,30 acima da cobertura (nota EX-SAN 03)", embutido="parede")
trecho(V, 100, [(5.0, 0.5, 2.80), (5.0, 0.5, 6.45)], "S", prancha="EX-SAN 03", memoria="Prolongamento do TQ-01 para ventilação", embutido="parede")
ponto("SAN-C-COB-001", "terminal de ventilação", V, 50, 5.0, 4.4, 6.45, 0.30, "C", "COB", "EX-SAN 03")
ponto("SAN-C-COB-002", "terminal de ventilação", V, 100, 5.0, 0.5, 6.45, 0.30, "C", "COB", "EX-SAN 03")

# ---------------------------------------------------------------- pluvial e drenos
P = "DRE-PLU"
trecho(P, 100, [(0.3, 3.0, 6.15), (0.3, 3.0, 5.95), (0.0, 3.0, 5.94), (0.0, 3.0, -0.45), (-1.25, 3.0, -0.50)], "C", prancha="EX-DRE 01", memoria="Condutor AP-01", embutido="parede")
trecho(P, 100, [(-1.5, 2.75, -0.60), (-1.5, -3.0, -0.75)], "T", prancha="EX-DRE 01", memoria="Saída para a sarjeta", limite_fim=True)
ponto("DRE-C-COB-001", "ralo da cobertura", P, 100, 0.3, 3.0, 6.15, 0.0, "C", "COB", "EX-DRE 01")
A = "DRE-AC"
trecho(A, 20, [(2.0, 7.95, 5.30), (0.0, 7.5, 5.25), (0.0, 7.5, -0.30), (-1.3, 3.2, -0.40)], "S", status="INFERIDO", prancha="EX-DRE 02",
       motivo="Traço sem legenda na planta; destino deduzido (CA-01)", memoria="Dreno do AC rastreado até CA-01", embutido="parede")
ponto("DRE-S-Q1-001", "dreno de ar condicionado", A, 20, 2.0, 7.95, 5.30, 2.20, "S", "Q1", "EX-DRE 02")

# ---------------------------------------------------------------- divergências
divs = [
    {"id": "DIV-001", "tipo": "Nível não cotado", "descricao": "Cota da base do TQ-01 não indicada; adotada -0,40 para fechar com a CI-01.", "pranchas": ["EX-SAN 03", "EX-ARQ 05"],
     "pos": [5.0, 0.5, -0.40], "ids": ["T-ESG-0007"], "gravidade": "media", "disciplinas": ["SAN", "ARQ"]},
    {"id": "DIV-002", "tipo": "Símbolo sem legenda", "descricao": "Dreno de AC desenhado com traço sem legenda; destino deduzido.", "pranchas": ["EX-DRE 02"],
     "pos": [0.0, 7.5, 2.0], "ids": ["T-DAC-0001", "DRE-S-Q1-001"], "gravidade": "baixa", "disciplinas": ["DRE"]},
    {"id": "DIV-003", "tipo": "Contagem iso ≠ planta", "descricao": "Isométrico ISO-01 mostra 3 pontos no BWC01; a planta mostra 4 (chuveiro).", "pranchas": ["EX-HID 02", "EX-HID 06"],
     "pos": [8.75, 6.75, 2.18], "ids": ["HID-T-BWC01-004"], "gravidade": "alta", "disciplinas": ["HID"]},
    {"id": "DIV-004", "tipo": "Nomenclatura de ambiente", "descricao": "ARQ chama 'WC Social' e HID chama 'Banheiro 01'.", "pranchas": ["EX-ARQ 02", "EX-HID 02"],
     "pos": [6.8, 6.0, 0.0], "ids": [], "gravidade": "baixa", "disciplinas": ["ARQ"]},
    {"id": "DIV-005", "tipo": "Símbolo sem legenda", "descricao": "Torneira de jardim: símbolo sem legenda e sem altura.", "pranchas": ["EX-HID 01"],
     "pos": [1.0, 0.0, 0.60], "ids": ["HID-T-EXT-001"], "gravidade": "media", "disciplinas": ["HID", "ARQ"]},
]

pranchas = [
    {"codigo": "EX-ARQ 02", "disciplina": "ARQ", "pavimento": "T", "titulo": "Planta do Térreo", "curto": "ARQ 02 · Planta Térreo", "escala": "1:50", "rev": "R02", "data": "2026-02-01"},
    {"codigo": "EX-ARQ 03", "disciplina": "ARQ", "pavimento": "S", "titulo": "Planta do Superior", "curto": "ARQ 03 · Planta Superior", "escala": "1:50", "rev": "R02", "data": "2026-02-01"},
    {"codigo": "EX-ARQ 05", "disciplina": "ARQ", "pavimento": "-", "titulo": "Cortes AA e BB", "curto": "ARQ 05 · Cortes", "escala": "1:50", "rev": "R01", "data": "2026-01-15"},
    {"codigo": "EX-ARQ 07", "disciplina": "ARQ", "pavimento": "-", "titulo": "Quadro de esquadrias", "curto": "ARQ 07 · Esquadrias", "escala": "-", "rev": "R00", "data": "2026-01-15"},
    {"codigo": "EX-HID 01", "disciplina": "HID", "pavimento": "T", "titulo": "Água fria — Implantação e entrada", "curto": "HID 01 · Entrada", "escala": "1:100", "rev": "R01", "data": "2026-03-10"},
    {"codigo": "EX-HID 02", "disciplina": "HID", "pavimento": "T", "titulo": "Água fria — Planta do Térreo", "curto": "HID 02 · Planta Térreo", "escala": "1:50", "rev": "R01", "data": "2026-03-10"},
    {"codigo": "EX-HID 04", "disciplina": "HID", "pavimento": "C", "titulo": "Água fria — Cobertura e caixas", "curto": "HID 04 · Cobertura", "escala": "1:50", "rev": "R01", "data": "2026-03-10"},
    {"codigo": "EX-HID 05", "disciplina": "HID", "pavimento": "S", "titulo": "Água fria — Planta do Superior", "curto": "HID 05 · Planta Superior", "escala": "1:50", "rev": "R01", "data": "2026-03-10"},
    {"codigo": "EX-HID 06", "disciplina": "HID", "pavimento": "-", "titulo": "Isométricos dos banheiros", "curto": "HID 06 · Isométricos", "escala": "s/e", "rev": "R01", "data": "2026-03-10"},
    {"codigo": "EX-SAN 01", "disciplina": "SAN", "pavimento": "T", "titulo": "Esgoto — Planta do Térreo", "curto": "SAN 01 · Planta Térreo", "escala": "1:50", "rev": "R00", "data": "2026-03-12"},
    {"codigo": "EX-SAN 02", "disciplina": "SAN", "pavimento": "S", "titulo": "Esgoto — Planta do Superior", "curto": "SAN 02 · Planta Superior", "escala": "1:50", "rev": "R00", "data": "2026-03-12"},
    {"codigo": "EX-SAN 03", "disciplina": "SAN", "pavimento": "-", "titulo": "Esgoto — Colunas e ventilação", "curto": "SAN 03 · Colunas", "escala": "s/e", "rev": "R00", "data": "2026-03-12"},
    {"codigo": "EX-DRE 01", "disciplina": "DRE", "pavimento": "T", "titulo": "Pluvial — Planta", "curto": "DRE 01 · Pluvial", "escala": "1:100", "rev": "R00", "data": "2026-03-12"},
    {"codigo": "EX-DRE 02", "disciplina": "DRE", "pavimento": "S", "titulo": "Drenos de AC", "curto": "DRE 02 · Drenos AC", "escala": "1:50", "rev": "R00", "data": "2026-03-12"},
]

modelo = {
    "meta": {"projeto": "Moradia unifamiliar (exemplo)", "codigo": "EX-001", "rev": "R00", "data": "2026-10-16", "escala": "1:50",
             "folha": "MOD-3D-01", "unidade": "m", "origem": "Vértice externo SO do térreo (eixo das paredes exteriores) — EX-ARQ 02",
             "rn": "RN = piso acabado do térreo = ±0,000 (EX-ARQ 05)", "z_terreno": -0.15,
             "cores": {"HID-AF": "#1e88e5", "SAN-ESG": "#8d5a2b", "SAN-VENT": "#5f9e3a", "DRE-PLU": "#0f9b8e", "DRE-AC": "#8e44ad"},
             "cores_fonte": "Exemplo: paleta padrão",
             "declividades": [
                 {"sistema": "SAN-ESG", "dn_min": 100, "dn_max": 999, "min": 0.01, "max": 0.05, "fonte": "EX-SAN 01 nota 3"},
                 {"sistema": "SAN-ESG", "dn_min": 0, "dn_max": 99, "min": 0.02, "max": 0.05, "fonte": "EX-SAN 01 nota 3"},
                 {"sistema": "DRE-PLU", "dn_min": 0, "dn_max": 999, "min": 0.01, "max": 0.05, "fonte": "EX-DRE 01 nota 1"},
                 {"sistema": "DRE-AC", "dn_min": 0, "dn_max": 999, "min": 0.01, "max": 0.05, "fonte": "EX-DRE 02 nota 1"}],
             "tolerancia_continuidade": 0.01},
    "pranchas": pranchas, "pavimentos": pav, "niveis": niveis, "pisos": pisos, "ambientes": ambientes, "paredes": paredes,
    "esquadrias": esq, "nos": nos, "pontos": pontos, "trechos": trechos, "loucas": loucas, "equipamentos": equip,
    "divergencias": divs,
    "premissas": ["Origem: vértice externo SO do térreo (eixo das paredes exteriores).",
                  "Z = cota de projeto; RN = piso acabado do térreo ±0,000.",
                  "Ramais de AF sobre o forro do térreo a +2,80 (INFERIDO: entre forro +2,70 e fundo da laje +2,90).",
                  "Registo de gaveta a 1,90 do piso (isométrico).",
                  "Máquina de lavar a 0,90 (altura usual de mercado, sem cota).",
                  "Muro frontal: altura adotada 1,80 (não cotada)."],
    "verificacoes": {}, "locacao": {},
}

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "modelo_exemplo.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(modelo, f, ensure_ascii=False, indent=1)
print(f"{out}: {len(pontos)} pontos, {len(trechos)} trechos, {len(nos)} nós")
