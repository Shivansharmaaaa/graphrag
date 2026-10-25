// Shared docx building blocks for the Review-III report and user manual (Review-I house style:
// Times New Roman 12 pt, 1.5 line spacing, navy headings, A4, running header and page footer).
const {
  Document, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, Header, Footer,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType, VerticalAlign, PageNumber,
  LevelFormat, TabStopType, PageBreak,
} = require("docx");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { Packer } = require("docx");

const A4W = 11906;
const A4H = 16838;
const M = 1134;
const CW = A4W - 2 * M; // 9638 twips of text width
const CW_PX = 640; // the same width in 96-dpi pixels, for images

const NAVY = "0F2A47";
const ACCENT = "1B4F72";
const HEAD = "E8EEF4";
const ALT = "F7F5F1";
const MUTED = "4A5560";
const FONT = "Times New Roman";
const MONO = "Courier New";

const thin = { style: BorderStyle.SINGLE, size: 4, color: "A0A7B0" };
const borders = { top: thin, bottom: thin, left: thin, right: thin };

const run = (text, o = {}) => new TextRun({ font: FONT, size: 24, ...o, text });
const runB = (text, o = {}) => run(text, { bold: true, ...o });
const runI = (text, o = {}) => run(text, { italics: true, ...o });
const code = (text, o = {}) => new TextRun({ font: MONO, size: 20, ...o, text });

// "plain **bold** `code`" -> runs
function rich(text, o = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(run(text.slice(last, m.index), o));
    const t = m[0];
    out.push(t.startsWith("**") ? runB(t.slice(2, -2), o) : code(t.slice(1, -1), o.size ? { size: o.size - 2 } : {}));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(run(text.slice(last), o));
  return out;
}

function p(text, extra = {}) {
  const children = typeof text === "string" ? rich(text) : text;
  return new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 160, line: 340 }, ...extra, children });
}

function h1(text, opts = {}) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: !!opts.newPage,
    spacing: { before: 320, after: 180 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NAVY, space: 4 } },
    children: [new TextRun({ text, font: FONT, size: 32, bold: true, color: NAVY })],
  });
}
const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: 240, after: 120 },
  children: [new TextRun({ text, font: FONT, size: 26, bold: true, color: ACCENT })],
});
const h3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3, keepNext: true, spacing: { before: 180, after: 80 },
  children: [new TextRun({ text, font: FONT, size: 24, bold: true, italics: true, color: "1A1A1A" })],
});

const caption = (text) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 60, after: 240 },
  children: [run(text, { italics: true, size: 20 })],
});

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

function figure(file, widthPx = CW_PX, alt = "") {
  const { w, h } = pngSize(file);
  const height = Math.round((widthPx * h) / w);
  return new Paragraph({
    alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 40 },
    children: [new ImageRun({
      type: "png", data: fs.readFileSync(file), transformation: { width: widthPx, height },
      altText: { title: alt, description: alt, name: alt },
    })],
  });
}

const bullet = (text, ref = "bullets", level = 0) => new Paragraph({
  numbering: { reference: ref, level }, spacing: { after: 70, line: 300 },
  children: typeof text === "string" ? rich(text) : text,
});

function cell(content, w, { header = false, fill = "FFFFFF", center = false, size = 20 } = {}) {
  const children = (Array.isArray(content) ? content : [content]).map((c) => (c instanceof Paragraph ? c : new Paragraph({
    alignment: header || center ? AlignmentType.CENTER : AlignmentType.LEFT,
    spacing: { after: 0, line: 260 },
    children: typeof c === "string" ? rich(c, { size, bold: header }) : [c],
  })));
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: { fill: header ? HEAD : fill, type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER, margins: { top: 50, bottom: 50, left: 80, right: 80 }, children,
  });
}

// rows[0] is the header row; cells are strings ("**bold** `code`" allowed) or TableCell
function table(colWidths, rows, { size = 20, center = [] } = {}) {
  return new Table({
    width: { size: colWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: colWidths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0, cantSplit: true,
      children: r.map((c, j) => (c instanceof TableCell ? c : cell(String(c), colWidths[j], {
        header: i === 0, fill: i > 0 && i % 2 === 0 ? ALT : "FFFFFF", center: center.includes(j), size,
      }))),
    })),
  });
}

// shaded call-out box (single-cell table)
function callout(lines, { fill = "EEF3F8", border = ACCENT } = {}) {
  const b = { style: BorderStyle.SINGLE, size: 6, color: border };
  return new Table({
    width: { size: CW, type: WidthType.DXA }, columnWidths: [CW],
    rows: [new TableRow({ children: [new TableCell({
      borders: { top: b, bottom: b, left: { style: BorderStyle.SINGLE, size: 24, color: border }, right: b },
      shading: { fill, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 },
      width: { size: CW, type: WidthType.DXA },
      children: lines.map((t) => new Paragraph({ spacing: { after: 60, line: 300 }, children: typeof t === "string" ? rich(t, { size: 22 }) : t })),
    })] })],
  });
}

