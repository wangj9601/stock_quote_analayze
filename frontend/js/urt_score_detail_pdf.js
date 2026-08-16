/**
 * URT 信号计算明细 · PDF 导出（jsPDF + autoTable，复用 BoardAnalysisPdf）
 */
(function (global) {
  function core() {
    const api = global.BoardAnalysisPdf;
    if (!api || typeof api.createDoc !== 'function') {
      throw new Error('BoardAnalysisPdf 未加载');
    }
    return api;
  }

  function cell(v) {
    if (v == null || v === '') return '--';
    return String(v);
  }

  /**
   * @param {object} detail API / 页面缓存的 URT 明细 JSON
   * @param {{filename?: string}|undefined} opts
   * @returns {Promise<string>} 文件名
   */
  async function exportFromDetail(detail, opts) {
    if (!detail || typeof detail !== 'object') {
      throw new Error('请先加载信号明细再导出');
    }
    if (!global.UrtScoreDetail || typeof global.UrtScoreDetail.buildExportModel !== 'function') {
      throw new Error('UrtScoreDetail 导出模型未加载');
    }
    const model = global.UrtScoreDetail.buildExportModel(detail);
    const api = core();
    const FONT_NAME = api.FONT_NAME || 'NotoSansSC';
    const doc = await api.createDoc({ orientation: 'portrait', unit: 'mm', format: 'a4' });

    const code = cell(model.code || detail.code);
    const name = cell(model.name || detail.name);
    const date = cell(model.date || detail.date);
    const filename =
      (opts && opts.filename) ||
      `URT信号明细_${code}_${date !== '--' ? date : '最新'}.pdf`.replace(/\s+/g, '');

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

    const sm = model.summary || {};
    drawTitle('URT 上升趋势 — 信号计算明细', 15, [15, 23, 42]);
    drawWrapped(`股票：${code} ${name}`, 9, 4.2);
    drawWrapped(`日期：${date} · 来源：${cell(model.source || detail.source)}`, 9, 4.2);
    drawWrapped(
      `总分 ${sm.total} / 阈值 ${sm.minScore} · 买点 ${sm.buy} · 硬筛 ${sm.filterOk}${
        sm.filterReason ? `（${sm.filterReason}）` : ''
      } · 得分达标 ${sm.scoreOk}`,
      9,
      4.2
    );
    y += 2;

    const bl = model.buyLogic || {};
    drawTitle('一、买点判断逻辑', 12, [30, 64, 175]);
    drawWrapped(bl.formula || '', 9, 4.2);
    if (bl.formulaDetail) drawWrapped(bl.formulaDetail, 8.5, 4);
    y += 1;
    if (bl.steps && bl.steps.length) {
      drawTable(
        [['条件', '规则', '实际值', '结果']],
        bl.steps,
        { 0: { cellWidth: 28 }, 1: { cellWidth: 'auto' }, 2: { cellWidth: 36 }, 3: { cellWidth: 18 } }
      );
    }
    if (bl.conclusion) {
      drawWrapped(`结论：${bl.conclusion}`, 9, 4.2);
      y += 2;
    }

    drawTitle('二、分项得分', 12, [30, 64, 175]);
    drawTable(
      [['分项', '得分', '满分', '说明']],
      model.scoreRows || [],
      { 0: { cellWidth: 24 }, 1: { cellWidth: 16 }, 2: { cellWidth: 14 }, 3: { cellWidth: 'auto' } }
    );

    drawTitle('三、输入指标', 12, [30, 64, 175]);
    drawTable(
      [['指标', '值']],
      model.inputs || [],
      { 0: { cellWidth: 36 }, 1: { cellWidth: 'auto' } }
    );

    const st = model.structure || {};
    drawTitle('四、支撑 / 阻力', 12, [30, 64, 175]);
    drawWrapped(
      `最近支撑 ${st.nearestSupport} · 最近阻力 ${st.nearestResistance} · 盈亏比 RR ${st.rr}` +
        `${st.rrFloored ? ' · 已用分母下限' : ''}` +
        `${st.rrReason ? ` · ${st.rrReason}` : ''}`,
      9,
      4.2
    );
    drawWrapped(
      `KDE ${st.kde} · 回看 ${st.lookback} 日${st.kdeReason ? ` · ${st.kdeReason}` : ''}`,
      9,
      4.2
    );
    y += 1;
    drawTable(
      [['类型', '价位（近→远）']],
      [
        ['阻力', st.resists || '--'],
        ['支撑', st.supports || '--'],
      ],
      { 0: { cellWidth: 22 }, 1: { cellWidth: 'auto' } }
    );

    if (model.advice) {
      const ad = model.advice;
      drawTitle('五、买点建议', 12, [30, 64, 175]);
      drawWrapped(
        `动作 ${ad.action} · 信心 ${ad.confidence}` +
          `${ad.structureRr != null ? ` · 结构盈亏比 RR≈${ad.structureRr}` : ''}` +
          `${ad.keyLevels ? ` · 关键位 ${ad.keyLevels}` : ''}`,
        9,
        4.2
      );
      y += 1;
      drawTable(
        [['项目', '价位/区间', '说明']],
        ad.rows || [],
        { 0: { cellWidth: 36 }, 1: { cellWidth: 40 }, 2: { cellWidth: 'auto' } }
      );
      if (ad.summary) {
        drawWrapped(ad.summary, 8.5, 4);
        y += 2;
      }
    }

    if (model.riskTags && model.riskTags.length) {
      drawTitle(model.advice ? '六、风险提示' : '五、风险提示', 12, [30, 64, 175]);
      model.riskTags.forEach((t) => {
        drawWrapped(
          `· ${t.label}${t.level && t.level !== 'info' ? `（${t.level}）` : ''}${
            t.reason ? `：${t.reason}` : ''
          }`,
          9,
          4.2
        );
      });
      y += 2;
    }

    drawWrapped('规则模板导出，非投资建议。', 8, 3.8);
    doc.save(filename);
    return filename;
  }

  global.UrtScoreDetailPdf = {
    exportFromDetail,
  };
})(typeof window !== 'undefined' ? window : this);
