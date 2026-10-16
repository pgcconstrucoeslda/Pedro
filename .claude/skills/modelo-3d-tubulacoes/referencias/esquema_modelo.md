# Esquema do `modelo.json` (fonte única de dados)

Unidades: metros (3 casas), DN em mm. Coordenadas no sistema da Etapa 2 (X direita da folha, Y topo, Z cota de projeto).
Status: `EXTRAIDO` | `INFERIDO` | `PENDENTE`. Sistemas: `HID-AF`, `SAN-ESG`, `SAN-VENT`, `DRE-PLU`, `DRE-AC`.
Disciplinas: `HID` (HID-AF), `SAN` (SAN-ESG, SAN-VENT), `DRE` (DRE-PLU, DRE-AC), `ARQ`.

Campos marcados (calc) são preenchidos por `verificar_modelo.py`; não escrever à mão.

```jsonc
{
  "meta": {
    "projeto": "Moradia unifamiliar",      // natureza + código; NUNCA cidade/país nem nome de pasta com localidade
    "codigo": "P-024",
    "rev": "R00", "data": "2026-10-16", "escala": "1:50", "folha": "MOD-3D-01",
    "unidade": "m",
    "origem": "Vértice externo SO da parede da garagem (ARQ 02, térreo)",
    "rn": "RN = piso acabado do térreo = ±0,000 (ARQ 05 Corte AA)",
    "z_terreno": -0.15,                     // nível do terreno fora dos polígonos de piso (ou usar pisos tipo 'terreno')
    "cores": { "HID-AF": "#1e88e5", "SAN-ESG": "#8d5a2b", "SAN-VENT": "#5f9e3a", "DRE-PLU": "#0f9b8e", "DRE-AC": "#8e44ad" },
    "cores_fonte": "Cores lidas das plantas (cor de traço RGB do PDF)",
    "declividades": [                       // das NOTAS das pranchas (citar)
      { "sistema": "SAN-ESG", "dn_min": 100, "dn_max": 999, "min": 0.01, "max": 0.05, "fonte": "SAN 01 nota 3" },
      { "sistema": "SAN-ESG", "dn_min": 0,   "dn_max": 99,  "min": 0.02, "max": 0.05, "fonte": "SAN 01 nota 3" }
    ],
    "tolerancia_continuidade": 0.01
  },
  "pranchas": [ { "codigo": "HID 02", "disciplina": "HID", "pavimento": "S", "titulo": "Planta Pavimento Superior", "curto": "HID 02 · Planta Superior", "escala": "1:50", "rev": "R01", "data": "2026-03-10", "arquivo": "HID-02.pdf", "pagina": 1, "vetorial": true, "texto": true,
      "registo": { "tx": 0.0, "ty": 0.0, "escala": 1.0, "rot": 0, "residuo_px": 1.2, "obs": "" } } ],
  "pavimentos": [ { "id": "T", "nome": "Térreo", "z_piso": 0.0, "z_forro": 2.70, "z_laje_fundo": 2.90, "z_laje_topo": 3.05, "fonte": "ARQ 05 Corte AA" } ],
  "niveis": [ { "pav": "T", "ambiente": "BWC01", "tipo": "piso", "z": -0.02, "fonte": "ARQ 02 cota -0,02", "status": "EXTRAIDO" } ],
  "pisos": [ { "id": "PS-T-01", "pav": "T", "ambiente": "Sala", "tipo": "piso", "z": 0.0, "esp": 0.10,
      "poly": [[0,0],[5,0],[5,4],[0,4]], "fonte": "ARQ 02" } ],      // tipo: piso | laje | terreno | cobertura
  "ambientes": [ { "id": "BWC01", "nome": "Banheiro social", "pav": "T", "pos": [2.1, 3.4] } ],
  "paredes": [ { "id": "W-T-001", "pav": "T", "a": [0,0], "b": [5,0], "esp": 0.15, "z0": 0.0, "z1": 2.90, "tipo": "parede", "fonte": "ARQ 02 vetor" } ],   // tipo: parede | muro
  "esquadrias": [ { "id": "ESQ-T-01", "ref": "P01", "tipo": "porta", "parede": "W-T-001", "centro": [2.0, 0.0],
      "largura": 0.80, "altura": 2.10, "peitoril": 0.0, "z_piso": 0.0, "status": "EXTRAIDO", "fonte": "Quadro de esquadrias ARQ 07" } ],
  "nos": [ { "id": "N-0001", "x": 1.0, "y": 2.0, "z": 0.35, "status": "EXTRAIDO", "memoria": "...", "limite_lote": false } ],
  "pontos": [ { "id": "HID-T-BWC01-001", "no": "N-0001", "tipo": "chuveiro", "sistema": "HID-AF", "dn": 25,
      "x": 1.0, "y": 2.0, "z": 2.20, "h": 2.20, "pav": "T", "ambiente": "BWC01", "prancha": "HID 05",
      "memoria": "X,Y: planta HID 02 registada; h=2,20 do isométrico ISO-02", "status": "EXTRAIDO", "motivo": "" } ],
  "trechos": [ { "id": "T-HID-0001", "sistema": "HID-AF", "dn": 25, "nos": ["N-0001","N-0002"], "pav": "T",
      "status": "EXTRAIDO", "prancha": "HID 02", "memoria": "...", "motivo": "", "embutido": "parede",  // parede | forro | piso | aparente | enterrado (opcional)
      "segmentos": [ { "a": [0,0,0], "b": [1,0,0], "enterrado": false } ],          // (calc)
      "comprimento": 1.0, "declividade": null } ],                                   // (calc)
  "loucas": [ { "id": "LC-T-BWC01-01", "tipo": "vaso", "pav": "T", "ambiente": "BWC01", "apoio": [1.0, 0.075], "normal": [0, 1],
      "largura": 0.36, "profundidade": 0.65, "altura": 0.40, "z": 0.0, "fonte": "ARQ 02 desenho", "status": "EXTRAIDO" } ],
      // tipos: vaso | bancada_1cuba | bancada_2cubas | tanque | maquina_lavar | banheira | chuveiro
  "equipamentos": [ { "id": "EQ-RI-01", "tipo": "reservatorio_inferior", "nome": "Reservatório inferior", "centro": [8,1,-0.8],
      "dims": [1.5, 1.2, 1.6], "rot": 0, "sistema": "HID-AF", "fonte": "HID 04 detalhe 2", "status": "EXTRAIDO" } ],
      // centro = centro geométrico; dims = [ao longo do eixo local x, local y, altura]; rot em graus (anti-horário)
  "divergencias": [ { "id": "DIV-001", "tipo": "Nível não cotado", "descricao": "...", "pranchas": ["SAN 01","ARQ 02"],
      "pos": [3,4,-0.4], "ids": ["T-SAN-0004"], "gravidade": "alta", "disciplinas": ["SAN","ARQ"] } ],
  "premissas": [ "Origem: ...", "Altura do ramal de AF no forro = +2,80 (INFERIDO: entre forro e laje)" ],
  "verificacoes": { },          // (calc) continuidade, pontos_sobre_trecho, declividades, loucas, locacao, resumo
  "locacao": { }                // (calc) por ponto: { "A": {...}, "B": {...}, "V": {...}, "apoio": "W-..", "obs": "" }
}
```

## Regras
- IDs de pontos, nós e trechos são permanentes: numa revisão, reaproveitar os IDs antigos (`ids_registo.json`), nunca renumerar.
- `pontos[].no` aponta para o nó onde o ponto está (o nó tem as mesmas coordenadas).
- Trechos de gravidade (SAN-ESG, DRE-PLU, DRE-AC): Z dos nós intermédios interpolado pelo comprimento entre nós com cota conhecida; registar a regra na `memoria` do nó.
- `nos[].limite_lote = true` só para nós na fronteira do lote (ligação à rede pública / rua).
- Paredes: `a`/`b` são o EIXO; faces a ±esp/2. Paredes inclinadas são segmentos genéricos.
- Louça: `apoio` = ponto médio da aresta traseira, SOBRE a face acabada; `normal` = vetor unitário para dentro do ambiente.
- `meta.projeto` e todos os textos: sem cidade, país ou localidade (incluindo nomes de pastas).
