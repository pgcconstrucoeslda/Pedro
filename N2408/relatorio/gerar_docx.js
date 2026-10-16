// Gera o relatório de incompatibilidades em Word a partir de conteudo.json
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, BorderStyle, ImageRun, PageOrientation, LevelFormat, Footer, PageNumber,
  PageBreak, VerticalAlign,
} = require('docx');

const dir = __dirname;
const c = JSON.parse(fs.readFileSync(path.join(dir, 'conteudo.json'), 'utf8'));
const FONT = 'Arial';
const AZUL = '1F3864';
const COR_PRIO = { Alta: 'F8CBAD', 'Média': 'FFE699', Baixa: 'E2EFDA' };

const t = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 20, bold: o.bold, color: o.color, italics: o.italics });
const p = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs, o)], spacing: { after: o.after ?? 120 }, alignment: o.align, ...(o.bullet ? { numbering: { reference: 'marcas', level: 0 } } : {}) });
const h = (text, level) => new Paragraph({ heading: level, children: [new TextRun({ text, font: FONT, bold: true, color: AZUL, size: level === HeadingLevel.HEADING_1 ? 28 : 24 })], spacing: { before: 240, after: 120 } });

const borda = { style: BorderStyle.SINGLE, size: 4, color: 'A6A6A6' };
const bordas = { top: borda, bottom: borda, left: borda, right: borda };

// Página paisagem A4: largura útil = 16838 - 2*1134 = 14570 DXA
const LARG = 14570;
const COLS = [700, 1400, 2550, 4400, 4220, 1300];
function cel(text, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA }, borders: bordas, verticalAlign: VerticalAlign.TOP,
    shading: o.fill ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fill } : undefined,
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    children: [new Paragraph({ children: [t(text, { size: 17, bold: o.bold, color: o.color })] })],
  });
}
const cabec = new TableRow({ tableHeader: true, children: ['Nº', 'Especialidade', 'Desenhos / referências', 'Incompatibilidade (evidência)', 'Ação pedida ao projetista', 'Prioridade'].map((x, i) => cel(x, COLS[i], { fill: AZUL, bold: true, color: 'FFFFFF' })) });
const linhas = c.itens.map((it) => new TableRow({ cantSplit: true, children: [
  cel(it.n, COLS[0], { bold: true }), cel(it.esp, COLS[1]), cel(it.des, COLS[2]), cel(it.txt, COLS[3]), cel(it.acao, COLS[4]), cel(it.prio, COLS[5], { fill: COR_PRIO[it.prio], bold: true }),
] }));
const tabela = new Table({ width: { size: LARG, type: WidthType.DXA }, columnWidths: COLS, rows: [cabec, ...linhas] });

// resumo por prioridade
const cont = {};
c.itens.forEach((i) => { cont[i.prio] = (cont[i.prio] || 0) + 1; });
const RC = [2000, 1500, 8000];
const resumo = new Table({ width: { size: RC.reduce((a, b) => a + b), type: WidthType.DXA }, columnWidths: RC, rows: [
  new TableRow({ children: ['Prioridade', 'Nº de itens', 'Critério'].map((x, i) => cel(x, RC[i], { fill: AZUL, bold: true, color: 'FFFFFF' })) }),
  ...['Alta', 'Média', 'Baixa'].map((k) => new TableRow({ children: [cel(k, RC[0], { fill: COR_PRIO[k], bold: true }), cel(String(cont[k] || 0), RC[1]), cel(c.prioridades[k], RC[2])] })),
] });

// pedidos agrupados por especialidade
const porEsp = {};
c.itens.forEach((i) => { (porEsp[i.esp] = porEsp[i.esp] || []).push(i); });
const pedidos = [];
for (const [esp, its] of Object.entries(porEsp)) {
  pedidos.push(p([t(esp, { bold: true, color: AZUL })], { after: 60 }));
  its.forEach((i) => pedidos.push(p([t(`${i.n} — `, { bold: true }), t(i.acao)], { bullet: true, after: 60 })));
}

const anexos = [];
c.anexos.forEach((a, k) => {
  const buf = fs.readFileSync(path.join(dir, a.img));
  const w = buf.readUInt32BE(16), hh = buf.readUInt32BE(20);
  const largura = 900, altura = Math.round(largura * hh / w);
  if (k > 0) anexos.push(new Paragraph({ children: [new PageBreak()] }));
  anexos.push(h(a.titulo, HeadingLevel.HEADING_2));
  anexos.push(new Paragraph({ children: [new ImageRun({ type: 'png', data: buf, transformation: { width: largura, height: Math.min(altura, 520) } })] }));
});

const doc = new Document({
  creator: 'N2408', title: c.titulo,
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  numbering: { config: [{ reference: 'marcas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [t('N2408 — Relatório de Incompatibilidades · pág. ', { size: 16, color: '808080' }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: '808080' })] })] }) },
    children: [
      new Paragraph({ children: [new TextRun({ text: c.titulo, font: FONT, size: 40, bold: true, color: AZUL })], spacing: { after: 60 } }),
      new Paragraph({ children: [t(c.subtitulo, { size: 24, color: '404040' })], spacing: { after: 200 }, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AZUL, space: 4 } } }),
      p([t('Data: ', { bold: true }), t(c.data), t('     Destinatários: ', { bold: true }), t(c.destinatarios)]),
      p([t('Elaborado por: ', { bold: true }), t('____________________')]),
      h('1. Objetivo', HeadingLevel.HEADING_1),
      ...c.objetivo.map((x) => p(x)),
      h('2. Âmbito e limitações', HeadingLevel.HEADING_1),
      ...c.ambito.map((x) => p(x, { bullet: true })),
      h('3. Resumo', HeadingLevel.HEADING_1),
      p(`Foram identificados ${c.itens.length} pontos a esclarecer:`),
      resumo,
      new Paragraph({ children: [new PageBreak()] }),
      h('4. Incompatibilidades e omissões', HeadingLevel.HEADING_1),
      tabela,
      p(c.metodo, { italics: true, size: 16, after: 120 }),
      new Paragraph({ children: [new PageBreak()] }),
      h('5. Pedidos de esclarecimento por especialidade', HeadingLevel.HEADING_1),
      ...pedidos,
      new Paragraph({ children: [new PageBreak()] }),
      h('6. Anexos', HeadingLevel.HEADING_1),
      ...anexos,
    ],
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(path.join(dir, 'N2408_Relatorio_Incompatibilidades.docx'), b); console.log('ok'); });
