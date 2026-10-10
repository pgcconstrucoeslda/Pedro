# Medições DWG × Mapa de Quantidades

Aplicação web que lê desenhos DWG/DXF, faz medições automáticas (áreas, perímetros, comprimentos,
contagens e grandezas derivadas) e compara-as com o Mapa de Quantidades (MQ) da obra, com
**rastreabilidade** de cada valor até à entidade do desenho (*handle*).

## Instalação

```bash
pip install -r requirements.txt
# conversor DWG -> DXF (escolha um):
#  a) ODA File Converter (gratuito): https://www.opendesign.com/guestfiles/oda_file_converter
#  b) LibreDWG:  ./scripts/install_libredwg.sh
streamlit run app.py
```

Sem conversor, pode exportar o DXF no AutoCAD (`SAVEAS` → DXF) e carregá-lo diretamente.

Linha de comandos (sem interface):

```bash
python -m medicoes_dwg.cli desenho.dwg mapa.xls -o relatorio.xlsx [--regras regras.xlsx] [--pe-direito 2.60]
```

## Fluxo de trabalho (etapas validáveis)

| # | Separador | O que validar |
|---|---|---|
| 1 | **Desenho** | Unidade (m/cm/mm), folhas detetadas e o **nível** de cada planta (Piso 1, R/C…), layers e blocos |
| 2 | **Compartimentos** | Área da etiqueta (`12.50m²`) vs área do polígono que a contém: desvios > 5 % = etiqueta desatualizada ou polígono errado |
| 3 | **Mapa de Quantidades** | Leitura do MQ + verificações formais (duplicados, itens sem unidade, numeração) |
| 4 | **Regras** | Ligação *artigo do MQ ↔ medição no desenho*; sugeridas automaticamente, editáveis, exportáveis para Excel e reutilizáveis |
| 5 | **Comparação** | Semáforo OK ≤ 3 % · ALERTA ≤ 10 % · CRÍTICO > 10 %; relatório Excel com fórmulas |

## Fontes de medição

| Fonte | Mede | Unid. |
|---|---|---|
| `AREA_COMPART` / `AREA_COMPART_GEOM` | área dos compartimentos (etiqueta / polígono) | m² |
| `PERIM_COMPART` | perímetro dos compartimentos | ml |
| `PAREDES_COMPART` | perímetro × fator (ex.: `PD`) − dedução (vãos) | m² |
| `COMPRIMENTO_LAYER` / `EIXO_LAYER` | comprimento de linhas no layer (eixo: fechadas ÷ 2) | ml |
| `AREA_LAYER` | área de tramas/polilinhas fechadas | m² |
| `CONTAGEM_BLOCOS` / `CONTAGEM_TEXTOS` | n.º de blocos / textos (regex) | un |
| `COMPRIMENTO_PAREDES` / `AREA_PAREDES` | paredes estimadas das tramas (comprimento e espessura), × PD | ml / m² |
| `VALOR_MANUAL` | valor medido à mão (fica registado) | — |

Filtros (`folhas`, `layers`, `filtro`, `excluir`) são expressões regulares. O campo `fator` aceita
números ou `PD` (pé-direito). Itens com o mesmo `grupo` comparam-se pela soma das quantidades do MQ.

## Relatório Excel

`Resumo` (avisos e incompatibilidades) · `Comparação` (fórmulas de desvio e estado) · `Detalhe medições`
(handle de cada entidade) · `Regras` · `Compartimentos` · `Paredes` · `Folhas` · `Layers` · `Blocos`.

Para localizar uma entidade no AutoCAD: `(command "_.SELECT" (handent "3DF1B") "")` ou o comando
`_ZOOM` → `_Object` após selecionar pelo handle.

## Limitações conhecidas

* Só se mede o que está desenhado de forma mensurável (polilinhas fechadas, tramas, blocos, etiquetas).
* Paredes a partir de tramas são **estimativas** (espessura média); verificar.
* Blocos sem nome reconhecível (ex.: `A$C0BD9282B`) não são identificados automaticamente: crie a regra
  com o nome do bloco visto no separador *Desenho*.
* A geometria em *paperspace* não é medida (apenas viewports usados para definir folhas).

## Estrutura

```
medicoes_dwg/
  converter.py   DWG -> DXF (ODA / LibreDWG)
  extractor.py   folhas, entidades, compartimentos, paredes
  mq_parser.py   leitura genérica do MQ + verificações
  rules.py       fontes de medição, aplicação e sugestão de regras
  compare.py     comparação e estados
  report.py      relatório Excel
  cli.py         linha de comandos
app.py           interface web (Streamlit)
tests/           teste com desenho sintético
```
