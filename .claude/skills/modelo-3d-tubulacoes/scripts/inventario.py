#!/usr/bin/env python3
"""Etapa 1 — inventário das pranchas.

Uso:  python3 -I inventario.py <pasta_entrada> -o <pasta_saida> [--dpi 60]

Para cada página de cada PDF (recursivo): disciplina (pela pasta/nome), código, pavimento, escala,
revisão e data (heurísticas por regex — CONFIRMAR À MÃO), nº de traços vetoriais, nº de caracteres de
texto, imagens raster, formato da folha. Grava:
  inventario.csv / inventario.json   — uma linha por página
  png/<arquivo>_pN.png               — miniatura para conferência visual
  texto/<arquivo>_pN.txt             — texto extraído (legendas, notas, carimbo)
e imprime a lista do que parece faltar (ARQ: planta por pavimento, corte, quadro de esquadrias; IHSD: HID, SAN, DRE).
"""
import argparse
import csv
import json
import os
import re
import sys

import pymupdf as fitz

DISC = [("ARQ", r"arq|arquit"), ("HID", r"\bhid|hidr|agua|água|af\b"), ("SAN", r"\bsan|esgot|sanit"),
        ("DRE", r"\bdre|pluv|dren"), ("EST", r"\best|estrut"), ("ELE", r"\bele|eletr|eléctr|electr")]
PAV = [("Subsolo", r"sub-?solo|cave|semi-?enterr"), ("Térreo", r"t[ée]rreo|r/?c\b|r[ée]s[- ]do[- ]ch[ãa]o|piso 0"),
       ("Superior", r"superior|1[ºo°]\s*(andar|piso|pavimento)|piso 1|pavimento superior"),
       ("Cobertura", r"cobertura|telhado|reservat|caixa d.?[áa]gua"), ("Implantação", r"implanta|situa[çc][ãa]o|localiza")]
TIPO = [("Planta", r"planta"), ("Corte", r"\bcorte"), ("Alçado/Fachada", r"al[çc]ado|fachada"), ("Isométrico", r"isom[ée]tric|iso\b|vista isom"),
        ("Detalhe", r"detalhe|pormenor"), ("Quadro de esquadrias", r"quadro de (esquadrias|v[ãa]os)|mapa de v[ãa]os|esquadrias"),
        ("Legenda/Notas", r"legenda|notas gerais")]
