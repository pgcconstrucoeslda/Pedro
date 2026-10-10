"""Registo de projetistas/gabinetes e respetivos perfis de desenho.

À medida que os projetos são lidos, cada desenho é associado a um perfil pela
sua **assinatura** (gabinete, blocos da legenda, prefixos de layers, padrão do
nome do ficheiro). O perfil acumula:

* especialidades, autores (iniciais da legenda) e projetos analisados;
* ``layers_conhecidos`` - layers usados por esse gabinete para cada papel
  (paredes, vãos, rodapés, guardas, cotas, compartimentos…);
* ``blocos_conhecidos`` - blocos para cada papel (sanita, lavatório, porta…),
  incluindo os que o utilizador "ensina" na aplicação.

Os perfis são guardados em JSON (``perfis/projetistas.json`` por defeito, ou o
caminho da variável ``MEDICOES_PERFIS``) e usados para afinar as sugestões de regras.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections import Counter
from pathlib import Path

CAMINHO_PADRAO = Path(os.environ.get("MEDICOES_PERFIS", Path(__file__).resolve().parent.parent / "perfis" / "projetistas.json"))

PAPEIS_LAYER = {
    "paredes": r"parede|wall|alvenaria",
    "vaos": r"porta|janela|v[ãa]o|caixilh|door|window",
    "rodape": r"rodap|skirt",
    "guardas": r"guard|railing",
    "cotas_nivel": r"cota|n[ií]vel|altim",
    "muros": r"muro",
    "pilares": r"pilar|column",
    "vigas": r"viga|beam",
    "lajes": r"laje|slab",
    "tubagens": r"tub|pipe|rede|abast|esgoto|drenag|pluv|residu",
}
PAPEIS_BLOCO = {
    "sanita": r"sanit|sant|toilet|^wc",
    "lavatorio": r"lavat|basin",
    "banheira": r"banheir|bath",
    "duche": r"duche|shower",
    "porta": r"porta|door",
}
RE_GABINETE = re.compile(r"(&\s*associados|\blda\b|arquitet|engenharia|gabinete|atelier|projectos|projetos|consult)", re.I)


def _agora() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def padrao_ficheiro(nome: str) -> str:
    base = Path(nome).stem
    base = re.sub(r"^[0-9a-f]{8}-", "", base)  # prefixo de upload
    return re.sub(r"\d", "9", base)


def prefixos_layers(layers) -> list[str]:
    c = Counter()
    for l in layers:
        l = l.split("|")[-1]
        m = re.match(r"^([^A-Za-z]*[A-Za-z]{1,5})[_\-. ]", l)
        if m:
            c[m.group(1)] += 1
    return [p for p, n in c.most_common(6) if n >= 2]


def gabinete_de(legenda: dict, blocos: list[str], metadados: dict | None = None) -> tuple[str, str]:
    """(gabinete, evidência)."""
    for k, v in (metadados or {}).items():
        m = re.search(r"\|\s*([^|]*(?:&\s*Associados|Lda\.?|Arquitet\w*|Engenharia)[^|]*)", str(v), re.I)
        if m:
            return m.group(1).strip(), f"metadados do ficheiro ({k})"
    for k, v in legenda.items():
        if k.startswith("_"):
            continue
        if k in ("GABINETE", "PROJETISTA", "PROJECTISTA", "AUTOR", "EMPRESA") or RE_GABINETE.search(str(v)):
            if k not in ("REQUERENTE", "DESIGNAÇÃODOPROJECTO", "LOCALIZAÇÃO", "TITULO"):
                return str(v), f"legenda ({k})"
    for b in blocos:
        m = re.match(r"^layout[_\- ]?([A-Za-z]{2,8})$", b, re.I)
        if m:
            return m.group(1).upper(), f"bloco de folha '{b}'"
    return "", ""


def assinatura(res, ficheiro: str, metadados: dict | None = None) -> dict:
    leg = res.legenda or {}
    blocos = leg.get("_BLOCOS", [])
    layers = sorted(set(res.entidades.layer)) if not res.entidades.empty else []
    gab, evid = gabinete_de(leg, blocos, metadados)
    blocos_leg = [b for b in blocos if re.search(r"rotulo|r[óo]tulo|legenda|carimbo|dados a preencher|layout|title", b, re.I)]
    autores = sorted({leg[k] for k in ("EMISSOR", "DESENHADOR", "VERIFICAÇÃO", "VERIFICACAO", "AUTOR") if leg.get(k)})
    return dict(
        gabinete=gab, evidencia_gabinete=evid,
        especialidade=leg.get("ESPECIALIDADE", "") or especialidade_de_nome(ficheiro, layers),
        subespecialidade=leg.get("SUBESPECIALIDADE", ""),
        autores=autores, blocos_legenda=blocos_leg, prefixos_layers=prefixos_layers(layers),
        padrao_ficheiro=padrao_ficheiro(ficheiro),
    )


def especialidade_de_nome(ficheiro: str, layers=()) -> str:
    n = Path(ficheiro).stem.upper()
    tabela = [("EST", "ESTABILIDADE"), ("IHD", "INSTALAÇÕES HIDRÁULICAS"), ("ELE", "INSTALAÇÕES ELÉTRICAS"),
              ("ITED", "ITED"), ("AVAC", "AVAC"), ("GAS", "GÁS"), ("TER", "TÉRMICO"), ("ACU", "ACÚSTICO"),
              ("ARQ", "ARQUITETURA")]
    for k, v in tabela:
        if re.search(rf"(^|[-_ ]){k}([-_ ]|$)", n):
            return v
    if any(l.upper().startswith((".ARQ", "ARQ", "A-")) for l in layers):
        return "ARQUITETURA"
    return ""


def aprender(res) -> tuple[dict, dict]:
    """Layers e blocos que o desenho usa para cada papel."""
    e = res.entidades
    layers, blocos = {}, {}
    if e.empty:
        return layers, blocos
    cont = e.groupby("layer").size()
    for papel, rx in PAPEIS_LAYER.items():
        ls = [l for l in cont.index if re.search(rx, l.split("|")[-1], re.I)]
        if ls:
            layers[papel] = sorted(ls, key=lambda l: -cont[l])[:6]
    if not res.compartimentos.empty:
        lp = res.compartimentos.layer_poligono[res.compartimentos.layer_poligono != ""]
        if not lp.empty:
            layers["compartimentos"] = lp.value_counts().index[:3].tolist()
        et = e[e.handle.isin(res.compartimentos.handle_etiqueta)].layer
        if not et.empty:
            layers["etiquetas_area"] = et.value_counts().index[:3].tolist()
    nomes = e[e.tipo == "INSERT"].bloco.value_counts()
    for papel, rx in PAPEIS_BLOCO.items():
        bs = [b for b in nomes.index if re.search(rx, b, re.I)]
        if bs:
            blocos[papel] = bs[:6]
    return layers, blocos


class Registo:
    def __init__(self, caminho: str | Path | None = None):
        self.caminho = Path(caminho or CAMINHO_PADRAO)
        self.perfis: list[dict] = []
        if self.caminho.exists():
            try:
                self.perfis = json.loads(self.caminho.read_text(encoding="utf-8")).get("perfis", [])
            except Exception:
                self.perfis = []

    def guardar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps({"atualizado": _agora(), "perfis": self.perfis}, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    def importar(self, texto: str, guardar: bool = True) -> tuple[int, int]:
        """Junta perfis de outro registo (ex.: do PC para uma sessão, ou vice-versa).
        Perfis com o mesmo gabinete ou a mesma assinatura são fundidos. Devolve (novos, fundidos)."""
        outros = json.loads(texto).get("perfis", [])
        novos = fundidos = 0
        for o in outros:
            alvo = next((p for p in self.perfis if (o.get("gabinete") and p.get("gabinete")
                                                    and o["gabinete"].lower() == p["gabinete"].lower())
                         or (set(o.get("blocos_legenda", [])) & set(p.get("blocos_legenda", [])))
                         or (o.get("prefixos_layers") and o.get("prefixos_layers") == p.get("prefixos_layers"))), None)
            if alvo is None:
                o = dict(o, id=f"P{len(self.perfis) + 1:03d}")
                self.perfis.append(o)
                novos += 1
                continue
            for k in ("especialidades", "autores", "blocos_legenda", "prefixos_layers", "padroes_ficheiro"):
                alvo[k] = sorted(set(alvo.get(k, [])) | set(o.get(k, [])))
            for k in ("layers_conhecidos", "blocos_conhecidos"):
                for papel, v in o.get(k, {}).items():
                    alvo.setdefault(k, {})[papel] = sorted(set(alvo[k].get(papel, [])) | set(v))
            fich = {p["ficheiro"] for p in alvo.get("projetos", [])}
            alvo["projetos"] = alvo.get("projetos", []) + [p for p in o.get("projetos", []) if p["ficheiro"] not in fich]
            if o.get("gabinete") and not alvo.get("gabinete"):
                alvo["gabinete"], alvo["nome"] = o["gabinete"], o.get("nome", o["gabinete"])
            fundidos += 1
        if guardar:
            self.guardar()
        return novos, fundidos

    def to_json(self) -> str:
        return json.dumps({"atualizado": _agora(), "perfis": self.perfis}, ensure_ascii=False, indent=2)

    @staticmethod
    def _score(p: dict, a: dict) -> float:
        s = 0.0
        if a["gabinete"] and p.get("gabinete") and a["gabinete"].lower() == p["gabinete"].lower():
            s += 3
        if set(a["blocos_legenda"]) & set(p.get("blocos_legenda", [])):
            s += 2
        pa, pp = set(a["prefixos_layers"]), set(p.get("prefixos_layers", []))
        if pa and pp:
            s += 2 * len(pa & pp) / len(pa | pp)
        if a["padrao_ficheiro"] in p.get("padroes_ficheiro", []):
            s += 1
        return s

    def identificar(self, res, ficheiro: str, metadados: dict | None = None, guardar: bool = True) -> tuple[dict, bool]:
        """Associa o desenho a um perfil (cria-o se não existir). Devolve (perfil, novo)."""
        a = assinatura(res, ficheiro, metadados)
        best, sc = None, 0.0
        for p in self.perfis:
            s = self._score(p, a)
            if s > sc:
                best, sc = p, s
        novo = best is None or sc < 1.5
        if novo:
            pid = f"P{len(self.perfis) + 1:03d}"
            nome = a["gabinete"] or f"Projetista não identificado ({a['especialidade'] or 'especialidade ?'}; " \
                                   f"layers {', '.join(a['prefixos_layers'][:2]) or '-'})"
            best = dict(id=pid, nome=nome, gabinete=a["gabinete"], evidencia_gabinete=a["evidencia_gabinete"],
                        especialidades=[], autores=[], blocos_legenda=[], prefixos_layers=[], padroes_ficheiro=[],
                        layers_conhecidos={}, blocos_conhecidos={}, projetos=[], notas="", criado=_agora())
            self.perfis.append(best)
        # atualizar perfil
        if a["gabinete"] and not best.get("gabinete"):
            best["gabinete"], best["evidencia_gabinete"] = a["gabinete"], a["evidencia_gabinete"]
            if best["nome"].startswith("Projetista não identificado"):
                best["nome"] = a["gabinete"]
        for k_src, k_dst in (("especialidade", "especialidades"), ("padrao_ficheiro", "padroes_ficheiro")):
            if a[k_src] and a[k_src] not in best[k_dst]:
                best[k_dst].append(a[k_src])
        for k in ("autores", "blocos_legenda", "prefixos_layers"):
            best[k] = sorted(set(best.get(k, [])) | set(a[k]))
        lay, blo = aprender(res)
        for papel, ls in lay.items():
            best["layers_conhecidos"][papel] = sorted(set(best["layers_conhecidos"].get(papel, [])) | set(ls))[:12]
        for papel, bs in blo.items():
            best["blocos_conhecidos"][papel] = sorted(set(best["blocos_conhecidos"].get(papel, [])) | set(bs))[:12]
        leg = res.legenda or {}
        proj = dict(ficheiro=Path(ficheiro).name, especialidade=a["especialidade"], subespecialidade=a["subespecialidade"],
                    titulo=leg.get("TITULO", ""), data=leg.get("DATA", ""), revisao=leg.get("REVISÃO", leg.get("REVISAO", "")),
                    requerente=leg.get("REQUERENTE", ""), lido_em=_agora())
        best["projetos"] = [p for p in best["projetos"] if p["ficheiro"] != proj["ficheiro"]] + [proj]
        best["atualizado"] = _agora()
        if guardar:
            self.guardar()
        return best, novo

    def associar_documento(self, ficheiro: str, metadados: dict, tipo: str = "Mapa de Quantidades",
                           guardar: bool = True) -> dict | None:
        """Liga um documento (ex.: MQ) ao perfil cujo gabinete aparece nos metadados."""
        gab, ev = gabinete_de({}, [], metadados)
        if not gab:
            return None
        alvo = next((p for p in self.perfis if p.get("gabinete") and
                     (p["gabinete"].lower() in gab.lower() or gab.lower() in p["gabinete"].lower())), None)
        if alvo is None:
            return None
        if len(gab) > len(alvo["gabinete"]):
            alvo["gabinete"], alvo["evidencia_gabinete"] = gab, f"{alvo.get('evidencia_gabinete', '')}; {ev}"
            alvo["nome"] = gab
        pessoas = sorted({re.split(r"\s*\|", v)[0].strip() for v in metadados.values() if v})
        alvo["autores"] = sorted(set(alvo.get("autores", [])) | set(pessoas))
        alvo["projetos"] = [p for p in alvo["projetos"] if p["ficheiro"] != Path(ficheiro).name] + [dict(
            ficheiro=Path(ficheiro).name, especialidade=tipo, subespecialidade="", titulo=tipo, data="", revisao="",
            requerente="", lido_em=_agora())]
        if guardar:
            self.guardar()
        return alvo

    def ensinar_bloco(self, perfil_id: str, papel: str, bloco: str, guardar: bool = True) -> None:
        for p in self.perfis:
            if p["id"] == perfil_id:
                p["blocos_conhecidos"].setdefault(papel, [])
                if bloco not in p["blocos_conhecidos"][papel]:
                    p["blocos_conhecidos"][papel].append(bloco)
                p["atualizado"] = _agora()
        if guardar:
            self.guardar()

    def get(self, pid: str) -> dict | None:
        return next((p for p in self.perfis if p["id"] == pid), None)


def metadados_ficheiro(path: str | Path) -> dict:
    """Autor/último a guardar de um xls/xlsx (ajuda a identificar o gabinete do MQ)."""
    path = Path(path)
    out = {}
    try:
        if path.suffix.lower() == ".xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True)
            out = {"autor": wb.properties.creator or "", "ultimo_a_guardar": wb.properties.lastModifiedBy or ""}
        elif path.suffix.lower() == ".xls":
            import olefile
            with olefile.OleFileIO(str(path)) as ole:
                m = ole.get_metadata()
                dec = lambda b: b.decode("cp1252", "ignore") if isinstance(b, bytes) else (b or "")
                out = {"autor": dec(m.author), "ultimo_a_guardar": dec(m.last_saved_by)}
    except Exception:
        pass
    return {k: v for k, v in out.items() if v}
