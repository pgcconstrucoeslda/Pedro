#!/usr/bin/env python3
"""Etapa 2 — confirma a escala da ARQ: texto de cota × comprimento vetorial da linha de cota.

Uso:  python3 -I escala_arq.py <pdf> --escala 50 [--pagina 1] [--larg-max 0.4] [--raio-mm 4] [-o cotas.csv]

Para cada texto numérico (ex.: "3,45", "345", "3.45"), procura o segmento fino mais próximo e paralelo ao
texto (linha de cota), mede-o à escala nominal e compara. Interpreta o valor como metros (com vírgula/ponto)
ou centímetros (inteiro >= 10). Relata quantas cotas conferem a ±1 %.
"""
import argparse
import csv
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf as fitz  # noqa: E402
import vetor  # noqa: E402

RX = re.compile(r"^\s*(\d{1,3}(?:[.,]\d{1,3})?)\s*$")


def valor_m(txt):
    m = RX.match(txt)
    if not m:
        return None
    s = m.group(1)
    if "," in s or "." in s:
        return float(s.replace(",", "."))
    v = int(s)
    return v / 100.0 if v >= 10 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--escala", type=float, required=True, help="denominador nominal (50 para 1:50)")
    ap.add_argument("--pagina", type=int, default=1)
    ap.add_argument("--larg-max", type=float, default=0.4, help="espessura máx. da linha de cota (pt)")
    ap.add_argument("--raio-mm", type=float, default=4.0, help="distância máx. texto–linha (mm no papel)")
    ap.add_argument("-o", "--saida")
    a = ap.parse_args()
    pg = fitz.open(a.pdf)[a.pagina - 1]
    k = vetor.k_m_por_pt(a.escala)
    raio = a.raio_mm / vetor.PT_MM
    segs = [s for s in vetor.segmentos(pg, curvas=False) if s["larg"] <= a.larg_max and vetor.comprimento(s) > 3]
    res = []
    for t in vetor.textos(pg):
        v = valor_m(t["texto"])
        if v is None or v <= 0:
            continue
        ang = math.radians(t["ang"])
        tx, ty = math.cos(ang), -math.sin(ang)
        melhor = None
        for s in segs:
            ux, uy, L = vetor._dir(s)
            if abs(ux * tx + uy * ty) < math.cos(math.radians(3)):
                continue
            mx, my = (s["p0"][0] + s["p1"][0]) / 2, (s["p0"][1] + s["p1"][1]) / 2
            d = math.hypot(mx - t["x"], my - t["y"])
            # perpendicular texto→linha
            perp = abs((t["x"] - s["p0"][0]) * (-uy) + (t["y"] - s["p0"][1]) * ux)
            along = abs((t["x"] - mx) * ux + (t["y"] - my) * uy)
            if perp > raio or along > L / 2:
                continue
            if melhor is None or perp < melhor[0]:
                melhor = (perp, L)
        if melhor:
            med = melhor[1] * k
            erro = (med - v) / v
            res.append({"texto": t["texto"], "valor_m": v, "medido_m": round(med, 4), "erro_pct": round(erro * 100, 2),
                        "confere_1pct": abs(erro) <= 0.01, "x_pt": round(t["x"], 1), "y_pt": round(t["y"], 1)})
    n = len(res)
    ok = sum(1 for r in res if r["confere_1pct"])
    print(f"Cotas analisadas: {n} | conferem a ±1 %: {ok} ({(ok / n * 100 if n else 0):.0f} %)")
    erradas = [r for r in res if not r["confere_1pct"]]
    if erradas:
        print("Não conferem (rever: texto alterado à mão, cota de outro objeto, ou escala diferente):")
        for r in erradas[:30]:
            print(f"  {r['texto']:>8}  medido {r['medido_m']:.3f} m  erro {r['erro_pct']:+.2f} %  em ({r['x_pt']}, {r['y_pt']})")
    if n and ok / n < 0.8:
        razoes = sorted(r["medido_m"] / r["valor_m"] for r in res)
        print(f"ATENÇÃO: menos de 80 % conferem. Razão mediana medido/texto = {razoes[len(razoes)//2]:.4f} "
              f"(escala provável 1:{a.escala / razoes[len(razoes)//2]:.0f})")
    if a.saida:
        with open(a.saida, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(res[0].keys()) if res else ["texto"], delimiter=";")
            w.writeheader()
            w.writerows(res)


if __name__ == "__main__":
    main()
