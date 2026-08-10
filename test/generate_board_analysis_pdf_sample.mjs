/**
 * 离线生成样例 PDF（与前端同源：jsPDF + autotable + NotoSansSC 子集），
 * 供 test_board_analysis_pdf_extract.py 用 pypdf 校验中文可提取。
 *
 * 优先使用 test/node_modules 中的 jspdf；否则用 frontend/js/vendor UMD（需浏览器桩）。
 */
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import vm from 'vm';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'test', '_tmp_board_analysis_sample.pdf');
const require = createRequire(import.meta.url);

function loadVendorJsPdf() {
  const sandbox = {
    console,
    navigator: { userAgent: 'node' },
    location: { href: 'http://localhost/', origin: 'http://localhost' },
    document: {
      createElement: () => ({
        style: {},
        setAttribute() {},
        click() {},
        dispatchEvent() {},
      }),
      createEvent: () => ({ initMouseEvent() {} }),
    },
    HTMLAnchorElement: function HTMLAnchorElement() {},
    Blob: class Blob {
      constructor(parts, opts) {
        this.parts = parts;
        this.type = (opts && opts.type) || '';
      }
    },
    FileReader: class FileReader {
      readAsDataURL() {
        this.result = 'data:application/octet-stream;base64,AA==';
        if (this.onloadend) this.onloadend();
      }
    },
    XMLHttpRequest: class XMLHttpRequest {
      open() {}
      send() {
        this.status = 404;
      }
      set responseType(_) {}
    },
    URL: { createObjectURL: () => 'blob:mock', revokeObjectURL() {} },
    webkitURL: { createObjectURL: () => 'blob:mock', revokeObjectURL() {} },
    atob: (s) => Buffer.from(s, 'base64').toString('binary'),
    btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
    TextEncoder,
    TextDecoder,
    Uint8Array,
    ArrayBuffer,
    DataView,
    Promise,
    setTimeout,
    clearTimeout,
  };
  sandbox.self = sandbox;
  sandbox.window = sandbox;
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  // 故意不提供 module/exports，走 UMD 浏览器分支挂到 sandbox.jspdf
  for (const rel of [
    'frontend/js/vendor/jspdf.umd.min.js',
    'frontend/js/vendor/jspdf.plugin.autotable.min.js',
  ]) {
    const code = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    vm.runInNewContext(code, sandbox, { filename: rel });
  }
  const jsPDF = sandbox.jspdf && sandbox.jspdf.jsPDF;
  if (!jsPDF) throw new Error('vendor jsPDF 未加载');
  return jsPDF;
}

function loadJsPdf() {
  try {
    const { jsPDF } = require('jspdf');
    require('jspdf-autotable');
    return jsPDF;
  } catch (_) {
    return loadVendorJsPdf();
  }
}

function main() {
  const jsPDF = loadJsPdf();
  if (!jsPDF.API || typeof jsPDF.API.autoTable !== 'function') {
    throw new Error('jspdf-autotable 未挂载');
  }

  const fontPath = path.join(ROOT, 'frontend/assets/fonts/NotoSansSC-Subset.ttf');
  const fontB64 = fs.readFileSync(fontPath).toString('base64');
  const FONT = 'NotoSansSC';
  const FONT_FILE = 'NotoSansSC-Subset.ttf';

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  doc.addFileToVFS(FONT_FILE, fontB64);
  doc.addFont(FONT_FILE, FONT, 'normal');
  doc.setFont(FONT, 'normal');

  doc.setFontSize(16);
  doc.text('板块分析结果', 10, 14);
  doc.setFontSize(9);
  doc.text('类型：行业板块 · 所选：半导体（BK0447） · 成分池：120 · 分析时间：2026-08-10', 10, 22);
  doc.setFontSize(11);
  doc.setTextColor(30, 64, 175);
  doc.text('各板短线角色', 10, 30);
  doc.setTextColor(15, 23, 42);
  doc.setFontSize(8);
  doc.text('短线角色 半导体：龙头 688981 中芯国际 (+2.10%) · 中军 002371 北方华创 (+1.20%)', 10, 36);

  doc.autoTable({
    startY: 42,
    theme: 'grid',
    styles: { font: FONT, fontSize: 8, cellPadding: 1.2, overflow: 'linebreak' },
    headStyles: { font: FONT, fillColor: [241, 245, 249], textColor: [15, 23, 42] },
    head: [['股票代码/名称', '板块名', '命中', '得分', '收盘', '角色', '买点', '卖点/防守']],
    body: [
      [
        '688981\n中芯国际',
        '半导体',
        '左侧',
        '总分 82.5',
        '48.60',
        '龙头',
        '买点区间 47.20–48.10',
        '防守 45.80',
      ],
      [
        '002371\n北方华创',
        '半导体',
        '右侧',
        '总分 76.0',
        '320.50',
        '中军',
        '买点区间 315.00–322.00',
        '防守 305.00',
      ],
    ],
    margin: { left: 10, right: 10 },
  });

  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont(FONT, 'normal');
    doc.setFontSize(8);
    doc.text(
      `第 ${i} / ${pageCount} 页`,
      doc.internal.pageSize.getWidth() / 2,
      doc.internal.pageSize.getHeight() - 6,
      { align: 'center' }
    );
  }

  const data = doc.output('arraybuffer');
  fs.writeFileSync(OUT, Buffer.from(data));
  console.log('Wrote', OUT, 'bytes', fs.statSync(OUT).size);
}

main();
