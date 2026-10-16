# Execução pela tarefa agendada

A tarefa agendada abre uma sessão nova (sem conversa anterior) e segue este guia. Não faz perguntas ao utilizador: tudo o que normalmente seria perguntado vai para o `RELATORIO.md`.

## 1. Encontrar trabalho
1. Listar as pastas de projeto em `00_CLIENTES` (ID `1WXACb787q_J2QYSy0_pIrRrkV6QffrcJ`): `search_files` com `parentId = '<id>' and mimeType = 'application/vnd.google-apps.folder'`.
2. Em cada projeto, procurar a pasta de instalações: `Especialidades/IHSD`, `IHSD`, ou pastas `HID`/`SAN`/`DRE` dentro de `Especialidades`. Sem PDF de instalações → ignorar o projeto.
3. Procurar a pasta de saída `Modelo 3D Tubulações` no projeto:
   - não existe → projeto candidato (modelo novo);
   - existe → candidato só se algum PDF de `Arquitetura/` ou das instalações tiver `modifiedTime` mais recente que o `RELATORIO.md` mais recente da saída (nova revisão).
4. Processar **no máximo 1 projeto por execução** (o mais antigo pendente). Se não houver candidatos, terminar sem criar nada e sem notificar.

## 2. Executar
1. Descarregar os PDF para `<scratchpad>/<codigo>/entrada/` (Arquitetura/, IHSD/…; ignorar Estrutural/ e Elétrico/ salvo para níveis de laje).
2. Instalar dependências: `pip install pymupdf shapely opencv-python-headless scikit-image playwright numpy`.
3. Seguir o SKILL.md, etapas 1 a 7, com estas regras:
   - Etapa 1: se faltar algo essencial (planta de um pavimento, corte com pé-direito, isométricos), **parar**: gravar só o inventário e o `RELATORIO.md` com a lista do que falta.
   - Revisão: se já existir modelo anterior, descarregar o `modelo.json` da última `Rev.NN` e reaproveitar os IDs (nunca renumerar).
   - Dúvidas que seriam perguntas → seguir a opção mais conservadora (marcar INFERIDO/PENDENTE) e listar no relatório em "Perguntas para o engenheiro".
4. `build.py` com `--proibir` contendo: cada palavra do nome da pasta do projeto que seja localidade, a cidade/concelho/freguesia/país que aparecer no carimbo ou na implantação. `meta.projeto` = natureza + código (ex.: "Moradia unifamiliar · P-024"), nunca o nome da pasta.
5. Correr `teste_visualizador.py` (no ambiente cloud o CDN pode estar bloqueado: `npm pack three@0.128.0 && tar xzf three-0.128.0.tgz` e passar `--three-dir package`) e `sobreposicao.py`; olhar para todas as imagens; corrigir e repetir até `TODOS OS TESTES OK`.

## 3. Entregar no Drive
Criar `Modelo 3D Tubulações/Rev.NN/` (NN = 00, 01, … seguinte ao existente) dentro da pasta do projeto e carregar:
- `modelo_3d_tubulacoes.html` (`text/html`, `disableConversionToGoogleType: true`)
- `pontos.csv`, `trechos.csv`, `divergencias.csv`, `niveis.csv` (`text/csv`, sem conversão)
- `modelo.json` (para a próxima revisão manter os IDs)
- `RELATORIO.md` (`text/markdown`, sem conversão)
- opcional: `_conferencia/` com os screenshots e sobreposições.

## 4. RELATORIO.md (sempre, mesmo quando para na Etapa 1)
Em lista por etapa:
1. Inventário: pranchas lidas (código, disciplina, pavimento, escala, rev., data) e o que falta.
2. Coordenadas e níveis: origem escolhida, RN, cotas que conferem a ±1 %, registo de cada planta (resíduo, divergências de escala/rotação).
3. Pontos por sistema e status; trechos e extensão por sistema.
4. Divergências por gravidade (lista DIV-xxx).
5. Verificação final (os 7 itens do SKILL.md com OK/FALHA).
6. Premissas adotadas (alturas inferidas, níveis).
7. Perguntas para o engenheiro.

## 5. Notificação
Terminar com um resumo de 5–8 linhas: projeto (sem localidade), revisão, pontos por status, divergências altas, pendências, link da pasta no Drive.
