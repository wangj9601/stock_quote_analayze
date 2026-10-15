/**
 * 指数分析 · 数据驱动 PDF（复用 BoardAnalysisPdf / jsPDF）
 * 覆盖：抬头、市场环境研判、广度/强弱/行业贡献、波段摘要、形态摘要、关位要点、江恩
 */
(function (global) {
  function cell(v) {
    if (v == null || v === '') return '--';
    return String(v);
  }

  function fmtNum(v, digits) {
    if (v == null || !Number.isFinite(Number(v))) return '--';
    return Number(v).toFixed(digits != null ? digits : 2);
  }

  function fmtPct(v) {
    if (v == null || !Number.isFinite(Number(v))) return '--';
    const n = Number(v);
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(2)}%`;
  }

  function core() {
    const api = global.BoardAnalysisPdf;
    if (!api || typeof api.createDoc !== 'function') {
      throw new Error('PDF 公共模块未加载，请刷新页面后重试');
    }
    return api;
  }

  /**
   * @param {object} host IndexAnalysis（需 lastBundle / lastCode / hasExportableResult）
   * @returns {Promise<string>} 文件名
   */
  async function exportFromHost(host) {
    if (!host || typeof host.hasExportableResult !== 'function' || !host.hasExportableResult()) {
      throw new Error('请先完成指数分析再导出');
    }
    const data = host.lastBundle || {};
    const idx = data.index || {};
    const api = core();
    const FONT_NAME = api.FONT_NAME || 'NotoSansSC';
    const doc = await api.createDoc({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const filename =
      typeof host.pdfFilename === 'function'
        ? String(host.pdfFilename()).replace(/\.png$/i, '.pdf')
        : `指数分析_${idx.code || host.lastCode || 'index'}.pdf`;

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

    // —— 抬头 ——
    drawTitle('指数分析报告', 16, [15, 23, 42]);
    const metaLines = [
      `指数：${cell(idx.code)}${idx.name ? ` ${idx.name}` : ''}${idx.ts_code ? `（${idx.ts_code}）` : ''}`,
      `点位：${fmtNum(idx.current != null ? idx.current : idx.last_close)}  涨跌幅：${fmtPct(idx.change_percent)}`,
      `基准日：${cell(data.trade_date)}${data.use_realtime ? '（含实时叠 K）' : ''}`,
      `日线根数：${cell(data.bar_count)}`,
    ];
    metaLines.forEach((line) => drawWrapped(line, 9, 4.2));
    y += 2;
    drawWrapped('说明：本报告描述指数环境与技术结构，不构成买卖或仓位建议。', 8, 3.8);
    y += 3;

    // —— 市场环境 ——
    drawTitle('一、指数环境研判', 12, [30, 64, 175]);
    const mv = data.market_view || {};
    if (!mv.ok) {
      drawWrapped(mv.error || '环境研判暂不可用', 9, 4.2);
    } else {
      drawWrapped(`结论：${cell(mv.bias_label || '中性')} — ${cell(mv.summary)}`, 9, 4.2);
      y += 1;
      (mv.bullets || []).forEach((b) => drawWrapped(`· ${b}`, 8.5, 4));
      y += 2;
      drawWrapped('仅作环境对照，请结合个股与仓位纪律独立判断。', 8, 3.8);
    }
    y += 2;

    // —— 广度 / 贡献 ——
    drawTitle('二、成分广度与行业贡献', 12, [30, 64, 175]);
    const br = data.breadth || {};
    if (!br.available) {
      drawWrapped(br.reason || '暂无成分数据，广度与贡献章节从略。', 9, 4.2);
    } else {
      drawTable(
        [['指标', '数值']],
        [
          ['成分数 / 有行情', `${cell(br.member_count)} / ${cell(br.quoted_count)}`],
          ['上涨 / 下跌 / 平盘', `${cell(br.up_count)} / ${cell(br.down_count)} / ${cell(br.flat_count)}`],
          ['上涨占比', br.up_ratio != null ? `${(br.up_ratio * 100).toFixed(1)}%` : '--'],
          ['涨跌幅中位数', fmtPct(br.median_change_percent)],
          ['涨跌幅均值', fmtPct(br.avg_change_percent)],
        ],
        { 0: { cellWidth: 40 }, 1: { cellWidth: 'auto' } }
      );
    }

    const leaders = data.leaders || {};
    if (leaders.available) {
      drawTitle('涨幅前列', 10, [71, 85, 105]);
      drawTable(
        [['代码', '名称', '涨跌幅']],
        (leaders.gainers || []).slice(0, 8).map((s) => [
          cell(s.code),
          cell(s.name),
          fmtPct(s.change_percent),
        ]),
        { 0: { cellWidth: 22 }, 1: { cellWidth: 40 }, 2: { cellWidth: 22 } }
      );
      drawTitle('跌幅前列', 10, [71, 85, 105]);
      drawTable(
        [['代码', '名称', '涨跌幅']],
        (leaders.losers || []).slice(0, 8).map((s) => [
          cell(s.code),
          cell(s.name),
          fmtPct(s.change_percent),
        ]),
        { 0: { cellWidth: 22 }, 1: { cellWidth: 40 }, 2: { cellWidth: 22 } }
      );
    }

    const sector = data.sector_contrib || {};
    drawWrapped(
      sector.disclaimer || '行业贡献按成分成交额加权近似，非官方指数权重。',
      8,
      3.8
    );
    y += 1;
    if (!sector.available) {
      drawWrapped(sector.reason || '暂无行业贡献数据', 9, 4.2);
    } else {
      drawTable(
        [['行业', '家数', '额权涨跌', '近似贡献']],
        (sector.items || []).slice(0, 15).map((it) => [
          cell(it.board_name || it.board_code),
          cell(it.member_count),
          fmtPct(it.weighted_change_percent),
          it.approx_contribution != null ? Number(it.approx_contribution).toFixed(3) : '--',
        ]),
        {
          0: { cellWidth: 40 },
          1: { cellWidth: 16 },
          2: { cellWidth: 24 },
          3: { cellWidth: 24 },
        }
      );
    }
    y += 2;

    // —— 波段 ——
    drawTitle('三、价格行为 · 波段与趋势', 12, [30, 64, 175]);
    const swing = data.swing || {};
    const swPayload = swing.payload || swing.data || {};
    const ms = swPayload.market_structure || {};
    if (!swing.ok) {
      drawWrapped(swing.error || '波段分析暂不可用', 9, 4.2);
    } else {
      drawWrapped(
        `日线结构：${cell(ms.trend || ms.trend_label || '--')}；周线：${cell(
          (swPayload.weekly && (swPayload.weekly.trend || swPayload.weekly.trend_label)) || '--'
        )}`,
        9,
        4.2
      );
      if (swPayload.counter_trend_note) {
        drawWrapped(`提示：${swPayload.counter_trend_note}`, 8.5, 4);
      }
      const contrast = ms.pattern_contrast;
      if (contrast && (contrast.note || contrast.text)) {
        drawWrapped(`与形态对照：${cell(contrast.note || contrast.text)}`, 8.5, 4);
      }
      drawWrapped('详情图表见页面「波段与趋势」区块。', 8, 3.8);
    }
    y += 2;

    // —— 形态 ——
    drawTitle('四、价格行为 · 形态识别', 12, [30, 64, 175]);
    const pattern = data.pattern || {};
    if (!pattern.ok) {
      drawWrapped(pattern.error || '形态识别暂不可用', 9, 4.2);
    } else {
      const items = pattern.items || (pattern.payload && pattern.payload.items) || [];
      const tactical = pattern.tactical || (pattern.payload && pattern.payload.tactical) || {};
      drawWrapped(
        `有效形态 ${items.length} 个；短线偏向：${cell(
          tactical.short_bias || tactical.bias || '--'
        )}`,
        9,
        4.2
      );
      if (tactical.summary || tactical.note) {
        drawWrapped(cell(tactical.summary || tactical.note), 8.5, 4);
      }
      const rows = items.slice(0, 12).map((h) => [
        cell(h.type_zh || h.type || h.name || '--'),
        cell(h.status || '--'),
        cell(h.bias || h.direction || '--'),
        cell(h.formed_at || h.asof || h.date || '--'),
      ]);
      if (rows.length) {
        drawTable(
          [['形态', '状态', '偏向', '形成/基准']],
          rows,
          {
            0: { cellWidth: 36 },
            1: { cellWidth: 22 },
            2: { cellWidth: 22 },
            3: { cellWidth: 28 },
          }
        );
      } else {
        drawWrapped('当前窗口内无有效形态命中。', 9, 4.2);
      }
    }
    y += 2;

    // —— 关位 ——
    drawTitle('五、价格行为 · 阻力支撑', 12, [30, 64, 175]);
    const levels = data.levels || {};
    const lv = levels.data || {};
    if (!levels.ok) {
      drawWrapped(levels.error || '阻力支撑暂不可用', 9, 4.2);
    } else {
      drawWrapped(`现价参考：${fmtNum(lv.current_price)}（指数日线、不复权）`, 9, 4.2);
      drawTable(
        [['类型', '价位']],
        [
          ['近端支撑', fmtNum(lv.nearest_support)],
          ['近端阻力', fmtNum(lv.nearest_resistance)],
          ...(Array.isArray(lv.support_levels)
            ? lv.support_levels.slice(0, 4).map((p, i) => [`支撑${i + 1}`, fmtNum(p)])
            : []),
          ...(Array.isArray(lv.resistance_levels)
            ? lv.resistance_levels.slice(0, 4).map((p, i) => [`阻力${i + 1}`, fmtNum(p)])
            : []),
        ],
        { 0: { cellWidth: 28 }, 1: { cellWidth: 28 } }
      );
      const classic = lv.classic_levels || {};
      if (classic && classic.ok === false && classic.reason) {
        drawWrapped(`经典参考位：${classic.reason}`, 8.5, 4);
      }
      drawWrapped('页面可查看完整 KDE / Fib / Pivot 明细。', 8, 3.8);
    }
    y += 2;

    // —— 江恩 ——
    drawTitle('六、江恩趋势预测', 12, [30, 64, 175]);
    const gann = data.gann || {};
    const gPayload = gann.payload || gann.data || {};
    const g = gPayload.gann_trend || {};
    if (!gann.ok) {
      drawWrapped(gann.error || '江恩分析暂不可用', 9, 4.2);
    } else {
      const v = g.verdict || {};
      drawWrapped(
        `结论：${cell(v.bias_label || v.bias)}${v.summary ? ` — ${v.summary}` : ''}`,
        9,
        4.2
      );
      if (g.scale != null) {
        drawWrapped(
          `1×1 单位(scale)=${g.scale}；${g.scale_note || '自适应价格单位，非屏幕45°'}`,
          8.5,
          4
        );
      }
      const angles = Array.isArray(g.angles) ? g.angles : [];
      if (angles.length) {
        drawTable(
          [['角度', '理论价']],
          angles.slice(0, 8).map((a) => [cell(a.name || a.label), fmtNum(a.price || a.theory_price)]),
          { 0: { cellWidth: 28 }, 1: { cellWidth: 28 } }
        );
      }
      drawWrapped(g.disclaimer || '几何参考，非投资建议；扇形详见页面。', 8, 3.8);
    }

    if (typeof api.addPageFooters === 'function') api.addPageFooters(doc);
    doc.save(filename);
    return filename;
  }

  global.IndexAnalysisPdf = {
    exportFromHost,
  };
})(typeof window !== 'undefined' ? window : globalThis);
