#!/usr/bin/env python3
"""Verificação final 7 — desenha o modelo (trechos e pontos) sobre cada planta de instalações.

Uso:  python3 -I sobreposicao.py modelo.json --pdf-dir <entrada> -o <pasta> [--dpi 110]

Usa, de cada prancha em `pranchas[]`, os campos `arquivo` (relativo a --pdf-dir), `pagina`, `pavimento`,
`disciplina` e `transf` ({escala_den, ox_pt, oy_pt, rot}). Desenha só os trechos/pontos do mesmo pavimento e
da(s) disciplina(s) da prancha: trechos a traço grosso semitransparente, pontos como losangos, IDs dos pontos.
Tudo o que está na prancha e não ficou coberto pelo desenho do modelo é o que FALTA modelar.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2  # noqa: E402
import pymupdf as fitz  # noqa: E402
import numpy as np  # noqa: E402
import vetor  # noqa: E402

DISC_SIS = {"HID": {"HID-AF"}, "SAN": {"SAN-ESG", "SAN-VENT"}, "DRE": {"DRE-PLU", "DRE-AC"}}


def bgr(h):
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modelo")
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()
    m = json.load(open(a.modelo, encoding="utf-8"))
    cores = {"HID-AF": "#1e88e5", "SAN-ESG": "#8d5a2b", "SAN-VENT": "#5f9e3a", "DRE-PLU": "#0f9b8e", "DRE-AC": "#8e44ad"}
    cores.update(m["meta"].get("cores", {}))
    nos = {n["id"]: n for n in m["nos"]}
    os.makedirs(a.saida, exist_ok=True)
    feitas = 0
    for pr in m.get("pranchas", []):
        T = pr.get("transf")
        if not T or pr.get("disciplina") not in DISC_SIS or not pr.get("arquivo"):
            continue
        cam = os.path.join(a.pdf_dir, pr["arquivo"])
        if not os.path.exists(cam):
            print("  sem ficheiro:", cam)
            continue
        pg = fitz.open(cam)[pr.get("pagina", 1) - 1]
        z = a.dpi / 72.0
        pix = pg.get_pixmap(dpi=a.dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1].copy()
        img = (img * 0.55 + 255 * 0.45).astype(np.uint8)  # prancha esbatida
        lay = img.copy()
        sis = DISC_SIS[pr["disciplina"]]
        pav = pr.get("pavimento")
        to_px = lambda X, Y: tuple(int(round(v * z)) for v in vetor.modelo_para_pdf(X, Y, T))
        nt = npnt = 0
        for t in m["trechos"]:
            if t["sistema"] not in sis or (pav and t.get("pav") != pav):
                continue
            pts = [to_px(nos[n]["x"], nos[n]["y"]) for n in t["nos"]]
            for p0, p1 in zip(pts[:-1], pts[1:]):
                cv2.line(lay, p0, p1, bgr(cores[t["sistema"]]), max(3, int(0.6 * z)), cv2.LINE_AA)
            nt += 1
        img = cv2.addWeighted(lay, 0.6, img, 0.4, 0)
        for p in m["pontos"]:
            if p["sistema"] not in sis or (pav and p.get("pav") != pav):
                continue
            x, y = to_px(p["x"], p["y"])
            r = max(4, int(2.2 * z))
            cor = (30, 84, 217) if p["status"] == "PENDENTE" else bgr(cores[p["sistema"]])
            cv2.polylines(img, [np.array([(x, y - r), (x + r, y), (x, y + r), (x - r, y)])], True, cor, 2, cv2.LINE_AA)
            cv2.putText(img, p["id"], (x + r + 2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.32 * z / 1.5, (20, 20, 20), 1, cv2.LINE_AA)
            npnt += 1
        nome = os.path.join(a.saida, f"sobreposicao_{pr['codigo'].replace(' ', '_')}.png")
        cv2.imwrite(nome, img)
        feitas += 1
        print(f"  {pr['codigo']}: {nt} trechos, {npnt} pontos → {nome}")
    print(f"{feitas} sobreposições geradas. OLHAR para cada uma: traço da prancha sem cor por cima = não modelado.")


if __name__ == "__main__":
    main()
