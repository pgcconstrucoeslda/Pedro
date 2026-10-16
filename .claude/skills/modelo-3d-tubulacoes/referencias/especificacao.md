# Especificação — Modelo 3D de tubulações a partir de pranchas 2D

> Texto normativo da rotina. Em caso de dúvida entre este ficheiro e o SKILL.md, vale este.

## PAPEL
Engenheiro de instalações prediais hidrossanitárias, com domínio de leitura de projeto e de modelação 3D para web. Tarefa: transformar as pranchas 2D num modelo 3D interativo de tubulação, para empreiteiros e executores de obra usarem no campo (telemóvel, tablet e portátil) e para o escritório conferir.

## PRINCÍPIOS (valem para tudo)
- A prancha é a fonte. Nada é inventado: o que não se lê na prancha entra como INFERIDO (com a regra escrita) ou como PENDENTE (com o motivo escrito).
- Status de cada ponto e trecho:
  - EXTRAÍDO: posição e altura lidas em prancha (cota, isométrico ou medida em escala sobre prancha registada).
  - INFERIDO: derivado por regra declarada, p. ex. "Z do ramal = +3,20, entre o forro (+2,90) e o fundo da laje (+3,48); cota não indicada".
  - PENDENTE: não determinável; o motivo vem escrito.
- Não atribuir a uma norma valor que não está nela. Altura usual de mercado é declarada como tal.
- Toda a quantidade e coordenada tem memória de cálculo (como X, Y e Z foram obtidos e em que prancha).
- Não identificar cidade nem país do projeto em nenhum entregável. A natureza do projeto pode aparecer.
- Antes de cada entrega: correr as verificações automáticas, fazer screenshots com navegador headless e olhar para as imagens. Não entregar sem ter visto o resultado.

## ENTRADAS (pasta do projeto)
- Arquitetura/: plantas, cortes, quadro de esquadrias (PDF vetorial). Única fonte de dimensões, níveis, paredes, portas e janelas.
- IHSD/: HID (água fria: plantas, cobertura/caixas, isométricos), SAN (esgoto e ventilação: plantas, detalhes, colunas), DRE (pluvial e drenos de ar condicionado).
- Ignorar Estrutural/ e Elétrico/, salvo para consultar níveis de laje.

## ETAPA 1 — INVENTÁRIO (parar e perguntar se faltar algo essencial)
1. Listar cada prancha: código, disciplina, pavimento, escala, revisão e data.
2. Ler legendas, notas e simbologia de cada disciplina. Símbolo sem legenda vira PENDENTE.
3. Verificar se as pranchas são vetoriais (pymupdf get_drawings) e se há texto extraível. Preferir sempre o vetor à imagem.
4. Se faltar algo essencial (corte com pé-direito, planta de um pavimento), parar e dizer o que falta.

## ETAPA 2 — SISTEMA DE COORDENADAS E NÍVEIS
- Origem (0,0,0): um vértice inequívoco da ARQ (p. ex. o ápice externo do térreo). Declarar qual foi escolhido. Unidade: metro, 3 casas. X para a direita da folha, Y para o topo da folha, Z = cota de projeto (RN declarada).
- Confirmar a escala da ARQ comparando os textos de cota com o comprimento vetorial das linhas de cota (relatar quantas cotas conferem a ±1 %).
- Registar cada planta de instalações sobre a ARQ por correlação de imagem (paredes da ARQ rasterizadas × prancha rasterizada; translação, escala nominal, rotação 0). Conferir com uma sobreposição visual por prancha e registar qualquer divergência de escala, rotação ou deslocamento.
- Tabela de níveis por pavimento, a partir de plantas e cortes: piso acabado de cada ambiente (atenção a pisos rebaixados, boxes, áreas externas e garagem), forro, fundo e topo de laje, laje das caixas de água, base das caixas. Cada nível com a fonte.
- Definir polígonos de piso/laje por pavimento e por nível (incluindo áreas rebaixadas e varandas sobre outros ambientes). Servem para: arquitetura, "cota vertical ao piso" e "trecho enterrado".

