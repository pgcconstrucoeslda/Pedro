#!/usr/bin/env python3
"""Verificações automáticas do modelo.json e campos calculados.

Uso:  python3 -I verificar_modelo.py modelo.json [-o modelo_verificado.json] [--relatorio verif.md]

Faz, por esta ordem:
  1. resolve as coordenadas de cada trecho a partir dos nós partilhados;
  2. divide cada segmento no ponto exato onde cruza o nível do piso do térreo / terreno
     e marca os pedaços enterrados (trechos[].segmentos);
  3. comprimento e declividade de cada trecho;
  4. continuidade (pontas soltas), pontos sobre trechos, declividades dentro das notas;
  5. louças: interseção com paredes (área = 0) e folga à face (<= 3 cm);
  6. cotas de locação (A, B perpendiculares à face de parede; V vertical) para TODOS os pontos,
     com conferência independente (distância shapely à linha de face);
  7. escreve `verificacoes` e `locacao` no JSON. Sai com código 1 se houver falhas.
"""
import argparse
import json
import math
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

GRAVIDADE = {"SAN-ESG", "DRE-PLU", "DRE-AC"}
TOL_LOUCA_AREA = 1e-6
FOLGA_MAX = 0.03


def r3(v):
    return None if v is None else round(float(v), 3)


# ---------------------------------------------------------------- utilidades geométricas
def sub(a, b):
    return [a[i] - b[i] for i in range(len(a))]


def norm(v):
    return math.sqrt(sum(c * c for c in v))


def dist_ponto_segmento3(p, a, b):
    ab = sub(b, a)
    L2 = sum(c * c for c in ab)
    if L2 < 1e-12:
        return norm(sub(p, a)), 0.0
    t = max(0.0, min(1.0, sum(sub(p, a)[i] * ab[i] for i in range(3)) / L2))
    q = [a[i] + ab[i] * t for i in range(3)]
    return norm(sub(p, q)), t


def dist_ponto_polilinha3(p, pts):
    best = float("inf")
    for i in range(len(pts) - 1):
        d, _ = dist_ponto_segmento3(p, pts[i], pts[i + 1])
        best = min(best, d)
    return best


class Modelo:
    def __init__(self, m):
        self.m = m
        self.nos = {n["id"]: n for n in m.get("nos", [])}
        self.pavs = sorted(m.get("pavimentos", []), key=lambda p: p["z_piso"])
        self.pav_baixo = self.pavs[0]["id"] if self.pavs else None
        self.z_terreno = m.get("meta", {}).get("z_terreno", 0.0)
        # polígonos que definem o "nível do chão" para efeito de enterrado
        self.chao = []
        for p in m.get("pisos", []):
            if p.get("tipo") == "terreno" or (p.get("pav") == self.pav_baixo and p.get("tipo", "piso") == "piso"):
                self.chao.append((Polygon(p["poly"]), p["z"]))
        self.paredes = m.get("paredes", [])
        self.poly_par = {}
        for w in self.paredes:
            ls = LineString([w["a"], w["b"]])
            self.poly_par[w["id"]] = ls.buffer(w["esp"] / 2.0, cap_style=2, join_style=2)

    def coords_trecho(self, t):
        out = []
        for nid in t["nos"]:
            n = self.nos.get(nid)
            if n is None:
                raise KeyError(f"Trecho {t['id']}: nó {nid} não existe")
            out.append([n["x"], n["y"], n["z"]])
        return out

    def nivel_chao(self, x, y):
        pt = Point(x, y)
        zs = [z for poly, z in self.chao if poly.buffer(1e-9).contains(pt)]
        return min(zs) if zs else self.z_terreno

    def piso_em(self, x, y, pav):
        pt = Point(x, y)
        zs = [p["z"] for p in self.m.get("pisos", [])
              if p.get("pav") == pav and p.get("tipo", "piso") in ("piso", "terreno")
              and Polygon(p["poly"]).buffer(1e-9).contains(pt)]
        if zs:
            return max(zs), "polígono de piso"
        return None, None


