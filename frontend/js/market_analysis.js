/**
 * 分析频道 · 市场分析：个股/板块资金流向 + 板块斜率趋势（图形 / 列表 / Excel 导出）
 */
const MarketAnalysis = {
  API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
  BOARD_CODE_SOURCE: 'tonghuashun',
  STOCK_SIDES: 40,

  views: { stock: 'chart', board: 'chart', slope: 'chart' },
  cache: {
    stock: { items: [], meta: {} },
    board: { items: [], meta: {} },
    slope: { items: [], meta: {}, raw: [] },
  },
  charts: { stock: null, board: null, slope: null },
  loadedOnce: false,
  _resizeBound: null,

  init() {
    this.bindEvents();
    this._resizeBound = () => this.resizeCharts();
    window.addEventListener('resize', this._resizeBound);
  },

  bindEvents() {
    document.querySelectorAll('input[name="maStockPeriod"]').forEach((el) => {
      el.addEventListener('change', () => this.loadStockFlow());
    });
    document.querySelectorAll('input[name="maBoardKind"]').forEach((el) => {
      el.addEventListener('change', () => this.loadBoardFlow());
    });
    document.querySelectorAll('input[name="maBoardPeriod"]').forEach((el) => {
      el.addEventListener('change', () => this.loadBoardFlow());
    });
    document.querySelectorAll('input[name="maSlopeKind"]').forEach((el) => {
      el.addEventListener('change', () => this.loadSlope());
    });
    const winSel = document.getElementById('maSlopeWindow');
    if (winSel) winSel.addEventListener('change', () => this.applySlopeWindowAndRender());

    document.querySelectorAll('.ma-view-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const block = btn.getAttribute('data-ma-block');
        const view = btn.getAttribute('data-ma-view');
        if (!block || !view) return;
        this.setView(block, view);
      });
    });

    const map = [
      ['maStockRefreshBtn', () => this.loadStockFlow()],
      ['maBoardRefreshBtn', () => this.loadBoardFlow()],
      ['maSlopeRefreshBtn', () => this.loadSlope()],
      ['maStockExportBtn', () => this.exportBlock('stock')],
      ['maBoardExportBtn', () => this.exportBlock('board')],
      ['maSlopeExportBtn', () => this.exportBlock('slope')],
    ];
    map.forEach(([id, fn]) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('click', fn);
    });
  },

  load() {
    this.loadedOnce = true;
    this.loadStockFlow();
    this.loadBoardFlow();
    this.loadSlope();
    requestAnimationFrame(() => this.resizeCharts());
  },

  radioValue(name, fallback) {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value : fallback;
  },

  setView(block, view) {
    this.views[block] = view === 'list' ? 'list' : 'chart';
    document.querySelectorAll(`.ma-view-btn[data-ma-block="${block}"]`).forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-ma-view') === this.views[block]);
    });
    const ids = {
      stock: { chart: 'maStockFlowChart', table: 'maStockFlowTableWrap' },
      board: { chart: 'maBoardFlowChart', table: 'maBoardFlowTableWrap' },
      slope: { chart: 'maSlopeChart', table: 'maSlopeTableWrap' },
    };
    const pair = ids[block];
    if (!pair) return;
    const chartEl = document.getElementById(pair.chart);
    const tableEl = document.getElementById(pair.table);
    const isChart = this.views[block] === 'chart';
    if (chartEl) chartEl.hidden = !isChart;
    if (tableEl) tableEl.hidden = isChart;
    if (isChart) {
      requestAnimationFrame(() => {
        this.renderChart(block);
        this.resizeCharts();
      });
    }
  },

  fetchJson(url) {
    const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
    return fetchFn(url).then(async (resp) => {
      const text = await resp.text();
      let body = {};
      try {
        body = text ? JSON.parse(text) : {};
      } catch (_) {
        body = { success: false, message: text?.slice(0, 200) || `HTTP ${resp.status}` };
      }
      if (!resp.ok) {
        throw new Error(body.message || `请求失败(${resp.status})`);
      }
      return body;
    });
  },

  toYi(yuan) {
    if (yuan == null || !Number.isFinite(Number(yuan))) return null;
    return Math.round((Number(yuan) / 1e8) * 100) / 100;
  },

  fmtYi(yuan) {
    const v = this.toYi(yuan);
    if (v == null) return '--';
    const sign = v > 0 ? '+' : '';
    return `${sign}${v.toFixed(2)}`;
  },

  fmtNum(v, digits) {
    if (v == null || !Number.isFinite(Number(v))) return '--';
    const n = Number(v);
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(digits)}`;
  },

  fmtSlope(v) {
    if (v == null || !Number.isFinite(Number(v))) return '--';
    const n = Number(v);
    const abs = Math.abs(n);
    const digits = abs >= 0.01 ? 4 : abs >= 0.001 ? 5 : 6;
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(digits)}`;
  },

  fmtRange(start, end) {
    if (start && end && start !== end) return `${start} ~ ${end}`;
    return end || start || '';
  },

  setStatus(id, text, isError) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text || '';
    el.classList.toggle('ma-status--error', !!isError);
  },

  setMeta(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text || '';
  },

  escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },

  colorClass(v) {
    if (v == null || !Number.isFinite(Number(v))) return '';
    if (Number(v) > 0) return 'ma-pos';
    if (Number(v) < 0) return 'ma-neg';
    return '';
  },

  ensureChart(block, el) {
    if (!el || typeof echarts === 'undefined') return null;
    if (this.charts[block]) return this.charts[block];
    this.charts[block] = echarts.init(el);
    return this.charts[block];
  },

  buildBarOption(names, values, xName, tooltipFormatter) {
    const useZoom = names.length > 20;
    const windowSize = 20;
    const startPct = useZoom
      ? Math.max(0, ((names.length - windowSize) / names.length) * 100)
      : 0;
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: tooltipFormatter,
      },
      grid: {
        left: 108,
        right: useZoom ? 36 : 28,
        top: 12,
        bottom: 28,
      },
      dataZoom: useZoom
        ? [
            {
              type: 'slider',
              yAxisIndex: 0,
              width: 14,
              right: 4,
              start: startPct,
              end: 100,
              brushSelect: false,
            },
            { type: 'inside', yAxisIndex: 0, start: startPct, end: 100 },
          ]
        : [],
      xAxis: {
        type: 'value',
        name: xName,
        nameLocation: 'middle',
        nameGap: 22,
        axisLabel: { fontSize: 11 },
        splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } },
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLabel: { fontSize: 11, width: 96, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: values.map((v) => ({
            value: v,
            itemStyle: {
              color: v >= 0 ? '#dc2626' : '#16a34a',
              borderRadius: v >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3],
            },
          })),
          barMaxWidth: 14,
        },
      ],
    };
  },

  renderChart(block) {
    if (this.views[block] !== 'chart') return;
    if (typeof echarts === 'undefined') {
      this.setStatus(
        block === 'stock' ? 'maStockFlowStatus' : block === 'board' ? 'maBoardFlowStatus' : 'maSlopeStatus',
        '图表库未加载，请刷新页面或切换到列表查看',
        true
      );
      return;
    }
    if (block === 'stock') this.renderStockChart();
    else if (block === 'board') this.renderBoardChart();
    else if (block === 'slope') this.renderSlopeChart();
  },

  /* ---------- 个股资金流向 ---------- */

  async loadStockFlow() {
    const period = this.radioValue('maStockPeriod', 'day');
    const statusId = 'maStockFlowStatus';
    this.setStatus(statusId, '加载中…', false);
    try {
      const q = new URLSearchParams({
        period,
        sides: String(this.STOCK_SIDES),
      });
      const body = await this.fetchJson(
        `${this.API_BASE_URL}/api/stock_fund_flow/rank?${q.toString()}`
      );
      if (!body.success) throw new Error(body.message || '加载失败');
      const data = body.data || {};
      const items = Array.isArray(data.items) ? data.items : [];
      items.sort((a, b) => Number(a.net_amount || 0) - Number(b.net_amount || 0));
      this.cache.stock = {
        items,
        meta: {
          period: data.period || period,
          period_label: data.period_label || '日',
          start_date: data.start_date || null,
          end_date: data.end_date || null,
          sides: data.sides != null ? data.sides : this.STOCK_SIDES,
          total_universe: data.total_universe,
        },
      };
      const range = this.fmtRange(data.start_date, data.end_date);
      const parts = [
        `${data.period_label || '日'}净流入`,
        range || null,
        items.length ? `${items.length} 只` : null,
        data.sides != null ? `两端各 ${data.sides}` : null,
      ].filter(Boolean);
      this.setMeta('maStockFlowMeta', parts.join(' · '));
      this.renderStockTable();
      this.renderChart('stock');
      this.setStatus(statusId, items.length ? '' : '暂无个股资金流（请先日采同花顺资金流向）', false);
    } catch (e) {
      this.cache.stock = { items: [], meta: {} };
      this.renderStockTable();
      this.setStatus(statusId, e.message || '加载失败', true);
      if (window.CommonUtils) CommonUtils.showToast(e.message || '个股资金流向加载失败', 'error');
    }
  },

  renderStockChart() {
    const el = document.getElementById('maStockFlowChart');
    const chart = this.ensureChart('stock', el);
    if (!chart) return;
    const items = this.cache.stock.items || [];
    const label = this.cache.stock.meta.period_label || '日';
    if (!items.length) {
      chart.clear();
      return;
    }
    const names = items.map((r) => String(r.name || r.code || '--'));
    const values = items.map((r) => this.toYi(r.net_amount) || 0);
    const meta = items.map((r) => ({
      code: r.code,
      inflow: r.inflow_amount,
      outflow: r.outflow_amount,
      days: r.days_count,
    }));
    const option = this.buildBarOption(names, values, `${label}净流入(亿)`, (params) => {
      const list = Array.isArray(params) ? params : [params];
      const p = list[0] || {};
      const idx = Number(p.dataIndex);
      const m = Number.isFinite(idx) ? meta[idx] : undefined;
      const v = Number(p.value);
      const sign = v > 0 ? '+' : '';
      return [
        `${p.name || ''}${m?.code ? `（${m.code}）` : ''}`,
        `${label}净流入：${sign}${v.toFixed(2)} 亿`,
        `流入：${this.fmtYi(m?.inflow)} 亿`,
        `流出：${this.fmtYi(m?.outflow)} 亿`,
        m?.days != null ? `覆盖交易日：${m.days}` : '',
      ]
        .filter(Boolean)
        .join('<br/>');
    });
    chart.setOption(option, true);
    chart.resize();
  },

  renderStockTable() {
    const tbody = document.getElementById('maStockFlowTbody');
    if (!tbody) return;
    const items = this.cache.stock.items || [];
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="ma-empty">暂无数据</td></tr>';
      return;
    }
    // 列表按净流入强→弱展示，便于阅读
    const rows = [...items].sort((a, b) => Number(b.net_amount || 0) - Number(a.net_amount || 0));
    tbody.innerHTML = rows
      .map((r, i) => {
        const net = Number(r.net_amount);
        return `<tr>
          <td>${i + 1}</td>
          <td><a class="ma-code-link" href="stock.html?code=${encodeURIComponent(r.code || '')}" target="_blank" rel="noopener">${this.escapeHtml(r.code || '--')}</a></td>
          <td>${this.escapeHtml(r.name || '--')}</td>
          <td class="ma-num ${this.colorClass(net)}">${this.fmtYi(r.net_amount)}</td>
          <td class="ma-num">${this.fmtYi(r.inflow_amount)}</td>
          <td class="ma-num">${this.fmtYi(r.outflow_amount)}</td>
          <td class="ma-num">${r.days_count != null ? r.days_count : '--'}</td>
        </tr>`;
      })
      .join('');
  },

  /* ---------- 板块资金流向 ---------- */

  async loadBoardFlow() {
    const kind = this.radioValue('maBoardKind', 'industry');
    const period = this.radioValue('maBoardPeriod', 'day');
    const statusId = 'maBoardFlowStatus';
    this.setStatus(statusId, '加载中…', false);
    try {
      const q = new URLSearchParams({
        board_kind: kind,
        period,
        board_code_source: this.BOARD_CODE_SOURCE,
      });
      const body = await this.fetchJson(
        `${this.API_BASE_URL}/api/board_fund_flow/rank?${q.toString()}`
      );
      if (!body.success) throw new Error(body.message || '加载失败');
      const data = body.data || {};
      const items = Array.isArray(data.items) ? data.items : [];
      items.sort(
        (a, b) => Number(a.main_net_inflow || 0) - Number(b.main_net_inflow || 0)
      );
      this.cache.board = {
        items,
        meta: {
          kind,
          period: data.period || period,
          period_label: data.period_label || '日',
          start_date: data.start_date || null,
          end_date: data.end_date || null,
        },
      };
      const kindLabel = kind === 'concept' ? '概念' : '行业';
      const range = this.fmtRange(data.start_date, data.end_date);
      const parts = [
        kindLabel,
        `${data.period_label || '日'}净流入`,
        range || null,
        items.length ? `${items.length} 个` : null,
      ].filter(Boolean);
      this.setMeta('maBoardFlowMeta', parts.join(' · '));
      this.renderBoardTable();
      this.renderChart('board');
      this.setStatus(statusId, items.length ? '' : '暂无板块资金流（请先日采）', false);
    } catch (e) {
      this.cache.board = { items: [], meta: {} };
      this.renderBoardTable();
      this.setStatus(statusId, e.message || '加载失败', true);
      if (window.CommonUtils) CommonUtils.showToast(e.message || '板块资金流向加载失败', 'error');
    }
  },

  renderBoardChart() {
    const el = document.getElementById('maBoardFlowChart');
    const chart = this.ensureChart('board', el);
    if (!chart) return;
    const items = this.cache.board.items || [];
    const label = this.cache.board.meta.period_label || '日';
    if (!items.length) {
      chart.clear();
      return;
    }
    const names = items.map((r) => String(r.board_name || r.board_code || '--'));
    const values = items.map((r) => this.toYi(r.main_net_inflow) || 0);
    const option = this.buildBarOption(names, values, `${label}净流入(亿)`, (params) => {
      const list = Array.isArray(params) ? params : [params];
      const p = list[0] || {};
      const v = Number(p.value);
      const sign = v > 0 ? '+' : '';
      return `${p.name || ''}<br/>${label}净流入：${sign}${v.toFixed(2)} 亿`;
    });
    chart.setOption(option, true);
    chart.resize();
  },

  renderBoardTable() {
    const tbody = document.getElementById('maBoardFlowTbody');
    if (!tbody) return;
    const items = this.cache.board.items || [];
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="ma-empty">暂无数据</td></tr>';
      return;
    }
    const rows = [...items].sort(
      (a, b) => Number(b.main_net_inflow || 0) - Number(a.main_net_inflow || 0)
    );
    tbody.innerHTML = rows
      .map((r, i) => {
        const net = Number(r.main_net_inflow);
        const chg = r.change_percent;
        return `<tr>
          <td>${i + 1}</td>
          <td>${this.escapeHtml(r.board_code || '--')}</td>
          <td>${this.escapeHtml(r.board_name || '--')}</td>
          <td class="ma-num ${this.colorClass(net)}">${this.fmtYi(r.main_net_inflow)}</td>
          <td class="ma-num">${this.fmtYi(r.inflow_amount)}</td>
          <td class="ma-num">${this.fmtYi(r.outflow_amount)}</td>
          <td class="ma-num ${this.colorClass(chg)}">${chg == null || !Number.isFinite(Number(chg)) ? '--' : this.fmtNum(chg, 2)}</td>
          <td class="ma-num">${r.days_count != null ? r.days_count : '--'}</td>
        </tr>`;
      })
      .join('');
  },

  /* ---------- 板块斜率 ---------- */

  slopeFieldForWindow(window) {
    const w = Number(window) || 60;
    if (w === 60) {
      return {
        slope: 'sector_slope',
        win: 'sector_slope_window',
        asof: 'slope_asof_date',
        source: 'slope_source',
        r2: 'slope_r2',
        env: 'board_env',
        envLabel: 'board_env_label',
        defaultWin: 60,
      };
    }
    if (w === 10) {
      return {
        slope: 'sector_slope_short',
        win: 'sector_slope_short_window',
        asof: 'slope_short_asof_date',
        source: 'slope_short_source',
        r2: 'slope_short_r2',
        env: 'board_env_short',
        envLabel: 'board_env_short_label',
        defaultWin: 10,
      };
    }
    const s = String(w);
    return {
      slope: `sector_slope_${s}`,
      win: `sector_slope_${s}_window`,
      asof: `slope_${s}_asof_date`,
      source: `slope_${s}_source`,
      r2: `slope_${s}_r2`,
      env: `board_env_${s}`,
      envLabel: `board_env_${s}_label`,
      defaultWin: w,
    };
  },

  normalizeSlopeItems(rawItems, window) {
    const f = this.slopeFieldForWindow(window);
    return (rawItems || [])
      .map((item) => {
        const slope = item[f.slope];
        const n = slope == null || slope === '' ? null : Number(slope);
        return {
          board_code: String(item.board_code || ''),
          board_name: String(item.board_name || item.board_code || '--'),
          sector_slope: Number.isFinite(n) ? n : null,
          sector_slope_window: Number(item[f.win]) || f.defaultWin,
          slope_asof_date: item[f.asof] != null ? String(item[f.asof]) : null,
          slope_source: item[f.source] != null ? String(item[f.source]) : null,
          slope_r2:
            item[f.r2] != null && Number.isFinite(Number(item[f.r2]))
              ? Number(item[f.r2])
              : null,
          board_env: item[f.env] != null ? String(item[f.env]) : null,
          board_env_label: item[f.envLabel] != null ? String(item[f.envLabel]) : null,
        };
      })
      .filter((x) => x.sector_slope != null)
      .sort((a, b) => Number(a.sector_slope) - Number(b.sector_slope));
  },

  currentSlopeWindow() {
    const sel = document.getElementById('maSlopeWindow');
    return sel ? Number(sel.value) || 60 : 60;
  },

  applySlopeWindowAndRender() {
    const window = this.currentSlopeWindow();
    const raw = this.cache.slope.raw || [];
    const items = this.normalizeSlopeItems(raw, window);
    const kind = this.cache.slope.meta.kind || this.radioValue('maSlopeKind', 'industry');
    let asof = '';
    for (let i = items.length - 1; i >= 0; i -= 1) {
      if (items[i].slope_asof_date) {
        asof = items[i].slope_asof_date;
        break;
      }
    }
    this.cache.slope.items = items;
    this.cache.slope.meta = {
      ...this.cache.slope.meta,
      kind,
      window,
      asof,
    };
    const kindLabel = kind === 'concept' ? '概念' : '行业';
    const parts = [
      kindLabel,
      `${window} 日斜率`,
      asof || null,
      items.length ? `${items.length} 个` : null,
    ].filter(Boolean);
    this.setMeta('maSlopeMeta', parts.join(' · '));
    this.renderSlopeTable();
    this.renderChart('slope');
    this.setStatus(
      'maSlopeStatus',
      items.length ? '' : '暂无板块斜率（请先在行情页刷新斜率入库）',
      false
    );
  },

  async loadSlope() {
    const kind = this.radioValue('maSlopeKind', 'industry');
    const statusId = 'maSlopeStatus';
    this.setStatus(statusId, '加载中…', false);
    try {
      const path =
        kind === 'concept'
          ? '/api/market/concept_board/list'
          : '/api/market/industry_board/list';
      const q = new URLSearchParams({ board_code_source: this.BOARD_CODE_SOURCE });
      const body = await this.fetchJson(`${this.API_BASE_URL}${path}?${q.toString()}`);
      if (!body.success) throw new Error(body.message || '加载失败');
      const raw = Array.isArray(body.data) ? body.data : [];
      this.cache.slope.raw = raw;
      this.cache.slope.meta = { kind };
      this.applySlopeWindowAndRender();
    } catch (e) {
      this.cache.slope = { items: [], meta: {}, raw: [] };
      this.renderSlopeTable();
      this.setStatus(statusId, e.message || '加载失败', true);
      if (window.CommonUtils) CommonUtils.showToast(e.message || '板块斜率加载失败', 'error');
    }
  },

  renderSlopeChart() {
    const el = document.getElementById('maSlopeChart');
    const chart = this.ensureChart('slope', el);
    if (!chart) return;
    const items = this.cache.slope.items || [];
    const window = this.cache.slope.meta.window || this.currentSlopeWindow();
    if (!items.length) {
      chart.clear();
      return;
    }
    const names = items.map((r) => String(r.board_name || r.board_code || '--'));
    const values = items.map((r) => Number(r.sector_slope));
    const meta = items.map((r) => ({
      source: r.slope_source || '--',
      r2: r.slope_r2,
      env: r.board_env_label || r.board_env || '--',
      window: r.sector_slope_window || window,
    }));
    const option = this.buildBarOption(names, values, `${window}日斜率`, (params) => {
      const list = Array.isArray(params) ? params : [params];
      const p = list[0] || {};
      const idx = Number(p.dataIndex);
      const m = Number.isFinite(idx) ? meta[idx] : undefined;
      const v = Number(p.value);
      const r2Text =
        m?.r2 != null && Number.isFinite(Number(m.r2)) ? Number(m.r2).toFixed(3) : '--';
      return [
        `${p.name || ''}`,
        `斜率(${m?.window || window}日)：${this.fmtSlope(v)}`,
        `R²：${r2Text}`,
        `来源：${m?.source || '--'}`,
        `环境：${m?.env || '--'}`,
      ].join('<br/>');
    });
    chart.setOption(option, true);
    chart.resize();
  },

  renderSlopeTable() {
    const tbody = document.getElementById('maSlopeTbody');
    if (!tbody) return;
    const items = this.cache.slope.items || [];
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="ma-empty">暂无数据</td></tr>';
      return;
    }
    const rows = [...items].sort(
      (a, b) => Number(b.sector_slope || 0) - Number(a.sector_slope || 0)
    );
    tbody.innerHTML = rows
      .map((r, i) => {
        const slope = Number(r.sector_slope);
        return `<tr>
          <td>${i + 1}</td>
          <td>${this.escapeHtml(r.board_code || '--')}</td>
          <td>${this.escapeHtml(r.board_name || '--')}</td>
          <td class="ma-num ${this.colorClass(slope)}">${this.fmtSlope(slope)}</td>
          <td class="ma-num">${r.slope_r2 != null && Number.isFinite(Number(r.slope_r2)) ? Number(r.slope_r2).toFixed(3) : '--'}</td>
          <td>${this.escapeHtml(r.board_env_label || r.board_env || '--')}</td>
          <td class="ma-num">${r.sector_slope_window != null ? r.sector_slope_window : '--'}</td>
          <td>${this.escapeHtml(r.slope_asof_date || '--')}</td>
          <td>${this.escapeHtml(r.slope_source || '--')}</td>
        </tr>`;
      })
      .join('');
  },

  resizeCharts() {
    Object.values(this.charts).forEach((c) => {
      try {
        if (c) c.resize();
      } catch (_) {
        /* ignore */
      }
    });
  },

  /* ---------- 导出 ---------- */

  stamp() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`;
  },

  async exportBlock(block) {
    const btnId =
      block === 'stock'
        ? 'maStockExportBtn'
        : block === 'board'
          ? 'maBoardExportBtn'
          : 'maSlopeExportBtn';
    const btn = document.getElementById(btnId);
    const prev = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '导出中…';
    }
    try {
      if (typeof window.ensureSheetJsLoaded === 'function') {
        await window.ensureSheetJsLoaded();
      }
      if (typeof XLSX === 'undefined') {
        throw new Error('Excel 组件未加载，请刷新页面后重试');
      }
      let aoa;
      let sheetName;
      let filename;
      const stamp = this.stamp();
      if (block === 'stock') {
        const items = [...(this.cache.stock.items || [])].sort(
          (a, b) => Number(b.net_amount || 0) - Number(a.net_amount || 0)
        );
        if (!items.length) throw new Error('暂无个股资金流向数据可导出');
        const m = this.cache.stock.meta || {};
        aoa = [
          ['个股资金流向'],
          [
            '周期',
            m.period_label || m.period || '',
            '区间',
            this.fmtRange(m.start_date, m.end_date),
          ],
          [],
          ['排名', '代码', '名称', '净流入(亿)', '流入(亿)', '流出(亿)', '覆盖交易日'],
          ...items.map((r, i) => [
            i + 1,
            r.code || '',
            r.name || '',
            this.toYi(r.net_amount),
            this.toYi(r.inflow_amount),
            this.toYi(r.outflow_amount),
            r.days_count != null ? r.days_count : '',
          ]),
        ];
        sheetName = '个股资金流向';
        filename = `个股资金流向_${m.period_label || m.period || '日'}_${stamp}.xlsx`;
      } else if (block === 'board') {
        const items = [...(this.cache.board.items || [])].sort(
          (a, b) => Number(b.main_net_inflow || 0) - Number(a.main_net_inflow || 0)
        );
        if (!items.length) throw new Error('暂无板块资金流向数据可导出');
        const m = this.cache.board.meta || {};
        const kindLabel = m.kind === 'concept' ? '概念' : '行业';
        aoa = [
          ['板块资金流向'],
          [
            '类型',
            kindLabel,
            '周期',
            m.period_label || m.period || '',
            '区间',
            this.fmtRange(m.start_date, m.end_date),
          ],
          [],
          [
            '排名',
            '代码',
            '名称',
            '主力净流入(亿)',
            '流入(亿)',
            '流出(亿)',
            '涨跌幅%',
            '覆盖交易日',
          ],
          ...items.map((r, i) => [
            i + 1,
            r.board_code || '',
            r.board_name || '',
            this.toYi(r.main_net_inflow),
            this.toYi(r.inflow_amount),
            this.toYi(r.outflow_amount),
            r.change_percent != null && Number.isFinite(Number(r.change_percent))
              ? Number(r.change_percent)
              : '',
            r.days_count != null ? r.days_count : '',
          ]),
        ];
        sheetName = '板块资金流向';
        filename = `板块资金流向_${kindLabel}_${m.period_label || m.period || '日'}_${stamp}.xlsx`;
      } else {
        const items = [...(this.cache.slope.items || [])].sort(
          (a, b) => Number(b.sector_slope || 0) - Number(a.sector_slope || 0)
        );
        if (!items.length) throw new Error('暂无板块斜率数据可导出');
        const m = this.cache.slope.meta || {};
        const kindLabel = m.kind === 'concept' ? '概念' : '行业';
        aoa = [
          ['板块斜率趋势'],
          ['类型', kindLabel, '窗口(日)', m.window || '', '截至', m.asof || ''],
          [],
          ['排名', '代码', '名称', '斜率', 'R²', '环境', '窗口', '截至日', '来源'],
          ...items.map((r, i) => [
            i + 1,
            r.board_code || '',
            r.board_name || '',
            r.sector_slope,
            r.slope_r2,
            r.board_env_label || r.board_env || '',
            r.sector_slope_window,
            r.slope_asof_date || '',
            r.slope_source || '',
          ]),
        ];
        sheetName = '板块斜率';
        filename = `板块斜率_${kindLabel}_${m.window || 60}日_${stamp}.xlsx`;
      }

      const ws = XLSX.utils.aoa_to_sheet(aoa);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, sheetName);
      XLSX.writeFile(wb, filename);
      if (window.CommonUtils) CommonUtils.showToast('导出成功', 'success');
    } catch (e) {
      if (window.CommonUtils) CommonUtils.showToast(e.message || '导出失败', 'error');
      else console.error(e);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prev || '导出 Excel';
      }
    }
  },
};

window.MarketAnalysis = MarketAnalysis;
