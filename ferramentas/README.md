# Ferramentas PROBUILT

## gerar_orcamento.py: orçamento DRAFT a partir do mapa de quantidades

**Entradas**
- Mapa de quantidades do projetista (`.xlsx`). A folha é detetada automaticamente pelo cabeçalho *Descrição / Un / Quant.*; pode ser indicada com `--folha`.
- `BASE_PRECOS_PROBUILT_REAL_v1.xlsx` (folha `Base`).
- Folha de orçamento PROBUILT `_Produção_Folha_de_orçamento.xlsx` (folha `Orçamento`).

**Saída:** `ORC_vDRAFT.xlsx` com quatro folhas:

| Folha | Conteúdo |
|---|---|
| Orçamento | A estrutura de capítulos do MQ, as quantidades e os preços propostos (decomposição J–M), com as fórmulas originais da folha PROBUILT. As colunas O–U mostram o artigo da base, o score, o estado, a fiabilidade, a fonte e a linha do MQ. |
| Resumo | Custo, venda e margem por capítulo, e o número de artigos sem preço. |
| Rastreabilidade | Linha a linha: artigo do MQ → artigo da base, score e alternativas. |
| Omissões (rastreio) | Pontos da Checklist de Omissões não encontrados no MQ, para decidir se se incluem. |

**Estados do preço**
- **Proposto** (score ≥ 0,60): correspondência forte; o preço da base é preenchido.
- **A confirmar** (score ≥ 0,45): o preço é preenchido mas tem de ser validado. É também o estado quando o material é fornecido pelo dono de obra (a descrição fica a laranja).
- **Sem preço** (< 0,45): não é preenchido e conta no aviso *"Faltam N preços"*.

**Regras de correspondência:** semelhança de texto ponderada, com estas penalizações:
- unidade diferente;
- elemento construtivo diferente (parede, pavimento, teto…);
- natureza diferente (demolição vs. execução);
- título do artigo ausente da base.

**Correção em relação ao modelo:** a célula J3 ("Seco") passa a ler o custo total com encargos (`SUMPRODUCT(E, N)`). No modelo original lia `N539`, que está vazia, e por isso a margem dava sempre zero.

**Uso**
```
python3 gerar_orcamento.py --mq MQ.xlsx --base BASE_PRECOS_PROBUILT_REAL_v1.xlsx \
    --modelo _Produção_Folha_de_orçamento.xlsx --saida ORC_vDRAFT.xlsx --obra "Nome da obra" --cliente "Cliente"
```

**Validação feita (10/10/2026)**
- Ribeira (L99): 32 de 32 preços iguais aos do orçamento original, ligados ao artigo correto da base. O teste é parcialmente circular, porque esses preços estão na base.
- Sra. da Hora (apartamento, MQ do projetista): 3 propostos, 6 a confirmar e 14 sem preço. Nenhum artigo ficou como "Proposto" com uma correspondência errada.