# ---------------------------------------------------------------- 2. enterrado
def dividir_segmento(M, a, b):
    """Divide a->b nos limites dos polígonos de chão e no cruzamento com o nível. Devolve pedaços."""
    ts = {0.0, 1.0}
    lh = math.hypot(b[0] - a[0], b[1] - a[1])
    if lh > 1e-9:
        ls = LineString([a[:2], b[:2]])
        for poly, _ in M.chao:
            inter = ls.intersection(poly.exterior)
            geoms = getattr(inter, "geoms", [inter])
            for g in geoms:
                if g.is_empty:
                    continue
                for c in getattr(g, "coords", []):
                    ts.add(max(0.0, min(1.0, ls.project(Point(c)) / lh)))
    ts = sorted(ts)
    lerp = lambda t: [a[i] + (b[i] - a[i]) * t for i in range(3)]
    pedacos = []
    for t0, t1 in zip(ts[:-1], ts[1:]):
        if t1 - t0 < 1e-9:
            continue
        tm = (t0 + t1) / 2
        pm = lerp(tm)
        g = M.nivel_chao(pm[0], pm[1])
        za, zb = lerp(t0)[2], lerp(t1)[2]
        cortes = [t0]
        if (za - g) * (zb - g) < 0:  # cruza o nível dentro do pedaço
            tc = t0 + (g - za) / (zb - za) * (t1 - t0)
            cortes.append(tc)
        cortes.append(t1)
        for s0, s1 in zip(cortes[:-1], cortes[1:]):
            pa, pb = lerp(s0), lerp(s1)
            mid = lerp((s0 + s1) / 2)
            ent = mid[2] < M.nivel_chao(mid[0], mid[1]) - 1e-6
            pedacos.append({"a": [r3(c) for c in pa], "b": [r3(c) for c in pb], "enterrado": ent})
    # junta pedaços consecutivos com a mesma marcação
    out = []
    for p in pedacos:
        if out and out[-1]["enterrado"] == p["enterrado"]:
            out[-1]["b"] = p["b"]
        else:
            out.append(dict(p))
    return out


# ---------------------------------------------------------------- 3/4. rede
def limites_decl(meta, sistema, dn):
    for d in meta.get("declividades", []):
        if d["sistema"] == sistema and d.get("dn_min", 0) <= dn <= d.get("dn_max", 9999):
            return d
    return None


