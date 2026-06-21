// Пререндер страниц PDF-книги в PNG для просмотрщика 1С.
//
// Движок "Поля HTML-документа" 1С (WebKit) не рисует глифы PDF.js на canvas, но
// надёжно показывает картинки (<img>). Поэтому страницы книги рендерятся в PNG
// заранее (офлайн), кладутся рядом с PDF, а начальное наполнение грузит их в
// табличную часть СтраницыКниги справочника МатериалыБиблиотеки.
//
// Использование:
//   node fixtures/books/render_pdf_pages.mjs <путь-к-pdf> [масштаб=2]
// Пример:
//   node fixtures/books/render_pdf_pages.mjs fixtures/books/demo-1c-book.pdf
//
// Результат: рядом с <name>.pdf создаётся папка <name>/ с page-001.png, page-002.png, ...
// Требует разовой установки: npm i -g pdf-to-img  (или локально в этой папке).

import { pdf } from "pdf-to-img";
import { writeFileSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { dirname, basename, extname, resolve, join } from "node:path";

const pdfArg = process.argv[2];
const scale = Number(process.argv[3]) || 2;
if (!pdfArg) {
  console.error("Укажите путь к PDF: node render_pdf_pages.mjs <pdf> [scale]");
  process.exit(1);
}

const pdfPath = resolve(pdfArg);
const stem = basename(pdfPath, extname(pdfPath));     // demo-1c-book
const outDir = join(dirname(pdfPath), stem);          // .../books/demo-1c-book

if (existsSync(outDir)) { rmSync(outDir, { recursive: true, force: true }); }
mkdirSync(outDir, { recursive: true });

const doc = await pdf(pdfPath, { scale });
let n = 0;
for await (const png of doc) {
  n++;
  const name = join(outDir, "page-" + String(n).padStart(3, "0") + ".png");
  writeFileSync(name, png);
}
console.log("OK: " + n + " стр. -> " + outDir + " (scale " + scale + ")");
