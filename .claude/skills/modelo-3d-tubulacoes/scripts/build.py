#!/usr/bin/env python3
"""Gera modelo_3d_tubulacoes.html (template + JSON embutido) e os CSV.

Uso:  python3 -I build.py modelo.json -o <pasta_saida> [--proibir "termo1,termo2"]

--proibir: termos (cidade, país, localidade, nome da pasta do cliente) que NÃO podem aparecer
em nenhum entregável. Se aparecerem, o build falha.
CSV: separador ';', vírgula decimal, UTF-8 com BOM (abre direto no Excel em português).
"""
import argparse
import csv
import io
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def num(v, casas=3):
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        return f"{v:.{casas}f}".replace(".", ",")
    return str(v)


def csv_texto(cab, linhas):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(cab)
    for l in linhas:
        w.writerow(l)
    return "﻿" + buf.getvalue()


def gerar_csvs(m):
    loc = m.get("locacao", {})
    pts = []
    for p in m.get("pontos", []):
        l = loc.get(p["id"], {})
        A, B, V = l.get("A") or {}, l.get("B") or {}, l.get("V") or {}
        pts.append([p["id"], p.get("tipo", ""), p["sistema"], p.get("dn", ""), num(p["x"]), num(p["y"]), num(p["z"]),
                    num(p.get("h")), p.get("pav", ""), p.get("ambiente", ""), p.get("prancha", ""), p["status"],
                    p.get("motivo", ""), p.get("memoria", ""), A.get("parede", ""), num(A.get("dist")),
                    B.get("parede", ""), num(B.get("dist")) if B.get("tipo") != "embutido" else "embutido",
                    num(V.get("valor")), V.get("tipo", "")])
    pontos = csv_texto(["id", "tipo", "sistema", "dn_mm", "x", "y", "z", "h_piso", "pavimento", "ambiente", "prancha",
                        "status", "motivo", "memoria", "cota_A_parede", "cota_A_m", "cota_B_parede", "cota_B_m",
                        "vertical_m", "vertical_tipo"], pts)
    tr = []
    for t in m.get("trechos", []):
        ent = sum(((s["b"][0] - s["a"][0]) ** 2 + (s["b"][1] - s["a"][1]) ** 2 + (s["b"][2] - s["a"][2]) ** 2) ** 0.5
                  for s in t.get("segmentos", []) if s.get("enterrado"))
        tr.append([t["id"], t["sistema"], t.get("dn", ""), t.get("pav", ""), " > ".join(t["nos"]), num(t.get("comprimento")),
                   num(t["declividade"] * 100, 2) if t.get("declividade") is not None else "", num(ent),
                   t.get("embutido", ""), t["status"], t.get("prancha", ""), t.get("motivo", ""), t.get("memoria", "")])
    trechos = csv_texto(["id", "sistema", "dn_mm", "pavimento", "nos", "comprimento_m", "declividade_pct", "enterrado_m",
                         "passagem", "status", "prancha", "motivo", "memoria"], tr)
    dv = []
    for d in m.get("divergencias", []):
        pos = d.get("pos") or [None, None, None]
        dv.append([d["id"], d.get("tipo", ""), d.get("gravidade", ""), ", ".join(d.get("disciplinas", [])),
                   d.get("descricao", ""), ", ".join(d.get("pranchas", [])), num(pos[0]), num(pos[1]), num(pos[2]),
                   ", ".join(d.get("ids", []))])
    divs = csv_texto(["id", "tipo", "gravidade", "disciplinas", "descricao", "pranchas", "x", "y", "z", "ids"], dv)
    nv = []
    for p in m.get("pavimentos", []):
        for k in ("z_piso", "z_forro", "z_laje_fundo", "z_laje_topo"):
            if p.get(k) is not None:
                nv.append([p["id"], "(pavimento)", k.replace("z_", ""), num(p[k]), "EXTRAIDO", p.get("fonte", "")])
    for n in m.get("niveis", []):
        nv.append([n.get("pav", ""), n.get("ambiente", ""), n.get("tipo", ""), num(n.get("z")), n.get("status", ""), n.get("fonte", "")])
    niveis = csv_texto(["pavimento", "ambiente", "tipo", "z", "status", "fonte"], nv)
    return {"pontos.csv": pontos, "trechos.csv": trechos, "divergencias.csv": divs, "niveis.csv": niveis}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modelo")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--template", default=os.path.join(AQUI, "template.html"))
    ap.add_argument("--proibir", default="")
    a = ap.parse_args()
    with open(a.modelo, encoding="utf-8") as f:
        m = json.load(f)
    if not m.get("verificacoes"):
        print("AVISO: modelo sem 'verificacoes' — correr verificar_modelo.py antes do build.", file=sys.stderr)
    with open(a.template, encoding="utf-8") as f:
        tpl = f.read()
    js = json.dumps(m, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    titulo = f"{m['meta'].get('projeto', 'Projeto')} · Tubulações 3D"
    csvs = gerar_csvs(m)
    js_csv = json.dumps(csvs, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if "/*__MODEL_JSON__*/{}" not in tpl or "/*__CSVS_JSON__*/{}" not in tpl:
        sys.exit("Marcadores do JSON não encontrados no template")
    html = (tpl.replace("/*__MODEL_JSON__*/{}", js).replace("/*__CSVS_JSON__*/{}", js_csv)
               .replace("__TITLE__", titulo.replace("<", "&lt;")))
    saidas = {"modelo_3d_tubulacoes.html": html}
    saidas.update(csvs)
    termos = [t.strip().lower() for t in a.proibir.split(",") if t.strip()]
    achados = [(nome, t) for nome, txt in saidas.items() for t in termos if t in txt.lower()]
    if achados:
        for nome, t in achados:
            print(f"ERRO: termo proibido '{t}' em {nome}", file=sys.stderr)
        sys.exit(2)
    os.makedirs(a.saida, exist_ok=True)
    for nome, txt in saidas.items():
        with open(os.path.join(a.saida, nome), "w", encoding="utf-8", newline="") as f:
            f.write(txt)
    print(f"OK: {len(saidas)} ficheiros em {a.saida} ({len(html)/1024:.0f} kB HTML)")


if __name__ == "__main__":
    main()