def verificar_rede(M):
    m = M.m
    meta = m.get("meta", {})
    tol = meta.get("tolerancia_continuidade", 0.01)
    trechos = m.get("trechos", [])
    coords = {}
    for t in trechos:
        pts = M.coords_trecho(t)
        coords[t["id"]] = pts
        segs = []
        for i in range(len(pts) - 1):
            segs.extend(dividir_segmento(M, pts[i], pts[i + 1]))
        t["segmentos"] = segs
        t["comprimento"] = r3(sum(norm(sub(pts[i + 1], pts[i])) for i in range(len(pts) - 1)))
        decl = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            lh = math.hypot(b[0] - a[0], b[1] - a[1])
            dz = abs(b[2] - a[2])
            if lh >= 0.05 and dz / lh <= 0.5:   # segmento "horizontal" (caimento); vertical/queda fica de fora
                decl.append(dz / lh)
        t["declividade"] = r3(min(decl)) if (decl and t["sistema"] in GRAVIDADE) else None
        t["_decl_segs"] = decl

    # uso dos nós
    uso = {}
    for t in trechos:
        for nid in t["nos"]:
            uso.setdefault(nid, set()).add(t["id"])
    pontos_por_no = {p.get("no") for p in m.get("pontos", [])}
    pts_xyz = [(p["id"], [p["x"], p["y"], p["z"]]) for p in m.get("pontos", [])]

    def em_equipamento(p):
        for e in m.get("equipamentos", []):
            c, d = e["centro"], e["dims"]
            ang = math.radians(e.get("rot", 0))
            dx, dy = p[0] - c[0], p[1] - c[1]
            lx = dx * math.cos(ang) + dy * math.sin(ang)
            ly = -dx * math.sin(ang) + dy * math.cos(ang)
            if (abs(lx) <= d[0] / 2 + tol and abs(ly) <= d[1] / 2 + tol and abs(p[2] - c[2]) <= d[2] / 2 + tol):
                return e["id"]
        return None

    soltas, limites = [], []
    for t in trechos:
        for idx in (0, -1):
            nid = t["nos"][idx]
            n = M.nos[nid]
            p = [n["x"], n["y"], n["z"]]
            if len(uso.get(nid, ())) > 1 or nid in pontos_por_no:
                continue
            toca = None
            for t2 in trechos:
                if t2["id"] != t["id"] and dist_ponto_polilinha3(p, coords[t2["id"]]) <= tol:
                    toca = t2["id"]
                    break
            if not toca:
                for pid, xyz in pts_xyz:
                    if norm(sub(p, xyz)) <= tol:
                        toca = pid
                        break
            if not toca:
                toca = em_equipamento(p)
            if toca:
                continue
            reg = {"trecho": t["id"], "no": nid, "xyz": [r3(c) for c in p]}
            (limites if n.get("limite_lote") else soltas).append(reg)

    fora = []
    for pid, xyz in pts_xyz:
        d = min((dist_ponto_polilinha3(xyz, c) for c in coords.values()), default=float("inf"))
        if d > tol:
            fora.append({"ponto": pid, "dist": r3(d) if d != float("inf") else None})

    decl_falhas, decl_ok = [], 0
    for t in trechos:
        if t["sistema"] not in GRAVIDADE:
            continue
        lim = limites_decl(meta, t["sistema"], t.get("dn", 0))
        if lim is None:
            decl_falhas.append({"trecho": t["id"], "motivo": "sem nota de declividade para este sistema/DN"})
            continue
        for s in t["_decl_segs"]:
            if s < lim["min"] - 1e-4 or s > lim["max"] + 1e-4:
                decl_falhas.append({"trecho": t["id"], "declividade": r3(s), "min": lim["min"], "max": lim["max"], "fonte": lim.get("fonte", "")})
                break
        else:
            decl_ok += 1
    for t in trechos:
        t.pop("_decl_segs", None)
    return {
        "continuidade": {"pontas_soltas": soltas, "limites_lote": limites, "ok": not soltas},
        "pontos_sobre_trecho": {"fora": fora, "ok": not fora},
        "declividades": {"falhas": decl_falhas, "trechos_ok": decl_ok, "ok": not decl_falhas},
    }


# ---------------------------------------------------------------- 5. louças
def retangulo_louca(l):
    ax, ay = l["apoio"]
    nx, ny = l["normal"]
    nn = math.hypot(nx, ny)
    nx, ny = nx / nn, ny / nn
    tx, ty = -ny, nx
    w, d = l["largura"] / 2, l["profundidade"]
    p1 = (ax + tx * w, ay + ty * w)
    p2 = (ax - tx * w, ay - ty * w)
    p3 = (p2[0] + nx * d, p2[1] + ny * d)
    p4 = (p1[0] + nx * d, p1[1] + ny * d)
    return Polygon([p1, p2, p3, p4]), LineString([p1, p2])


def verificar_loucas(M):
    res = []
    for l in M.m.get("loucas", []):
        paredes = [M.poly_par[w["id"]] for w in M.paredes if w["pav"] == l["pav"]]
        uni = unary_union(paredes) if paredes else None
        rect, costas = retangulo_louca(l)
        area = rect.intersection(uni).area if uni is not None else 0.0
        folga = costas.distance(uni) if uni is not None else None
        ok = area <= TOL_LOUCA_AREA and folga is not None and folga <= FOLGA_MAX + 1e-6
        res.append({"louca": l["id"], "area_invasao_m2": round(area, 6), "folga": r3(folga), "ok": ok})
    return {"itens": res, "ok": all(r["ok"] for r in res)}


# ---------------------------------------------------------------- 6. locação
def _dir(w):
    dx, dy = w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]
    L = math.hypot(dx, dy)
    return dx / L, dy / L, L


def _paralelas(w1, w2, tol_graus=15):
    d1, d2 = _dir(w1), _dir(w2)
    c = abs(d1[0] * d2[0] + d1[1] * d2[1])
    return c >= math.cos(math.radians(tol_graus))


