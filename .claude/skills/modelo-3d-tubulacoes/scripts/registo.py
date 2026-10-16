#!/usr/bin/env python3
"""Etapa 2 — regista uma planta de instalações sobre a planta de arquitetura do mesmo pavimento.

Uso:
  python3 -I registo.py --arq ARQ-02.pdf --arq-pag 1 --arq-transf arq_T.json \
                        --inst HID-02.pdf --inst-pag 1 --inst-escala 50 \
                        [--roi-arq x0,y0,x1,y1] [--roi-inst x0,y0,x1,y1] [--ppm 40] -o saida/HID-02

arq_T.json = transformação da ARQ (origem escolhida na Etapa 2): {"escala_den":50,"ox_pt":..,"oy_pt":..,"rot":0}

Método (modo vetor, padrão): paredes da ARQ (traços com espessura >= --arq-larg-min) × base de arquitetura da folha de
instalações (traços finos <= --inst-larg-max, sem textos nem tubos grossos), ambas desenhadas ao MESMO nº de píxeis por
metro do modelo (escala nominal de cada folha); translação por correlação cruzada linear (rotação 0, escala nominal).
Modo raster: página inteira binarizada (folhas digitalizadas). Testa também escala ±2 % e rotação ±1° só para DETETAR divergência (não a aplica).
Saída: <saida>_transf.json (transformação da folha de instalações), <saida>_sobreposicao.png, relatório no ecrã.
ROI (em pontos PDF) serve para excluir carimbo, legenda e quadros que não existem na outra folha.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2  # noqa: E402
import pymupdf as fitz  # noqa: E402
import numpy as np  # noqa: E402
import vetor  # noqa: E402


def raster(pdf, pag, escala_den, ppm, roi=None):
    """Modo raster (folhas digitalizadas): página inteira binarizada."""
    pg = fitz.open(pdf)[pag - 1]
    zoom = ppm * vetor.k_m_por_pt(escala_den)  # píxeis por ponto PDF
    clip = fitz.Rect(*roi) if roi else pg.rect
    pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w)
    mask = (img < 200).astype(np.float32)
    return mask, zoom, (clip.x0, clip.y0)


def raster_vetor(pdf, pag, escala_den, ppm, roi=None, larg_min=0.0, larg_max=1e9, cor=None, tol=0.12):
    """Modo vetorial: desenha só os traços selecionados (ex.: paredes da ARQ pela espessura;
    base de arquitetura da folha de instalações pela cor/espessura). Ignora textos."""
    pg = fitz.open(pdf)[pag - 1]
    zoom = ppm * vetor.k_m_por_pt(escala_den)
    clip = fitz.Rect(*roi) if roi else pg.rect
    h, w = int(clip.height * zoom) + 1, int(clip.width * zoom) + 1
    mask = np.zeros((h, w), np.uint8)
    segs = vetor.filtrar(vetor.segmentos(pg, curvas=False), cor, tol, larg_min, larg_max)
    for s_ in segs:
        (x0, y0), (x1, y1) = s_["p0"], s_["p1"]
        if not (clip.contains(fitz.Point(x0, y0)) or clip.contains(fitz.Point(x1, y1))):
            continue
        p0 = (int(round((x0 - clip.x0) * zoom)), int(round((y0 - clip.y0) * zoom)))
        p1 = (int(round((x1 - clip.x0) * zoom)), int(round((y1 - clip.y0) * zoom)))
        cv2.line(mask, p0, p1, 1, 1)
    return mask.astype(np.float32), zoom, (clip.x0, clip.y0), len(segs)


def correl_linear(A, I):
    """Correlação cruzada LINEAR (FFT com zero-padding, sem dobras). Devolve (dx, dy, pico_rel):
    o traço que está em (u, v) na imagem A está em (u + dx, v + dy) na imagem I."""
    H, W = A.shape[0] + I.shape[0], A.shape[1] + I.shape[1]
    FA = np.fft.rfft2(A, (H, W))
    FI = np.fft.rfft2(I, (H, W))
    c = np.fft.irfft2(np.conj(FA) * FI, (H, W))
    iy, ix = np.unravel_index(np.argmax(c), c.shape)
    dy = iy if iy < H // 2 else iy - H
    dx = ix if ix < W // 2 else ix - W
    # refinamento sub-píxel (parábola)
    def sub(cm, c0, cp):
        d = cm - 2 * c0 + cp
        return 0.0 if d == 0 else 0.5 * (cm - cp) / d
    fy = sub(c[(iy - 1) % H, ix], c[iy, ix], c[(iy + 1) % H, ix])
    fx = sub(c[iy, (ix - 1) % W], c[iy, ix], c[iy, (ix + 1) % W])
    norm = math.sqrt(float((A * A).sum()) * float((I * I).sum())) or 1.0
    return dx + fx, dy + fy, float(c[iy, ix]) / norm


def pad(a, h, w):
    out = np.zeros((h, w), np.float32)
    out[:a.shape[0], :a.shape[1]] = a
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arq", required=True)
    ap.add_argument("--arq-pag", type=int, default=1)
    ap.add_argument("--arq-transf", required=True)
    ap.add_argument("--inst", required=True)
    ap.add_argument("--inst-pag", type=int, default=1)
    ap.add_argument("--inst-escala", type=float, required=True)
    ap.add_argument("--roi-arq")
    ap.add_argument("--roi-inst")
    ap.add_argument("--ppm", type=float, default=100.0, help="píxeis por metro do modelo")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--modo", choices=["vetor", "raster"], default="vetor")
    ap.add_argument("--arq-larg-min", type=float, default=0.45, help="espessura mín. (pt) das linhas de parede da ARQ")
    ap.add_argument("--arq-cor", help="cor das paredes da ARQ (#rrggbb), opcional")
    ap.add_argument("--inst-larg-max", type=float, default=0.45, help="espessura máx. (pt) da base de arquitetura na folha de instalações")
    ap.add_argument("--inst-cor", help="cor da base de arquitetura na folha de instalações (#rrggbb), opcional")
    a = ap.parse_args()
    Ta = json.load(open(a.arq_transf))
    roi_a = [float(v) for v in a.roi_arq.split(",")] if a.roi_arq else None
    roi_i = [float(v) for v in a.roi_inst.split(",")] if a.roi_inst else None
    if a.modo == "vetor":
        A, za, offa, na = raster_vetor(a.arq, a.arq_pag, Ta["escala_den"], a.ppm, roi_a, larg_min=a.arq_larg_min, cor=a.arq_cor)
        I, zi, offi, ni = raster_vetor(a.inst, a.inst_pag, a.inst_escala, a.ppm, roi_i, larg_max=a.inst_larg_max, cor=a.inst_cor)
        print(f"Traços usados: ARQ {na} | instalações {ni}")
        if na < 10 or ni < 10:
            print("ATENÇÃO: poucos traços selecionados — ajustar --arq-larg-min/--inst-larg-max/--*-cor (ver `vetor.py cores`) ou usar --modo raster")
    else:
        A, za, offa = raster(a.arq, a.arq_pag, Ta["escala_den"], a.ppm, roi_a)
        I, zi, offi = raster(a.inst, a.inst_pag, a.inst_escala, a.ppm, roi_i)
    h, w = max(A.shape[0], I.shape[0]), max(A.shape[1], I.shape[1])
    A2, I2 = pad(A, h, w), pad(I, h, w)
    Ab, Ib = cv2.GaussianBlur(A2, (0, 0), 1.5), cv2.GaussianBlur(I2, (0, 0), 1.5)
    dx, dy, resp = correl_linear(Ab, Ib)
    # deteção de divergência de escala/rotação (não aplicada)
    melhor = (resp, 1.0, 0.0)
    for s_ in (0.98, 0.99, 1.0, 1.01, 1.02):
        for r in (-1.0, -0.5, 0.0, 0.5, 1.0):
            if s_ == 1.0 and r == 0.0:
                continue
            M = cv2.getRotationMatrix2D((w / 2, h / 2), r, s_)
            _, _, rr = correl_linear(Ab, cv2.warpAffine(Ib, M, (w, h)))
            if rr > melhor[0] * 1.15:
                melhor = (rr, s_, r)
    # resíduo: distância dos traços da instalação (deslocados) aos traços da ARQ
    Ms = np.array([[1, 0, -dx], [0, 1, -dy]], np.float32)
    Ialin = cv2.warpAffine(I2, Ms, (w, h))
    dt = cv2.distanceTransform((A2 < 0.5).astype(np.uint8), cv2.DIST_L2, 3)
    sel = Ialin > 0.5
    resid = float(np.median(dt[sel])) if sel.any() else float("nan")
    # transformação da folha de instalações
    ka, ki = vetor.k_m_por_pt(Ta["escala_den"]), vetor.k_m_por_pt(a.inst_escala)
    # pixel u da ARQ ↔ pt_a = offa + u/za ; X = (pt_a - ox_a)·ka. Na instalação o mesmo X está em u+dx.
    ox_i = offi[0] + ((Ta["ox_pt"] - offa[0]) * za + dx) / zi
    oy_i = offi[1] + ((Ta["oy_pt"] - offa[1]) * za + dy) / zi
    Ti = {"escala_den": a.inst_escala, "ox_pt": round(ox_i, 3), "oy_pt": round(oy_i, 3), "rot": 0,
          "registo": {"dx_px": round(dx, 2), "dy_px": round(dy, 2), "resposta": round(float(resp), 4),
                      "residuo_px": round(resid, 2), "residuo_mm_modelo": round(resid / a.ppm * 1000, 1),
                      "ppm": a.ppm, "melhor_escala": melhor[1], "melhor_rot": melhor[2]}}
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    json.dump(Ti, open(a.saida + "_transf.json", "w"), indent=1)
    # sobreposição: ARQ a cinzento, instalação a magenta
    over = np.full((h, w, 3), 255, np.uint8)
    over[A2 > 0.5] = (150, 150, 150)
    over[Ialin > 0.5] = (200, 0, 200)
    over[(A2 > 0.5) & (Ialin > 0.5)] = (40, 40, 40)
    cv2.imwrite(a.saida + "_sobreposicao.png", over)
    print(f"Translação: dx={dx:.2f} px, dy={dy:.2f} px (ppm={a.ppm}) | resposta {resp:.3f}")
    print(f"Origem do modelo na folha de instalações: ({ox_i:.2f}, {oy_i:.2f}) pt")
    print(f"Resíduo mediano: {resid:.2f} px = {resid / a.ppm * 1000:.0f} mm no modelo")
    if melhor[1] != 1.0 or melhor[2] != 0.0:
        print(f"DIVERGÊNCIA: correlação melhora com escala {melhor[1]} e rotação {melhor[2]}° → registar e rever a folha")
    if resid / a.ppm > 0.05:
        print("ATENÇÃO: resíduo > 5 cm — rever ROI, escala ou se a base de arquitetura da folha é a mesma revisão")
    print(f"→ {a.saida}_transf.json e {a.saida}_sobreposicao.png (OLHAR para a imagem)")


if __name__ == "__main__":
    main()
