// Генератор демонстрационного PDF (без зависимостей). Helvetica/WinAnsi -> текст
// латиницей: задача демо-книги - проверить хранение PDF в 1С и открытие во
// внешнем просмотрщике, а не качество контента. Реальную книгу можно подменить.
const fs = require('fs');
const path = require('path');

const pages = [
  {
    title: '1C:Enterprise 8.3 - Application Development (demo excerpt)',
    lines: [
      'This is a placeholder book bundled with the learning platform to',
      'demonstrate the "book inside 1C" feature: a PDF stored in the',
      'infobase and opened in the external PDF viewer from the dashboard.',
      '',
      'Chapter 1. Metadata objects',
      'A configuration is a tree of metadata objects: catalogs, documents,',
      'registers, reports and data processors. Each object describes data',
      'structure and behaviour; the platform generates the database schema.',
      '',
      'Replace this file with a real textbook PDF via the material card.',
    ],
  },
  {
    title: 'Chapter 2. The query language',
    lines: [
      'Queries read data from the database in a declarative SQL-like',
      'language. A query has SELECT fields, FROM sources, WHERE filters,',
      'GROUP BY and ORDER BY clauses, and virtual tables for registers.',
      '',
      'Example:',
      '  SELECT Goods.Name, SUM(Sales.Amount) AS Total',
      '  FROM Document.Sales.Goods AS Sales',
      '  GROUP BY Goods.Name',
      '  ORDER BY Total DESC',
      '',
      'Prefer reading through references and caching repeated lookups.',
    ],
  },
  {
    title: 'Chapter 3. Managed forms',
    lines: [
      'Managed forms separate client and server contexts. Code runs',
      'either on the client (&AtClient) or on the server (&AtServer);',
      'data moves between them explicitly. Keep server calls coarse-',
      'grained to reduce round trips.',
      '',
      'Form items are bound to attributes via DataPath. Commands carry',
      'user intent; handlers dispatch them. For rich visuals an HTML',
      'document field can embed a small web UI (see the dashboards).',
      '',
      '-- End of demo excerpt --',
    ],
  },
];

// --- сборка PDF ---
const enc = (s) => Buffer.from(s, 'latin1');
const esc = (s) => s.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');

const objects = []; // строки тел объектов (без "N 0 obj")
function addObj(body) { objects.push(body); return objects.length; } // 1-based

const FONT_OBJ = 1; // зарезервируем номера ниже после подсчёта
// Порядок объектов: 1=Catalog, 2=Pages, 3=Font, далее по 2 на страницу.
const catalogNo = 1, pagesNo = 2, fontNo = 3;
const pageNos = [];
const contentNos = [];
let next = 4;
for (let i = 0; i < pages.length; i++) { pageNos.push(next++); contentNos.push(next++); }

const bodies = {};
bodies[catalogNo] = `<< /Type /Catalog /Pages ${pagesNo} 0 R >>`;
bodies[pagesNo] = `<< /Type /Pages /Kids [${pageNos.map((n) => `${n} 0 R`).join(' ')}] /Count ${pages.length} >>`;
bodies[fontNo] = `<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>`;

pages.forEach((pg, i) => {
  let cs = 'BT\n/F1 16 Tf\n50 790 Td\n(' + esc(pg.title) + ') Tj\n/F1 11 Tf\n';
  cs += '0 -28 TL\n'; // leading
  // первая строка тела
  pg.lines.forEach((ln, idx) => {
    cs += (idx === 0 ? '0 -10 Td\n' : '') + 'T*\n(' + esc(ln) + ') Tj\n';
  });
  cs += 'ET';
  const stream = `<< /Length ${Buffer.byteLength(cs, 'latin1')} >>\nstream\n${cs}\nendstream`;
  bodies[pageNos[i]] = `<< /Type /Page /Parent ${pagesNo} 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 ${fontNo} 0 R >> >> /Contents ${contentNos[i]} 0 R >>`;
  bodies[contentNos[i]] = stream;
});

const total = next - 1;
let pdf = '%PDF-1.4\n%\xE2\xE3\xCF\xD3\n';
const offsets = [];
for (let n = 1; n <= total; n++) {
  offsets[n] = Buffer.byteLength(pdf, 'latin1');
  pdf += `${n} 0 obj\n${bodies[n]}\nendobj\n`;
}
const xrefPos = Buffer.byteLength(pdf, 'latin1');
pdf += `xref\n0 ${total + 1}\n`;
pdf += '0000000000 65535 f \n';
for (let n = 1; n <= total; n++) {
  pdf += String(offsets[n]).padStart(10, '0') + ' 00000 n \n';
}
pdf += `trailer\n<< /Size ${total + 1} /Root ${catalogNo} 0 R >>\nstartxref\n${xrefPos}\n%%EOF`;

const out = path.join(__dirname, 'demo-1c-book.pdf');
fs.writeFileSync(out, enc(pdf));
console.log('written', out, Buffer.byteLength(pdf, 'latin1'), 'bytes,', pages.length, 'pages');