def candidatos_parede(M, x, y, pav):
    out = []
    for w in M.paredes:
        if w["pav"] != pav:
            continue
        ux, uy, L = _dir(w)
        ax, ay = w["a"]
        s = (x - ax) * ux + (y - ay) * uy
        if s < -1e-6 or s > L + 1e-6:
            continue  # pé da perpendicular fora da parede
        fx, fy = ax + ux * s, ay + uy * s
        d_eixo = math.hypot(x - fx, y - fy)
        e = w["esp"] / 2
        if d_eixo < 1e-9:
            nx, ny = -uy, ux
        else:
            nx, ny = (x - fx) / d_eixo, (y - fy) / d_eixo  # normal do eixo para o lado do ponto
        pe = (fx + nx * e, fy + ny * e)                 # pé na face acabada voltada para o ponto
        out.append({"w": w, "d_eixo": d_eixo, "dist": d_eixo - e, "pe": pe})
    return out


def visivel(M, x, y, c, excluir):
    """A linha ponto -> pé na face não pode atravessar outra parede."""
    seg = LineString([(x, y), c["pe"]])
    if seg.length < 1e-6:
        return True
    for w in M.paredes:
        if w["id"] in excluir or w["pav"] != c["w"]["pav"]:
            continue
        poly = M.poly_par[w["id"]]
        inter = seg.intersection(poly)
        if not inter.is_empty and inter.length > 0.005:
            return False
    return True


def locacao_ponto(M, p):
    x, y, z = p["x"], p["y"], p["z"]
    cands = candidatos_parede(M, x, y, p["pav"])
    apoio = None
    emb = [c for c in cands if c["dist"] <= 0.005]
    if emb:
        apoio = min(emb, key=lambda c: c["d_eixo"])
    excl = {apoio["w"]["id"]} if apoio else set()
    vis = sorted([c for c in cands if c["dist"] > 0.005 and visivel(M, x, y, c, excl | {c["w"]["id"]})],
                 key=lambda c: c["dist"])
    fmt = lambda c: {"parede": c["w"]["id"], "dist": r3(c["dist"]), "pe": [r3(c["pe"][0]), r3(c["pe"][1])]}
    A = B = None
    if apoio:
        trans = [c for c in vis if not _paralelas(c["w"], apoio["w"])]
        A = trans[0] if trans else None
        B_info = {"parede": apoio["w"]["id"], "tipo": "embutido",
                  "prof": r3(apoio["w"]["esp"] / 2 - apoio["d_eixo"]), "dist": 0.0,
                  "pe": [r3(apoio["pe"][0]), r3(apoio["pe"][1])]}
        res = {"apoio": apoio["w"]["id"], "A": fmt(A) if A else None, "B": B_info}
    else:
        if vis:
            A = vis[0]
            for c in vis[1:]:
                if not _paralelas(c["w"], A["w"]):
                    B = c
                    break
        res = {"apoio": None, "A": fmt(A) if A else None, "B": fmt(B) if B else None}
    # vertical
    if p.get("h") is not None:
        zp, fonte = z - p["h"], "Z − h"
    else:
        zp, fonte = M.piso_em(x, y, p["pav"])
        if zp is None:
            zp, fonte = M.nivel_chao(x, y), "terreno"
    v = z - zp
    res["V"] = {"z_piso": r3(zp), "valor": r3(abs(v)), "tipo": "altura" if v >= 0 else "profundidade", "fonte": fonte}
    obs = []
    if res["A"] is None:
        obs.append("sem parede de referência A")
    if res["B"] is None:
        obs.append("sem parede de referência B")
    res["obs"] = "; ".join(obs)
    return res


def conferencia_independente(M, p, loc):
    """Recalcula a distância de A/B com shapely (ponto -> linha da face) e compara."""
    erros = []
    for k in ("A", "B"):
        c = loc.get(k)
        if not c or c.get("tipo") == "embutido":
            continue
        w = next(w for w in M.paredes if w["id"] == c["parede"])
        eixo = LineString([w["a"], w["b"]])
        faces = [eixo.parallel_offset(w["esp"] / 2, "left"), eixo.parallel_offset(w["esp"] / 2, "right")]
        d = min(f.distance(Point(p["x"], p["y"])) for f in faces)
        if abs(d - c["dist"]) > 0.001:
            erros.append({"ponto": p["id"], "cota": k, "calc": c["dist"], "indep": r3(d)})
    return erros


