---
name: modelo-3d-tubulacoes
description: Transforma as pranchas 2D de instalações hidrossanitárias (água fria, esgoto, ventilação, pluvial, drenos de AC) e a arquitetura de um projeto num modelo 3D interativo de tubulação (HTML autocontido + CSV) para uso em obra e conferência no escritório. Usar quando o utilizador pedir "modelo 3D das tubulações", "3D hidráulico", "rede hidrossanitária em 3D", "visualizador de tubulações", ou quando a tarefa agendada encontrar um projeto novo com pasta IHSD/.
---

# Modelo 3D de tubulações a partir de pranchas 2D

Papel: engenheiro de instalações prediais hidrossanitárias com domínio de leitura de projeto e de modelação 3D para web.
Destino: empreiteiros e executores (telemóvel, tablet, portátil) e o escritório (conferência).

A especificação completa e normativa está em `referencias/especificacao.md`. **Ler esse ficheiro inteiro antes de começar.** Este SKILL.md é o roteiro de execução: ordem das etapas, scripts a usar, pontos de paragem e critérios de aceitação.

## Princípios (valem para tudo)

- A prancha é a fonte. Nada é inventado. O que não se lê na prancha entra como **INFERIDO** (com a regra escrita) ou **PENDENTE** (com o motivo escrito).
- Não atribuir a uma norma um valor que não está nela. Altura usual de mercado é declarada como tal.
- Toda a quantidade e coordenada tem memória de cálculo (como X, Y, Z foram obtidos e em que prancha).
- Não identificar cidade nem país do projeto em nenhum entregável (nem no nome da pasta de saída, nem no rodapé, nem nos CSV). A natureza do projeto pode aparecer ("Moradia unifamiliar"). Atenção: os nomes das pastas do Drive costumam ter a localidade — `meta.projeto` = natureza + código, nunca o nome da pasta.
- Não entregar sem ter corrido as verificações e **olhado** para os screenshots.

## Ferramentas (scripts desta skill)

Todos em `scripts/` (executar com `python3 -I <caminho>`; os PDF do cliente ficam numa pasta própria de trabalho, nunca dentro da pasta dos scripts):

| Script | Etapa | O que faz |
|---|---|---|
| `inventario.py` | 1 | Lista páginas de todos os PDF: vetorial?, texto?, código, escala, revisão, data (heurística por regex, a confirmar). Gera `inventario.csv/json` e PNG de cada folha. |
| `vetor.py` | 2–4 | Biblioteca: leitura de desenhos por cor/espessura, eixos de pares paralelos, esqueletização de raster, união de colineares, textos com posição. Tem CLI `cores` para listar cores/espessuras de uma página. |
| `escala_arq.py` | 2 | Confere a escala: texto de cota × comprimento vetorial da linha de cota (relata quantas conferem a ±1 %). |
| `registo.py` | 2 | Regista cada planta de instalações sobre a ARQ: paredes da ARQ (traço grosso) × base de arquitetura da folha (traço fino), mesma resolução por metro, correlação linear (translação, escala nominal, rotação 0). Deteta divergência de escala/rotação. Gera `<folha>_transf.json` e PNG de sobreposição. `--modo raster` para folhas digitalizadas; `--roi-*` para excluir carimbos. |
| `verificar_modelo.py` | 4–6 | Divide trechos em enterrado/não enterrado, verifica continuidade, pontos sobre trechos, declividades, louças (shapely), calcula cotas de locação de todos os pontos. Escreve o resultado em `verificacoes` e `locacao` do JSON. |
| `build.py` | 7 | Injeta o JSON no `template.html` → `modelo_3d_tubulacoes.html` e exporta `pontos.csv`, `trechos.csv`, `divergencias.csv`, `niveis.csv`. |
| `teste_visualizador.py` | Final | Playwright headless (Chromium): temas claro/escuro, consola sem erros, seleção, filtros por disciplina, corte, medição com Shift, Esc, exportações CSV, minimizar painel; screenshots. |
| `sobreposicao.py` | Final | Desenha trechos e pontos do modelo sobre cada planta de instalações (usa `pranchas[].transf` + `arquivo` + `pagina`). |

Esquema do JSON: `referencias/esquema_modelo.md`. Paleta e identidade visual: `referencias/paleta.md`. Exemplo funcional: `exemplo/modelo_exemplo.json`.

Dependências: `pip install pymupdf shapely opencv-python-headless scikit-image playwright numpy`. O Chromium já existe em `/opt/pw-browsers` nas sessões cloud (não correr `playwright install`).

