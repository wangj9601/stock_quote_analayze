/**
 * ECharts 统一主题（ops 深色面板）。
 * 图表 tooltip / 轴文字请优先用这里的预设，避免白底浅字或各自一份样式。
 */
(function (global) {
  const INK = '#d9e2ec';
  const INK_MUTED = '#8b9aab';
  const PANEL = 'rgba(22, 28, 36, 0.96)';
  const BORDER = 'rgba(217, 226, 236, 0.22)';
  const AXIS = 'rgba(217, 226, 236, 0.35)';
  const RISE = '#c23b3b';
  const FALL = '#2f9e6b';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * 深色轴触发 tooltip。extra 可覆盖任意字段（如 formatter）。
   */
  function opsTooltip(extra) {
    const base = {
      trigger: 'axis',
      confine: true,
      backgroundColor: PANEL,
      borderColor: BORDER,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: INK, fontSize: 12 },
      extraCssText:
        'border-radius:2px;box-shadow:0 8px 18px rgba(0,0,0,0.35);color:#d9e2ec !important;',
      axisPointer: {
        type: 'line',
        lineStyle: { color: AXIS, type: 'dashed' },
      },
    };
    if (!extra) return base;
    return Object.assign({}, base, extra, {
      textStyle: Object.assign({}, base.textStyle, extra.textStyle || {}),
      axisPointer: Object.assign({}, base.axisPointer, extra.axisPointer || {}),
    });
  }

  /**
   * 通用 axis tooltip formatter：系列名 + 数值；数值可按涨跌着色。
   * @param {object} opts
   * @param {(raw:any, seriesName:string)=>string} [opts.formatValue]
   * @param {boolean} [opts.colorBySign] 数值按正红负绿着色
   */
  function opsAxisFormatter(opts) {
    const o = opts || {};
    return function (params) {
      const list = Array.isArray(params) ? params : [params];
      const head = list[0] || {};
      const date = esc(String(head.axisValueLabel || head.axisValue || ''));
      const rows = list
        .map((p) => {
          const raw = p && p.value;
          const n =
            raw != null && typeof raw === 'object' && 'value' in raw
              ? raw.value
              : raw;
          let text;
          if (typeof o.formatValue === 'function') {
            text = o.formatValue(n, p.seriesName || '');
          } else if (n == null || n === '' || Number.isNaN(Number(n))) {
            text = '--';
          } else {
            text = String(n);
          }
          let color = INK;
          if (o.colorBySign && n != null && n !== '' && !Number.isNaN(Number(n))) {
            const num = Number(n);
            color = num > 0 ? RISE : num < 0 ? FALL : INK;
          }
          return `<div style="display:flex;justify-content:space-between;gap:14px;align-items:baseline;margin-top:4px;color:${INK};">
            <span style="color:${INK};">${p.marker || ''}${esc(p.seriesName || '')}</span>
            <span style="color:${color};font-variant-numeric:tabular-nums;">${esc(text)}</span>
          </div>`;
        })
        .join('');
      return `<div style="min-width:9.5rem;line-height:1.45;color:${INK};">
        <div style="color:${INK_MUTED};font-variant-numeric:tabular-nums;">${date}</div>
        ${rows}
      </div>`;
    };
  }

  function legendTextStyle(extra) {
    return Object.assign({ fontSize: 11, color: INK_MUTED }, extra || {});
  }

  global.EchartsTheme = {
    INK,
    INK_MUTED,
    PANEL,
    BORDER,
    AXIS,
    RISE,
    FALL,
    opsTooltip,
    opsAxisFormatter,
    legendTextStyle,
  };
})(typeof window !== 'undefined' ? window : globalThis);
