/**
 * 个股分析 · 数据驱动 PDF 导出（复用 BoardAnalysisPdf 的 jsPDF / 中文字体封装）
 * 覆盖：综合交易策略 + 策略分析 + 阻力支撑位 + 形态识别 + 波段与趋势 + 江恩趋势
 */
(function (global) {
  function cell(v) {
    if (v == null || v === '') return '--';
    return String(v);
  }

  function fmtPrice(v) {
    return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(2) : '--';
  }

  function fmtPriceOrNote(price, note) {
    if (price != null && Number.isFinite(Number(price))) return fmtPrice(price);
    const n = note != null ? String(note).trim() : '';
    return n || '--';
  }

  function fmtConfluenceStrength(z) {
    if (!z || typeof z !== 'object') return '--';
    const s = z.strength != null && Number.isFinite(Number(z.strength)) ? z.strength : null;
    if (s == null) return '--';
    if (z.chips_void) {
      const note = z.void_note
        ? String(z.void_note)
        : '位于筹码真空区，需防范高ATR击穿效应';
      const adj =
        z.strength_adjusted != null && Number.isFinite(Number(z.strength_adjusted))
          ? `，折减后${z.strength_adjusted}`
          : '';
      return `${s}（注：${note}${adj}）`;
    }
    if (z.chips_hvz) {
      const note = z.hvz_note
        ? String(z.hvz_note)
        : '重叠VP密集抛压区，压制因子放大';
      return `${s}（注：${note}）`;
    }
    return String(s);
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

    const conf = classic.confluence_zones || d.confluence_zones || null;
    if (conf && conf.ok) {
      const zoneTxt = (z) => {
        if (!z) return '--';
        return `${fmtPrice(z.center)} [${fmtPrice(z.low)}–${fmtPrice(z.high)}]`;
      };
      const pickStrongOrNearest = (zones, nearest) => {
        const strong = (zones || []).filter((z) => z && z.tier === 'strong');
        if (strong.length) {
          const sorted = strong.slice().sort((a, b) => {
            const sa = Number(a.strength_adjusted != null ? a.strength_adjusted : a.strength) || 0;
            const sb = Number(b.strength_adjusted != null ? b.strength_adjusted : b.strength) || 0;
            return sb - sa;
          });
          return { zone: sorted[0], isStrong: true };
        }
        if (nearest) return { zone: nearest, isStrong: nearest.tier === 'strong' };
        if ((zones || []).length) return { zone: zones[0], isStrong: false };
        return { zone: null, isStrong: false };
      };
      const heroS = pickStrongOrNearest(conf.supports, conf.nearest_support_zone);
      const heroR = pickStrongOrNearest(conf.resistances, conf.nearest_resistance_zone);
      const heroLine = (picked, side) => {
        const z = picked && picked.zone;
        if (!z) return [`强共振${side}`, '--'];
        const lab = z.label_zh || (picked.isStrong ? `强共振${side}` : `共振${side}`);
        const note = picked.isStrong ? '' : '（非强）';
        const src = (z.sources || []).join('+') || '--';
        return [
          `${lab}${note}`,
          `${zoneTxt(z)} · 强度${fmtConfluenceStrength(z)} · ${src}`,
        ];
      };
      const confBody = [
        heroLine(heroS, '支撑'),
        heroLine(heroR, '压力'),
        ['最近支撑带', zoneTxt(conf.nearest_support_zone)],
        ['最近压力带', zoneTxt(conf.nearest_resistance_zone)],
      ];
      // 支撑：center 降序（近现价=支撑1）；压力：center 升序（近现价=压力1）
      const pushZones = (arr, tag, desc) => {
        const sorted = (arr || []).slice().sort((a, b) => {
          const ca = Number(a && a.center);
          const cb = Number(b && b.center);
          if (!Number.isFinite(ca) || !Number.isFinite(cb)) return 0;
          return desc ? cb - ca : ca - cb;
        });
        sorted.forEach((z, i) => {
          const src = (z.sources || []).join('+') || '--';
          const strength = fmtConfluenceStrength(z);
          const tierBit = z.tier === 'strong' ? '强·' : '';
          const lab = z.label_zh || tag;
          confBody.push([`${tierBit}${lab}${i + 1}·强度${strength}·${src}`, fmtPrice(z.center)]);
        });
      };
      pushZones(conf.supports, '支撑', true);
      pushZones(conf.resistances, '压力', false);
      sections.push({
        title: '多算法强共振（主结论）',
        head: [['项目', '价格/区间']],
        body: confBody,
      });
    } else if (conf && conf.reason) {
      sections.push({ note: `共振带：${conf.reason}` });
    }

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
          ['最近支撑', fmtPriceOrNote(vp.nearest_support, vp.support_note)],
          ['最近压力', fmtPriceOrNote(vp.nearest_resistance, vp.resistance_note)],
          [
            '回看',
            vp.bars_used != null || vp.lookback != null
              ? `${vp.bars_used != null ? vp.bars_used : vp.lookback} 日`
              : '--',
          ],
        ],
      });
      const alignTxt = (row) => {
        if (!row || row.kde == null || row.vp == null) {
          return row && row.note ? '语义' : '--';
        }
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
            fmtPriceOrNote(
              vpCmp.support && vpCmp.support.vp,
              vpCmp.support && vpCmp.support.note
            ),
            diffTxt(vpCmp.support),
            alignTxt(vpCmp.support),
          ],
          [
            '压力',
            fmtPrice(vpCmp.resistance && vpCmp.resistance.kde),
            fmtPriceOrNote(
              vpCmp.resistance && vpCmp.resistance.vp,
              vpCmp.resistance && vpCmp.resistance.note
            ),
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
        ['最近支撑', fmtPriceOrNote(fib.nearest_support ?? classic.nearest_fib_support, classic.fib_support_note || fib.support_note)],
        ['最近压力', fmtPriceOrNote(fib.nearest_resistance ?? classic.nearest_fib_resistance, classic.fib_resistance_note || fib.resistance_note)],
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
          fmtPriceOrNote(
            classic.nearest_cam_support != null ? classic.nearest_cam_support : cam.nearest_support,
            classic.cam_support_note || cam.support_note
          ),
        ],
        [
          '最近压力',
          fmtPriceOrNote(
            classic.nearest_cam_resistance != null
              ? classic.nearest_cam_resistance
              : cam.nearest_resistance,
            classic.cam_resistance_note || cam.resistance_note
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
      const levelsData = (host.lastLevels && host.lastLevels.data) || {};
      const classic = levelsData.classic_levels || levelsData.classic || {};
      const confluence =
        classic.confluence_zones || levelsData.confluence_zones || null;
      const a = PT.buildExpertAnalysis(visible, {
        asof: pack.asof || '',
        confluenceZones: confluence,
        classicLevels: classic,
        kdeLevels: {
          nearest_resistance: levelsData.nearest_resistance,
          nearest_support: levelsData.nearest_support,
          resistance_levels: levelsData.resistance_levels,
          support_levels: levelsData.support_levels,
        },
        tactical: pack.tactical || null,
      });
      if (typeof PT.formatTacticalPlainText === 'function' && pack.tactical) {
        a.tacticalPlain = PT.formatTacticalPlainText(pack.tactical);
      }
      // 与页面 _buildExpertHtml 共用同一套字段（含结构防守与目标 / 测幅）
      expert =
        typeof PT.formatExpertPlainText === 'function'
          ? PT.formatExpertPlainText(a)
          : [
              a.tacticalPlain || '',
              a.primaryLabel
                ? `主形态：${a.primaryLabel}${a.primaryConf ? `（置信度 ${a.primaryConf}）` : ''}`
                : '',
              a.shortTerm ? `短线：${a.shortTerm}` : '',
              a.mediumTerm ? `中线：${a.mediumTerm}` : '',
              a.structureText || a.tradeLevelsText || '',
              a.risk || '',
            ]
              .filter(Boolean)
              .join('\n');
    }
    if (!expert && pack.tactical && PT && typeof PT.formatTacticalPlainText === 'function') {
      expert = PT.formatTacticalPlainText(pack.tactical);
    }
    if (!expert) {
      expert = plainFromEl(document.querySelector('#ssaPatternHost .pattern-expert-analysis'));
    }
    return { error: pack.error || null, rows, expert, empty: !rows.length };
  }

  function zoneTxt(z) {
    if (!z || typeof z !== 'object') return '--';
    const lo = z.low;
    const hi = z.high;
    const px = z.price;
    if (lo != null && hi != null) return `${fmtPrice(lo)} – ${fmtPrice(hi)}`;
    if (px != null) return fmtPrice(px);
    if (lo != null) return fmtPrice(lo);
    return '--';
  }

  function tradePlanBody(host) {
    const pack = host.lastTradePlan;
    if (!pack) return { missing: true };
    if (pack.error && !pack.plan) return { error: pack.error };
    const plan = pack.plan || {};
    const st = plan.short_term || {};
    const mt = plan.medium_term || {};
    const kl = plan.key_levels || {};
    const confMap = { high: '高', medium: '中', low: '低' };
    const isStructWatch =
      plan.stance_short === 'watch' &&
      st.entry_zone &&
      st.entry_zone.basis === 'structure_watch';
    const entryLabel = isStructWatch ? '观察区' : '入场/承接';
    const stopLabel =
      st.stop_zone && st.stop_zone.basis === 'structure_invalidation'
        ? '失效参考'
        : '止损参考';
    const tpLabel =
      st.take_profit && st.take_profit.basis === 'structure_resistance'
        ? '压力观察'
        : '止盈参考';
    const rows = [
      ['短线立场', cell(plan.stance_short_label || st.action_label)],
      ['中长线立场', cell(plan.stance_medium_label || mt.bias_label)],
      ['信心', cell(confMap[plan.confidence] || plan.confidence)],
      ['主策略', cell(plan.primary_strategy_name || plan.primary_strategy)],
      [entryLabel, zoneTxt(st.entry_zone), cell((st.entry_zone && st.entry_zone.label) || '')],
      [stopLabel, zoneTxt(st.stop_zone), cell((st.stop_zone && st.stop_zone.label) || '')],
      [
        tpLabel,
        zoneTxt(
          st.take_profit && st.take_profit.prices
            ? { price: (st.take_profit.prices || [])[0] }
            : st.take_profit
        ),
        cell((st.take_profit && st.take_profit.label) || ''),
      ],
      [
        '回撤观察',
        zoneTxt(mt.watch_zone),
        cell((mt.watch_zone && mt.watch_zone.label) || (mt.ma20 != null ? `MA20≈${fmtPrice(mt.ma20)}` : '')),
      ],
      [
        '关键位',
        `支撑 ${fmtPrice(kl.support)} / 现价 ${fmtPrice(kl.close)} / 阻力 ${fmtPrice(kl.resistance)}`,
        '',
      ],
    ];
    return {
      error: pack.error || null,
      plan,
      rows,
      shortSummary: st.summary || '',
      mediumSummary: mt.summary || mt.holding_plan || '',
      conflicts: Array.isArray(plan.conflicts) ? plan.conflicts : [],
      disclaimer: plan.disclaimer || '',
    };
  }

  function swingBody(host) {
    const pack = host.lastSwing;
    if (!pack) return { error: null, text: '', rows: null };
    if (pack.error && !pack.data) {
      return { error: pack.error, text: '', rows: null };
    }
    const data = pack.data || {};
    const ms = data.market_structure || data;
    const MST = global.MarketStructureTool;
    let text = '';
    if (MST && typeof MST.formatPlainText === 'function') {
      text = MST.formatPlainText(ms, {
        code: pack.code || data.code,
        name: pack.name || data.name,
        weekly: data.weekly || null,
        counter_trend_note: data.counter_trend_note || (ms && ms.counter_trend_note) || null,
      });
    }
    if (!text) {
      text = plainFromEl(document.querySelector('#ssaSwingHost .ms-result-wrap'));
    }
    const ta = ms && ms.trend_analysis;
    if (ta && ta.text && text && text.indexOf('趋势分析说明') < 0) {
      text += `\n【趋势分析说明】\n${ta.text}`;
    }
    const pts = (ms && ms.points) || [];
    const rows = pts.map((p) => [
      cell(p.date),
      p.kind === 'high' ? '高点' : p.kind === 'low' ? '低点' : cell(p.kind),
      p.price != null ? Number(p.price).toFixed(2) : '--',
      cell(p.structure || '—'),
    ]);
    return {
      error: pack.error || null,
      text,
      rows: rows.length ? rows : null,
      trend: (ms && (ms.trend_label || ms.trend)) || '--',
      bos: ms && ms.last_bos_like,
      contrast: ms && ms.pattern_contrast,
    };
  }

  function gannBody(host) {
    const pack = host.lastGann;
    if (!pack) return { error: null, text: '', angleRows: null, twRows: null, bias: '' };
    if (pack.error && !pack.data) {
      return { error: pack.error, text: '', angleRows: null, twRows: null, bias: '' };
    }
    const data = pack.data || {};
    const g = data.gann_trend || data;
    const GT = global.GannTrendTool;
    let text = '';
    if (GT && typeof GT.formatPlainText === 'function') {
      text = GT.formatPlainText(g, {
        code: pack.code || data.code,
        name: pack.name || data.name,
      });
    }
    if (!text) {
      text = plainFromEl(document.querySelector('#ssaGannHost .gann-result-wrap'));
    }
    const angleRows = (g.angles || []).map((a) => [
      cell(a.name),
      a.price_at_asof != null ? Number(a.price_at_asof).toFixed(2) : '--',
      a.slope_per_bar != null ? Number(a.slope_per_bar).toFixed(4) : '--',
    ]);
    const twRows = (g.time_windows || []).map((t) => [
      `+${t.bars}`,
      cell(t.status_label || t.status),
      cell(t.target_date || '—'),
      t.bars_from_asof != null ? String(t.bars_from_asof) : '--',
    ]);
    const v = g.verdict || {};
    return {
      error: pack.error || null,
      text,
      angleRows: angleRows.length ? angleRows : null,
      twRows: twRows.length ? twRows : null,
      bias: v.bias_label || v.bias || '',
      summary: v.summary || '',
      scale: g.scale,
      scaleNote: g.scale_note || '',
      disclaimer: g.disclaimer || '几何参考，非投资建议。',
      ok: !!g.ok,
    };
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

    // —— 综合交易策略 ——
    drawTitle('一、综合交易策略', 12, [30, 64, 175]);
    const tp = tradePlanBody(host);
    if (tp.missing) {
      drawWrapped('本报告未包含综合交易策略结果', 9, 4.2);
      y += 2;
    } else if (tp.error && !tp.plan) {
      drawWrapped(`综合交易策略合成失败：${tp.error}`, 9, 4.2);
      y += 2;
    } else {
      drawTable(
        [['项目', '价位/结论', '说明']],
        tp.rows,
        { 0: { cellWidth: 28 }, 1: { cellWidth: 42 }, 2: { cellWidth: 'auto' } }
      );
      if (tp.shortSummary) {
        drawTitle('短线摘要', 10, [71, 85, 105]);
        drawWrapped(tp.shortSummary, 8.5, 4);
      }
      if (tp.mediumSummary) {
        drawTitle('中长线摘要', 10, [71, 85, 105]);
        drawWrapped(tp.mediumSummary, 8.5, 4);
      }
      if (tp.conflicts && tp.conflicts.length) {
        drawTitle('冲突提示', 10, [185, 28, 28]);
        tp.conflicts.forEach((c) => drawWrapped(`• ${c}`, 8.5, 4));
      }
      if (tp.disclaimer) {
        y += 1;
        drawWrapped(tp.disclaimer, 8, 3.8);
      }
    }

    // —— 策略分析 ——
    drawTitle('二、策略分析', 12, [30, 64, 175]);
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
    drawTitle('三、阻力支撑位', 12, [30, 64, 175]);
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
    drawTitle('四、形态识别', 12, [30, 64, 175]);
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

    // —— 波段与趋势 ——
    drawTitle('五、波段与趋势', 12, [30, 64, 175]);
    const sw = swingBody(host);
    if (!host.lastSwing) {
      drawWrapped('本报告未包含波段趋势结果', 9, 4.2);
    } else if (sw.error && !sw.rows && !sw.text) {
      drawWrapped(`波段趋势分析失败：${sw.error}`, 9, 4.2);
    } else {
      drawWrapped(`趋势：${sw.trend || '--'}`, 9, 4.2);
      if (sw.contrast) {
        drawWrapped(sw.contrast, 8.5, 4);
      }
      if (sw.bos) {
        drawWrapped(
          `关键事件：${sw.bos.label || sw.bos.type || ''} @ ${sw.bos.level != null ? sw.bos.level : '--'}`,
          8.5,
          4
        );
      }
      if (sw.text) {
        y += 1;
        drawWrapped(sw.text, 8.5, 4);
      }
      if (sw.rows) {
        drawTitle('摆动点', 10, [71, 85, 105]);
        drawTable(
          [['日期', '类型', '价格', '标注']],
          sw.rows,
          { 0: { cellWidth: 28 }, 1: { cellWidth: 18 }, 2: { cellWidth: 22 }, 3: { cellWidth: 18 } }
        );
      }
      if (sw.error) {
        y += 2;
        drawWrapped(`提示：${sw.error}`, 8.5, 4);
      }
    }

    // —— 江恩趋势预测 ——
    drawTitle('六、江恩趋势预测', 12, [30, 64, 175]);
    const gn = gannBody(host);
    if (!host.lastGann) {
      drawWrapped('本报告未包含江恩趋势结果', 9, 4.2);
    } else if (gn.error && !gn.text && !gn.angleRows) {
      drawWrapped(`江恩趋势分析失败：${gn.error}`, 9, 4.2);
    } else {
      if (gn.bias) {
        drawWrapped(`结论：${gn.bias}${gn.summary ? ` — ${gn.summary}` : ''}`, 9, 4.2);
      }
      if (gn.scale != null) {
        drawWrapped(
          `1×1 单位(scale)=${gn.scale}；${gn.scaleNote || '1×1 为自适应价格单位，非屏幕45°'}`,
          8.5,
          4
        );
      }
      if (gn.text) {
        y += 1;
        drawWrapped(gn.text, 8.5, 4);
      }
      if (gn.angleRows) {
        drawTitle('角度线（基准日理论价）', 10, [71, 85, 105]);
        drawTable(
          [['角度', '理论价', '斜率/根']],
          gn.angleRows,
          { 0: { cellWidth: 22 }, 1: { cellWidth: 28 }, 2: { cellWidth: 28 } }
        );
      }
      if (gn.twRows) {
        drawTitle('时间窗口（交易日）', 10, [71, 85, 105]);
        drawTable(
          [['窗口', '状态', '目标日', '相对基准']],
          gn.twRows,
          {
            0: { cellWidth: 18 },
            1: { cellWidth: 18 },
            2: { cellWidth: 28 },
            3: { cellWidth: 22 },
          }
        );
      }
      drawWrapped(
        `${gn.disclaimer || '几何参考，非投资建议。'} 扇形为价-时间示意（非蜡烛图）；页面可查看 SVG 扇形。`,
        8,
        3.8
      );
      if (gn.error) {
        y += 2;
        drawWrapped(`提示：${gn.error}`, 8.5, 4);
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