def verificar_locacao(M):
    loc, sem, erros = {}, [], []
    for p in M.m.get("pontos", []):
        l = locacao_ponto(M, p)
        loc[p["id"]] = l
        if l["obs"]:
            sem.append({"ponto": p["id"], "obs": l["obs"]})
        erros.extend(conferencia_independente(M, p, l))
    M.m["locacao"] = loc
    return {"calculadas": len(loc), "sem_referencia": sem, "conferencia_independente_erros": erros,
            "ok": not erros}


# ---------------------------------------------------------------- resumo
def resumo(M):
    m = M.m
    r = {"pontos": {}, "trechos": {}, "extensao_m": {}, "divergencias": {}}
    for p in m.get("pontos", []):
        r["pontos"].setdefault(p["sistema"], {}).setdefault(p["status"], 0)
        r["pontos"][p["sistema"]][p["status"]] += 1
    for t in m.get("trechos", []):
        r["trechos"].setdefault(t["sistema"], {}).setdefault(t["status"], 0)
        r["trechos"][t["sistema"]][t["status"]] += 1
        r["extensao_m"][t["sistema"]] = r3(r["extensao_m"].get(t["sistema"], 0) + (t.get("comprimento") or 0))
    for d in m.get("divergencias", []):
        r["divergencias"][d["gravidade"]] = r["divergencias"].get(d["gravidade"], 0) + 1
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modelo")
    ap.add_argument("-o", "--saida")
    ap.add_argument("--relatorio")
    a = ap.parse_args()
    with open(a.modelo, encoding="utf-8") as f:
        m = json.load(f)
    M = Modelo(m)
    v = verificar_rede(M)
    v["loucas"] = verificar_loucas(M)
    v["locacao"] = verificar_locacao(M)
    v["resumo"] = resumo(M)
    m["verificacoes"] = v
    with open(a.saida or a.modelo, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)

    linhas = ["# Verificação automática", ""]
    def item(nome, ok, det=""):
        linhas.append(f"- [{'OK' if ok else 'FALHA'}] {nome}{(' — ' + det) if det else ''}")
    c = v["continuidade"]
    item("Continuidade", c["ok"], f"{len(c['pontas_soltas'])} pontas soltas; {len(c['limites_lote'])} nos limites do lote")
    for s in c["pontas_soltas"]:
        linhas.append(f"    - ponta solta: {s['trecho']} nó {s['no']} {s['xyz']}")
    item("Pontos sobre trechos", v["pontos_sobre_trecho"]["ok"], f"{len(v['pontos_sobre_trecho']['fora'])} fora")
    for s in v["pontos_sobre_trecho"]["fora"]:
        linhas.append(f"    - {s['ponto']} a {s['dist']} m")
    d = v["declividades"]
    item("Declividades", d["ok"], f"{d['trechos_ok']} trechos OK, {len(d['falhas'])} falhas")
    for s in d["falhas"]:
        linhas.append(f"    - {s}")
    lc = v["loucas"]
    item("Louças (invasão = 0, folga <= 3 cm)", lc["ok"], f"{sum(1 for i in lc['itens'] if i['ok'])}/{len(lc['itens'])}")
    for s in lc["itens"]:
        if not s["ok"]:
            linhas.append(f"    - {s}")
    lo = v["locacao"]
    item("Cotas de locação", lo["ok"], f"{lo['calculadas']} pontos; {len(lo['sem_referencia'])} sem parede de referência; "
         f"{len(lo['conferencia_independente_erros'])} erros na conferência independente")
    for s in lo["sem_referencia"]:
        linhas.append(f"    - {s['ponto']}: {s['obs']}")
    txt = "\n".join(linhas)
    print(txt)
    if a.relatorio:
        with open(a.relatorio, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
    falhou = not (c["ok"] and v["pontos_sobre_trecho"]["ok"] and d["ok"] and lc["ok"] and lo["ok"])
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
