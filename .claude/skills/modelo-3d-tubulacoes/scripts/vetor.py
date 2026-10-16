#!/usr/bin/env python3
"""Leitura vetorial de pranchas PDF (pymupdf) e conversão para coordenadas do modelo.

Uso como biblioteca (sys.path.insert(0, <scripts>); import vetor) ou CLI:
  python3 -I vetor.py cores <pdf> [--pagina 1]          # cores/espessuras com comprimento total (identificar tubos e paredes)
  python3 -I vetor.py textos <pdf> [--pagina 1] [--filtro "Ø|DN|AF|TQ"]
  python3 -I vetor.py extrair <pdf> --cor "#1e88e5" [--tol 0.08] [--larg-min 0] [--larg-max 9] --transf transf.json

Transformação de folha (`transf`): {"escala_den": 50, "ox_pt": 150.0, "oy_pt": 700.0, "rot": 0}
  ox_pt/oy_pt = posição, em pontos PDF, da origem (0,0) do modelo nessa folha (obtida na Etapa 2 / registo.py).
  X = (x_pt - ox_pt)·k ; Y = -(y_pt - oy_pt)·k ; k = 25,4/72/1000·escala_den  (metros por ponto PDF)
"""
import argparse
import json
import math
import sys

import pymupdf as fitz

PT_MM = 25.4 / 72.0


# ---------------------------------------------------------------- transformações
def k_m_por_pt(escala_den):
    return PT_MM / 1000.0 * escala_den


def pdf_para_modelo(x, y, T):
    k = k_m_por_pt(T["escala_den"])
    X, Y = (x - T["ox_pt"]) * k, -(y - T["oy_pt"]) * k
    r = math.radians(T.get("rot", 0) or 0)
    if r:
        X, Y = X * math.cos(r) - Y * math.sin(r), X * math.sin(r) + Y * math.cos(r)
    return round(X, 3), round(Y, 3)


def modelo_para_pdf(X, Y, T):
    r = math.radians(T.get("rot", 0) or 0)
    if r:
        X, Y = X * math.cos(-r) - Y * math.sin(-r), X * math.sin(-r) + Y * math.cos(-r)
    k = k_m_por_pt(T["escala_den"])
    return X / k + T["ox_pt"], -Y / k + T["oy_pt"]


# ---------------------------------------------------------------- cores
def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_hex(c):
    if c is None:
        return None
    return "#" + "".join(f"{int(round(v * 255)):02x}" for v in c[:3])


