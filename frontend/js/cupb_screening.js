/**
 * CUPB 选股页：只读 cupb_signal_trace（日终预计算）。
 */
(function () {
  let bound = false;
  let lastRows = [];
  let lastMeta = null;
  let pageOffset = 0;

  const VOLUME_FLAG_LABELS = {
    bottom_shrink: '杯底缩量',
    right_expand: '右侧放量',
    handle_shrink: '柄部缩量',
    breakout_expand: '突破放量',
  };

  function apiBase() {
    if (typeof window.API_BASE_URL === 'string' && window.API_BASE_URL) {
      return window.API_BASE_URL.replace(/\/+$/, '');
    }
    if (typeof Config !== 'undefined' && Config && typeof Config.getApiBaseUrl === 'function') {
      return String(Config.getApiBaseUrl() || '').replace(/\/+$/, '');
    }
    return '';
  }

  function authHeaders() {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function num(v, digits) {
    if (v == null || v === '') return '—';
    const x = Number(v);
    if (!Number.isFinite(x)) return String(v);
    if (digits == null) return String(v);
    return x.toFixed(digits);
  }

  function fmtVal(v) {
    if (v == null || v === '') return '—';
    return String(v);
  }

  function statusLabel(s) {
    const k = String(s || '').toLowerCase();
    if (k === 'confirmed') return '已确认';
    if (k === 'forming') return '形成中';
    return s || '—';
  }

  function priceAdjustLabel(raw) {
    const p = String(raw || '');
    if (p === 'qfq') return '前复权';
    if (p === 'none' || p === 'raw') return '不复权';
    return p || '—';
  }

  function formatBoardLabels(raw) {
    if (raw == null || raw === '') return '—';
    if (Array.isArray(raw)) return raw.map((x) => String(x)).filter(Boolean).join('、') || '—';
    return String(raw);
  }

  function volumeFlagRows(row) {
    const flags = (row && row.detail && row.detail.volume_flags) || (row && row.volume_flags);
    if (!flags || typeof flags !== 'object') return [];
    return Object.keys(VOLUME_FLAG_LABELS).map((key) => ({
      key,
      label: VOLUME_FLAG_LABELS[key],
      ok: Boolean(flags[key]),
    }));
  }

  const QUALITY_FLAG_LABELS = {
    extended_base: '杯体偏长',
    prior_trend_ok: '前置上升趋势成立',
    prior_trend_fail: '前置上升趋势不足',
    u_shape_ok: '杯底偏圆',
    handle_upward: '柄部上飘',
    volume_weak: '量价偏弱',
  };

  function qualityFlagLabels(row) {
    const qf = (row && row.detail && row.detail.quality_flags) || (row && row.quality_flags);
    if (!qf) return [];
    let keys = [];
    if (Array.isArray(qf)) {
      keys = qf.map((x) => String(x)).filter(Boolean);
    } else if (typeof qf === 'object') {
      keys = Object.entries(qf)
        .filter(([, v]) => Boolean(v))
        .map(([k]) => String(k));
    } else {
      keys = [String(qf)];
    }
    return keys.map((k) => QUALITY_FLAG_LABELS[k] || k);
  }

  function qualityFlagText(row) {
    return qualityFlagLabels(row).join('、');
  }

  function setError(msg) {
    const el = document.getElementById('cupbError');
    if (!el) return;
    el.style.display = msg ? 'block' : 'none';
    el.textContent = msg || '';
  }

  function pageSize() {
    const n = parseInt((document.getElementById('cupbPageSize') || {}).value, 10);
    return [50, 100, 200].includes(n) ? n : 50;
  }

  // 与后端 VSB / CUPB 板型前缀一致（创业板含 301）
  const BOARD_PREFIXES = {
    MAIN: ['600', '601', '602', '603', '605', '000', '001'],
    SZ_SME: ['002'],
    CYB: ['300', '301'],
    KCB: ['688', '689'],
    BJ: ['43', '83', '87', '88', '92'],
  };

  const BOARD_LABELS = {
    MAIN: '主板',
    SZ_SME: '中小板',
    CYB: '创业板',
    KCB: '科创板',
    BJ: '北证',
  };

  function selectedBoardSegments() {
    const root = document.getElementById('cupb-content') || document;
    const out = [];
    root.querySelectorAll('input[name="cupbCnBoardSegment"]:checked').forEach((el) => {
      const v = String(el.value || '').trim().toUpperCase();
      if (v && BOARD_PREFIXES[v] && !out.includes(v)) out.push(v);
    });
    return out;
  }

  function codeMatchesBoards(code, segs) {
    if (!segs || !segs.length) return true;
    const c = String(code || '').trim().replace(/\D/g, '').padStart(6, '0').slice(-6);
    if (c.length !== 6) return false;
    return segs.some((seg) => (BOARD_PREFIXES[seg] || []).some((p) => c.startsWith(p)));
  }

  function buildQuery(opts) {
    const options = opts || {};
    const boards = selectedBoardSegments();
    const params = new URLSearchParams();
    let start = (document.getElementById('cupbDate') || {}).value || '';
    let end = (document.getElementById('cupbEndDate') || {}).value || '';
    if (start && end && end < start) {
      const swapped = start;
      start = end;
      end = swapped;
      const startEl = document.getElementById('cupbDate');
      const endEl = document.getElementById('cupbEndDate');
      if (startEl) startEl.value = start;
      if (endEl) endEl.value = end;
    }
    if (start && end) {
      params.set('start_date', start);
      params.set('end_date', end);
    } else if (start || end) {
      params.set('trade_date', start || end);
    }
    const status = (document.getElementById('cupbStatus') || {}).value || 'both';
    if (status && status !== 'both') params.set('status', status);
    const code = String((document.getElementById('cupbCode') || {}).value || '').trim();
    if (code) params.set('code', code);
    boards.forEach((seg) => params.append('cn_board_segment', seg));
    if (boards.length) params.set('cn_board_segments', boards.join(','));
    params.set('limit', String(options.wide ? 500 : pageSize()));
    params.set('offset', String(options.wide ? 0 : Math.max(0, pageOffset)));
    return params.toString();
  }

  function tag(kind, label) {
    const key = String(kind || 'none').toLowerCase();
    return `<span class="sepa-tag sepa-tag--${esc(key)}">${esc(label || key)}</span>`;
  }

  function statusOneLiner(row) {
    const st = String(row.status || '').toLowerCase();
    if (st === 'confirmed') {
      return `已确认突破杯口：收盘 ${fmtVal(row.last_close)} 站上杯口 ${fmtVal(row.rim)}（确认日 ${fmtVal(row.confirm_date)}）。`;
    }
    if (row.ever_confirmed) {
      return `曾于 ${fmtVal(row.first_confirm_date)} 确认过，现又跌回杯口下方，回到形成中。`;
    }
    return `杯+柄已成型，收盘 ${fmtVal(row.last_close)} 尚未站稳杯口 ${fmtVal(row.rim)}。`;
  }

  function detailHtml(row) {
    const st = String(row.status || '').toLowerCase();
    const stCls = st === 'confirmed' ? 'breakout' : 'forming';
    const volRows = volumeFlagRows(row);
    const volPass = volRows.filter((x) => x.ok).length;
    const volTotal = volRows.length || 4;
    const volChips = volRows.length
      ? volRows.map((item) => (
        `<span class="cupb-vol-chip ${item.ok ? 'is-ok' : 'is-fail'}">`
        + `<i>${item.ok ? '✓' : '✗'}</i>${esc(item.label)}</span>`
      )).join('')
      : '<span class="cupb-vol-chip is-fail">暂无量价数据</span>';
    const stages = [
      { key: 'left', title: '① 左沿', hint: '左侧杯沿', price: row.left_rim_price, date: row.left_rim_date },
      { key: 'bottom', title: '② 杯底', hint: '回撤最低', price: row.cup_bottom_price, date: row.cup_bottom_date, accent: true },
      { key: 'right', title: '③ 右沿', hint: '右侧回升', price: row.right_rim_price, date: row.right_rim_date },
      { key: 'handle', title: '④ 柄低', hint: '柄部低点', price: row.handle_low_price, date: row.handle_low_date },
      { key: 'rim', title: '⑤ 杯口', hint: '突破参考价', price: row.rim, date: null, accent: true },
    ].map((s) => (
      `<li class="cupb-stage${s.accent ? ' is-accent' : ''}">`
      + `<div class="cupb-stage-title">${esc(s.title)}<small>${esc(s.hint)}</small></div>`
      + `<div class="cupb-stage-price sepa-num">${esc(fmtVal(s.price))}</div>`
      + `<div class="cupb-stage-date">${esc(fmtVal(s.date))}</div>`
      + `</li>`
    )).join('');
    const quality = qualityFlagLabels(row)
      .map((t) => `<span class="cupb-qtag">${esc(t)}</span>`)
      .join('');
    return `
      <div class="cupb-detail-panel">
        <div class="cupb-detail-head">
          <div class="cupb-detail-headline">
            ${tag(stCls, statusLabel(row.status))}
            <span class="cupb-grade">等级 ${esc(fmtVal(row.grade))}</span>
            <span class="cupb-kv">量价 <b>${esc(String(row.volume_score == null ? '—' : row.volume_score))}/${volTotal}</b></span>
            <span class="cupb-kv">杯深 <b class="sepa-num">${esc(fmtVal(row.cup_depth_pct))}%</b></span>
            <span class="cupb-kv">柄回撤 <b class="sepa-num">${esc(fmtVal(row.handle_retrace_pct))}%</b></span>
          </div>
          <p class="cupb-detail-story">${esc(statusOneLiner(row))}</p>
        </div>

        <div class="cupb-detail-block">
          <div class="cupb-block-label">形态怎么走下来的</div>
          <ol class="cupb-stage-rail">${stages}</ol>
          <p class="cupb-rail-note">按时间从左到右：先做杯，再做柄；收盘站稳「杯口」才算确认。</p>
        </div>

        <div class="cupb-detail-block">
          <div class="cupb-block-label">量价是否配合（${volPass}/${volTotal}）</div>
          <div class="cupb-vol-row">${volChips}</div>
        </div>

        ${quality ? `<div class="cupb-detail-block"><div class="cupb-block-label">形态备注</div><div class="cupb-qtags">${quality}</div></div>` : ''}

        <div class="cupb-detail-foot">
          <span>板块 ${esc(formatBoardLabels(row.board_labels))}</span>
          <span>复权 ${esc(priceAdjustLabel(row.price_adjust))}</span>
          <span>${row.ever_confirmed ? `历史确认 ${esc(fmtVal(row.first_confirm_date))}` : '尚无历史确认'}</span>
        </div>
      </div>`;
  }

  function renderMeta(data) {
    const total = data.total || 0;
    const limit = data.limit || pageSize();
    const offset = data.offset || 0;
    const count = document.getElementById('cupbCount');
    if (count) {
      count.textContent = `共 ${total} 条 · 本页 ${(data.items || []).length} 条 · 列表为摘要，点「明细」看完整字段`;
    }
    const dateEl = document.getElementById('cupbTradeDate');
    if (dateEl) {
      const start = data.start_date || '';
      const end = data.end_date || '';
      const code = String((document.getElementById('cupbCode') || {}).value || '').trim();
      let span = '';
      if (data.mode === 'stock' && code) {
        span = start && end ? `个股 ${code} 历史 ${start} 至 ${end}` : `个股 ${code} 历史`;
      } else if (start && end && start !== end) {
        span = `区间 ${start} 至 ${end}`;
      } else if (data.trade_date) {
        span = `基准日 ${data.trade_date}`;
      } else if (start) {
        span = `基准日 ${start}`;
      }
      dateEl.textContent = span ? `${span} · 配置 #${data.config_id || '—'}` : '';
    }
    const hint = document.getElementById('cupbPoolHint');
    if (hint) {
      const boardLabel = data.cn_board_segment_label || '不限板型';
      hint.textContent = `已入库信号（cupb_signals_cn，不复权）。只填开始日查该日；两端都填查历史区间，不限天数。当前板型：${boardLabel}。`;
    }
    const pageInfo = document.getElementById('cupbPageInfo');
    const page = Math.floor(offset / limit) + 1;
    const pages = Math.max(1, Math.ceil(total / limit) || 1);
    if (pageInfo) pageInfo.textContent = `第 ${page} / ${pages} 页`;
    const prev = document.getElementById('cupbPrevPage');
    const next = document.getElementById('cupbNextPage');
    if (prev) prev.disabled = offset <= 0;
    if (next) next.disabled = offset + limit >= total;
  }

  function renderRows(rows) {
    const body = document.getElementById('cupbTableBody');
    if (!body) return;
    if (!rows.length) {
      const code = String((document.getElementById('cupbCode') || {}).value || '').trim();
      const empty = code
        ? `代码 ${esc(code)} 没有已入库的杯底信号`
        : '没有符合条件的杯底信号';
      body.innerHTML = `<tr><td colspan="10" class="empty-state">${empty}</td></tr>`;
      return;
    }
    body.innerHTML = rows.map((row, index) => {
      const code = esc(row.code);
      const name = esc(row.name || '');
      const href = `stock.html?code=${encodeURIComponent(row.code || '')}&name=${encodeURIComponent(row.name || '')}`;
      const hist = `stock_cupb_trace.html?code=${encodeURIComponent(row.code || '')}&name=${encodeURIComponent(row.name || '')}`;
      const st = String(row.status || '').toLowerCase();
      const stCls = st === 'confirmed' ? 'sepa-tag--breakout' : 'sepa-tag--forming';
      return `
        <tr class="cupb-row" data-index="${index}">
          <td class="sepa-num">${esc(row.date || '—')}</td>
          <td><a href="${href}" target="_blank" rel="noopener noreferrer">${code}</a></td>
          <td>${name}</td>
          <td><span class="sepa-tag ${stCls}">${esc(statusLabel(row.status))}</span></td>
          <td>${esc(row.grade || '—')}</td>
          <td class="sepa-num">${row.volume_score == null ? '—' : esc(row.volume_score)}</td>
          <td class="sepa-num">${num(row.cup_depth_pct, 1)}</td>
          <td>${esc(row.confirm_date || '—')}</td>
          <td class="sepa-num">${num(row.last_close)}</td>
          <td class="sepa-actions">
            <button type="button" class="gms-op-btn cupb-detail-btn" data-index="${index}" aria-expanded="false">明细</button>
            <a class="gms-op-btn" href="${hist}" target="_blank" rel="noopener noreferrer" title="该股杯底历史信号">历史</a>
            <a class="gms-op-btn" href="${href}" target="_blank" rel="noopener noreferrer">详情</a>
          </td>
        </tr>
        <tr class="cupb-detail-row" hidden>
          <td colspan="10">${detailHtml(row)}</td>
        </tr>`;
    }).join('');
  }

  function exportCsv() {
    if (!lastRows.length) return;
    const header = [
      '信号日', '代码', '名称', '状态', '曾确认', '历史确认日', '等级', '量价',
      '所属板块', '复权', '收盘', '左沿', '杯底', '右沿', '柄低', '杯口',
      '杯深%', '柄回撤%', '左沿日', '杯底日', '右沿日', '柄低日', '确认日', '质量标记',
    ];
    const lines = [header.join(',')];
    lastRows.forEach((row) => {
      const cells = [
        row.date, row.code, row.name, statusLabel(row.status),
        row.ever_confirmed ? '是' : '否', row.first_confirm_date,
        row.grade, row.volume_score, formatBoardLabels(row.board_labels),
        priceAdjustLabel(row.price_adjust), row.last_close,
        row.left_rim_price, row.cup_bottom_price, row.right_rim_price,
        row.handle_low_price, row.rim, row.cup_depth_pct, row.handle_retrace_pct,
        row.left_rim_date, row.cup_bottom_date, row.right_rim_date,
        row.handle_low_date, row.confirm_date, qualityFlagText(row),
      ].map((v) => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`);
      lines.push(cells.join(','));
    });
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    const day = (lastMeta && (lastMeta.start_date && lastMeta.end_date && lastMeta.start_date !== lastMeta.end_date
      ? `${lastMeta.start_date}_${lastMeta.end_date}`
      : lastMeta.trade_date)) || 'cupb';
    a.href = URL.createObjectURL(blob);
    a.download = `cupb-${day}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function load() {
    const loading = document.getElementById('cupbLoading');
    const refresh = document.getElementById('refreshBtn-cupb');
    const exportBtn = document.getElementById('cupbExportBtn');
    if (loading) loading.style.display = 'flex';
    if (refresh) refresh.disabled = true;
    if (exportBtn) exportBtn.style.display = 'none';
    setError('');
    const boards = selectedBoardSegments();
    try {
      const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
      const res = await fetchFn(`${apiBase()}/api/stock/cupb/signals?${buildQuery()}`, {
        headers: authHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.success === false) {
        const msg = data.message || data.detail || res.statusText || '请求失败';
        throw new Error(typeof msg === 'string' ? msg : '筛选失败');
      }
      const payload = data.data || {};
      let items = payload.items || [];
      const total = payload.total || 0;
      const limit = payload.limit || pageSize();
      const offset = payload.offset || 0;
      const boardLabel = boards.length
        ? boards.map((s) => BOARD_LABELS[s] || s).join('、')
        : '不限板型';
      if (boards.length) {
        items = items.filter((row) => codeMatchesBoards(row.code, boards));
      }

      lastRows = items;
      lastMeta = Object.assign({}, payload, {
        total,
        limit,
        offset,
        cn_board_segments: boards,
        cn_board_segment_label: boardLabel,
        items,
      });
      if (payload.trade_date && !(document.getElementById('cupbDate') || {}).value) {
        const dateInput = document.getElementById('cupbDate');
        if (dateInput) dateInput.value = payload.trade_date;
      }
      renderMeta(lastMeta);
      renderRows(lastRows);
      if (exportBtn && lastRows.length) exportBtn.style.display = '';
    } catch (err) {
      lastRows = [];
      renderRows([]);
      const count = document.getElementById('cupbCount');
      if (count) count.textContent = '筛选没有完成';
      setError(`筛选没有完成：${err && err.message ? err.message : '网络错误'}。请稍后重试。`);
    } finally {
      if (loading) loading.style.display = 'none';
      if (refresh) refresh.disabled = false;
    }
  }

  function onTableClick(event) {
    const btn = event.target.closest('.cupb-detail-btn');
    if (!btn) return;
    const row = btn.closest('tr');
    const detail = row && row.nextElementSibling;
    if (!detail || !detail.classList.contains('cupb-detail-row')) return;
    const open = detail.hasAttribute('hidden');
    detail.toggleAttribute('hidden', !open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.classList.toggle('active', open);
  }

  function init() {
    if (bound) return;
    const refresh = document.getElementById('refreshBtn-cupb');
    const body = document.getElementById('cupbTableBody');
    if (!refresh || !body) return;
    bound = true;
    refresh.addEventListener('click', () => {
      pageOffset = 0;
      void load();
    });
    const exportBtn = document.getElementById('cupbExportBtn');
    if (exportBtn) exportBtn.addEventListener('click', exportCsv);
    body.addEventListener('click', onTableClick);
    const prev = document.getElementById('cupbPrevPage');
    const next = document.getElementById('cupbNextPage');
    if (prev) {
      prev.addEventListener('click', () => {
        pageOffset = Math.max(0, pageOffset - pageSize());
        void load();
      });
    }
    if (next) {
      next.addEventListener('click', () => {
        pageOffset += pageSize();
        void load();
      });
    }
    const pageSizeEl = document.getElementById('cupbPageSize');
    if (pageSizeEl) {
      pageSizeEl.addEventListener('change', () => {
        pageOffset = 0;
        void load();
      });
    }
    document.querySelectorAll('input[name="cupbCnBoardSegment"]').forEach((el) => {
      el.addEventListener('change', () => {
        pageOffset = 0;
        void load();
      });
    });
  }

  window.CupbScreening = { init, load };
  init();
})();
