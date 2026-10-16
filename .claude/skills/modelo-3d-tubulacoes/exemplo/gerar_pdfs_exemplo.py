#!/usr/bin/env python3
"""Gera PDFs vetoriais fictícios (ARQ e HID do térreo, 1:50) a partir de modelo_exemplo.json,
com a origem do modelo em posições DIFERENTES nas duas folhas — para testar inventario.py,
escala_arq.py, registo.py, vetor.py e sobreposicao.py.

Uso: python3 -I gerar_pdfs_exemplo.py <pasta_saida>
"""
import json
import math
import os
import sys

import pymupdf as fitz

AQUI = os.path.dirname(os.path.abspath(__file__))
K = 25.4 / 72 / 1000 * 50  # m por pt a 1:50


def P(X, Y, O):
    return fitz.Point(O[0] + X / K, O[1] - Y / K)


def faces(w):
    dx, dy = w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * w["esp"] / 2, dx / L * w["esp"] / 2
    return [((w["a"][0] + nx, w["a"][1] + ny), (w["b"][0] + nx, w["b"][1] + ny)),
            ((w["a"][0] - nx, w["a"][1] - ny), (w["b"][0] - nx, w["b"][1] - ny))]


def carimbo(pg, linhas):
    r = fitz.Rect(900, 700, 1170, 820)
    pg.draw_rect(r, color=(0, 0, 0), width=0.8)
    for i, t in enumerate(linhas):
        pg.insert_text((908, 718 + i * 14), t, fontsize=9)


def main():
    out = sys.argv[1]
    m = json.load(open(os.path.join(AQUI, "modelo_exemplo.json"), encoding="utf-8"))
    nos = {n["id"]: n for n in m["nos"]}
    paredes = [w for w in m["paredes"] if w["pav"] == "T" and w["tipo"] == "parede"]

    # ---------------- ARQ (origem em 150, 700)
    OA = (150.0, 700.0)
    os.makedirs(os.path.join(out, "Arquitetura"), exist_ok=True)
    doc = fitz.open()
    pg = doc.new_page(width=1190, height=842)
    for w in paredes:
        for a, b in faces(w):
            pg.draw_line(P(*a, OA), P(*b, OA), color=(0, 0, 0), width=0.6)
    cotas = [((0, -1.2), (10, -1.2), "10,00"), ((0, -1.8), (5, -1.8), "5,00"), ((5, -1.8), (10, -1.8), "5,00"),
             ((10, -2.4), (7.5, -2.4), "2,60")]  # a última está ERRADA de propósito (2,50 no desenho)
    for a, b, t in cotas:
        pa, pb = P(*a, OA), P(*b, OA)
        pg.draw_line(pa, pb, color=(0, 0, 0), width=0.2)
        mid = fitz.Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2)
        pg.insert_text((mid.x - 10, mid.y - 3), t, fontsize=7)
    # cotas verticais (texto rodado 90°)
    for a, b, t in [((-1.2, 0), (-1.2, 8), "8,00"), ((10.8, 0), (10.8, 4), "4,00")]:
        pa, pb = P(*a, OA), P(*b, OA)
        pg.draw_line(pa, pb, color=(0, 0, 0), width=0.2)
        mid = fitz.Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2)
        pg.insert_text((mid.x - 3, mid.y + 8), t, fontsize=7, rotate=90)
    for amb in m["ambientes"]:
        if amb["pav"] == "T":
            p = P(*amb["pos"], OA)
            pg.insert_text((p.x - 15, p.y), amb["nome"], fontsize=8)
    carimbo(pg, ["EX-ARQ 02 - Planta do Térreo", "Arquitetura", "Esc. 1:50", "Rev. R02", "Data 01/02/2026"])
    doc.save(os.path.join(out, "Arquitetura", "EX-ARQ-02.pdf"))

    # ---------------- HID (origem em 185, 690: deslocada 35 pt e -10 pt)
    OH = (185.0, 690.0)
    os.makedirs(os.path.join(out, "IHSD"), exist_ok=True)
    doc = fitz.open()
    pg = doc.new_page(width=1190, height=842)
    for w in paredes:
        for a, b in faces(w):
            pg.draw_line(P(*a, OH), P(*b, OH), color=(0.55, 0.55, 0.55), width=0.3)
    azul = (0x1e / 255, 0x88 / 255, 0xe5 / 255)
    for t in m["trechos"]:
        if t["sistema"] != "HID-AF" or t["pav"] != "T":
            continue
        for n0, n1 in zip(t["nos"][:-1], t["nos"][1:]):
            a, b = nos[n0], nos[n1]
            if math.hypot(b["x"] - a["x"], b["y"] - a["y"]) < 0.01:
                continue  # trecho vertical: na planta é só um símbolo
            pg.draw_line(P(a["x"], a["y"], OH), P(b["x"], b["y"], OH), color=azul, width=1.4)
    for p in m["pontos"]:
        if p["sistema"] == "HID-AF" and p["pav"] == "T":
            c = P(p["x"], p["y"], OH)
            pg.draw_circle(c, 2.5, color=azul, width=0.8)
            pg.insert_text((c.x + 4, c.y - 3), f"Ø{p['dn']}", fontsize=6, color=azul)
    carimbo(pg, ["EX-HID 02 - Água fria - Planta do Térreo", "Instalações hidráulicas", "Esc. 1:50", "Rev. R01", "Data 10/03/2026"])
    pg.insert_text((60, 60), "LEGENDA: ——— Água fria (AF)   o Ponto de consumo", fontsize=8)
    doc.save(os.path.join(out, "IHSD", "EX-HID-02.pdf"))
    json.dump({"escala_den": 50, "ox_pt": OA[0], "oy_pt": OA[1], "rot": 0}, open(os.path.join(out, "arq_T_transf.json"), "w"))
    print("PDFs de exemplo em", out, "| origem real HID:", OH)


if __name__ == "__main__":
    main()
