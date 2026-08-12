/**
 * 个股分析 · 数据驱动 PDF 导出（复用 BoardAnalysisPdf 的 jsPDF / 中文字体封装）
 * 覆盖：策略分析 + 阻力支撑位 + 形态识别
 */
(function (global) {
  function cell(v) {
    if (v == null || v === '') return '--';
    return String(v);
  }

  function fmtPrice(v) {
    return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(2) : '--';
  }

  function plainFromEl(el) {
    if (!el) return '';
    return String(el.innerText || el.textContent || '')
      .replace(/\u00a0/g, ' ')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function core() {
    const api = global.BoardAnalysisPdf;
    if (!api || typeof api.createDoc !== 'function') {
      throw new Error('PDF 公共模块未加载，请刷新页面后重试');
    }
    return api;
  }

  function buildMetaLines(host) {
    const data = host.lastStrategy || {};
    const stock = data.stock || host.lastStock || {};
    const levels = (host.lastLevels && host.lastLevels.data) || {};
    const pattern = host.lastPattern || {};
    const lines = [];
    const code = stock.code || levels.stock_code || pattern.code || '';
    const name = stock.name || levels.stock_name || pattern.name || '';
    if (code || name) lines.push(`股票：${code}${name ? ` ${name}` : ''}`);
    if (data.trade_date) lines.push(`基准日：${data.trade_date}`);
    if (data.asof) lines.push(`分析时间：${data.asof}`);
    if (data.hit_count != null) lines.push(`策略命中：${data.hit_count}/4`);
    if (pattern.asof && pattern.asof !== data.trade_date) {
      lines.push(`形态基准日：${pattern.asof}`);
    }
    const PT = global.PatternTool;
    if (pattern.price_adjust && PT && typeof PT.adjustLabel === 'function') {
      lines.push(`形态口径：${PT.adjustLabel(pattern.price_adjust)}`);
    }
    return lines;
  }

  function strategyBody(host) {
    const data = host.lastStrategy;
    if (!data) return null;
    const order = ['rpe', 'sbbr', 'gms', 'urt'];
    const byKey = {};
    (data.results || []).forEach((r) => {
      if (r && r.strategy) byKey[r.strategy] = r;
    });
    return order.map((key) => {
      const r = byKey[key] || {
        strategy: key,
        name: key.toUpperCase(),
        hit: false,
        label: '--',
        score_display: '--',
        reason: '无结果',
      };
      const hit = r.error
        ? `失败`
        : r.hit
          ? cell(r.label || '命中')
          : '未命中';
      const reason = r.error ? cell(r.error) : cell(r.reason || '');
      return [cell(r.name || key.toUpperCase()), hit, cell(r.score_display || '--'), reason];
    });
  }

  function levelsTables(host) {
    const pack = host.lastLevels;
    if (!pack) return { error: null, sections: [] };
    if (pack.error && !pack.data) return { error: pack.error, sections: [] };
    const d = pack.data || {};
    const sections = [];
    const vp = d.volume_profile || {};
    const vpCmp = d.vp_vs_kde || {};
    const classic = d.classic_levels || {};
    const fib = classic.fibonacci || null;
    const pivot = classic.pivot || null;

    const supportRows = (d.support_levels || []).map((p, i) => [`支撑 ${i + 1}`, fmtPrice(p)]);
    const resistRows = (d.resistance_levels || []).map((p, i) => [`压力 ${i + 1}`, fmtPrice(p)]);
    sections.push({
      title: 'KDE 结构位',
      head: [['项目', '价格']],
      body: [
        ['现价', fmtPrice(d.current_price)],
        ['最近支撑', fmtPrice(d.nearest_support)],
        ['最近压力', fmtPrice(d.nearest_resistance)],
        ...supportRows,
        ...resistRows,
      ],
    });

    if (vp && (vp.ok || vp.poc != null)) {
      sections.push({
        title: 'Volume Profile（参考）',
        head: [['项目', '价格/说明']],
        body: [
          ['POC', fmtPrice(vp.poc)],
          ['VAL', fmtPrice(vp.val)],
          ['VAH', fmtPrice(vp.vah)],
          ['最近支撑', fmtPrice(vp.nearest_support)],
          ['最近压力', fmtPrice(vp.nearest_resistance)],
          [
            '回看',
            vp.bars_used != null || vp.lookback != null
              ? `${vp.bars_used != null ? vp.bars_used : vp.lookback} 日`
              : '--',
          ],
        ],
      });
      const alignTxt = (row) => {
        if (!row || row.kde == null || row.vp == null) return '--';
        return row.aligned ? '是' : '否';
      };
      const diffTxt = (row) => {
        if (!row || row.diff == null) return '--';
        const sign = Number(row.diff) > 0 ? '+' : '';
        const pct = row.diff_pct != null ? `（${Number(row.diff_pct).toFixed(2)}%）` : '';
        return `${sign}${fmtPrice(row.diff)}${pct}`;
      };
      sections.push({
        title: 'KDE ↔ VP 对比',
        head: [['', 'KDE', 'VP', '差值', '共振']],
        body: [
          [
            '支撑',
            fmtPrice(vpCmp.support && vpCmp.support.kde),
            fmtPrice(vpCmp.support && vpCmp.support.vp),
            diffTxt(vpCmp.support),
            alignTxt(vpCmp.support),
          ],
          [
            '压力',
            fmtPrice(vpCmp.resistance && vpCmp.resistance.kde),
            fmtPrice(vpCmp.resistance && vpCmp.resistance.vp),
            diffTxt(vpCmp.resistance),
            alignTxt(vpCmp.resistance),
          ],
        ],
      });
    } else if (vp && vp.reason) {
      sections.push({ note: `Volume Profile：${vp.reason}` });
    }

    if (fib) {
      const fibBody = [
        ['锚定', cell(fib.anchor_method === 'zigzag_fractal' ? 'ZigZag+分形' : fib.anchor_method)],
        ['高点', `${fmtPrice(fib.swing_high)}${fib.swing_high_date ? `（${fib.swing_high_date}）` : ''}`],
        ['低点', `${fmtPrice(fib.swing_low)}${fib.swing_low_date ? `（${fib.swing_low_date}）` : ''}`],
        ['最近支撑', fmtPrice(fib.nearest_support)],
        ['最近压力', fmtPrice(fib.nearest_resistance)],
      ];
      (fib.retracements || []).forEach((x) => {
        fibBody.push([`回撤 ${x.ratio}`, fmtPrice(x.price)]);
      });
      sections.push({ title: '黄金分割（ZigZag）', head: [['项目', '值']], body: fibBody });
    }
    if (pivot) {
      const pivBody = ['R3', 'R2', 'R1', 'P', 'S1', 'S2', 'S3']
        .filter((k) => pivot[k] != null)
        .map((k) => [k, fmtPrice(pivot[k])]);
      if (pivBody.length) {
        sections.push({ title: 'Pivot', head: [['级别', '价格']], body: pivBody });
      }
    }

    const cam = classic.camarilla || null;
    const atrPiv = classic.atr_pivot || null;
    if (cam) {
      const camBody = [
        [
          '最近支撑',
          fmtPrice(classic.nearest_cam_support != null ? classic.nearest_cam_support : cam.nearest_support),
        ],
        [
          '最近压力',
          fmtPrice(
            classic.nearest_cam_resistance != null
              ? classic.nearest_cam_resistance
              : cam.nearest_resistance
          ),
        ],
      ];
      ['R4', 'R3', 'R2', 'R1', 'S1', 'S2', 'S3', 'S4'].forEach((k) => {
        if (cam[k] != null) camBody.push([k, fmtPrice(cam[k])]);
      });
      if (atrPiv && atrPiv.atr != null) {
        camBody.push([
          'ATR-Pivot',
          `P=${fmtPrice(atrPiv.P)} ±1ATR R1/S1=${fmtPrice(atrPiv.R1)}/${fmtPrice(atrPiv.S1)}`
            + ` ±2ATR R2/S2=${fmtPrice(atrPiv.R2)}/${fmtPrice(atrPiv.S2)}（ATR=${fmtPrice(atrPiv.atr)}）`,
        ]);
      }
      sections.push({
        title: 'Camarilla（波动率修正）',
        head: [['项目', '价格/说明']],
        body: camBody,
      });
    }

    const conf = classic.confluence_zones || d.confluence_zones || null;
    if (conf && conf.ok) {
      const zoneTxt = (z) => {
        if (!z) return '--';
        return `${fmtPrice(z.center)} [${fmtPrice(z.low)}–${fmtPrice(z.high)}]`;
      };
      const confBody = [
        ['最近支撑带', zoneTxt(conf.nearest_support_zone)],
        ['最近压力带', zoneTxt(conf.nearest_resistance_zone)],
      ];
      const pushZones = (arr, tag) => {
        (arr || []).forEach((z, i) => {
          const src = (z.sources || []).join('+') || '--';
          const strength = z.strength != null ? z.strength : '--';
          confBody.push([`${tag}${i + 1}·强度${strength}·${src}`, fmtPrice(z.center)]);
        });
      };
      pushZones(conf.supports, '支撑');
      pushZones(conf.resistances, '压力');
      sections.push({
        title: '共振带',
        head: [['项目', '价格/区间']],
        body: confBody,
      });
    } else if (conf && conf.reason) {
      sections.push({ note: `共振带：${conf.reason}` });
    }

    if (pack.error) {
      sections.push({ note: `提示：${pack.error}` });
    }
    return { error: null, sections };
  }

  function patternBody(host) {
    const pack = host.lastPattern;
    if (!pack) return { error: null, rows: null, expert: '' };
    if (pack.error && !(pack.items && pack.items.length)) {
      return { error: pack.error, rows: null, expert: '' };
    }
    const PT = global.PatternTool;
    const items = pack.items || [];
    const visible =
      PT && typeof PT._activeHits === 'function' ? PT._activeHits(items) : items.filter(Boolean);
    const rows = (visible.length ? visible : items).map((r) => {
      const type =
        PT && typeof PT.typeLabel === 'function' ? PT.typeLabel(r.pattern_type) : cell(r.pattern_type);
      const status =
        PT && typeof PT.statusLabel === 'function' ? PT.statusLabel(r.status) : cell(r.status);
      const formed =
        PT && typeof PT.formedAtText === 'function' ? PT.formedAtText(r) : cell(r.formed_at);
      const levels =
        PT && typeof PT.keyLevelsText === 'function'
          ? PT.keyLevelsText(r.key_levels)
          : cell(r.key_levels);
      const reason =
        PT && typeof PT.reasonText === 'function' ? PT.reasonText(r) : cell(r.reason || r.message);
      return [
        cell(r.code || pack.code),
        cell(r.name || pack.name || '--'),
        cell(type),
        cell(status),
        cell(formed),
        r.confidence != null ? Number(r.confidence).toFixed(2) : '--',
        cell(levels),
        cell(reason),
      ];
    });
    let expert = '';
    if (PT && typeof PT.buildExpertAnalysis === 'function' && visible.length) {
      const a = PT.buildExpertAnalysis(visible);
      const parts = [];
      if (a.primaryLabel) parts.push(`主形态：${a.primaryLabel}${a.primaryConf ? `（置信度 ${a.primaryConf}）` : ''}`);
      if (a.shortTerm) parts.push(`短线：${a.shortTerm}`);
      if (a.mediumTerm) parts.push(`中线：${a.mediumTerm}`);
      if (a.keyLevelsRef) parts.push(`关键位置：${a.keyLevelsRef}`);
      if (a.risk) parts.push(a.risk);
      expert = parts.filter(Boolean).join('\n');
    }
    if (!expert) {
      expert = plainFromEl(document.querySelector('#ssaPatternHost .pattern-expert-analysis'));
    }
    return { error: pack.error || null, rows, expert, empty: !rows.length };
  }

  /**
   * @param {object} host StockMultiStrategy
   * @returns {Promise<string>} 文件名
   */
  async function exportFromHost(host) {
    if (!host || typeof host.hasExportableResult !== 'function' || !host.hasExportableResult()) {
      throw new Error('请先完成个股分析再导出');
    }
    const api = core();
    const FONT_NAME = api.FONT_NAME || 'NotoSansSC';
    const doc = await api.createDoc({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const filename =
      typeof host.pdfFilename === 'function' ? host.pdfFilename() : '个股分析.pdf';
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const marginX = 12;
    const maxY = pageHeight - 14;
    let y = 14;

    function ensureSpace(need) {
      if (y + need > maxY) {
        doc.addPage();
        y = 14;
      }
    }

    function drawTitle(text, size, color) {
      ensureSpace(size * 0.5 + 4);
      doc.setFont(FONT_NAME, 'normal');
      doc.setFontSize(size);
      doc.setTextColor(color[0], color[1], color[2]);
      doc.text(text, marginX, y);
      y += size * 0.45 + 2;
      doc.setTextColor(15, 23, 42);
    }

    function drawWrapped(text, fontSize, lineH) {
      doc.setFont(FONT_NAME, 'normal');
      doc.setFontSize(fontSize);
      const wrapped = doc.splitTextToSize(String(text || ''), pageWidth - marginX * 2);
      for (let i = 0; i < wrapped.length; i++) {
        ensureSpace(lineH + 1);
        doc.text(wrapped[i], marginX, y);
        y += lineH;
      }
    }

    function drawTable(head, body, colStyles) {
      ensureSpace(20);
      doc.autoTable({
        startY: y,
        head,
        body: body && body.length ? body : [['暂无数据']],
        theme: 'grid',
        styles: {
          font: FONT_NAME,
          fontStyle: 'normal',
          fontSize: 8,
          cellPadding: 1.4,
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
          fontSize: 8.5,
        },
        margin: { left: marginX, right: marginX, top: 12, bottom: 12 },
        columnStyles: colStyles || {},
      });
      y = (doc.lastAutoTable && doc.lastAutoTable.finalY) || y;
      y += 6;
    }

    drawTitle('个股分析结果', 16, [15, 23, 42]);
    doc.setFontSize(9);
    for (const line of buildMetaLines(host)) {
      drawWrapped(line, 9, 4.2);
    }
    y += 3;

    // —— 策略分析 ——
    drawTitle('一、策略分析', 12, [30, 64, 175]);
    if (host.lastStrategyError && !host.lastStrategy) {
      drawWrapped(`策略分析失败：${host.lastStrategyError}`, 9, 4.2);
      y += 2;
    } else {
      const body = strategyBody(host);
      if (body) {
        drawTable(
          [['策略', '命中', '得分', '说明']],
          body,
          { 0: { cellWidth: 22 }, 1: { cellWidth: 22 }, 2: { cellWidth: 36 }, 3: { cellWidth: 'auto' } }
        );
      } else {
        drawWrapped('暂无策略分析结果', 9, 4.2);
        y += 2;
      }
    }

    // —— 阻力支撑 ——
    drawTitle('二、阻力支撑位', 12, [30, 64, 175]);
    const lv = levelsTables(host);
    if (!host.lastLevels) {
      drawWrapped('本报告未包含阻力支撑结果', 9, 4.2);
      y += 2;
    } else if (lv.error) {
      drawWrapped(`阻力支撑计算失败：${lv.error}`, 9, 4.2);
      y += 2;
    } else if (!lv.sections.length) {
      drawWrapped('暂无阻力支撑数据', 9, 4.2);
      y += 2;
    } else {
      lv.sections.forEach((sec) => {
        if (sec.note) {
          drawWrapped(sec.note, 8.5, 4);
          y += 2;
          return;
        }
        drawTitle(sec.title, 10, [71, 85, 105]);
        drawTable(sec.head, sec.body);
      });
    }

    // —— 形态识别 ——
    drawTitle('三、形态识别', 12, [30, 64, 175]);
    const pt = patternBody(host);
    if (!host.lastPattern) {
      drawWrapped('本报告未包含形态识别结果', 9, 4.2);
    } else if (pt.error && !pt.rows) {
      drawWrapped(`形态识别失败：${pt.error}`, 9, 4.2);
    } else if (pt.empty) {
      drawWrapped('未识别到选定形态。', 9, 4.2);
      if (pt.error) drawWrapped(`提示：${pt.error}`, 8.5, 4);
    } else {
      drawTable(
        [['代码', '名称', '形态', '状态', '形成日', '置信度', '关键价', '说明']],
        pt.rows,
        {
          0: { cellWidth: 16 },
          1: { cellWidth: 18 },
          2: { cellWidth: 22 },
          3: { cellWidth: 16 },
          4: { cellWidth: 20 },
          5: { cellWidth: 14 },
          6: { cellWidth: 28 },
          7: { cellWidth: 'auto' },
        }
      );
      if (pt.expert) {
        drawTitle('形态解读', 10, [71, 85, 105]);
        drawWrapped(pt.expert, 8.5, 4);
      }
      if (pt.error) {
        y += 2;
        drawWrapped(`提示：${pt.error}`, 8.5, 4);
      }
    }

    if (typeof api.addPageFooters === 'function') api.addPageFooters(doc);
    doc.save(filename);
    return filename;
  }

  global.StockAnalysisPdf = {
    exportFromHost,
  };
})(typeof window !== 'undefined' ? window : globalThis);
