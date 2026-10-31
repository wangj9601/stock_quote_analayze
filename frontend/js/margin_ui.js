/**
 * 两融展示公共工具：金额格式、踩踏旁证徽标、信号摘要 HTML。
 * 旁证非机构爆仓实锤。
 */
(function (global) {
  const RISK_LABEL = {
    none: '未见踩踏旁证',
    low: '踩踏风险偏低',
    mid: '踩踏风险中等',
    high: '踩踏风险偏高',
  };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtYi(v, digits) {
    if (v == null || Number.isNaN(Number(v))) return '--';
    const n = Number(v) / 1e8;
    const d = digits == null ? 2 : digits;
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(d)}亿`;
  }

  /** 绝对额（融资余额等）：不带 +/- */
  function fmtYiAbs(v, digits) {
    if (v == null || Number.isNaN(Number(v))) return '--';
    const n = Number(v) / 1e8;
    const d = digits == null ? 2 : digits;
    return `${n.toFixed(d)}亿`;
  }

  function fmtPct(v, digits) {
    if (v == null || Number.isNaN(Number(v))) return '--';
    const n = Number(v) * 100;
    const d = digits == null ? 1 : digits;
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(d)}%`;
  }

  /**
   * 近 5 日余额变化。正值是余额下降，负值是余额上升。
   * 用「上升 / 下降」写出来，避免「降幅」配上升箭头。
   */
  function fmtDropPct(v, digits) {
    if (v == null || Number.isNaN(Number(v))) return '--';
    const n = Number(v) * 100;
    const d = digits == null ? 1 : digits;
    const abs = Math.abs(n).toFixed(d);
    if (n > 0) return `下降 ${abs}%`;
    if (n < 0) return `上升 ${abs}%`;
    return '基本持平';
  }

  const NOTE_FALLBACK = {
    rzye: '还没还清的融资借款。这是存量，不是当天成交。',
    rz_net: '当天新借减去偿还。负数是在还钱，正数是在加杠杆。',
    crowding: '融资余额占流通市值的比例。8% 及以上记为高拥挤。',
    drop_5d: '和 5 个交易日前比。上升是杠杆在加，下降是在撤。下降达到 8% 记为骤降。',
  };

  function noteOf(signal, key) {
    const notes = signal && signal.notes;
    const text = notes && notes[key];
    return text || NOTE_FALLBACK[key] || '';
  }

  /** 接口还没带 reading 时，用同一套阈值在页面上补一句判断。 */
  function readingOf(signal) {
    if (!signal || !signal.available) return '';
    if (signal.reading) return String(signal.reading);
    const crowding = signal.crowding == null ? null : Number(signal.crowding);
    const rzNet = signal.rz_net == null ? null : Number(signal.rz_net);
    const drop5 = signal.rzye_drop_5d == null ? null : Number(signal.rzye_drop_5d);
    const flags = signal.flags || {};
    const risk = String(signal.squeeze_risk || 'none');
    const streak = Number(signal.neg_net_streak || 0);
    const parts = ['这些数看的是借钱买这只股票还剩多少，以及当天是在加杠杆还是在还钱。'];
    if (Number.isFinite(crowding)) {
      const pct = `${(crowding * 100).toFixed(2)}%`;
      parts.push(
        crowding >= 0.08
          ? `融资余额约占流通市值 ${pct}，已经过了 8% 的高拥挤线。`
          : `融资余额约占流通市值 ${pct}，还没到 8% 的高拥挤线。`
      );
    } else {
      parts.push('缺少流通市值，算不出杠杆占流通盘的比例。');
    }
    if (Number.isFinite(rzNet)) {
      const yi = Math.abs(rzNet) / 1e8;
      if (rzNet < 0) parts.push(`当天净偿还 ${yi.toFixed(2)} 亿。`);
      else if (rzNet > 0) parts.push(`当天净借入 ${yi.toFixed(2)} 亿。`);
      else parts.push('当天借贷和偿还基本抵消。');
    }
    if (Number.isFinite(drop5)) {
      if (drop5 > 0) parts.push(`近 5 日余额下降了 ${(drop5 * 100).toFixed(1)}%。`);
      else if (drop5 < 0) parts.push(`近 5 日余额上升了 ${(Math.abs(drop5) * 100).toFixed(1)}%。`);
      else parts.push('近 5 日余额基本没变。');
    }
    const fired = [];
    if (flags.high_crowding) fired.push('拥挤度过高');
    if (flags.balance_collapse) fired.push('近5日余额骤降');
    if (flags.neg_net_streak_ge_3) fired.push(`已连续 ${streak} 日净偿还`);
    if (flags.accel_repay) fired.push('当天偿还明显快于近几日');
    parts.push(
      fired.length
        ? `需要留意的是：${fired.join('、')}。`
        : '高拥挤、余额骤降、连续多日净偿还、偿还突然加快，这四项都没出现。'
    );
    if (risk === 'high') parts.push('这几项叠在一起，融资盘撤退的迹象偏重。这不能证明机构被强平。');
    else if (risk === 'mid') parts.push('这几项叠在一起，融资盘在减杠杆，先放慢。这不能证明机构被强平。');
    else if (risk === 'low') parts.push('有一项偏谨慎，还谈不上集中撤退。');
    else parts.push('所以目前看不出融资盘在集中撤退。');
    return parts.join('');
  }

  function clsYi(v) {
    if (v == null || Number.isNaN(Number(v))) return '';
    return Number(v) >= 0 ? 'is-up' : 'is-down';
  }

  /** 降幅着色：余额下降（正降幅）按风险偏红，上升偏绿 */
  function clsDrop(v) {
    if (v == null || Number.isNaN(Number(v))) return '';
    if (Number(v) > 0) return 'is-up';
    if (Number(v) < 0) return 'is-down';
    return '';
  }

  function riskClass(risk) {
    const r = String(risk || 'none').toLowerCase();
    if (r === 'high') return 'margin-risk-high';
    if (r === 'mid') return 'margin-risk-mid';
    if (r === 'low') return 'margin-risk-low';
    return 'margin-risk-none';
  }

  function riskLabel(risk) {
    const r = String(risk || 'none').toLowerCase();
    return RISK_LABEL[r] || r;
  }

  function badgeHtml(signal, opts) {
    const o = opts || {};
    if (!signal || !signal.available) {
      return o.hideEmpty
        ? ''
        : `<span class="margin-risk-badge margin-risk-none" title="暂无两融数据">两融--</span>`;
    }
    const risk = signal.squeeze_risk || 'none';
    const label = signal.squeeze_label || riskLabel(risk);
    const title = esc(
      [
        label,
        signal.trade_date ? `披露日 ${signal.trade_date}` : '',
        signal.disclaimer || '',
      ]
        .filter(Boolean)
        .join(' · ')
    );
    const short =
      risk === 'high' ? '踩踏偏高' : risk === 'mid' ? '踩踏中等' : risk === 'low' ? '踩踏偏低' : '两融正常';
    return `<span class="margin-risk-badge ${riskClass(risk)}" title="${title}">${esc(short)}</span>`;
  }

  function signalCardsHtml(signal) {
    if (!signal || !signal.available) {
      return `<p class="margin-empty">${esc((signal && signal.error) || '暂无两融数据（需日终采集，T+1 披露）')}</p>`;
    }
    const lhb = signal.dragon_tiger;
    let lhbHtml = '';
    if (lhb && lhb.org_net_value != null) {
      const orgNote =
        Number(lhb.org_net_value) < 0
          ? '同一天龙虎榜上，机构席位净卖出。只说明席位方向，不能证明被强平。'
          : '同一天龙虎榜上，机构席位净买入。只说明席位方向。';
      lhbHtml = `<div class="margin-metric"><span>龙虎榜机构净额</span><strong class="${clsYi(lhb.org_net_value)}">${fmtYi(lhb.org_net_value)}</strong><em>${esc(orgNote)}</em></div>`;
    }
    const hint = signal.composite_hint
      ? `<p class="margin-composite-hint">${esc(signal.composite_hint)}</p>`
      : '';
    const chartNote = signal.chart_note || '蓝线是还没还的融资借款。红柱是当天新借多于偿还，绿柱是偿还多于新借。';
    return `
      <div class="margin-signal-summary">
        <div class="margin-signal-head">
          ${badgeHtml(signal)}
          <span class="margin-signal-date">披露日 ${esc(signal.trade_date || '--')}，交易所次日才公布</span>
        </div>
        <p class="margin-reading">${esc(readingOf(signal))}</p>
        <div class="margin-metrics">
          <div class="margin-metric"><span>融资余额</span><strong>${fmtYiAbs(signal.rzye)}</strong><em>${esc(noteOf(signal, 'rzye'))}</em></div>
          <div class="margin-metric"><span>融资净买入</span><strong class="${clsYi(signal.rz_net)}">${fmtYi(signal.rz_net)}</strong><em>${esc(noteOf(signal, 'rz_net'))}</em></div>
          <div class="margin-metric"><span>拥挤度</span><strong>${signal.crowding == null ? '--' : (Number(signal.crowding) * 100).toFixed(2) + '%'}</strong><em>${esc(noteOf(signal, 'crowding'))}</em></div>
          <div class="margin-metric"><span>近5日余额</span><strong class="${clsDrop(signal.rzye_drop_5d)}">${fmtDropPct(signal.rzye_drop_5d)}</strong><em>${esc(noteOf(signal, 'drop_5d'))}</em></div>
          ${lhbHtml}
        </div>
        ${hint}
        <p class="margin-chart-note">${esc(chartNote)}</p>
        <p class="margin-disclaimer">${esc(signal.disclaimer || '这些是公开余额和净偿还推出来的旁证，不能证明某家机构被券商强平。')}</p>
      </div>`;
  }

  function chartOption(series) {
    const rows = Array.isArray(series) ? series : [];
    const dates = rows.map((r) => r.trade_date || '');
    const rzye = rows.map((r) => {
      const v = r.rzye;
      if (v == null || Number.isNaN(Number(v))) return null;
      return Number((Number(v) / 1e8).toFixed(4));
    });
    const rzNet = rows.map((r) => {
      const v = r.rz_net != null ? r.rz_net : (Number(r.rzmre || 0) - Number(r.rzche || 0));
      if (v == null || Number.isNaN(Number(v))) return null;
      return Number((Number(v) / 1e8).toFixed(4));
    });
    const T = global.EchartsTheme;
    const tooltip = T
      ? T.opsTooltip({
          formatter: T.opsAxisFormatter({
            colorBySign: true,
            formatValue: (n, name) => {
              if (n == null || n === '' || Number.isNaN(Number(n))) return '--';
              const num = Number(n);
              if (String(name || '').indexOf('净买入') >= 0) {
                return `${num > 0 ? '+' : ''}${num.toFixed(4)}`;
              }
              return num.toFixed(4);
            },
          }),
        })
      : {
          trigger: 'axis',
          backgroundColor: 'rgba(22, 28, 36, 0.96)',
          borderColor: 'rgba(217, 226, 236, 0.22)',
          textStyle: { color: '#d9e2ec', fontSize: 12 },
          extraCssText: 'color:#d9e2ec !important;',
        };
    return {
      tooltip,
      legend: {
        data: ['融资余额(亿)', '融资净买入(亿)'],
        textStyle: T ? T.legendTextStyle() : { color: '#8b9aab', fontSize: 11 },
      },
      grid: { left: 48, right: 24, top: 36, bottom: 28 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: T ? T.INK_MUTED : '#8b9aab', fontSize: 10 },
        axisLine: { lineStyle: { color: 'rgba(217,226,236,0.22)' } },
      },
      yAxis: [
        {
          type: 'value',
          name: '余额',
          scale: true,
          nameTextStyle: { color: T ? T.INK_MUTED : '#8b9aab' },
          axisLabel: { color: T ? T.INK_MUTED : '#8b9aab' },
          splitLine: { lineStyle: { color: 'rgba(217,226,236,0.08)' } },
        },
        {
          type: 'value',
          name: '净买入',
          scale: true,
          splitLine: { show: false },
          nameTextStyle: { color: T ? T.INK_MUTED : '#8b9aab' },
          axisLabel: { color: T ? T.INK_MUTED : '#8b9aab' },
        },
      ],
      series: [
        {
          name: '融资余额(亿)',
          type: 'line',
          data: rzye,
          smooth: true,
          itemStyle: { color: '#2563eb' },
          areaStyle: { color: 'rgba(37,99,235,0.08)' },
        },
        {
          name: '融资净买入(亿)',
          type: 'bar',
          yAxisIndex: 1,
          data: rzNet,
          itemStyle: {
            color: (p) =>
              p.value == null
                ? '#94a3b8'
                : p.value >= 0
                  ? T
                    ? T.RISE
                    : '#c23b3b'
                  : T
                    ? T.FALL
                    : '#2f9e6b',
          },
        },
      ],
    };
  }

  async function fetchJson(url) {
    const fetcher =
      typeof authFetch === 'function'
        ? authFetch
        : (u, o) => fetch(u, o);
    const resp = await fetcher(url);
    const payload = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, payload };
  }

  async function loadSeries(apiBase, code, days) {
    const end = new Date();
    const start = new Date(end.getTime() - (days || 60) * 86400000);
    const fmt = (d) => d.toISOString().slice(0, 10);
    const q = new URLSearchParams({
      start: fmt(start),
      end: fmt(end),
    });
    return fetchJson(`${apiBase}/api/stock/${encodeURIComponent(code)}/margin?${q}`);
  }

  async function loadSignal(apiBase, code, tradeDate) {
    const q = new URLSearchParams();
    if (tradeDate) q.set('trade_date', tradeDate);
    q.set('with_lhb', 'true');
    const qs = q.toString();
    return fetchJson(
      `${apiBase}/api/stock/${encodeURIComponent(code)}/margin/signal${qs ? `?${qs}` : ''}`
    );
  }

  async function loadSignalsBatch(apiBase, codes, tradeDate) {
    const list = (codes || []).filter(Boolean).slice(0, 80);
    if (!list.length) return { ok: true, payload: { success: true, data: {} } };
    const q = new URLSearchParams({
      codes: list.join(','),
      with_lhb: 'false',
    });
    if (tradeDate) q.set('trade_date', tradeDate);
    return fetchJson(`${apiBase}/api/stock/margin/signals?${q}`);
  }

  async function loadMarketSummary(apiBase, tradeDate) {
    const q = new URLSearchParams();
    if (tradeDate) q.set('trade_date', tradeDate);
    const qs = q.toString();
    return fetchJson(`${apiBase}/api/stock/margin/market/summary${qs ? `?${qs}` : ''}`);
  }

  async function loadRank(apiBase, metric, opts) {
    const o = opts || {};
    const q = new URLSearchParams({
      metric: metric || 'rz_net',
      limit: String(o.limit || 40),
      side: o.side || 'top',
    });
    if (o.trade_date) q.set('trade_date', o.trade_date);
    return fetchJson(`${apiBase}/api/stock/margin/rank?${q}`);
  }

  global.MarginUI = {
    esc,
    fmtYi,
    fmtYiAbs,
    fmtPct,
    fmtDropPct,
    clsYi,
    clsDrop,
    riskClass,
    riskLabel,
    badgeHtml,
    signalCardsHtml,
    chartOption,
    loadSeries,
    loadSignal,
    loadSignalsBatch,
    loadMarketSummary,
    loadRank,
    DISCLAIMER:
      '旁证基于公开两融余额/净偿还与流通市值推断，不能证明某家机构账户被券商强平。',
  };
})(typeof window !== 'undefined' ? window : globalThis);
