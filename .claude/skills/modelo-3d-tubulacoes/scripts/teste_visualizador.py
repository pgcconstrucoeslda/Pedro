#!/usr/bin/env python3
"""Testa modelo_3d_tubulacoes.html com Playwright (Chromium headless) e tira screenshots.

Uso:  python3 -I teste_visualizador.py <html> -o <pasta_screens> [--three-dir <pasta do pacote three@0.128.0>]

--three-dir: quando a rede bloqueia os CDN, serve three.min.js e OrbitControls.js a partir de um
pacote local (obtido com `npm pack three@0.128.0 && tar xzf three-0.128.0.tgz` → pasta 'package').
Sem rede, as fontes Google são substituídas por CSS vazio (a página usa as fontes de sistema).

Termina com "TODOS OS TESTES OK" (código 0) ou lista as falhas (código 1).
"""
import argparse
import os
import sys

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--three-dir")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    url = "file://" + os.path.abspath(a.html)
    falhas, oks = [], []

    def check(nome, cond, det=""):
        (oks if cond else falhas).append(nome + (f" — {det}" if det else ""))
        print(("  OK   " if cond else "  FALHA ") + nome + (f" — {det}" if det else ""))

    def rotas(ctx):
        if a.three_dir:
            ctx.route("**/three.js/r128/three.min.js", lambda r: r.fulfill(path=os.path.join(a.three_dir, "build", "three.min.js"), content_type="application/javascript"))
            ctx.route("**/three@0.128.0/examples/js/controls/OrbitControls.js", lambda r: r.fulfill(path=os.path.join(a.three_dir, "examples", "js", "controls", "OrbitControls.js"), content_type="application/javascript"))
            ctx.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(body="", content_type="text/css"))
            ctx.route("https://fonts.gstatic.com/**", lambda r: r.fulfill(body="", content_type="font/woff2"))

    def abrir(browser, tema, vw=1440, vh=900, rm="reduce", mobile=False):
        ctx = browser.new_context(viewport={"width": vw, "height": vh}, color_scheme=tema, reduced_motion=rm,
                                  accept_downloads=True, is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
        rotas(ctx)
        pg = ctx.new_page()
        erros = []
        pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: erros.append(str(e)))
        pg.goto(url)
        pg.wait_for_function("window.__app && window.__app.ready", timeout=20000)
        pg.wait_for_timeout(600)
        return ctx, pg, erros

    def shot(pg, nome):
        p = os.path.join(a.saida, nome)
        pg.screenshot(path=p)
        print("  screenshot:", p)

    def canvas_xy(pg, x, y, z):
        s = pg.evaluate(f"window.__app.toScreen({x},{y},{z})")
        box = pg.locator("#vp canvas").bounding_box()
        return box["x"] + s["x"], box["y"] + s["y"]

    with sync_playwright() as p:
        kw = {"executable_path": CHROMIUM} if os.path.exists(CHROMIUM) else {}
        browser = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"], **kw)

        # ------------------------------------------------ tema claro
        print("Tema claro")
        ctx, pg, erros = abrir(browser, "light")
        M = pg.evaluate("window.__app.M")
        shot(pg, "01_visao_geral_claro.png")

        # seleção por proximidade (clicar a 4 px do ponto)
        pts = [q for q in M["pontos"] if q["sistema"] == "HID-AF"] or M["pontos"]
        alvo = pts[0]
        pg.evaluate(f"window.__app.goTo('{alvo['id']}')")
        pg.wait_for_timeout(300)
        pg.evaluate("window.__app.selectItem(null,null)")
        x, y = canvas_xy(pg, alvo["x"], alvo["y"], alvo["z"])
        pg.mouse.click(x + 4, y + 3)
        pg.wait_for_timeout(200)
        sel = pg.evaluate("window.__app.S.sel")
        check("Seleção por proximidade em ecrã", bool(sel) and sel["kind"] == "ponto", str(sel))
        txt = pg.inner_text("#pb")
        check("Painel de campo com situação e medidas", ("Conforme projeto" in txt or "Confirmar" in txt or "Não executar" in txt) and "Altura do piso" in txt)
        check("Cotas de locação desenhadas", pg.locator("#ov g.loc").count() >= 1, f"{pg.locator('#ov g.loc').count()} cotas")
        shot(pg, "02_painel_campo_desktop.png")

        # trecho: clicar no meio de um segmento
        t = next((t for t in M["trechos"] if t["sistema"] == "HID-AF" and t.get("comprimento", 0) > 1), M["trechos"][0])
        seg = max(t["segmentos"], key=lambda s: sum((s["b"][i] - s["a"][i]) ** 2 for i in range(3)))
        mid = [(seg["a"][i] + seg["b"][i]) / 2 for i in range(3)]
        pg.evaluate(f"window.__app.goTo('{t['id']}')")
        pg.wait_for_timeout(300)
        x, y = canvas_xy(pg, *mid)
        pg.mouse.click(x + 3, y - 3)
        pg.wait_for_timeout(200)
        sel = pg.evaluate("window.__app.S.sel")
        check("Seleção de tubo fino", bool(sel) and sel["kind"] in ("trecho", "ponto"), str(sel))
        if sel and sel["kind"] == "trecho":
            check("Painel do tubo: comprimento e por onde passa", "Por onde passa" in pg.inner_text("#pb"))
        shot(pg, "03_painel_tubo.png")

        # filtros por disciplina → divergências somem e voltam
        pg.click(".tab[data-tab=div]")
        n0, m0 = pg.evaluate("window.__app.divListCount()"), pg.evaluate("window.__app.visibleDivMarkers()")
        disc = None
        for d in M["divergencias"]:
            ds = [x for x in d["disciplinas"] if x != "ARQ"]
            if ds:
                disc = ds[0]
                break
        if disc:
            sis = {"HID": ["HID-AF"], "SAN": ["SAN-ESG", "SAN-VENT"], "DRE": ["DRE-PLU", "DRE-AC"]}[disc]
            for s in sis:
                loc = pg.locator(f"label[data-sys='{s}'] input")
                if loc.count():
                    loc.uncheck()
            n1, m1 = pg.evaluate("window.__app.divListCount()"), pg.evaluate("window.__app.visibleDivMarkers()")
            check(f"Filtro {disc} esconde divergências da lista e marcadores", n1 < n0 and m1 < m0, f"lista {n0}->{n1}, marcadores {m0}->{m1}")
            for s in sis:
                loc = pg.locator(f"label[data-sys='{s}'] input")
                if loc.count():
                    loc.check()
            n2, m2 = pg.evaluate("window.__app.divListCount()"), pg.evaluate("window.__app.visibleDivMarkers()")
            check("Divergências voltam ao religar", n2 == n0 and m2 == m0, f"{n2}/{n0}, {m2}/{m0}")
        arq_only = [d for d in M["divergencias"] if set(d["disciplinas"]) == {"ARQ"}]
        if arq_only:
            pg.locator("label[data-cam='arq'] input").uncheck()
            n3 = pg.evaluate("window.__app.divListCount()")
            pg.locator("label[data-cam='arq'] input").check()
            check("Divergência só de ARQ segue a camada de arquitetura", n3 == n0 - len(arq_only), f"{n3} vs {n0}-{len(arq_only)}")
        # clicar numa divergência liga disciplinas e centra
        pg.locator("label[data-sys] input").first.uncheck()
        first_div = M["divergencias"][0]["id"]
        pg.evaluate(f"window.__app.selectItem('div','{first_div}',true)")
        on = pg.evaluate("Object.values(window.__app.S.sys).every(x=>x) || true")
        check("Clique em divergência abre registo", "Divergência" in pg.inner_text("#pb"))
        pg.locator("label[data-sys] input").first.check()
        shot(pg, "04_divergencias.png")

        # corte + planta
        pg.click("#vPlanta")
        pg.locator("#corteOn").check()
        pg.eval_on_selector("#corteH", "el=>{el.value='1.0'; el.dispatchEvent(new Event('input'))}")
        pg.wait_for_timeout(300)
        cl = pg.evaluate("window.__app.S.corte")
        check("Corte horizontal ativo", cl["on"] and abs(cl["h"] - 1.0) < 1e-6)
        shot(pg, "05_planta_corte.png")
        pg.locator("#corteOn").uncheck()

        # sob o piso
        pg.click("#vSob")
        pg.wait_for_timeout(400)
        shot(pg, "06_sob_o_piso.png")

        # medição com Shift
        pg.click("#vPersp")
        pg.wait_for_timeout(400)
        hid = [q for q in M["pontos"] if q["pav"] == alvo["pav"]]
        p1, p2 = hid[0], next((q for q in hid[1:] if abs(q["x"] - hid[0]["x"]) > 0.3 or abs(q["y"] - hid[0]["y"]) > 0.3), hid[-1])
        pg.evaluate(f"window.__app.goTo('{p1['id']}')")
        pg.wait_for_timeout(300)
        pg.evaluate("window.__app.selectItem(null,null)")
        pg.click("#bMedir")
        x1, y1 = canvas_xy(pg, p1["x"], p1["y"], p1["z"])
        pg.mouse.move(x1, y1)
        pg.mouse.click(x1, y1)
        x2, y2 = canvas_xy(pg, p2["x"], p2["y"], p2["z"])
        pg.keyboard.down("Shift")
        pg.mouse.move(x2, y2)
        pg.mouse.click(x2, y2)
        pg.keyboard.up("Shift")
        cot = pg.evaluate("window.__app.cotas()")
        ok_shift = bool(cot) and sum(1 for k in ("dx", "dy", "dz") if abs(cot[-1][k]) < 1e-6) >= 2
        check("Medição com Shift trava num eixo", ok_shift, str(cot[-1] if cot else None))
        # medição livre
        pg.mouse.click(x1, y1)
        pg.mouse.click(x2, y2)
        cot = pg.evaluate("window.__app.cotas()")
        check("Medição livre cria 2.ª cota", len(cot) >= 2, str(len(cot)))
        if len(cot) >= 2:
            import math
            d = math.dist([p1["x"], p1["y"], p1["z"]], [p2["x"], p2["y"], p2["z"]])
            check("Valor da cota = distância entre pontos (snap)", abs(cot[-1]["d3"] - d) < 0.002, f"{cot[-1]['d3']:.3f} vs {d:.3f}")
        check("Painel Cotas lista C-01", "C-01" in pg.inner_text("#pb"))
        shot(pg, "07_cotas.png")
        pg.mouse.click(x1, y1)
        pg.keyboard.press("Escape")
        check("Esc cancela a medição", pg.evaluate("window.__app.S.medir") is False)

        # exportações
        pg.click("#bExp")
        nomes = pg.eval_on_selector_all("#expList [data-exp]", "els=>els.map(e=>e.dataset.exp)")
        for nome in nomes:
            if nome.startswith("__"):
                continue
            with pg.expect_download() as dl:
                pg.click(f"#expList [data-exp='{nome}']")
            dest = os.path.join(a.saida, "export_" + nome)
            dl.value.save_as(dest)
            txt = open(dest, encoding="utf-8-sig").read()
            check(f"Exportação {nome}", txt.count("\n") >= 1 and ";" in txt.splitlines()[0], f"{txt.count(chr(10))} linhas")
        pg.click("#bExp")

        # minimizar painel
        pg.click("#bMin")
        mn = pg.evaluate("document.getElementById('painel').classList.contains('min')")
        pg.click("#bMin")
        mx = pg.evaluate("!document.getElementById('painel').classList.contains('min')")
        check("Minimizar e abrir painel", mn and mx)

        # close de 2 banheiros
        amb_pts = {}
        for q in M["pontos"]:
            amb_pts.setdefault(q["ambiente"], []).append(q)
        bwc = [k for k in amb_pts if any(s in (k + " " + next((a["nome"] for a in M["ambientes"] if a["id"] == k), "")).lower() for s in ("bwc", "wc", "banh", "i.s", "sanit"))]
        bwc = sorted(bwc, key=lambda k: -len(amb_pts[k]))[:2] or sorted(amb_pts, key=lambda k: -len(amb_pts[k]))[:2]
        for i, k in enumerate(bwc):
            q = amb_pts[k][0]
            pg.evaluate(f"window.__app.selectItem('ponto','{q['id']}',true)")
            pg.wait_for_timeout(450)
            shot(pg, f"08_banheiro_{i+1}_{k}.png")
        check("Sem erros de consola (tema claro)", not erros, "; ".join(erros[:5]))
        ctx.close()

        # ------------------------------------------------ tema escuro (com animações)
        print("Tema escuro")
        ctx, pg, erros = abrir(browser, "dark", rm="no-preference")
        bg = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
        check("Tema escuro aplicado (prefers-color-scheme)", bg.lower() == "#0f141a", bg)
        pg.evaluate(f"window.__app.selectItem('ponto','{alvo['id']}',true)")
        pg.wait_for_timeout(700)
        shot(pg, "09_tema_escuro.png")
        pg.click("#bTema")
        bg2 = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
        check("Botão Tema alterna para claro", bg2.lower() == "#eef1f4", bg2)
        check("Sem erros de consola (tema escuro)", not erros, "; ".join(erros[:5]))
        ctx.close()

        # ------------------------------------------------ telemóvel
        print("Telemóvel")
        ctx, pg, erros = abrir(browser, "light", vw=390, vh=844, mobile=True)
        shot(pg, "10_telemovel_geral.png")
        pg.evaluate(f"window.__app.selectItem('ponto','{alvo['id']}',true)")
        pg.wait_for_timeout(400)
        shot(pg, "11_telemovel_painel.png")
        sw = pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        check("Telemóvel sem scroll horizontal", sw)
        check("Sem erros de consola (telemóvel)", not erros, "; ".join(erros[:5]))
        ctx.close()
        browser.close()

    print()
    print(f"{len(oks)} OK, {len(falhas)} falhas")
    if falhas:
        for f in falhas:
            print("  FALHA:", f)
        sys.exit(1)
    print("TODOS OS TESTES OK")


if __name__ == "__main__":
    main()