def dist_cor(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


# ---------------------------------------------------------------- desenhos
def segmentos(page, curvas=True):
    """Todos os traços como segmentos: {p0, p1, cor, larg, preench, tipo, dashes}."""
    out = []
    for d in page.get_drawings():
        cor = d.get("color")
        larg = d.get("width") or 0.0
        fill = d.get("fill")
        dashes = d.get("dashes")
        for it in d["items"]:
            op = it[0]
            if op == "l":
                out.append({"p0": (it[1].x, it[1].y), "p1": (it[2].x, it[2].y), "cor": cor, "larg": larg, "preench": fill, "tipo": "l", "dashes": dashes})
            elif op == "re":
                r = it[1]
                pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                for i in range(4):
                    out.append({"p0": pts[i], "p1": pts[(i + 1) % 4], "cor": cor, "larg": larg, "preench": fill, "tipo": "re", "dashes": dashes})
            elif op == "qu":
                q = it[1]
                pts = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
                for i in range(4):
                    out.append({"p0": pts[i], "p1": pts[(i + 1) % 4], "cor": cor, "larg": larg, "preench": fill, "tipo": "qu", "dashes": dashes})
            elif op == "c" and curvas:
                out.append({"p0": (it[1].x, it[1].y), "p1": (it[4].x, it[4].y), "cor": cor, "larg": larg, "preench": fill, "tipo": "c", "dashes": dashes})
    return out


def comprimento(s):
    return math.hypot(s["p1"][0] - s["p0"][0], s["p1"][1] - s["p0"][1])


def tabela_cores(segs):
    agg = {}
    for s in segs:
        k = (rgb_hex(s["cor"]), round(s["larg"], 2), bool(s["dashes"] and s["dashes"] not in ("[] 0",)))
        a = agg.setdefault(k, [0, 0.0])
        a[0] += 1
        a[1] += comprimento(s)
    return sorted(([*k, v[0], v[1]] for k, v in agg.items()), key=lambda r: -r[4])


def filtrar(segs, cor=None, tol=0.08, larg_min=0.0, larg_max=1e9, min_comp=0.0):
    c = hex_rgb(cor) if isinstance(cor, str) else cor
    out = []
    for s in segs:
        if s["cor"] is None:
            continue
        if c is not None and dist_cor(s["cor"], c) > tol:
            continue
        if not (larg_min <= s["larg"] <= larg_max):
            continue
        if comprimento(s) < min_comp:
            continue
        out.append(s)
    return out


# ---------------------------------------------------------------- geometria de segmentos
def _dir(s):
    dx, dy = s["p1"][0] - s["p0"][0], s["p1"][1] - s["p0"][1]
    L = math.hypot(dx, dy) or 1e-12
    return dx / L, dy / L, L


def pares_paralelos(segs, esp_min, esp_max, ang_tol=2.0, sobrep_min=0.5):
    """Agrupa pares de linhas paralelas (contorno duplo de parede ou de tubo) em eixo + espessura.
    esp_min/esp_max em pontos PDF. Devolve [{a, b, esp_pt, i, j}] (a, b = extremos do eixo na zona de sobreposição)."""
    out, usados = [], set()
    cos_tol = math.cos(math.radians(ang_tol))
    info = [(_dir(s), s) for s in segs]
    for i, ((ux, uy, Li), si) in enumerate(info):
        if i in usados or Li < 1e-6:
            continue
        melhor = None
        for j in range(i + 1, len(info)):
            if j in usados:
                continue
            (vx, vy, Lj), sj = info[j]
            if abs(ux * vx + uy * vy) < cos_tol:
                continue
            # distância perpendicular de sj à linha de si
            nx, ny = -uy, ux
            d0 = (sj["p0"][0] - si["p0"][0]) * nx + (sj["p0"][1] - si["p0"][1]) * ny
            d1 = (sj["p1"][0] - si["p0"][0]) * nx + (sj["p1"][1] - si["p0"][1]) * ny
            if abs(d0 - d1) > esp_max * 0.1:
                continue
            d = (d0 + d1) / 2
            if not (esp_min <= abs(d) <= esp_max):
                continue
            # sobreposição ao longo do eixo
            t0 = 0.0
            ta = (sj["p0"][0] - si["p0"][0]) * ux + (sj["p0"][1] - si["p0"][1]) * uy
            tb = (sj["p1"][0] - si["p0"][0]) * ux + (sj["p1"][1] - si["p0"][1]) * uy
            lo, hi = max(t0, min(ta, tb)), min(Li, max(ta, tb))
            if hi - lo < sobrep_min * min(Li, Lj):
                continue
            if melhor is None or abs(d) < abs(melhor[1]):
                melhor = (j, d, lo, hi)
        if melhor:
            j, d, lo, hi = melhor
            usados.update((i, j))
            nx, ny = -uy, ux
            a = (si["p0"][0] + ux * lo + nx * d / 2, si["p0"][1] + uy * lo + ny * d / 2)
            b = (si["p0"][0] + ux * hi + nx * d / 2, si["p0"][1] + uy * hi + ny * d / 2)
            out.append({"a": a, "b": b, "esp_pt": abs(d), "i": i, "j": j})
    return out


def unir_colineares(linhas, ang_tol=1.5, dist_tol=0.8, gap_max=2.0):
    """Une segmentos {a, b, ...} colineares e contíguos (tolerâncias em pontos PDF)."""
    ls = [dict(l) for l in linhas]
    mudou = True
    cos_tol = math.cos(math.radians(ang_tol))
    while mudou:
        mudou = False
        for i in range(len(ls)):
            if ls[i] is None:
                continue
            a = ls[i]
            ux, uy = a["b"][0] - a["a"][0], a["b"][1] - a["a"][1]
            La = math.hypot(ux, uy) or 1e-12
            ux, uy = ux / La, uy / La
            for j in range(i + 1, len(ls)):
                b = ls[j]
                if b is None:
                    continue
                vx, vy = b["b"][0] - b["a"][0], b["b"][1] - b["a"][1]
                Lb = math.hypot(vx, vy) or 1e-12
                if abs((ux * vx + uy * vy) / Lb) < cos_tol:
                    continue
                if abs(b.get("esp_pt", 0) - a.get("esp_pt", 0)) > dist_tol:
                    continue
                nx, ny = -uy, ux
                if max(abs((b["a"][0] - a["a"][0]) * nx + (b["a"][1] - a["a"][1]) * ny),
                       abs((b["b"][0] - a["a"][0]) * nx + (b["b"][1] - a["a"][1]) * ny)) > dist_tol:
                    continue
                ts = [0, La, (b["a"][0] - a["a"][0]) * ux + (b["a"][1] - a["a"][1]) * uy, (b["b"][0] - a["a"][0]) * ux + (b["b"][1] - a["a"][1]) * uy]
                tb0, tb1 = sorted(ts[2:])
                if tb0 > La + gap_max or tb1 < -gap_max:
                    continue
                lo, hi = min(ts), max(ts)
                a["a"] = (a["a"][0] + ux * lo, a["a"][1] + uy * lo)
                a["b"] = (a["a"][0] + ux * (hi - lo), a["a"][1] + uy * (hi - lo))
                ls[j] = None
                mudou = True
                break
            if mudou:
                break
    return [l for l in ls if l is not None]


def vaos(linhas, larg_min_pt, larg_max_pt, ang_tol=1.5, dist_tol=0.8):
    """Intervalos entre segmentos colineares (candidatos a vãos de portas/janelas). Devolve [{centro, largura_pt, i, j}]."""
    out = []
    cos_tol = math.cos(math.radians(ang_tol))
    for i, a in enumerate(linhas):
        ux, uy = a["b"][0] - a["a"][0], a["b"][1] - a["a"][1]
        La = math.hypot(ux, uy) or 1e-12
        ux, uy = ux / La, uy / La
        for j, b in enumerate(linhas):
            if j <= i:
                continue
            vx, vy = b["b"][0] - b["a"][0], b["b"][1] - b["a"][1]
            Lb = math.hypot(vx, vy) or 1e-12
            if abs((ux * vx + uy * vy) / Lb) < cos_tol:
                continue
            nx, ny = -uy, ux
            if abs((b["a"][0] - a["a"][0]) * nx + (b["a"][1] - a["a"][1]) * ny) > dist_tol:
                continue
            tb = sorted([(b["a"][0] - a["a"][0]) * ux + (b["a"][1] - a["a"][1]) * uy, (b["b"][0] - a["a"][0]) * ux + (b["b"][1] - a["a"][1]) * uy])
            if tb[0] > La:
                g0, g1 = La, tb[0]
            elif tb[1] < 0:
                g0, g1 = tb[1], 0
            else:
                continue
            w = g1 - g0
            if larg_min_pt <= w <= larg_max_pt:
                c = (a["a"][0] + ux * (g0 + g1) / 2, a["a"][1] + uy * (g0 + g1) / 2)
                out.append({"centro": c, "largura_pt": w, "i": i, "j": j})
    return out


# ---------------------------------------------------------------- textos
def textos(page, filtro=None):
    import re
    rx = re.compile(filtro, re.I) if filtro else None
    out = []
    d = page.get_text("dict")
    for b in d["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if not txt or (rx and not rx.search(txt)):
                continue
            x0, y0, x1, y1 = l["bbox"]
            ang = math.degrees(math.atan2(-l["dir"][1], l["dir"][0]))
            out.append({"texto": txt, "x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "bbox": [x0, y0, x1, y1],
                        "tam": l["spans"][0]["size"], "ang": round(ang, 1), "cor": "#%06x" % l["spans"][0].get("color", 0)})
    return out


# ---------------------------------------------------------------- raster → esqueleto
def esqueleto_cor(page, cor, tol=0.12, dpi=150, epsilon_px=1.5, min_px=8):
    """Para traços em mancha/raster: máscara da cor → esqueleto → polilinhas (em pontos PDF)."""
    import cv2
    import numpy as np
    from skimage.morphology import skeletonize
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].astype(float) / 255
    c = np.array(hex_rgb(cor) if isinstance(cor, str) else cor)
    mask = (np.sqrt(((img - c) ** 2).sum(axis=2)) <= tol).astype(np.uint8)
    sk = skeletonize(mask > 0).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(sk, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    esc = 72.0 / dpi
    out = []
    for cn in cnts:
        if cv2.arcLength(cn, False) < min_px:
            continue
        ap = cv2.approxPolyDP(cn, epsilon_px, False)
        out.append([(float(p[0][0]) * esc, float(p[0][1]) * esc) for p in ap])
    return out


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["cores", "textos", "extrair"])
    ap.add_argument("pdf")
    ap.add_argument("--pagina", type=int, default=1)
    ap.add_argument("--filtro")
    ap.add_argument("--cor")
    ap.add_argument("--tol", type=float, default=0.08)
    ap.add_argument("--larg-min", type=float, default=0.0)
    ap.add_argument("--larg-max", type=float, default=1e9)
    ap.add_argument("--transf")
    a = ap.parse_args()
    doc = fitz.open(a.pdf)
    pg = doc[a.pagina - 1]
    if a.acao == "cores":
        segs = segmentos(pg)
        print(f"{len(segs)} segmentos")
        print("cor;largura_pt;tracejado;n;comprimento_pt")
        for r in tabela_cores(segs)[:60]:
            print(f"{r[0]};{r[1]};{r[2]};{r[3]};{r[4]:.0f}")
    elif a.acao == "textos":
        for t in textos(pg, a.filtro):
            print(f"{t['x']:.1f};{t['y']:.1f};{t['ang']};{t['tam']:.1f};{t['texto']}")
    else:
        segs = filtrar(segmentos(pg), a.cor, a.tol, a.larg_min, a.larg_max)
        T = json.load(open(a.transf)) if a.transf else None
        out = []
        for s in segs:
            r = {"p0_pt": s["p0"], "p1_pt": s["p1"], "larg": s["larg"]}
            if T:
                r["p0_m"] = pdf_para_modelo(*s["p0"], T)
                r["p1_m"] = pdf_para_modelo(*s["p1"], T)
            out.append(r)
        json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
