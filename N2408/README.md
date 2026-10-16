# N2408 — Hostel Bonfim · Medições a partir dos DWG

- `N2408_Medicoes_DWG.xlsx` — folha de medições (Resumo, famílias, Verificações, Rastreio por handle CAD).
- `verificacao/` — imagens: verde = hatch com legenda, vermelho = sem legenda (handle + área).
- `manifesto.tsv` — ficheiros do Drive (ID, pasta, tamanho).
- `scripts/` — pipeline:
  1. `decode.py` — descodifica os downloads do Google Drive para `dwg/`.
  2. CADCraft (`cadcraft-cli convert x.dwg x.dxf`) — DWG → DXF.
  3. `extrair.py` / `correr_todos.sh` — mede entidades e classifica pela legenda → `json/`.
  4. `construir_excel.py` — gera a folha Excel (fórmulas SUMIFS/COUNTIFS).
  5. `mapa_verificacao.py` — imagens de verificação.

Os DWG/DXF e ficheiros intermédios não estão no repositório (ver `.gitignore`).
