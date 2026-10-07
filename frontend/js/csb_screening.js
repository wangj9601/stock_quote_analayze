/**
 * CSB 通道粘合突破 — 选股页（精简 Tab：策略选股）
 */
(function () {
  let lastSignalRows = [];
  /** @type {Set<string>} CN:code */
  let observeCodeSet = new Set();
  let observeCodesLoaded = false;

  function apiBase() {
    if (typeof window.API_BASE_URL === 'string' && window.API_BASE_URL) {
      return window.API_BASE_URL.replace(/\/+$/, '');
    }
    if (typeof Config !== 'undefined' && Config && typeof Config.getApiBaseUrl === 'function') {
      return String(Config.getApiBaseUrl() || '').replace(/\/+$/, '');
    }
    return '';
  }

  function apiUrl(path) {
    const p = path.startsWith('/') ? path : `/${path}`;
    return `${apiBase()}${p}`;
  }

  function authHeaders() {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token') || '';
    const h = { 'Content-Type': 'application/json' };
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }

  async function api(url, options) {
    const full = url.startsWith('http') ? url : apiUrl(url);
    const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
    const res = await fetchFn(full, {
      ...options,
      headers: { ...authHeaders(), ...(options && options.headers) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.message || res.statusText;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }

  function toast(msg, type) {
    if (window.CommonUtils && typeof CommonUtils.showToast === 'function') {
      CommonUtils.showToast(msg, type || 'info');
      return;
    }
    if (type === 'error') console.error(msg);
  }

  function showErr(msg) {
    const el = document.getElementById('csbError');
    if (!el) return;
    el.style.display = msg ? 'block' : 'none';
    el.textContent = msg || '';
  }

  function fmt(v, n) {
    if (v == null || v === '') return '-';
    const x = Number(v);
    return Number.isFinite(x) ? x.toFixed(n == null ? 2 : n) : String(v);
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function signalTypeLabel(t) {
    const s = String(t || '').trim();
    const map = {
      CSB_SETUP: 'SETUP',
      CSB_PROBE: 'PROBE',
      CSB_BREAKOUT: 'BREAKOUT',
      CSB_LPS: 'LPS',
      CSB_FALSE_BREAK: '假突破',
      CSB_STOP: '止损',
      CSB_TRAIL: '跟踪',
      CSB_DISTRIBUTE: '派发',
    };
    return map[s] || s || '-';
  }

  function observeKey(code) {
    const c = String(code || '').trim();
    return c ? `CN:${c}` : '';
  }

  function isObserved(code) {
    const key = observeKey(code);
    return key ? observeCodeSet.has(key) : false;
  }

  async function loadObserveCodes() {
    try {
      const data = await api('/api/stock/trade-observe/codes?source=csb');
      observeCodeSet = new Set(Array.isArray(data) ? data : []);
      observeCodesLoaded = true;
    } catch (_) {
      // 未登录时忽略，按钮仍显示「观察」
      observeCodesLoaded = false;
    }
  }

  function stockAnalysisHref(code, name) {
    if (window.StockTradeLink && typeof window.StockTradeLink.buildHref === 'function') {
      return window.StockTradeLink.buildHref(code, name, { tab: 'analysis' });
    }
    const q = new URLSearchParams({ tab: 'analysis' });
    const c = String(code || '').trim();
    const n = String(name || '').trim();
    if (c) q.set('code', c);
    if (n) q.set('name', n);
    return `stock.html?${q.toString()}`;
  }

  function getScreeningApp() {
    if (typeof ScreeningPage !== 'undefined') return ScreeningPage;
    if (typeof window !== 'undefined') return window.ScreeningPage || null;
    return null;
  }

  function selectedIndustryCodes() {
    const app = getScreeningApp();
    if (app && typeof app.getCsbSelectedIndustryBoardCodes === 'function') {
      return app.getCsbSelectedIndustryBoardCodes();
    }
    return Array.isArray(app?.csbSelectedIndustryBoardCodes)
      ? app.csbSelectedIndustryBoardCodes.filter(Boolean)
      : [];
  }

  function selectedConceptCodes() {
    const app = getScreeningApp();
    if (app && typeof app.getCsbSelectedConceptBoardCodes === 'function') {
      return app.getCsbSelectedConceptBoardCodes();
    }
    return Array.isArray(app?.csbSelectedConceptBoardCodes)
      ? app.csbSelectedConceptBoardCodes.filter(Boolean)
      : [];
  }

  const CSB_CN_BOARD_SEG_LABELS = {
    MAIN: '主板',
    CYB: '创业板',
    SZ_SME: '中小板',
    KCB: '科创板',
    BJ: '北证',
  };

  function selectedBoardSegments() {
    const segs = [];
    document.querySelectorAll('input[name="csbCnBoardSegment"]:checked').forEach((el) => {
      const v = String(el.value || '').trim().toUpperCase();
      if (v && v !== 'ALL' && !segs.includes(v)) segs.push(v);
    });
    return segs;
  }

  function preferredBoardCodeSource(kind, codes) {
    const app = getScreeningApp();
    if (app && typeof app._gmsPreferredBoardCodeSource === 'function') {
      return app._gmsPreferredBoardCodeSource(kind, codes);
    }
    return 'tonghuashun';
  }

  function syncScopeUI() {
    const scope = document.getElementById('csbScope')?.value || 'market';
    const indWrap = document.getElementById('csbIndustryBoardWrap');
    const conWrap = document.getElementById('csbConceptBoardWrap');
    const stockGroup = document.getElementById('csbStockCodeGroup');
    const singleHint = document.getElementById('csbSingleSkipFilterHint');
    const traceWrap = document.getElementById('csbTraceOnlyWrap');
    if (indWrap) indWrap.style.display = scope === 'industry_board' ? 'flex' : 'none';
    if (conWrap) conWrap.style.display = scope === 'concept_board' ? 'flex' : 'none';
    if (stockGroup) stockGroup.style.display = scope === 'single' ? 'flex' : 'none';
    if (singleHint) singleHint.style.display = scope === 'single' ? 'flex' : 'none';
    if (traceWrap) traceWrap.style.display = scope === 'market' ? '' : 'none';
    const app = getScreeningApp();
    if (app && typeof app.refreshBoardRolesPanelForOwner === 'function') {
      if (scope === 'industry_board' && typeof app.loadGmsIndustryBoardOptions === 'function') {
        void app.loadGmsIndustryBoardOptions().then(() => app.refreshBoardRolesPanelForOwner('csb'));
      } else if (scope === 'concept_board' && typeof app.loadGmsConceptBoardOptions === 'function') {
        void app.loadGmsConceptBoardOptions().then(() => app.refreshBoardRolesPanelForOwner('csb'));
      } else {
        app.refreshBoardRolesPanelForOwner('csb');
      }
    }
  }

  function resolveSignalDate(row) {
    const raw = row && (row.signal_date || row.trade_date || row.date || row.search_date);
    if (!raw) return null;
    const s = String(raw).trim().slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null;
  }

  function buildObserveSnapshot(row) {
    return {
      source: 'csb',
      signal_type: row.signal_type || null,
      score: row.score != null ? Number(row.score) : null,
      close: row.close != null ? Number(row.close) : null,
      channel_lower: row.channel_lower != null ? Number(row.channel_lower) : null,
      channel_upper: row.channel_upper != null ? Number(row.channel_upper) : null,
      squeeze_days: row.squeeze_days != null ? Number(row.squeeze_days) : null,
      squeeze_pct: row.squeeze_pct != null ? Number(row.squeeze_pct) : null,
      entry_kind: row.entry_kind || null,
      entry_low: row.entry_low != null ? Number(row.entry_low) : null,
      suggested_position: row.suggested_position != null ? Number(row.suggested_position) : null,
      signal_date: resolveSignalDate(row),
    };
  }

  function observeButtonHtml(row, index) {
    const code = String(row.code || '').trim();
    const added = isObserved(code);
    const cls = `gms-op-btn gms-op-btn--primary csb-trade-observe-add${added ? ' is-added' : ''}`;
    const label = added ? '已观察' : '观察';
    const title = added ? '已在交易观察列表（通道突破）' : '加入统一交易观察（来源：通道突破）';
    return `<button type="button" class="${cls}" data-row="${index}" data-code="${esc(code)}" title="${esc(title)}" ${added ? 'disabled' : ''}>${label}</button>`;
  }

  function renderSignalRows(rows, opts = {}) {
    const body = document.getElementById('csbResultsBody');
    if (!body) return;
    const list = rows || [];
    lastSignalRows = list;
    document.getElementById('csbResultsCount').textContent = `共 ${list.length} 只`;
    if (!list.length) {
      const emptyText = opts.emptyHint || '无符合条件的结果';
      body.innerHTML = `<tr><td colspan="9" class="empty-state">${esc(emptyText)}</td></tr>`;
      return;
    }
    body.innerHTML = list
      .map((r, index) => {
        const histHref = `stock_csb_trace.html?code=${encodeURIComponent(r.code || '')}&name=${encodeURIComponent(r.name || '')}`;
        const analysisHref = stockAnalysisHref(r.code, r.name);
        const codeCell = r.code
          ? `<a class="stock-code gms-stock-code-link" href="${esc(analysisHref)}" target="_blank" rel="noopener noreferrer" title="打开个股分析">${esc(r.code)}</a>`
          : '';
        const sig = signalTypeLabel(r.signal_type);
        const sigCls = String(r.signal_type || '').toLowerCase().replace(/_/g, '-');
        const ops = [
          observeButtonHtml(r, index),
          `<button type="button" class="gms-op-btn csb-score-detail-toggle" data-row="${index}" title="展开/收起信号计算明细" aria-expanded="false">明细</button>`,
          `<a href="${histHref}" class="gms-op-btn" target="_blank" rel="noopener noreferrer" title="该股历史信号">历史</a>`,
        ];
        let detailHtml = '<div class="gms-score-detail-inner">明细组件未加载</div>';
        if (window.CsbScoreDetail && typeof window.CsbScoreDetail.buildHtml === 'function') {
          detailHtml = window.CsbScoreDetail.buildHtml(r);
        }
        return `<tr class="csb-signal-row" data-csb-row="${index}">
          <td class="gms-col-code">${codeCell}</td>
          <td>${esc(r.name || '')}</td>
          <td><span class="csb-signal-tag csb-signal-tag--${esc(sigCls)}">${esc(sig)}</span></td>
          <td class="csb-num">${fmt(r.score, 1)}</td>
          <td class="csb-num">${fmt(r.close)}</td>
          <td class="csb-num">${fmt(r.channel_lower)}</td>
          <td class="csb-num">${fmt(r.channel_upper)}</td>
          <td class="csb-num">${r.squeeze_days != null ? String(r.squeeze_days) : '-'}</td>
          <td class="gms-col-actions"><div class="action-links csb-action-links">${ops.join('')}</div></td>
        </tr>
        <tr class="gms-score-detail-row csb-score-detail-row" data-detail-for="${index}" hidden>
          <td colspan="9" class="gms-score-detail-cell csb-score-detail-cell">${detailHtml}</td>
        </tr>`;
      })
      .join('');
  }

  async function addTradeObserve(rowIndex, btnEl) {
    const row = lastSignalRows[rowIndex];
    if (!row || !row.code) {
      toast('未找到该行信号数据，请刷新筛选后重试', 'warning');
      return;
    }
    const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
    if (!user || !user.id) {
      toast('请先登录后再加入交易观察', 'warning');
      window.location.href = 'login.html';
      return;
    }
    const code = String(row.code || '').trim();
    const key = observeKey(code);
    if (isObserved(code)) {
      toast('已在交易观察列表中', 'info');
      if (btnEl) {
        btnEl.textContent = '已观察';
        btnEl.classList.add('is-added');
        btnEl.disabled = true;
      }
      return;
    }
    try {
      if (btnEl) {
        btnEl.disabled = true;
        btnEl.textContent = '加入中...';
      }
      await api('/api/stock/trade-observe/add', {
        method: 'POST',
        body: JSON.stringify({
          code,
          market: 'CN',
          name: row.name || code,
          source: 'csb',
          signal_date: resolveSignalDate(row),
          snapshot: buildObserveSnapshot(row),
          extra: {
            source: 'csb',
            signal_type: row.signal_type || null,
            entry_kind: row.entry_kind || null,
          },
        }),
      });
      if (key) observeCodeSet.add(key);
      toast(`已加入交易观察：${row.name || code}`, 'success');
      if (btnEl) {
        btnEl.textContent = '已观察';
        btnEl.classList.add('is-added');
        btnEl.disabled = true;
        btnEl.title = '已在交易观察列表（通道突破）';
      }
    } catch (e) {
      toast(e.message || '加入交易观察失败', 'error');
      await loadObserveCodes();
      const still = isObserved(code);
      if (btnEl) {
        if (still) {
          btnEl.textContent = '已观察';
          btnEl.classList.add('is-added');
          btnEl.disabled = true;
        } else {
          btnEl.textContent = '观察';
          btnEl.classList.remove('is-added');
          btnEl.disabled = false;
        }
      }
    }
  }

  function toggleDetail(rowIndex, btnEl) {
    const tbody = document.getElementById('csbResultsBody');
    const detailRow = tbody?.querySelector(`tr.csb-score-detail-row[data-detail-for="${rowIndex}"]`);
    const signalRow = tbody?.querySelector(`tr.csb-signal-row[data-csb-row="${rowIndex}"]`);
    if (!detailRow) return;
    const willShow = detailRow.hasAttribute('hidden');
    detailRow.toggleAttribute('hidden', !willShow);
    if (btnEl) {
      btnEl.classList.toggle('active', willShow);
      btnEl.setAttribute('aria-expanded', willShow ? 'true' : 'false');
      btnEl.textContent = willShow ? '收起' : '明细';
    }
    if (signalRow) signalRow.classList.toggle('is-detail-open', willShow);
  }

  async function refreshSignals() {
    const loading = document.getElementById('csbLoading');
    const body = document.getElementById('csbResultsBody');
    showErr('');
    if (loading) loading.style.display = 'flex';
    try {
      if (!observeCodesLoaded) {
        await loadObserveCodes();
      }
      const scope = document.getElementById('csbScope').value || 'market';
      const date = document.getElementById('csbDate').value || '';
      const entryOnly = document.getElementById('csbEntryOnly').checked;
      const traceOnly = document.getElementById('csbTraceOnly')?.checked;
      const signalType = (document.getElementById('csbSignalType')?.value || '').trim();
      const configRaw = (document.getElementById('csbConfigId')?.value || '').trim();
      const stockCode = (document.getElementById('csbStockCode')?.value || '').trim();
      const industryCodes = selectedIndustryCodes();
      const conceptCodes = selectedConceptCodes();
      const boardSegs = selectedBoardSegments();

      if (scope === 'industry_board' && !industryCodes.length) {
        throw new Error('请先选择行业板块');
      }
      if (scope === 'concept_board' && !conceptCodes.length) {
        throw new Error('请先选择概念板块');
      }
      if (scope === 'single' && !stockCode) {
        throw new Error('个股范围需要填写股票代码或名称');
      }

      const q = new URLSearchParams({
        scope,
        entry_only: String(entryOnly),
        max_results: scope === 'single' ? '10' : '10000',
      });
      if (date) q.set('date', date);
      if (stockCode) q.set('stock_code', stockCode);
      if (signalType) q.set('signal_type', signalType);
      if (configRaw && /^\d+$/.test(configRaw)) q.set('config_id', configRaw);
      if (traceOnly && scope === 'market') q.set('trace_only', 'true');
      if (scope !== 'single') {
        boardSegs.forEach((seg) => q.append('cn_board_segment', seg));
      }
      industryCodes.forEach((c) => q.append('industry_board_code', c));
      conceptCodes.forEach((c) => q.append('concept_board_code', c));
      if (scope === 'industry_board' && industryCodes.length) {
        q.set('board_code_source', preferredBoardCodeSource('industry', industryCodes));
      } else if (scope === 'concept_board' && conceptCodes.length) {
        q.set('board_code_source', preferredBoardCodeSource('concept', conceptCodes));
      }

      let data = await api(`/api/screening/csb-strategy?${q}`);
      if (traceOnly && scope === 'market' && (!data.data || !data.data.length)) {
        q.delete('trace_only');
        data = await api(`/api/screening/csb-strategy?${q}`);
      }

      const rows = data.data || [];
      const asof = data.search_date || data.asof_date || '-';
      const srcLabel =
        data.source === 'csb_signal_trace'
          ? '预计算'
          : data.source === 'live' || data.source === 'realtime'
            ? '实时计算'
            : data.source || 'live';
      const metaParts = [
        `回溯基准日 ${asof}`,
        `数据来源 ${srcLabel}`,
        data.config_id != null ? `config ${data.config_id}` : '',
      ].filter(Boolean);
      if (data.stock_code) metaParts.push(`个股 ${data.stock_code}`);
      const boardLabel =
        data.cn_board_segment_label ||
        data.cn_board_segment ||
        (Array.isArray(data.cn_board_segments) && data.cn_board_segments.length
          ? data.cn_board_segments.map((s) => CSB_CN_BOARD_SEG_LABELS[s] || s).join('、')
          : '');
      if (boardLabel) metaParts.push(`板型 ${boardLabel}`);
      if (data.industry_board_codes && data.industry_board_codes.length) {
        metaParts.push(`行业 ${data.industry_board_codes.join(',')}`);
      }
      if (data.concept_board_codes && data.concept_board_codes.length) {
        metaParts.push(`概念 ${data.concept_board_codes.join(',')}`);
      }
      if (data.message) showErr(data.message);
      const metaEl = document.getElementById('csbSearchMeta');
      if (metaEl) metaEl.textContent = metaParts.join(' · ');
      const hint = document.getElementById('csbDataDateHint');
      if (hint) {
        hint.textContent = data.need_precompute
          ? '（全市场需预计算或缩小范围）'
          : traceOnly && scope === 'market'
            ? '（优先读预计算，无数据时回退现算）'
            : '';
      }
      const dateEl = document.getElementById('csbDate');
      if (dateEl && asof && asof !== '-' && (!date || data.date_snapped)) {
        dateEl.value = asof;
      }
      renderSignalRows(rows, {
        emptyHint: data.need_precompute
          ? '全市场暂无预计算结果。请先在管理端执行 CSB 预计算，或改用自选/板块/个股范围。'
          : null,
      });
    } catch (e) {
      showErr(e.message || String(e));
      if (body) body.innerHTML = '<tr><td colspan="9" class="empty-state">加载失败</td></tr>';
    } finally {
      if (loading) loading.style.display = 'none';
    }
  }

  function bind() {
    const root = document.getElementById('csb-content');
    if (!root) return;

    syncScopeUI();
    void loadObserveCodes();
    document.getElementById('csbScope')?.addEventListener('change', () => syncScopeUI());
    document.getElementById('csbRefreshBtn')?.addEventListener('click', () => refreshSignals());
    document.getElementById('csbStockCode')?.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const scope = document.getElementById('csbScope')?.value || 'market';
      if (scope !== 'single') return;
      e.preventDefault();
      refreshSignals();
    });
    document.getElementById('csbResultsBody')?.addEventListener('click', (e) => {
      const observeBtn = e.target.closest('.csb-trade-observe-add');
      if (observeBtn) {
        e.preventDefault();
        const rowIndex = parseInt(observeBtn.getAttribute('data-row') || '-1', 10);
        if (Number.isFinite(rowIndex) && rowIndex >= 0) {
          void addTradeObserve(rowIndex, observeBtn);
        }
        return;
      }
      const detailBtn = e.target.closest('.csb-score-detail-toggle');
      if (!detailBtn) return;
      e.preventDefault();
      const rowIndex = detailBtn.getAttribute('data-row');
      toggleDetail(rowIndex, detailBtn);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
