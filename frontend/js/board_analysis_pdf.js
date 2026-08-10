/**
 * 板块分析 · 数据驱动 PDF 导出（jsPDF + jspdf-autotable，嵌入中文字体）
 * 主路径：按 lastResult 结构化画表并一键下载；失败时由 BoardAnalysis.exportViaPrint 兜底。
 */
(function (global) {
  const FONT_NAME = 'NotoSansSC';
  const FONT_FILE = 'NotoSansSC-Subset.ttf';
  const FONT_LOCAL_URL = 'assets/fonts/NotoSansSC-Subset.ttf';
  /**
   * CDN 兜底（TTF）：jsPDF 仅可靠支持 TTF/OTF，不可直接 addFont WOFF。
   * 优先仍用本地 vendor；CDN 仅在本地 404 时尝试。
   */
  const FONT_CDN_URL =
    'https://cdn.jsdelivr.net/gh/googlefonts/noto-cjk@Sans2.004/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf';
  const IDB_NAME = 'ba_pdf_font_cache_v1';
  const IDB_STORE = 'fonts';
  const IDB_KEY = 'NotoSansSC-Subset';

  const LIBS = [
    { ready: () => !!(global.jspdf && global.jspdf.jsPDF), src: 'js/vendor/jspdf.umd.min.js' },
    {
      ready: () => {
        const J = global.jspdf && global.jspdf.jsPDF;
        return !!(J && J.API && typeof J.API.autoTable === 'function');
      },
      src: 'js/vendor/jspdf.plugin.autotable.min.js',
    },
  ];

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.async = true;
      el.src = src;
      el.onload = () => resolve();
      el.onerror = () => reject(new Error(`加载脚本失败: ${src}`));
      document.head.appendChild(el);
    });
  }

  async function ensureLibs() {
    for (const lib of LIBS) {
      if (lib.ready()) continue;
      await loadScript(lib.src);
      if (!lib.ready()) throw new Error(`脚本已加载但 API 不可用: ${lib.src}`);
    }
  }

  function openIdb() {
    return new Promise((resolve) => {
      if (!global.indexedDB) {
        resolve(null);
        return;
      }
      const req = indexedDB.open(IDB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(IDB_STORE)) db.createObjectStore(IDB_STORE);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });
  }

  async function idbGet(key) {
    const db = await openIdb();
    if (!db) return null;
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, 'readonly');
        const req = tx.objectStore(IDB_STORE).get(key);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      } catch (_) {
        resolve(null);
      }
    });
  }

  async function idbSet(key, value) {
    const db = await openIdb();
    if (!db) return;
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, 'readwrite');
        tx.objectStore(IDB_STORE).put(value, key);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  }

  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    const chunk = 0x8000;
    let binary = '';
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  async function fetchArrayBuffer(url) {
    const res = await fetch(url, { cache: 'force-cache' });
    if (!res.ok) throw new Error(`字体下载失败 ${res.status}: ${url}`);
    return res.arrayBuffer();
  }

  /** 优先 IndexedDB → 本地 TTF → CDN WOFF */
  async function loadFontBase64() {
    const cached = await idbGet(IDB_KEY);
    if (cached && typeof cached === 'string' && cached.length > 1000) return cached;

    let buf;
    try {
      buf = await fetchArrayBuffer(FONT_LOCAL_URL);
    } catch (e) {
      console.warn('本地 PDF 字体不可用，尝试 CDN', e);
      buf = await fetchArrayBuffer(FONT_CDN_URL);
    }
    const b64 = arrayBufferToBase64(buf);
    await idbSet(IDB_KEY, b64);
    return b64;
  }

  function cell(v) {
    if (v == null || v === '') return '--';
    return String(v);
  }

  function rolesPlainText() {
    const el = document.getElementById('baRolesHost');
    if (!el) return '暂无短线角色';
    const t = String(el.innerText || el.textContent || '')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    return t || '暂无短线角色';
  }

  function buildMetaLines(host, payload) {
    const board = payload.board || {};
    const kindLabel = host.boardKind === 'concept' ? '概念板块' : '行业板块';
    const lines = [];
    lines.push(`类型：${kindLabel}`);
    if (board.multi_boards) {
      const n =
        board.board_count != null ? board.board_count : (board.selected_board_codes || []).length;
      lines.push(`已选板块：${n}`);
    } else {
      lines.push(`板块：${board.board_name || board.board_code || '--'}`);
      if (board.board_code) lines.push(`代码：${board.board_code}`);
    }
    const memberN =
      board.stock_count != null
        ? board.stock_count
        : payload.member_count != null
          ? payload.member_count
          : '--';
    lines.push(`成分池：${memberN}`);
    if (board.board_env_label) lines.push(`环境：${board.board_env_label}`);
    if (payload.asof) lines.push(`分析时间：${payload.asof}`);
    const selectedNames = (host.selectedBoardCodes || [])
      .map((c) => {
        const b = typeof host.boardByCode === 'function' ? host.boardByCode(c) : null;
        return b ? `${b.board_name || c}（${c}）` : c;
      })
      .join('、');
    if (selectedNames) lines.push(`所选：${selectedNames}`);
    return lines;
  }

  function strategyRows(host, strategy, items, boardFallback) {
    return (items || []).map((row) => {
      const code = row.code || row.stock_code || '';
      const name = row.name || row.stock_name || '';
      const stock = name ? `${code}\n${name}` : cell(code);
      const boardName = host.boardLabelForRow(row, boardFallback);
      const hit = host.hitLabel(strategy, row);
      const score = host.scoreDisplay(strategy, row);
      const lastClose = host.fmtPrice2(
        row.last_close ??
          row.close ??
          row.trade_advice?.reference_levels?.last_close ??
          row.latest_price
      );
      const roles = host.roleTextForPdf(row);
      const advice = row.trade_advice || {};
      const buy = advice.buy_zone?.label || (advice.summary || '').split('；')[0] || '--';
      const sell =
        advice.stop_zone?.label ||
        (advice.sell_triggers || []).map((x) => x.label).join('；') ||
        '--';
      return [
        stock,
        cell(boardName),
        cell(hit),
        cell(score),
        cell(lastClose),
        cell(roles),
        cell(buy),
        cell(sell),
      ];
    });
  }

  function addPageFooters(doc) {
    const pageCount = doc.internal.getNumberOfPages();
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFont(FONT_NAME, 'normal');
      doc.setFontSize(8);
      doc.setTextColor(100);
      doc.text(`第 ${i} / ${pageCount} 页`, pageWidth / 2, pageHeight - 6, { align: 'center' });
    }
    doc.setTextColor(15);
  }

  /**
   * @param {object} host BoardAnalysis（含 lastResult 与表格字段辅助方法）
   * @returns {Promise<string>} 文件名
   */
  async function exportFromHost(host) {
    if (!host || !host.lastResult || !host.lastResult.strategies) {
      throw new Error('请先完成板块分析再导出');
    }
    await ensureLibs();
    const fontB64 = await loadFontBase64();
    const { jsPDF } = global.jspdf;
    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    doc.addFileToVFS(FONT_FILE, fontB64);
    doc.addFont(FONT_FILE, FONT_NAME, 'normal');
    doc.setFont(FONT_NAME, 'normal');

    const payload = host.lastResult;
    const boardFallback = host.defaultBoardLabel(payload);
    const strategies = payload.strategies || {};
    const errors = payload.errors || {};
    const order = ['gms', 'urt', 'sbbr', 'rpe'];
    const labels = { gms: 'GMS', urt: 'URT', sbbr: 'SBBR', rpe: 'RPE' };
    const filename = typeof host.pdfFilename === 'function' ? host.pdfFilename() : '板块分析.pdf';
    const pageWidth = doc.internal.pageSize.getWidth();
    const marginX = 10;
    let y = 12;

    doc.setFontSize(16);
    doc.setTextColor(15, 23, 42);
    doc.text('板块分析结果', marginX, y);
    y += 8;

    doc.setFontSize(9);
    for (const line of buildMetaLines(host, payload)) {
      const wrapped = doc.splitTextToSize(line, pageWidth - marginX * 2);
      if (y + wrapped.length * 4.2 > 190) {
        doc.addPage();
        y = 12;
      }
      doc.text(wrapped, marginX, y);
      y += wrapped.length * 4.2;
    }
    y += 3;

    if (y > 170) {
      doc.addPage();
      y = 12;
    }
    doc.setFontSize(11);
    doc.setTextColor(30, 64, 175);
    doc.text('各板短线角色', marginX, y);
    y += 5;
    doc.setFontSize(8);
    doc.setTextColor(15, 23, 42);
    const rolesWrapped = doc.splitTextToSize(rolesPlainText(), pageWidth - marginX * 2);
    const maxRoleLines = 18;
    const roleShow =
      rolesWrapped.length > maxRoleLines
        ? rolesWrapped.slice(0, maxRoleLines).concat(['…（角色过多，完整内容见页面）'])
        : rolesWrapped;
    doc.text(roleShow, marginX, y);
    y += roleShow.length * 3.8 + 5;

    const head = [['股票代码/名称', '板块名', '命中', '得分', '收盘', '角色', '买点', '卖点/防守']];
    const tableOptsBase = {
      theme: 'grid',
      styles: {
        font: FONT_NAME,
        fontStyle: 'normal',
        fontSize: 7.5,
        cellPadding: 1.2,
        overflow: 'linebreak',
        valign: 'top',
        textColor: [15, 23, 42],
        lineColor: [226, 232, 240],
        lineWidth: 0.1,
      },
      headStyles: {
        font: FONT_NAME,
        fontStyle: 'normal',
        fillColor: [241, 245, 249],
        textColor: [15, 23, 42],
        fontSize: 8,
      },
      margin: { left: marginX, right: marginX, top: 12, bottom: 12 },
      columnStyles: {
        0: { cellWidth: 28 },
        1: { cellWidth: 32 },
        2: { cellWidth: 16 },
        3: { cellWidth: 28 },
        4: { cellWidth: 16 },
        5: { cellWidth: 22 },
        6: { cellWidth: 48 },
        7: { cellWidth: 48 },
      },
    };

    function ensureSpace(minY) {
      if (y > minY) {
        doc.addPage();
        y = 14;
      }
    }

    function drawSectionTitle(text, color) {
      ensureSpace(185);
      doc.setFont(FONT_NAME, 'normal');
      doc.setFontSize(10);
      doc.setTextColor(color[0], color[1], color[2]);
      doc.text(text, marginX, y);
      y += 4;
      doc.setTextColor(15, 23, 42);
    }

    function drawTable(body) {
      doc.autoTable({
        ...tableOptsBase,
        startY: y,
        head,
        body: body.length ? body : [['暂无命中', '', '', '', '', '', '', '']],
      });
      y = (doc.lastAutoTable && doc.lastAutoTable.finalY) || y;
      y += 6;
    }

    for (const key of order) {
      if (!strategies[key]) continue;
      const block = strategies[key];
      const err = errors[key];
      const title = `${labels[key]} 策略命中（${block.total || 0}）${err ? `（${err}）` : ''}`;
      drawSectionTitle(title, [30, 64, 175]);
      drawTable(strategyRows(host, key, block.items || [], boardFallback));

      if (key === 'sbbr' && (block.watch_items || []).length) {
        drawSectionTitle(`筑底关注（${block.watch_total || 0}）`, [71, 85, 105]);
        drawTable(strategyRows(host, key, block.watch_items || [], boardFallback));
      }
    }

    addPageFooters(doc);
    doc.save(filename);
    return filename;
  }

  global.BoardAnalysisPdf = {
    FONT_LOCAL_URL,
    FONT_CDN_URL,
    ensureLibs,
    loadFontBase64,
    exportFromHost,
  };
})(typeof window !== 'undefined' ? window : globalThis);
