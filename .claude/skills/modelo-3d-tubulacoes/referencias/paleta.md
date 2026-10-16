# Paleta e identidade visual

Direção: viewport de software BIM, tech e leve. Só a tubagem tem cor forte; arquitetura e interface discretas.
Tokens definidos em `:root` do `template.html`; variante escura por `prefers-color-scheme` (salvo `data-theme="light"`) e por `data-theme="dark"`.

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--bg` | `#eef1f4` | `#0f141a` | fundo da cena e da página |
| `--bg2` | `#e2e7ec` | `#161d25` | barras, células do rodapé |
| `--panel` | `rgba(248,250,252,.84)` + blur 12px | `rgba(20,27,35,.82)` + blur 12px | painéis |
| `--line` | `#c7d0d9` | `#2a3541` | bordas 1px |
| `--text` | `#17202a` | `#e3e9ef` | texto |
| `--text2` | `#5a6774` | `#8a98a6` | texto secundário |
| `--accent` | `#0a7fa6` | `#3cc4e8` | seleção, cotas, cantoneiras |
| `--pend` | `#d9541e` | `#ff8a4c` | exclusiva para pendência e divergência |
| `--arq` | `#8795a3` | `#64748a` | arestas da arquitetura |
| `--grid` | `#c9d2db` | `#222c37` | grelha |

Tubagens (iguais nos dois temas; substituídas por `meta.cores` quando lidas das plantas):
- Água fria `HID-AF` `#1e88e5`
- Esgoto `SAN-ESG` `#8d5a2b`
- Ventilação `SAN-VENT` `#5f9e3a` (traço mais fino, 60 %)
- Pluvial `DRE-PLU` `#0f9b8e`
- Dreno de AC `DRE-AC` `#8e44ad`

Nenhuma cor de tubo pode ser laranja/vermelho-alaranjado (reservado a pendência). Se a planta usar laranja para um sistema, escurecer para castanho e declarar em `meta.cores_fonte`.

Tipografia: IBM Plex Sans 400/500/600 (interface), IBM Plex Mono 400/500 (IDs, números, coordenadas, DN). Caixa normal nos rótulos.
Painéis retos, sem sombra, borda 1px, cantoneiras 9px em `--accent` (superior esquerda e inferior direita). Painel de detalhe: borda superior 2px na cor do sistema do item. Sem emoji, sem ícones decorativos.