// monospace block (commands, sample output)
function codeBlock(lines) {
  const b = { style: BorderStyle.SINGLE, size: 4, color: "C8CDD3" };
  return new Table({
    width: { size: CW, type: WidthType.DXA }, columnWidths: [CW],
    rows: [new TableRow({ children: [new TableCell({
      borders: { top: b, bottom: b, left: b, right: b }, shading: { fill: "F4F5F7", type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 140, right: 140 }, width: { size: CW, type: WidthType.DXA },
      children: lines.map((t) => new Paragraph({ spacing: { after: 0, line: 250 }, children: [code(t, { size: 18 })] })),
    })] })],
  });
}

const spacer = (after = 160) => new Paragraph({ spacing: { after }, children: [] });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

const LIST = (ref, format, text) => ({
  reference: ref,
  levels: [
    { level: 0, format, text, alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 640, hanging: 320 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1100, hanging: 300 } } } },
  ],
});

function makeDocument({ children, headerLeft, headerRight, footerLeft, numbered = [] }) {
  const small = { size: 16, color: MUTED };
  return new Document({
    creator: "Shivansh Sharma, Himali Sharma, Aayush Sinha",
    title: headerLeft,
    styles: {
      default: { document: { run: { font: FONT, size: 24 } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 32, bold: true, font: FONT, color: NAVY }, paragraph: { spacing: { before: 320, after: 180 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 26, bold: true, font: FONT, color: ACCENT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 24, bold: true, italics: true, font: FONT }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
      ],
    },
    numbering: {
      config: [LIST("bullets", LevelFormat.BULLET, "•"),
        ...numbered.map((ref) => LIST(ref, LevelFormat.DECIMAL, "%1."))],
    },
    sections: [{
      properties: { titlePage: true, page: { size: { width: A4W, height: A4H }, margin: { top: M, right: M, bottom: M, left: M } } },
      headers: {
        first: new Header({ children: [new Paragraph({ children: [] })] }),
        default: new Header({ children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: CW }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 4 } }, spacing: { after: 80 },
          children: [run(headerLeft, small), run(`\t${headerRight}`, small)],
        })] }),
      },
      footers: {
        first: new Footer({ children: [new Paragraph({ children: [] })] }),
        default: new Footer({ children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: CW }],
          border: { top: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 6 } }, spacing: { before: 80 },
          children: [run(footerLeft, small), run("\tPage ", small),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: MUTED })],
        })] }),
      },
      children,
    }],
  });
}

// Write <out>.docx and <out>.pdf (LibreOffice), then find the page of each contents entry in the
// PDF. If any page moved, re-run the calling script once so the contents table shows real pages.
async function publish(doc, out, sections, cacheFile, script) {
  fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
  const previous = fs.existsSync(cacheFile) ? JSON.parse(fs.readFileSync(cacheFile, "utf8")) : {};
  fs.writeFileSync(`${out}.docx`, await Packer.toBuffer(doc));
  execFileSync("soffice", ["--headless", "--convert-to", "pdf", "--outdir", path.dirname(out), `${out}.docx`], { stdio: "ignore" });
  const pages = execFileSync("pdftotext", ["-layout", `${out}.pdf`, "-"], { encoding: "utf8" }).split("\f");
  const norm = (t) => t.replace(/\s+/g, " ").trim();
  const found = {};
  for (const s of sections) {
    const i = pages.findIndex((pg, k) => k > 1 && pg.split("\n").some((ln) => norm(ln) === norm(s)));
    if (i >= 0) found[s] = i + 1;
  }
  fs.writeFileSync(cacheFile, JSON.stringify(found, null, 2));
  if (sections.some((s) => previous[s] !== found[s]) && !process.env.ONE_PASS) {
    execFileSync(process.execPath, [script], { stdio: "inherit", env: { ...process.env, ONE_PASS: "1" } });
    return;
  }
  console.log(`wrote ${out}.docx and .pdf — ${pages.filter((t) => t.trim()).length} pages`);
}

const tocFrom = (cacheFile) => (fs.existsSync(cacheFile) ? JSON.parse(fs.readFileSync(cacheFile, "utf8")) : {});

module.exports = {
  publish, tocFrom,
  A4W, CW, CW_PX, NAVY, ACCENT, MUTED, run, runB, runI, code, rich, p, h1, h2, h3, caption, figure,
  bullet, cell, table, callout, codeBlock, spacer, pageBreak, makeDocument, Paragraph, AlignmentType, BorderStyle,
};
