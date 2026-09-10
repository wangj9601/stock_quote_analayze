/**
 * CSB 通道粘合突破 — 选股页（精简 Tab：策略选股）
 */
(function () {
  let lastSignalRows = [];

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
      CSB_FALSE_BREAK: '假突破',
      CSB_STOP: '止损',
      CSB_TRAIL: '跟踪',
    };
    return map[s] || s || '-';
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

  function selectedBoardSegment() {
    const el = document.querySelector('input[name="csbCnBoardSegment"]:checked');
    return el ? String(el.value || 'ALL').trim().toUpperCase() : 'ALL';
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

  function renderSignalRows(rows) {
    const body = document.getElementById('csbResultsBody');
    if (!body) return;
    const list = rows || [];
    lastSignalRows = list;
    document.getElementById('csbResultsCount').textContent = `共 ${list.length} 只`;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty-state">无符合条件的结果</td></tr>';
      return;
    }
    body.innerHTML = list
      .map((r, index) => {
        const histHref = `stock_csb_trace.html?code=${encodeURIComponent(r.code || '')}&name=${encodeURIComponent(r.name || '')}`;
        const analysisHref = stockAnalysisHref(r.code, r.name);
        const codeCell = r.code
          ? `<a class="stock-code gms-stock-code-link" href="${esc(analysisHref)}" target="_blank" rel="noopener noreferrer" title="打开个股分析">${esc(r.code)}</a>`
          : '';
        const ops = [
          `<button type="button" class="gms-op-btn csb-score-detail-toggle" data-row="${index}" title="展开/收起信号计算明细">明细</button>`,
          `<a href="${histHref}" class="gms-op-btn" target="_blank" rel="noopener noreferrer" title="该股历史信号">历史</a>`,
        ];
        let detailHtml = '<div class="gms-score-detail-inner">明细组件未加载</div>';
        if (window.CsbScoreDetail && typeof window.CsbScoreDetail.buildHtml === 'function') {
          detailHtml = window.CsbScoreDetail.buildHtml(r);
        }
        return `<tr data-csb-row="${index}">
          <td class="gms-col-code">${codeCell}</td>
          <td>${esc(r.name || '')}</td>
          <td>${esc(signalTypeLabel(r.signal_type))}</td>
          <td>${fmt(r.score, 1)}</td>
          <td>${fmt(r.close)}</td>
          <td>${fmt(r.channel_lower)}</td>
          <td>${fmt(r.channel_upper)}</td>
          <td>${r.squeeze_days != null ? String(r.squeeze_days) : '-'}</td>
          <td class="gms-col-actions"><div class="action-links">${ops.join('')}</div></td>
        </tr>
        <tr class="gms-score-detail-row csb-score-detail-row" data-detail-for="${index}" style="display:none;">
          <td colspan="9" class="gms-score-detail-cell">${detailHtml}</td>
        </tr>`;
      })
      .join('');
  }

  async function refreshSignals() {
    const loading = document.getElementById('csbLoading');
    const body = document.getElementById('csbResultsBody');
    showErr('');
    if (loading) loading.style.display = 'flex';
    try {
      const scope = document.getElementById('csbScope').value || 'market';
      const date = document.getElementById('csbDate').value || '';
      const entryOnly = document.getElementById('csbEntryOnly').checked;
      const traceOnly = document.getElementById('csbTraceOnly')?.checked;
      const signalType = (document.getElementById('csbSignalType')?.value || '').trim();
      const configRaw = (document.getElementById('csbConfigId')?.value || '').trim();
      const stockCode = (document.getElementById('csbStockCode')?.value || '').trim();
      const industryCodes = selectedIndustryCodes();
      const conceptCodes = selectedConceptCodes();
      const boardSeg = selectedBoardSegment();

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
        max_results: scope === 'single' ? '10' : '200',
      });
      if (date) q.set('date', date);
      if (stockCode) q.set('stock_code', stockCode);
      if (signalType) q.set('signal_type', signalType);
      if (configRaw && /^\d+$/.test(configRaw)) q.set('config_id', configRaw);
      if (traceOnly && scope === 'market') q.set('trace_only', 'true');
      if (boardSeg && boardSeg !== 'ALL' && scope !== 'single') q.set('cn_board_segment', boardSeg);
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
      if (data.cn_board_segment) metaParts.push(`板型 ${data.cn_board_segment}`);
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
      renderSignalRows(rows);
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
      const detailBtn = e.target.closest('.csb-score-detail-toggle');
      if (!detailBtn) return;
      e.preventDefault();
      const rowIndex = detailBtn.getAttribute('data-row');
      const tbody = document.getElementById('csbResultsBody');
      const detailRow = tbody?.querySelector(`tr.csb-score-detail-row[data-detail-for="${rowIndex}"]`);
      if (!detailRow) return;
      const show = detailRow.style.display === 'none' || !detailRow.style.display;
      detailRow.style.display = show ? 'table-row' : 'none';
      detailBtn.classList.toggle('active', show);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