## Autoteste da rotina (correr quando alterar scripts ou template)
```
python3 -I exemplo/gerar_exemplo.py /tmp/ex/modelo.json
python3 -I scripts/verificar_modelo.py /tmp/ex/modelo.json
python3 -I scripts/build.py /tmp/ex/modelo.json -o /tmp/ex/out
python3 -I scripts/teste_visualizador.py /tmp/ex/out/modelo_3d_tubulacoes.html -o /tmp/ex/out/_conf --three-dir <package>
python3 -I exemplo/gerar_pdfs_exemplo.py /tmp/ex/pdf     # ARQ + HID fictícios, origem HID em (185, 690) pt
python3 -I scripts/registo.py --arq /tmp/ex/pdf/Arquitetura/EX-ARQ-02.pdf --arq-transf /tmp/ex/pdf/arq_T_transf.json \
        --inst /tmp/ex/pdf/IHSD/EX-HID-02.pdf --inst-escala 50 -o /tmp/ex/pdf/_reg/HID02   # deve dar ≈ (185, 690)
python3 -I scripts/escala_arq.py /tmp/ex/pdf/Arquitetura/EX-ARQ-02.pdf --escala 50       # 5 de 6 conferem (a 2,60 está errada de propósito)
```
(`gerar_pdfs_exemplo.py` lê `exemplo/modelo_exemplo.json`; gerá-lo antes com `gerar_exemplo.py` sem argumentos.)

## Entradas (Google Drive)

Raiz dos projetos: pasta `00_CLIENTES` (ID `1WXACb787q_J2QYSy0_pIrRrkV6QffrcJ`). Cada projeto é uma subpasta com:
- `Arquitetura/` — plantas, cortes, quadro de esquadrias (PDF vetorial). Única fonte de dimensões, níveis, paredes, portas e janelas.
- `Especialidades/IHSD/` (ou `IHSD/` na raiz do projeto) — HID, SAN, DRE.
- Ignorar `Estrutural/` e `Elétrico/`, salvo para consultar níveis de laje.

Procedimento de leitura:
1. `mcp__Google_Drive__search_files` com `parentId = '<pasta>'` para percorrer as pastas (recursivo, à mão).
2. `mcp__Google_Drive__download_file_content` para cada PDF → base64 → gravar em `<scratchpad>/<projeto>/entrada/<disciplina>/<nome>.pdf`.
3. Saída: criar no Drive, dentro da pasta do projeto, a subpasta `Modelo 3D Tubulações` e carregar o HTML e os 4 CSV (`mcp__Google_Drive__create_file`, `disableConversionToGoogleType: true`, HTML como `text/html`, CSV como `text/csv`). Se já existir, criar `Rev.NN` dentro dela (nunca apagar o anterior).

## Etapas

Criar uma lista de tarefas (TaskCreate) com as etapas abaixo e marcar à medida que avançam. Antes de começar, fazer ao utilizador as perguntas estratégicas (ver "Perguntas iniciais"), salvo se a execução for da tarefa agendada (aí, registar as dúvidas no relatório em vez de perguntar).

### Etapa 1 — Inventário (PONTO DE PARAGEM)
1. `python3 -I scripts/inventario.py <pasta_entrada> -o <trabalho>/01_inventario` — confirmar à mão código, disciplina, pavimento, escala, revisão e data de cada folha (olhar para os PNG).
2. Ler legendas, notas e simbologia de cada disciplina (texto extraído + PNG). Símbolo sem legenda → PENDENTE.
3. Preferir sempre vetor a imagem. Página sem desenhos vetoriais → registar e usar raster (esqueletização).
4. Se faltar algo essencial (corte com pé-direito, planta de um pavimento, isométrico de um banheiro, quadro de esquadrias), **parar e dizer o que falta**. Na tarefa agendada: gerar só o relatório de inventário com a lista do que falta e terminar.

### Etapa 2 — Coordenadas e níveis
- Origem (0,0,0) num vértice inequívoco da ARQ (ex.: ápice externo do térreo). Declarar qual. Metros, 3 casas. X para a direita da folha, Y para o topo, Z = cota de projeto (RN declarada).
- `escala_arq.py` → relatar quantas cotas conferem a ±1 %.
- `registo.py` para cada planta de instalações × ARQ do mesmo pavimento → olhar para cada sobreposição; registar divergências de escala/rotação/deslocamento.
- Tabela de níveis (piso acabado por ambiente, rebaixos, boxes, exteriores, garagem, forro, fundo e topo de laje, laje e base das caixas de água), cada um com fonte.
- Polígonos de piso/laje por pavimento e por nível (inclui rebaixos e varandas sobre outros ambientes).

### Etapa 3 — Arquitetura (contexto)
Paredes do vetor (espessura/cor de traço) → pares paralelos → eixo + espessura → unir colineares; paredes inclinadas como segmentos genéricos. Altura: do piso do lado mais baixo ao fundo da laje; muros com altura adotada declarada. Vãos → etiqueta mais próxima → quadro de esquadrias (largura, altura, peitoril). Vão sem etiqueta: verga a 2,10 (INFERIDO). Etiqueta sem vão: divergência. Sem mobiliário.