## ETAPA 3 — ARQUITETURA (contexto, não protagonista)
- Paredes: extrair do vetor da ARQ as linhas de parede pela espessura/cor de traço; agrupar pares paralelos em eixo + espessura (0,13 / 0,15 etc.); unir segmentos colineares. A casa NÃO é toda ortogonal: tratar paredes inclinadas como segmentos genéricos, nunca alinhadas a X/Y.
- Altura da parede: do piso do lado mais baixo até ao fundo da laje do pavimento. Fora da edificação = muro (altura adotada declarada).
- Portas e janelas: detetar vãos (intervalo entre segmentos colineares e vão entre extremidade livre e face de parede transversal). Associar cada vão à etiqueta mais próxima (P01, J03…) e aplicar largura, altura e peitoril do QUADRO DE ESQUADRIAS. Gerar verga e peitoril como volumes; janela com vidro translúcido; rótulo da esquadria acima do vão. Vão sem etiqueta: verga a 2,10 (INFERIDO). Etiqueta sem vão compatível: divergência.
- Lajes e pisos com os polígonos da Etapa 2. Nomes dos ambientes como rótulos discretos.
- Nada de mobiliário nem acabamento, exceto louças (Etapa 6).

## ETAPA 4 — PONTOS E TRECHOS (rede contínua)
Extração:
- Traços de tubagem por cor e espessura no vetor de cada planta. Quando o traço for um contorno duplo, calcular a linha de eixo pelo par de linhas paralelas. Quando for mancha/raster, esqueletizar a máscara de cor e simplificar (approxPolyDP). Converter para coordenadas do modelo pela transformação da Etapa 2.
- Textos de DN, rótulos de colunas (AF01, TQ02, TV03, AP04…), setas de declividade e "vem de / vai para".
- Isométricos: alturas (h=) de cada ponto e altura dos ramais internos dos banheiros. Seguir o traçado do isométrico: descida da coluna, registo a 1,90, ramal a 1,15–1,25, ramal baixo a ~0,60, derivações verticais para cada ponto. Altura de ramal não cotada no iso = medida em escala no iso (declarar).

Registo de cada ponto:
- ID hierárquico [SISTEMA]-[PAV]-[AMBIENTE]-[SEQ] (ex.: HID-T-BWC01-003). Os IDs nunca mudam depois de criados.
- Tipo, sistema (HID-AF, SAN-ESG, SAN-VENT, DRE-PLU, DRE-AC), DN, X, Y, Z, h sobre o piso, pavimento, ambiente, prancha de origem, memória de cálculo e status.

Rede (o mais importante):
- Modelar por NÓS partilhados: cada vértice é um nó nomeado e os trechos referenciam nós. A continuidade é garantida por construção.
- Água fria, sequência completa: rua → hidrómetro → tê → (a) subida direta para a caixa de água e (b) ramal enterrado até ao reservatório inferior com boia; reservatório inferior → válvula de pé → sucção → motobomba → recalque → caixa; barrilete → limpeza e extravasor → descidas das colunas → ramais de cada pavimento → pontos. Não deixar de fora a entrada da rua, o abastecimento do reservatório inferior nem o recalque.
- Desvios de coluna entre pavimentos: quando o XY de uma coluna muda entre plantas, procurar o desvio no isométrico. Se não houver, modelar como INFERIDO e registar divergência.
- Esgoto e pluvial por gravidade: cotas nos nós (saída do aparelho, caixa sifonada, coletor, base do TQ, fundo de caixa), Z intermédio interpolado pelo comprimento e declividade resultante calculada. Todas dentro do mínimo e do máximo das notas (ex.: 1–5 % Ø100; 2–5 % Ø<100). Quando a rede não fecha em nível (rede da frente mais alta que a caixa da área rebaixada), modelar queda dentro da caixa e registar divergência.
- Ventilação: ramais e colunas até ao topo acima da cobertura (altura da nota).
- Drenos de ar condicionado: rastrear até à caixa de destino, mesmo em traço sem legenda (registar divergência de simbologia).
- Só desenhar trechos que estejam na prancha. Ligação óbvia não desenhada = trecho INFERIDO.

