"""Análise de um projeto com vários desenhos (várias especialidades).

* converte e extrai cada desenho, resolvendo xrefs fornecidas no mesmo lote;
* identifica especialidade, legenda e projetista (registo de perfis);
* verificações de **integridade** (xrefs em falta, desenhos sem geometria,
  legendas incoerentes);
* verificações de **compatibilização**:
  - base de arquitetura usada pelas outras especialidades vs arquitetura analisada;
  - cotas de pavimento incoerentes no mesmo piso;
  - etiquetas de área vs polígonos;
  - compartimentos citados no MQ que não existem no desenho;
  - mapa de vãos do MQ vs vãos detetados em planta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .converter import dwg_to_dxf
from .extractor import Resultado, extrair, norm
from .niveis import marcas_nivel
from .projetistas import Registo, assinatura

COLS_ISSUE = ["n", "categoria", "gravidade", "especialidade", "desenho", "descricao", "evidencia", "acao"]


@dataclass
class Desenho:
    ficheiro: str
    dxf: str
    res: Resultado
    especialidade: str = ""
    subespecialidade: str = ""
    titulo: str = ""
    data: str = ""
    revisao: str = ""
    autores: str = ""
    requerente: str = ""
    localizacao: str = ""
    perfil_id: str = ""
    perfil_nome: str = ""

    def resumo(self) -> dict:
        r = self.res
        xr = [x for x in r.xrefs if x["estado"] == "EM FALTA"]
        return dict(desenho=self.ficheiro, especialidade=self.especialidade, subespecialidade=self.subespecialidade,
                    titulo=self.titulo, vistas=r.legenda.get("VISTAS", ""), data=self.data, revisao=self.revisao,
                    autores=self.autores, projetista=self.perfil_nome,
                    entidades=len(r.entidades), compartimentos=len(r.compartimentos),
                    xrefs_em_falta=", ".join(x["nome"] for x in xr))


@dataclass
class Projeto:
    desenhos: list[Desenho] = field(default_factory=list)
    xrefs_fornecidas: dict = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    bases: dict = field(default_factory=dict)  # nome -> Resultado de bases embutidas

    def tabela(self) -> pd.DataFrame:
        return pd.DataFrame([d.resumo() for d in self.desenhos])

    def issues_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self.issues, columns=COLS_ISSUE[1:])
        df.insert(0, "n", range(1, len(df) + 1))
        return df

    def principal(self) -> Desenho | None:
        arq = [d for d in self.desenhos if "ARQ" in d.especialidade.upper()]
        cand = arq or self.desenhos
        return max(cand, key=lambda d: (len(d.res.compartimentos), len(d.res.entidades))) if cand else None

    def add(self, categoria, gravidade, desenho, descricao, evidencia="", acao="", especialidade=""):
        self.issues.append(dict(categoria=categoria, gravidade=gravidade, especialidade=especialidade,
                                desenho=desenho, descricao=descricao, evidencia=evidencia, acao=acao))


def _stem(nome: str) -> str:
    return re.sub(r"^[0-9a-f]{8}-", "", Path(nome).stem).lower()


def carregar(ficheiros: list[tuple[str, str]], registo: Registo | None = None, progress=None,
             metadados: dict | None = None, layers_ignorar: str = "", mq: pd.DataFrame | None = None) -> Projeto:
    """``ficheiros``: [(nome_original, caminho)] - DWG ou DXF (desenhos e xrefs)."""
    prj = Projeto()
    dxfs = []
    for i, (nome, path) in enumerate(ficheiros):
        if progress:
            progress(i / max(len(ficheiros), 1) * 0.3, f"A converter {nome}")
        p = Path(path)
        try:
            dxf = dwg_to_dxf(p, p.parent / "dxf") if p.suffix.lower() == ".dwg" else p
        except Exception as ex:
            prj.add("Integridade", "Alta", nome, f"Não foi possível converter o ficheiro: {ex}")
            continue
        dxfs.append((nome, str(dxf)))
    # ficheiros xref: nome começa por XREF ou coincide com a referência de outro desenho
    xr = {_stem(n): d for n, d in dxfs if _stem(n).startswith("xref")}
    prj.xrefs_fornecidas = xr
    principais = [(n, d) for n, d in dxfs if _stem(n) not in xr]
    for i, (nome, dxf) in enumerate(principais):
        if progress:
            progress(0.3 + 0.6 * i / max(len(principais), 1), f"A analisar {nome}")
        res = extrair(dxf, xrefs=xr, layers_ignorar=layers_ignorar)
        leg = res.legenda
        a = assinatura(res, nome)
        d = Desenho(ficheiro=nome, dxf=dxf, res=res, especialidade=a["especialidade"], subespecialidade=a["subespecialidade"],
                    titulo=leg.get("TITULO", "") or (res.folhas[0].nome if res.folhas else ""), data=leg.get("DATA", ""),
                    revisao=leg.get("REVISÃO", leg.get("REVISAO", "")), autores=", ".join(a["autores"]),
                    requerente=leg.get("REQUERENTE", ""), localizacao=leg.get("LOCALIZAÇÃO", leg.get("LOCALIZACAO", "")))
        if registo is not None:
            p, _ = registo.identificar(res, nome, metadados, guardar=False)
            d.perfil_id, d.perfil_nome = p["id"], p["nome"]
        prj.desenhos.append(d)
    if registo is not None:
        registo.guardar()
    verificar_integridade(prj)
    verificar_compatibilizacao(prj, mq=mq, progress=progress)
    if progress:
        progress(1.0, "Concluído")
    return prj


# ---------------------------------------------------------------- integridade

def verificar_integridade(prj: Projeto) -> None:
    falta: dict[str, list[str]] = {}
    sem_geo: dict[str, list[str]] = {}
    bases: dict[tuple, list[str]] = {}
    for d in prj.desenhos:
        r = d.res
        for x in r.xrefs:
            if x["estado"] == "EM FALTA":
                falta.setdefault(x["nome"], []).append(d.ficheiro)
            elif x["estado"].startswith("definida mas não inserida") and x["entidades"] > 1000:
                bases.setdefault((x["nome"], x["entidades"], x["caminho"]), []).append(d.ficheiro)
        geo = r.entidades[~r.entidades.tipo.isin(["INSERT", "ATTRIB"])] if not r.entidades.empty else r.entidades
        if len(geo) < 20:
            sem_geo.setdefault(d.especialidade or "?", []).append(d.ficheiro)
    for esp, ds in sem_geo.items():
        prj.add("Integridade", "Alta", f"{len(ds)} desenho(s)",
                f"{esp}: os desenhos não têm geometria própria no espaço modelo (só legenda e referências externas) - "
                "não é possível medir nem compatibilizar esta especialidade.",
                evidencia="; ".join(sorted(ds)), especialidade=esp,
                acao="Pedir os desenhos com as xrefs (eTransmit) ou com as xrefs ligadas (BIND).")
    for (nome, n, cam), ds in bases.items():
        prj.add("Integridade", "Info", f"{len(ds)} desenho(s)",
                f"Contêm a referência '{nome}' embutida mas não inserida ({n} entidades) - base de arquitetura usada pelo projetista.",
                evidencia=f"{cam}; " + "; ".join(sorted(ds)[:3]) + (" …" if len(ds) > 3 else ""))
    for nome, ds in falta.items():
        prj.add("Integridade", "Alta", f"{len(ds)} desenho(s)",
                f"Referência externa em falta: '{nome}'. A geometria destes desenhos não foi entregue.",
                evidencia="; ".join(sorted(ds)[:8]) + (" …" if len(ds) > 8 else ""),
                acao=f"Solicitar o ficheiro '{nome}.dwg' (ou eTransmit do conjunto).")
    # coerência das legendas
    for campo in ("requerente", "localizacao"):
        vals = {}
        for d in prj.desenhos:
            v = getattr(d, campo)
            if v:
                vals.setdefault(norm(v), []).append((v, d.ficheiro))
        if len(vals) > 1:
            txt = " | ".join(f"'{v[0][0]}' ({len(v)} des.)" for v in vals.values())
            prj.add("Integridade", "Média", "legendas", f"{campo.capitalize()} diferente entre desenhos: {txt}")
    datas = {d.data for d in prj.desenhos if d.data}
    if len(datas) > 1:
        prj.add("Integridade", "Info", "legendas", "Datas de emissão diferentes entre especialidades: " + ", ".join(sorted(datas)),
                acao="Confirmar que as especialidades estão coordenadas com a mesma versão de arquitetura.")


# ---------------------------------------------------------------- compatibilização

def _rooms(res: Resultado) -> pd.DataFrame:
    c = res.compartimentos
    if c.empty:
        return pd.DataFrame(columns=["chave", "compartimento", "area"])
    c = c[c.compartimento != "(sem nome)"]
    return (c.assign(chave=c.compartimento.map(norm), area=c.area_etiqueta)
            .drop_duplicates(subset=["chave", "area"])[["chave", "compartimento", "area"]])


def comparar_bases(arq: Resultado, base: Resultado) -> list[tuple[str, str, str]]:
    """Diferenças entre a arquitetura analisada e a base usada por outra especialidade.
    Devolve [(gravidade, descrição, evidência)]."""
    out = []
    a, b = _rooms(arq), _rooms(base)
    if a.empty or b.empty:
        return [("Info", "Sem etiquetas de compartimentos suficientes para comparar as bases.", "")]
    ka, kb = set(a.chave), set(b.chave)
    for k in sorted(ka - kb):
        out.append(("Média", f"Compartimento '{a[a.chave == k].compartimento.iloc[0]}' existe na arquitetura mas não na base da especialidade.", ""))
    for k in sorted(kb - ka):
        out.append(("Média", f"Compartimento '{b[b.chave == k].compartimento.iloc[0]}' existe na base da especialidade mas não na arquitetura.", ""))
    for k in sorted(ka & kb):
        va, vb = sorted(a[a.chave == k].area), sorted(b[b.chave == k].area)
        if va != vb:
            out.append(("Média", f"Área de '{a[a.chave == k].compartimento.iloc[0]}' diferente: arquitetura {va} m² vs base {vb} m².", ""))
    ma, mb = marcas_nivel(arq), marcas_nivel(base)
    la, lb = set(ma.cota.round(2)), set(mb.cota.round(2))
    if la and lb and la != lb:
        dif = sorted(la ^ lb)
        if dif:
            out.append(("Baixa", "Cotas de nível presentes só numa das versões: " + ", ".join(f"{x:.2f}" for x in dif[:12]), ""))
    if not out:
        out.append(("OK", f"Base coincidente com a arquitetura analisada ({len(ka)} compartimentos e áreas iguais).", ""))
    return out


def verificar_compatibilizacao(prj: Projeto, mq: pd.DataFrame | None = None, progress=None) -> None:
    arq = prj.principal()
    if arq is None:
        return
    # 1) bases de arquitetura embutidas noutras especialidades
    vistos = {}
    for d in prj.desenhos:
        if d is arq:
            continue
        for x in d.res.xrefs:
            if not (x["estado"].startswith("definida mas não inserida") and x["entidades"] > 1000):
                continue
            chave = (x["nome"], x["entidades"])
            if chave not in vistos:
                if progress:
                    progress(0.92, f"A comparar base '{x['nome']}' com a arquitetura")
                try:
                    base = extrair(d.dxf, bloco_fonte=x["nome"], unidade=arq.res.unidade)
                    prj.bases[x["nome"]] = base
                    vistos[chave] = (comparar_bases(arq.res, base), [])
                except Exception as ex:
                    vistos[chave] = ([("Info", f"Não foi possível ler a base '{x['nome']}': {ex}", "")], [])
            vistos[chave][1].append(d)
    for (nome, _), (difs, ds) in vistos.items():
        esp = sorted({d.especialidade for d in ds})
        for g, desc, ev in difs:
            prj.add("Compatibilização", g, f"{len(ds)} desenho(s) {', '.join(esp)}",
                    f"Base '{nome}' vs arquitetura '{arq.ficheiro}': {desc}", ev,
                    "" if g in ("OK", "Info") else "Confirmar com o projetista qual a versão de arquitetura usada.",
                    especialidade=", ".join(esp))
    # 2) cotas de pavimento diferentes no mesmo piso
    r = arq.res
    mk = marcas_nivel(r)
    for _, n in r.niveis.iterrows() if not r.niveis.empty else []:
        m = mk[(mk.folha == n.folha) & ~mk.soleira]
        c = r.compartimentos[r.compartimentos.folha == n.folha]
        if m.empty or c.empty:
            continue
        d = m.apply(lambda q: (((c.x - q.x) ** 2 + (c.y - q.y) ** 2) ** 0.5).min() * r.fator, axis=1)
        v = sorted(set(m[d <= 6].cota.round(2)))
        if len(v) > 1 and max(v) - min(v) <= 0.10:
            prj.add("Compatibilização", "Baixa", arq.ficheiro,
                    f"{n.nivel}: cotas de pavimento interiores diferentes no mesmo piso ({', '.join(f'{x:.2f}' for x in v)}).",
                    acao="Confirmar se há desnível intencional (ex.: zonas húmidas) ou erro de cota.")
    # 3) etiquetas vs polígonos
    c = r.compartimentos
    if not c.empty:
        for _, q in c[c["desvio_%"].abs() > 5].iterrows():
            prj.add("Desenho", "Média", arq.ficheiro,
                    f"'{q.compartimento}': área da etiqueta {q.area_etiqueta:.2f} m² vs polígono {q.area_geometria:.2f} m² "
                    f"({q['desvio_%']:+.1f} %).", f"etiqueta {q.handle_etiqueta} / polígono {q.handle_poligono}",
                    "Confirmar a área correta com o projetista de arquitetura.", "ARQUITETURA")
    if mq is not None:
        verificar_mq_vs_desenho(prj, mq)


RE_ROOM = re.compile(r"\b(i\.?\s?s\.?|quarto|sala|suite|cozinha|garagem|hall|escrit|closet|lavand|arrumo|despensa|"
                     r"circula|alpendre|anexo|wc|instala[çc][ãa]o sanit)", re.I)


def verificar_mq_vs_desenho(prj: Projeto, mq: pd.DataFrame) -> None:
    from .vaos import aplicar_alturas, associar_mq, mapa_vaos_mq
    arq = prj.principal()
    if arq is None or mq is None or mq.empty:
        return
    r = arq.res
    nomes = {norm(x) for x in r.compartimentos.compartimento} if not r.compartimentos.empty else set()
    # compartimentos citados no MQ que não existem no desenho
    falta = {}
    for _, it in mq[mq.local != ""].iterrows():
        loc = str(it.local)
        # nome curto (até ao primeiro separador); tem de ser, ele próprio, um nome de compartimento
        curto = re.split(r"[,(:\-]| com ", loc)[0].strip()
        if not RE_ROOM.search(curto) or re.match(r"^\s*(arm[áa]rio|portas?|v[ãa]os?|v[ei]\d|janela|espelho|m[óo]vel)", curto, re.I):
            continue
        k = norm(curto)
        k1 = k[:-1] if k.endswith("s") else k
        if len(k) < 3 or any(k in n or n in k or k1 in n for n in nomes if len(n) >= 3):
            continue
        falta.setdefault(curto, []).append(it.id)
    for nome, ids in falta.items():
        prj.add("MQ x Desenho", "Média", "MQ", f"O MQ refere '{nome}', que não existe como compartimento no desenho de arquitetura.",
                evidencia=", ".join(ids[:5]), acao="Confirmar a designação/localização ou atualizar o MQ.")
    # mapa de vãos
    mapa = mapa_vaos_mq(mq)
    if r.vaos is None or r.vaos.empty or mapa.empty:
        return
    v = associar_mq(r.vaos, mapa)
    ext = mapa[mapa.codigo != ""]
    for _, m in ext.iterrows():
        hit = v[(v.codigo_mq == m.codigo) & ((v.largura - m.largura).abs() <= 0.06)]
        if hit.empty:
            prj.add("MQ x Desenho", "Média", "MQ / plantas",
                    f"Vão {m.codigo} do MQ ({m.largura:.2f}x{m.altura:.2f}) sem vão com a mesma largura nas plantas.",
                    evidencia=m.item_mq[:60], acao="Verificar se o vão existe no desenho com outra dimensão.")
    sem = v[(v.codigo_mq == "") & (v.tipo != "porta") & (v.largura >= 0.9)]
    for _, q in sem.iterrows():
        prj.add("MQ x Desenho", "Baixa", arq.ficheiro,
                f"Vão de {q.largura:.2f} m em '{q.compartimento}' sem correspondência de largura no mapa de vãos do MQ.",
                evidencia=f"{q.id} ({q.handles})", acao="Confirmar se o vão está orçamentado.")