FORMATOS = {"A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420), "A4": (210, 297)}


def formato(w_pt, h_pt):
    w, h = sorted((w_pt * 25.4 / 72, h_pt * 25.4 / 72))
    for k, (a, b) in FORMATOS.items():
        if abs(w - a) < 12 and abs(h - b) < 12:
            return k
    return f"{w:.0f}x{h:.0f} mm"


def achar(lista, txt):
    return [k for k, rx in lista if re.search(rx, txt, re.I)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--dpi", type=int, default=60)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.saida, "png"), exist_ok=True)
    os.makedirs(os.path.join(a.saida, "texto"), exist_ok=True)
    linhas = []
    for raiz, _, fs in os.walk(a.entrada):
        for f in sorted(fs):
            if not f.lower().endswith(".pdf"):
                continue
            cam = os.path.join(raiz, f)
            rel = os.path.relpath(cam, a.entrada)
            try:
                doc = fitz.open(cam)
            except Exception as e:
                linhas.append({"arquivo": rel, "pagina": "", "erro": str(e)})
                continue
            for i, pg in enumerate(doc):
                txt = pg.get_text()
                nd = sum(len(d["items"]) for d in pg.get_drawings())  # nº de traços (itens de desenho)
                nimg = len(pg.get_images())
                area = pg.rect.width * pg.rect.height or 1
                cob_img = sum(abs(fitz.Rect(i["bbox"]).get_area()) for i in pg.get_image_info()) / area
                base = re.sub(r"[^\w\-]+", "_", os.path.splitext(rel)[0])
                with open(os.path.join(a.saida, "texto", f"{base}_p{i+1}.txt"), "w", encoding="utf-8") as fh:
                    fh.write(txt)
                pg.get_pixmap(dpi=a.dpi).save(os.path.join(a.saida, "png", f"{base}_p{i+1}.png"))
                chave = rel + " " + txt[:4000]
                disc = achar(DISC, rel) or achar(DISC, txt[:3000])
                esc = sorted(set(re.findall(r"\b1\s*[:/]\s*(\d{2,4})\b", txt)), key=lambda x: int(x))
                rev = re.findall(r"\b(?:rev(?:is[ãa]o)?\.?|R)\s*[:\-]?\s*(\d{1,2}|[A-Z])\b", txt, re.I)
                datas = re.findall(r"\b(\d{1,2}[/.\-]\d{1,2}[/.\-](?:\d{4}|\d{2}))\b", txt)
                cod = re.findall(r"\b((?:ARQ|HID|SAN|DRE|EST|ELE|IHSD|AF|ES|AP)[\s\-_.]*\d{1,3}[A-Z]?)\b", chave, re.I)
                linhas.append({
                    "arquivo": rel, "pagina": i + 1, "disciplina": ",".join(dict.fromkeys(disc)) or "?",
                    "codigo_provavel": cod[0] if cod else "", "tipo": ",".join(achar(TIPO, chave)) or "?",
                    "pavimento": ",".join(achar(PAV, chave)) or "?", "escalas_no_texto": ";".join("1:" + e for e in esc),
                    "revisao_provavel": rev[-1] if rev else "", "datas_no_texto": ";".join(dict.fromkeys(datas)),
                    "formato": formato(pg.rect.width, pg.rect.height), "tracos_vetoriais": nd, "caracteres_texto": len(txt),
                    "imagens_raster": nimg, "cobertura_imagem_pct": round(cob_img * 100), "vetorial": nd >= 20 and cob_img < 0.5,
                    "texto_extraivel": len(txt.strip()) > 20,
                    "obs": "" if (nd >= 20 and cob_img < 0.5) else "PROVÁVEL RASTER (imagem cobre a folha ou poucos traços) — usar esqueleto_cor / registo --modo raster"})
    if not linhas:
        sys.exit("Nenhum PDF encontrado.")
    cols = list(dict.fromkeys(k for l in linhas for k in l))
    with open(os.path.join(a.saida, "inventario.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    with open(os.path.join(a.saida, "inventario.json"), "w", encoding="utf-8") as fh:
        json.dump(linhas, fh, ensure_ascii=False, indent=1)

    # o que parece faltar
    falta = []
    tem = lambda d, t=None, p=None: any(d in l.get("disciplina", "") and (t is None or t in l.get("tipo", "")) and (p is None or p in l.get("pavimento", "")) for l in linhas)
    if not tem("ARQ", "Planta"):
        falta.append("ARQ: nenhuma planta identificada")
    if not tem("ARQ", "Corte"):
        falta.append("ARQ: nenhum corte (pé-direito, níveis de laje)")
    if not tem("ARQ", "Quadro de esquadrias"):
        falta.append("ARQ: quadro de esquadrias não identificado")
    for d in ("HID", "SAN", "DRE"):
        if not tem(d):
            falta.append(f"{d}: nenhuma prancha identificada")
    if not tem("HID", "Isométrico"):
        falta.append("HID: isométricos não identificados (alturas dos pontos)")
    pav_arq = {p for l in linhas if "ARQ" in l.get("disciplina", "") for p in l.get("pavimento", "").split(",") if p and p != "?"}
    for l in linhas:
        if l.get("disciplina", "") in ("HID", "SAN") and "Planta" in l.get("tipo", ""):
            for p in l["pavimento"].split(","):
                if p not in ("?", "Implantação", "Cobertura") and p not in pav_arq:
                    falta.append(f"ARQ: planta do pavimento '{p}' (há instalações nesse pavimento)")
    print(f"{len(linhas)} páginas inventariadas → {a.saida}")
    print("Vetoriais:", sum(1 for l in linhas if l.get("vetorial")), "| Sem texto:", sum(1 for l in linhas if not l.get("texto_extraivel")))
    if falta:
        print("\nPOSSÍVEIS FALTAS (confirmar antes de avançar):")
        for f in dict.fromkeys(falta):
            print("  -", f)
    else:
        print("\nNada essencial parece faltar (confirmar à mão).")


if __name__ == "__main__":
    main()