Verificação automática de continuidade (obrigatória):
- Toda a extremidade de trecho toca outro trecho, um ponto ou um equipamento (tolerância de 1 cm). Listar as exceções; só são aceites nos limites do lote (rede pública, saída para a rua).
- Todo o ponto está sobre algum trecho.
- Nenhuma declividade fora do intervalo da nota.

## ETAPA 5 — VERIFICAÇÃO CRUZADA (divergências)
Listar com ID (DIV-001…), tipo, descrição, pranchas, posição XYZ, IDs relacionados, gravidade e DISCIPLINAS envolvidas (HID, SAN, DRE, ARQ). Procurar:
- ponto fora de parede ou de ambiente; ralo em ambiente seco;
- tubo de queda ou coluna sem correspondência entre pavimentos;
- condutor sem caixa de destino;
- contagem de pontos no isométrico ≠ planta;
- ARQ × instalações: fossa, poço, caixas de água, shafts citados em nota e não desenhados;
- diâmetros incoerentes; símbolo sem legenda; níveis não cotados que impedem fechar a rede;
- divergência de nomenclatura de ambientes.

## ETAPA 6 — LOUÇAS E EQUIPAMENTOS (contexto visual)
- Louças (sanita/vaso, bancada com 1 ou 2 cubas, tanque, máquina de lavar, banheira, chuveiro): posição e ORIENTAÇÃO lidas do desenho vetorial da ARQ. Cada louça é definida pelo ponto de apoio na face da parede + normal para dentro do ambiente, nunca pela "parede mais próxima do centro".
- Dimensões: as cotadas na ARQ. Se o texto da cota diferir do desenho, usar o desenho e registar a diferença. Sem cota: dimensão usual de mercado (declarar).
- Verificação geométrica obrigatória (shapely): nenhuma louça invade parede (área de interseção = 0) e todas encostam na face (folga ≤ 3 cm). Sobrepor as louças ao desenho da ARQ em imagens de conferência e olhar cada banheiro, cozinha e área de serviço, especialmente nas paredes inclinadas.
- Equipamentos como volumes: reservatório inferior, caixas de água, hidrómetro, motobomba, caixas de inspeção, de gordura e de passagem, fossa, filtro e sumidouro, com as dimensões dos detalhes.

## ETAPA 7 — SAÍDA
1. Fonte única de dados: um JSON embutido no HTML (`<script id="model" type="application/json">`) com pontos, trechos (com segmentos marcados como enterrados), níveis, divergências, paredes, esquadrias, pisos, louças, equipamentos, premissas, pranchas e verificações. O 3D é gerado só a partir dele. Exportável também em CSV (pontos, trechos, divergências, níveis).
2. Um único HTML autocontido, Three.js de versão fixa (r128: `three.min.js` via cdnjs; `OrbitControls.js` de `three@0.128.0` via jsDelivr, porque o cdnjs não o publica), a funcionar ao abrir o ficheiro, sem servidor.
3. HTML gerado por script (`template.html` + `build.py` que injeta o JSON), para reconstruir a cada correção.

## VISUALIZADOR — FUNCIONALIDADES
Cena:
- Arquitetura fantasma (preenchimento quase transparente e arestas finas); tubagem em destaque; grelha de base abaixo do piso; névoa leve.
- Cores das tubagens = cores das plantas de origem, por sistema (água fria, esgoto, ventilação, pluvial, dreno de AC), iguais nos dois temas.
- Convenções de traço: aparente/embutido = contínuo; abaixo do piso do térreo ou do terreno = TRACEJADO (segmento dividido no ponto exato onde cruza o nível); INFERIDO = PONTILHADO.
- Pontos: octaedro sólido = extraído; octaedro em wireframe com núcleo = inferido; cor de pendência com anel pulsante voltado à câmara = pendente. Ventilação com traço mais fino. Diâmetro visual proporcional ao DN.