### Etapa 4 — Pontos e trechos (rede contínua)
Seguir a especificação (secção ETAPA 4). Em resumo:
- Traços de tubo por cor/espessura; contorno duplo → eixo; raster → esqueleto + approxPolyDP; converter com a transformação do registo.
- Textos de DN, rótulos de colunas, setas de declividade, "vem de / vai para"; isométricos para alturas.
- IDs `[SISTEMA]-[PAV]-[AMBIENTE]-[SEQ]` imutáveis (manter um `ids_registo.json` entre revisões).
- Rede por NÓS partilhados. Água fria completa: rua → hidrómetro → tê → (a) caixa de água e (b) reservatório inferior; sucção → motobomba → recalque; barrilete → limpeza/extravasor → colunas → ramais → pontos.
- Esgoto/pluvial: cotas nos nós, Z interpolado pelo comprimento, declividade dentro das notas; queda dentro da caixa quando não fecha (divergência).
- Ventilação até acima da cobertura; drenos de AC até à caixa de destino.
- Só trechos da prancha; ligação óbvia não desenhada = INFERIDO.

### Etapa 5 — Divergências (DIV-001…)
Com tipo, descrição, pranchas, XYZ, IDs relacionados, gravidade (alta/média/baixa) e disciplinas (HID, SAN, DRE, ARQ). Lista de verificação na especificação.

### Etapa 6 — Louças e equipamentos
Ponto de apoio na face da parede + normal para dentro do ambiente (lidos do vetor da ARQ). Dimensões cotadas; sem cota → usual de mercado (declarar). Equipamentos como volumes com dimensões dos detalhes.

### Etapa 7 — Saída
1. Montar `modelo.json` (esquema em `referencias/esquema_modelo.md`).
2. `python3 -I scripts/verificar_modelo.py modelo.json` → corrige até não haver falhas (exceto pontas nos limites do lote marcadas `limite_lote: true`).
3. `python3 -I scripts/build.py modelo.json -o <saida> --proibir "<localidades>"` → HTML + CSV. `--proibir` leva as palavras de localidade do nome da pasta do projeto e do carimbo (o build falha se aparecerem).
4. `python3 -I scripts/teste_visualizador.py <saida>/modelo_3d_tubulacoes.html -o <saida>/_conferencia [--three-dir package]` → tem de terminar com `TODOS OS TESTES OK`. Se o CDN estiver bloqueado na sessão: `npm pack three@0.128.0 && tar xzf three-0.128.0.tgz` e passar `--three-dir package` (o HTML entregue continua a usar o CDN). **Abrir e olhar para cada screenshot** (Read nos PNG): visão geral, 2 banheiros, planta com corte, sob o piso, painel de campo (telemóvel e desktop), tema escuro.
5. `python3 -I scripts/sobreposicao.py modelo.json --pdf-dir <entrada> -o <saida>/_conferencia` → olhar para cada sobreposição; nada da prancha pode ter ficado de fora.
6. Corrigir e repetir 2–5 até estar limpo.

## Verificação final (relatar antes de entregar)
1. Continuidade: 0 pontas soltas, exceto limites do lote.
2. Declividades dentro das notas.
3. Louças: 0 invasão de parede, folga ≤ 3 cm.
4. Cotas de locação para todos os pontos (listar os sem parede de referência).
5. Playwright sem erros (claro e escuro) e funcionalidades testadas.
6. Screenshots vistos e corrigidos.
7. Sobreposição sobre cada planta conferida.

## Entrega
- Drive: `<projeto>/Modelo 3D Tubulações/` com `modelo_3d_tubulacoes.html`, `pontos.csv`, `trechos.csv`, `divergencias.csv`, `niveis.csv` (+ `_conferencia/` com screenshots e sobreposições, opcional).
- Resumo curto no chat, em lista por etapa: pontos por sistema e status, pendências, divergências por gravidade, premissas adotadas (origem, níveis, alturas inferidas).

## Perguntas iniciais (fazer antes de começar, num só AskUserQuestion)
1. Qual o projeto (pasta do Drive) e quais pavimentos entram?
2. Há revisão anterior do modelo a manter (IDs imutáveis)?
3. Cotas de projeto: qual a RN / cota do piso do térreo?
4. Notas de declividade e altura da ventilação acima da cobertura: confirmar se as notas das pranchas são as válidas.
5. Cores das plantas: usar as lidas das pranchas (padrão) ou cores próprias?

## Execução pela tarefa agendada
Ver `referencias/tarefa_agendada.md`: procura projetos em `00_CLIENTES` com IHSD e sem modelo (ou com PDF mais recente que o modelo), corre as etapas sem perguntas, para na Etapa 1 se faltar algo essencial, e grava sempre um `RELATORIO.md` na pasta de saída com o que foi feito e o que ficou pendente.
