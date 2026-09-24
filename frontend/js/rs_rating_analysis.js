/**
 * 分析频道 · 个股相对强度分析（A股 / 港股 RS Rating 排行 + 批量个股分析）
 */
(function (global) {
  'use strict';

  const TRACE_PAGE = 'stock_rs_trace.html';

  function apiBase() {
    // 与 rpe_screening / common.js 对齐：优先 Config，其次脚本全局 API_BASE_URL
    if (typeof global.Config !== 'undefined' && Config && typeof Config.getApiBaseUrl === 'function') {
      const b = String(Config.getApiBaseUrl() || '').replace(/\/+$/, '');
      if (b) return b;
    }
    if (typeof global.API_BASE_URL === 'string' && global.API_BASE_URL) {
      return global.API_BASE_URL.replace(/\/+$/, '');
    }
    try {
      // common.js 顶层 const 不挂 window，但同页脚本可见
      if (typeof API_BASE_URL === 'string' && API_BASE_URL) {
        return String(API_BASE_URL).replace(/\/+$/, '');
      }
    } catch (e) { /* ignore */ }
    // 本地静态站（非 80/443/5000）兜底直连后端
    try {
      const host = global.location && global.location.hostname;
      const port = String((global.location && global.location.port) || '');
      const protocol = (global.location && global.location.protocol) || 'http:';
      if (
        (host === 'localhost' || host === '127.0.0.1') &&
        port &&
        port !== '80' &&
        port !== '443' &&
        port !== '5000'
      ) {
        return `${protocol}//${host}:5000`;
      }
    } catch (e2) { /* ignore */ }
    return '';
  }

  function apiUrl(path) {
    const p = path.startsWith('/') ? path : `/${path}`;
    return `${apiBase()}${p}`;
  }

  const state = {
    market: 'CN',
    page: 1,
    pageSize: 50,
    total: 0,
    asof: null,
    rows: [],
    selected: new Map(), // code -> { code, name, market }
    loaded: false,
    binding: false,
    watchlistBusy: false,
  };

  function toast(msg, type) {
    if (global.CommonUtils && CommonUtils.showToast) {
      CommonUtils.showToast(msg, type || 'info');
      return;
    }
    console.log(`[rsa] ${msg}`);
  }

  function authFetch(url, opts) {
    if (typeof global.authFetch === 'function') {
      return global.authFetch(url, opts || {});
    }
    if (typeof global.Auth !== 'undefined' && Auth.fetch) {
      return Auth.fetch(url, opts || {});
    }
    return fetch(url, opts || {});
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtRoc(v) {
    if (v == null || v === '' || Number.isNaN(Number(v))) return '--';
    const n = Number(v) * 100;
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(1)}%`;
  }

  function fmtRaw(v) {
    if (v == null || v === '' || Number.isNaN(Number(v))) return '--';
    return Number(v).toFixed(4);
  }

  function rsToneClass(rating) {
    const n = Number(rating);
    if (!Number.isFinite(n)) return '';
    if (n >= 90) return 'rsa-tone-strong';
    if (n >= 70) return 'rsa-tone-good';
    if (n >= 50) return 'rsa-tone-mid';
    return 'rsa-tone-weak';
  }

  function currentMarket() {
    const el = document.querySelector('input[name="rsaMarket"]:checked');
    return el && el.value === 'HK' ? 'HK' : 'CN';
  }

  function syncBoardWrap() {
    const wrap = document.getElementById('rsaBoardWrap');
    if (!wrap) return;
    wrap.style.display = currentMarket() === 'CN' ? '' : 'none';
  }

  function selectedBoardSegments() {
    if (currentMarket() !== 'CN') return [];
    return Array.from(document.querySelectorAll('input[name="rsaCnBoard"]:checked'))
      .map((c) => String(c.value || '').trim().toUpperCase())
      .filter(Boolean);
  }

  function updateBatchBtn() {
    const btn = document.getElementById('rsaBatchAnalyzeBtn');
    const wlBtn = document.getElementById('rsaBatchWatchlistBtn');
    const meta = document.getElementById('rsaMeta');
    const n = state.selected.size;
    if (btn) btn.disabled = n === 0;
    if (wlBtn) wlBtn.disabled = n === 0 || !!state.watchlistBusy;
    if (meta && state.loaded) {
      const base = state.asof
        ? `基准日 ${state.asof} · 共 ${state.total} 只 · 第 ${state.page} 页`
        : `共 ${state.total} 只`;
      meta.textContent = n > 0 ? `${base} · 已选 ${n}` : base;
    }
  }

  function buildQueryFixed() {
    const params = new URLSearchParams();
    params.set('market', currentMarket());
    params.set('page', String(state.page));
    params.set('page_size', String(state.pageSize));
    const kw = document.getElementById('rsaKeyword');
    if (kw && kw.value.trim()) params.set('keyword', kw.value.trim());
    const dateEl = document.getElementById('rsaDate');
    if (dateEl && dateEl.value) params.set('date', dateEl.value);
    const minEl = document.getElementById('rsaMinRating');
    if (minEl && minEl.value) params.set('min_rating', minEl.value);
    selectedBoardSegments().forEach((s) => params.append('cn_board_segments', s));
    return params;
  }

  function renderRows(rows) {
    const body = document.getElementById('rsaResultsBody');
    if (!body) return;
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="13" class="empty-state">当前条件下无数据</td></tr>';
      return;
    }
    const mkt = currentMarket();
    body.innerHTML = rows
      .map((r) => {
        const code = String(r.code || '').trim();
        const name = r.name || '';
        const checked = state.selected.has(code) ? ' checked' : '';
        const rating = r.rs_rating == null ? '--' : String(r.rs_rating);
        const tone = rsToneClass(r.rs_rating);
        const detailHref =
          mkt === 'HK'
            ? `stock.html?code=${encodeURIComponent(code)}&market=HK`
            : `stock.html?code=${encodeURIComponent(code)}`;
        const traceHref = `${TRACE_PAGE}?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`;
        return `<tr data-code="${esc(code)}">
          <td class="rsa-col-check"><input type="checkbox" class="rsa-row-cb" data-code="${esc(code)}" data-name="${esc(name)}"${checked}></td>
          <td class="${tone}"><strong>${esc(rating)}</strong></td>
          <td>${esc(r.strength_label || '--')}</td>
          <td><a class="ba-stock-code-link" href="${esc(detailHref)}" target="_blank" rel="noopener">${esc(code)}</a></td>
          <td>${esc(name || '--')}</td>
          <td>${esc((r.date || '').slice(0, 10) || '--')}</td>
          <td>${esc(fmtRoc(r.roc_63))}</td>
          <td>${esc(fmtRoc(r.roc_126))}</td>
          <td>${esc(fmtRoc(r.roc_189))}</td>
          <td>${esc(fmtRoc(r.roc_252))}</td>
          <td>${esc(fmtRaw(r.rs_raw))}</td>
          <td>${r.universe_size != null ? esc(r.universe_size) : '--'}</td>
          <td>
            <a class="gms-op-btn" href="${esc(traceHref)}" target="_blank" rel="noopener">追溯</a>
            <button type="button" class="gms-op-btn rsa-analyze-one" data-code="${esc(code)}" data-name="${esc(name)}">分析</button>
            <button type="button" class="gms-op-btn rsa-watchlist-one" data-code="${esc(code)}" data-name="${esc(name)}" data-perm="channel.watchlist.tab.default.btn.add" title="加入自选股">自选</button>
          </td>
        </tr>`;
      })
      .join('');
  }

  function renderPager() {
    const pager = document.getElementById('rsaPager');
    const info = document.getElementById('rsaPageInfo');
    const prev = document.getElementById('rsaPrevBtn');
    const next = document.getElementById('rsaNextBtn');
    if (!pager) return;
    const pages = Math.max(1, Math.ceil(state.total / state.pageSize) || 1);
    pager.hidden = !state.loaded;
    if (info) info.textContent = `第 ${state.page} / ${pages} 页（共 ${state.total} 只）`;
    if (prev) prev.disabled = state.page <= 1;
    if (next) next.disabled = state.page >= pages;
  }

  async function load(opts) {
    const options = opts || {};
    if (options.resetPage) state.page = 1;
    state.market = currentMarket();
    syncBoardWrap();
    const body = document.getElementById('rsaResultsBody');
    if (body) {
      body.innerHTML = '<tr><td colspan="13" class="empty-state">加载中…</td></tr>';
    }
    const qs = buildQueryFixed().toString();
    const url = `${apiUrl('/api/analysis/rs-ratings')}?${qs}`;
    try {
      const resp = await authFetch(url);
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.success === false) {
        const msg = data.message || data.detail || `加载失败 ${resp.status}`;
        if (body) {
          body.innerHTML = `<tr><td colspan="13" class="empty-state">${esc(msg)}</td></tr>`;
        }
        toast(msg, 'error');
        state.loaded = false;
        renderPager();
        updateBatchBtn();
        return;
      }
      state.rows = Array.isArray(data.data) ? data.data : [];
      state.total = Number(data.total) || 0;
      state.page = Number(data.page) || state.page;
      state.pageSize = Number(data.page_size) || state.pageSize;
      state.asof = data.asof || null;
      state.loaded = true;
      renderRows(state.rows);
      renderPager();
      updateBatchBtn();
      const allCb = document.getElementById('rsaSelectAllCb');
      if (allCb) allCb.checked = false;
    } catch (e) {
      const msg = (e && e.message) || '网络错误';
      if (body) {
        body.innerHTML = `<tr><td colspan="13" class="empty-state">${esc(msg)}</td></tr>`;
      }
      toast(msg, 'error');
    }
  }

  function setRowSelected(code, name, on) {
    const c = String(code || '').trim();
    if (!c) return;
    if (on) {
      state.selected.set(c, { code: c, name: name || '', market: currentMarket() });
    } else {
      state.selected.delete(c);
    }
    updateBatchBtn();
  }

  function selectPage(on) {
    state.rows.forEach((r) => {
      const code = String(r.code || '').trim();
      if (!code) return;
      setRowSelected(code, r.name || '', on);
    });
    document.querySelectorAll('#rsaResultsBody .rsa-row-cb').forEach((cb) => {
      cb.checked = !!on;
    });
    const allCb = document.getElementById('rsaSelectAllCb');
    if (allCb) allCb.checked = !!on;
  }

  function clearSelection() {
    state.selected.clear();
    document.querySelectorAll('#rsaResultsBody .rsa-row-cb').forEach((cb) => {
      cb.checked = false;
    });
    const allCb = document.getElementById('rsaSelectAllCb');
    if (allCb) allCb.checked = false;
    updateBatchBtn();
  }

  function openBatchAnalyze() {
    const list = Array.from(state.selected.values()).map((s) => ({
      code: s.code,
      name: s.name || '',
      market: s.market || currentMarket(),
    }));
    if (!list.length) {
      toast('请先勾选至少一只股票', 'warning');
      return;
    }
    if (global.StockTradeLink && typeof StockTradeLink.openBatchAnalysis === 'function') {
      StockTradeLink.openBatchAnalysis(list, { toastPrefix: '已打开个股分析' });
      return;
    }
    toast('批量分析模块未加载', 'error');
  }

  function openOneAnalyze(code, name) {
    const list = [{ code, name: name || '', market: currentMarket() }];
    if (global.StockTradeLink && typeof StockTradeLink.openBatchAnalysis === 'function') {
      StockTradeLink.openBatchAnalysis(list, { toastPrefix: '已打开个股分析', confirmLarge: false });
      return;
    }
    toast('分析模块未加载', 'error');
  }

  function currentUserId() {
    try {
      if (global.CommonUtils && CommonUtils.auth && typeof CommonUtils.auth.getUserInfo === 'function') {
        const u = CommonUtils.auth.getUserInfo();
        return u && u.id != null ? u.id : null;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  function ensureLogin() {
    if (global.CommonUtils && typeof CommonUtils.checkLoginAndHandleExpiry === 'function') {
      return !!CommonUtils.checkLoginAndHandleExpiry();
    }
    const uid = currentUserId();
    if (!uid) {
      toast('请先登录后再操作自选股', 'warning');
      return false;
    }
    return true;
  }

  /**
   * @returns {'ok'|'exists'|'fail'}
   */
  async function postAddWatchlist(code, name) {
    const uid = currentUserId();
    const res = await authFetch(apiUrl('/api/watchlist'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: uid,
        stock_code: code,
        stock_name: name || code,
        group_name: 'default',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.success) {
      // 加入自选仅写库，不再调用第三方接口拉取历史行情/指标
      return 'ok';
    }
    const msg = String(data.message || '');
    if (res.status === 400 && (msg.includes('已在自选') || msg.includes('已存在'))) {
      return 'exists';
    }
    throw new Error(msg || `添加失败 ${res.status}`);
  }

  async function addOneWatchlist(code, name, btnEl) {
    const c = String(code || '').trim();
    if (!c) {
      toast('股票代码无效', 'warning');
      return;
    }
    if (!ensureLogin()) return;
    if (btnEl) {
      btnEl.disabled = true;
      btnEl.textContent = '…';
    }
    try {
      const st = await postAddWatchlist(c, name || c);
      if (st === 'ok') {
        toast(`已添加 ${name || c} 到自选股`, 'success');
        if (btnEl) {
          btnEl.textContent = '已自选';
          btnEl.classList.add('is-added');
          btnEl.disabled = true;
        }
      } else if (st === 'exists') {
        toast(`${name || c} 已在自选股中`, 'info');
        if (btnEl) {
          btnEl.textContent = '已自选';
          btnEl.classList.add('is-added');
          btnEl.disabled = true;
        }
      }
    } catch (e) {
      toast((e && e.message) || '加入自选失败', 'error');
      if (btnEl) {
        btnEl.textContent = '自选';
        btnEl.disabled = false;
      }
    }
  }

  async function batchAddWatchlist() {
    if (!ensureLogin()) return;
    const list = Array.from(state.selected.values());
    if (!list.length) {
      toast('请先勾选至少一只股票', 'warning');
      return;
    }
    if (list.length >= 40) {
      const ok = global.confirm(
        `将把 ${list.length} 只股票加入自选股，数量较多，是否继续？`
      );
      if (!ok) return;
    }
    if (state.watchlistBusy) return;
    state.watchlistBusy = true;
    updateBatchBtn();
    const wlBtn = document.getElementById('rsaBatchWatchlistBtn');
    if (wlBtn) wlBtn.textContent = '加入中…';

    let okN = 0;
    let existN = 0;
    let failN = 0;
    try {
      for (const s of list) {
        try {
          const st = await postAddWatchlist(s.code, s.name || s.code);
          if (st === 'ok') okN += 1;
          else if (st === 'exists') existN += 1;
          else failN += 1;
        } catch (e) {
          failN += 1;
        }
      }
      const parts = [`成功 ${okN}`];
      if (existN) parts.push(`已存在 ${existN}`);
      if (failN) parts.push(`失败 ${failN}`);
      toast(`加入自选完成：${parts.join('，')}`, failN && !okN ? 'error' : 'success');
      // 刷新本页行按钮状态
      document.querySelectorAll('#rsaResultsBody .rsa-watchlist-one').forEach((btn) => {
        const code = btn.getAttribute('data-code');
        if (code && state.selected.has(code)) {
          btn.textContent = '已自选';
          btn.classList.add('is-added');
          btn.disabled = true;
        }
      });
    } finally {
      state.watchlistBusy = false;
      if (wlBtn) wlBtn.textContent = '加入自选';
      updateBatchBtn();
    }
  }

  function bindEvents() {
    if (state.binding) return;
    state.binding = true;

    document.querySelectorAll('input[name="rsaMarket"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        clearSelection();
        syncBoardWrap();
        void load({ resetPage: true });
      });
    });

    document.getElementById('rsaQueryBtn')?.addEventListener('click', () => {
      void load({ resetPage: true });
    });
    document.getElementById('rsaKeyword')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        void load({ resetPage: true });
      }
    });
    document.getElementById('rsaSelectPageBtn')?.addEventListener('click', () => selectPage(true));
    document.getElementById('rsaClearSelectBtn')?.addEventListener('click', () => clearSelection());
    document.getElementById('rsaBatchAnalyzeBtn')?.addEventListener('click', () => openBatchAnalyze());
    document.getElementById('rsaBatchWatchlistBtn')?.addEventListener('click', () => {
      void batchAddWatchlist();
    });
    document.getElementById('rsaSelectAllCb')?.addEventListener('change', (e) => {
      selectPage(!!e.target.checked);
    });
    document.getElementById('rsaPrevBtn')?.addEventListener('click', () => {
      if (state.page > 1) {
        state.page -= 1;
        void load();
      }
    });
    document.getElementById('rsaNextBtn')?.addEventListener('click', () => {
      const pages = Math.max(1, Math.ceil(state.total / state.pageSize) || 1);
      if (state.page < pages) {
        state.page += 1;
        void load();
      }
    });
    document.getElementById('rsaPageSize')?.addEventListener('change', (e) => {
      const n = parseInt(e.target.value, 10);
      if (!Number.isNaN(n) && n > 0) {
        state.pageSize = n;
        void load({ resetPage: true });
      }
    });

    document.getElementById('rsaResultsBody')?.addEventListener('change', (e) => {
      const cb = e.target.closest('.rsa-row-cb');
      if (!cb) return;
      setRowSelected(cb.getAttribute('data-code'), cb.getAttribute('data-name'), cb.checked);
    });
    document.getElementById('rsaResultsBody')?.addEventListener('click', (e) => {
      const btn = e.target.closest('.rsa-analyze-one');
      if (btn) {
        e.preventDefault();
        openOneAnalyze(btn.getAttribute('data-code'), btn.getAttribute('data-name'));
        return;
      }
      const wl = e.target.closest('.rsa-watchlist-one');
      if (wl) {
        e.preventDefault();
        void addOneWatchlist(wl.getAttribute('data-code'), wl.getAttribute('data-name'), wl);
      }
    });
  }

  function init() {
    bindEvents();
    syncBoardWrap();
    if (!state.loaded) {
      void load({ resetPage: true });
    }
  }

  function reload() {
    bindEvents();
    syncBoardWrap();
    void load({ resetPage: false });
  }

  global.RsRatingAnalysis = { init, reload, load };
})(typeof window !== 'undefined' ? window : globalThis);