Navegação e filtros:
- Vistas: Perspetiva, Planta (ortográfica), Sob o piso; Enquadrar; Tema (claro/escuro, respeitando prefers-color-scheme).
- Filtros por sistema, pavimento e status, com contagem de pontos, trechos e divergências. Camadas: arquitetura, nomes de ambientes, marcadores de divergência, louças e equipamentos, grelha.
- O filtro de sistema mostra/esconde também os marcadores e a lista de divergências dessa disciplina. Lista agrupada por disciplina. Divergência só de ARQ segue a camada de arquitetura. Clicar numa divergência liga as disciplinas dela e centra a câmara.
- Corte horizontal por pavimento, com deslizador da altura do plano.
- Busca por ID com sugestões.
- Seleção por proximidade em ecrã (tolerância em píxeis). Tooltip ao passar o cursor.
- prefers-reduced-motion: sem pulso, sem rotação, sem animação de câmara.

Medição com cotas:
- Botão "Medir"; Esc cancela.
- Snap por prioridade: ponto → vértice de trecho → eixo do trecho → superfície da arquitetura. Marcador sob o cursor indica o tipo capturado e a distância parcial. Shift trava o 2.º ponto no eixo dominante (X, Y ou Z).
- Cota no 3D: linha com traços oblíquos nas extremidades, linhas de chamada quando deslocada, rótulo sempre voltado à câmara com tamanho constante no ecrã, em metros com vírgula decimal. Opção de decompor em ΔX, ΔY, ΔZ encadeadas.
- Painel "Cotas": C-01, C-02… com início e fim (ID ou coordenada), 3D, horizontal, ΔX, ΔY, ΔZ. Clicar centra; excluir, limpar, mostrar/ocultar. Exportação CSV junto com o CSV de pontos. As cotas são da sessão e não alteram os dados do projeto.

Cotas de locação ao selecionar um ponto:
- Cotas PERPENDICULARES à face acabada das duas paredes mais próximas que não sejam paralelas entre si (A e B). Nunca X/Y.
- Ignorar paredes ocultas atrás de outra parede. Ponto embutido numa parede → "parede de apoio"; a cota vai às paredes transversais.
- Cota vertical: altura do ponto sobre o piso do ambiente (Z − h quando h é conhecido; senão o polígono de piso/terreno do pavimento). Abaixo do piso → profundidade.
- Testar os valores para todos os pontos e conferir alguns por cálculo independente.

Painel de registo em linguagem de campo:
- Topo: "Conforme projeto" / "Confirmar antes de executar" / "Não executar — pendente".
- Título sem siglas ("Ponto de chuveiro", "Tubo de esgoto"); abaixo: sistema · Ø mm e ambiente · pavimento.
- Medidas em número grande, 2 casas: altura do piso, "embutido na parede", até à parede (A e B). Tubo: comprimento, caimento e por onde passa (sobre o forro, na parede a X m do piso, enterrado, vertical).
- Motivo numa linha quando inferido ou pendente. "Ver na prancha" com folha curta (ex.: "HID 02 · Planta Superior"). Divergências ligadas.
- Coordenadas, código, vértices, memória de cálculo e nome completo das pranchas num bloco recolhido "Detalhes técnicos (escritório)".
- Painel direito minimizável (abre ao selecionar), abas Registo, Divergências, Cotas e Resumo. Resumo: contagem por sistema e status, extensão por sistema, verificações, níveis, premissas e pranchas.

## IDENTIDADE VISUAL
Ver `paleta.md`. Viewport de software BIM, tech e leve. Só a tubagem tem cor forte. IBM Plex Sans 400/500/600 (interface) e IBM Plex Mono 400/500 (IDs, números, coordenadas, DN). Painéis retos, sem sombra, borda 1px, cantoneiras de 9px na cor de destaque (superior esquerda e inferior direita). Painel de detalhe com borda superior de 2px na cor do sistema. Sem emoji nem ícones decorativos. Legenda fixa. Rodapé em células: Projeto | Rev. | Esc. | Data | Folha. Responsivo (no telemóvel os painéis viram blocos recolhíveis).

## VERIFICAÇÃO FINAL e ENTREGA
Ver SKILL.md.
