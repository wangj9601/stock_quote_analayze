/**
 * 比价效应（RPE）选股页：选股 / 交易观察 / 正式交易
 */
(function () {
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
    const el = document.getElementById('rpeError');
    if (!el) return;
    el.style.display = msg ? 'block' : 'none';
    el.textContent = msg || '';
  }

  /** 兼容后端 name / stock_name */
  function displayName(r) {
    if (!r) return '';
    return String(r.name || r.stock_name || '').trim();
  }

  function switchSub(name) {
    document.querySelectorAll('#rpe-content [data-rpe-sub]').forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-rpe-sub') === name);
    });
    ['signals', 'observe', 'formal'].forEach((k) => {
      const panel = document.getElementById(`rpe-sub-${k}`);
      if (panel) panel.style.display = k === name ? 'block' : 'none';
    });
  }

  function fmt(v, n) {
    if (v == null || v === '') return '-';
    const x = Number(v);
    return Number.isFinite(x) ? x.toFixed(n == null ? 2 : n) : String(v);
  }

  function yn(v) {
    if (v === true) return '是';
    if (v === false) return '否';
    return '-';
  }

  function signalLabel(r) {
    if (!r) return '-';
    if (r.signal_type) return r.signal_type;
    const reason = (r.detail && r.detail.signal_reason) || r.signal_reason;
    if (reason === 'in_band' || reason === 'no_z') return '无信号';
    return '无信号';
  }

  function snapField(snap, key, fallback) {
    if (snap && snap[key] != null && snap[key] !== '') return snap[key];
    return fallback;
  }

  /** code -> observe id */
  const observeIdByCode = new Map();

  function normCode(code) {
    const s = String(code || '').trim();
    if (/^\d{1,6}$/.test(s)) return s.padStart(6, '0');
    return s;
  }

  async function loadObserveMap() {
    observeIdByCode.clear();
    try {
      const data = await api('/api/stock/rpe-trade-observe/list');
      (data.items || []).forEach((it) => {
        const c = normCode(it.code);
        if (c && it.id != null) observeIdByCode.set(c, it.id);
      });
    } catch (_) {
      // 未登录时忽略，按钮仍显示「观察」
    }
  }

  function setObserveButtonState(btn, { observed, observeId, code }) {
    if (!btn) return;
    const c = normCode(code || btn.getAttribute('data-code'));
    if (observed) {
      btn.textContent = '取消观察';
      btn.classList.add('is-added', 'rpe-cancel-observe');
      btn.classList.remove('rpe-add-observe');
      btn.title = '移出交易观察';
      if (observeId != null) btn.setAttribute('data-id', String(observeId));
      else if (observeIdByCode.has(c)) btn.setAttribute('data-id', String(observeIdByCode.get(c)));
    } else {
      btn.textContent = '观察';
      btn.classList.remove('is-added', 'rpe-cancel-observe');
      btn.classList.add('rpe-add-observe');
      btn.title = '加入交易观察';
      btn.removeAttribute('data-id');
    }
    btn.disabled = false;
  }

  function renderObserveButtonHtml(r) {
    const code = normCode(r.code);
    const oid = observeIdByCode.get(code);
    const snap = encodeURIComponent(JSON.stringify(r));
    const nm = displayName(r);
    if (oid != null) {
      return `<button type="button" class="gms-op-btn is-added rpe-cancel-observe"
        data-code="${r.code || ''}" data-name="${nm}" data-date="${r.date || ''}"
        data-id="${oid}" data-snap="${snap}" title="移出交易观察">取消观察</button>`;
    }
    return `<button type="button" class="gms-op-btn rpe-add-observe"
      data-code="${r.code || ''}" data-name="${nm}" data-date="${r.date || ''}"
      data-snap="${snap}" title="加入交易观察">观察</button>`;
  }

  function getScreeningApp() {
    if (typeof ScreeningPage !== 'undefined') return ScreeningPage;
    if (typeof window !== 'undefined') return window.ScreeningPage || null;
    return null;
  }

  function syncScopeUI() {
    const scope = document.getElementById('rpeScope')?.value || 'cn';
    const indWrap = document.getElementById('rpeIndustryBoardWrap');
    const conWrap = document.getElementById('rpeConceptBoardWrap');
    const stockGroup = document.getElementById('rpeStockCodeGroup');
    const singleHint = document.getElementById('rpeSingleSkipFilterHint');
    if (indWrap) indWrap.style.display = scope === 'industry_board' ? 'flex' : 'none';
    if (conWrap) conWrap.style.display = scope === 'concept_board' ? 'flex' : 'none';
    if (stockGroup) stockGroup.style.display = scope === 'single' ? 'flex' : 'none';
    if (singleHint) singleHint.style.display = scope === 'single' ? 'flex' : 'none';
    const app = getScreeningApp();
    if (app && typeof app.refreshBoardRolesPanelForOwner === 'function') {
      if (scope === 'industry_board' && typeof app.loadGmsIndustryBoardOptions === 'function') {
        void app.loadGmsIndustryBoardOptions().then(() => app.refreshBoardRolesPanelForOwner('rpe'));
      } else if (scope === 'concept_board' && typeof app.loadGmsConceptBoardOptions === 'function') {
        void app.loadGmsConceptBoardOptions().then(() => app.refreshBoardRolesPanelForOwner('rpe'));
      } else {
        app.refreshBoardRolesPanelForOwner('rpe');
      }
    }
  }

  function preferredBoardCodeSource(kind, codes) {
    const app = getScreeningApp();
    if (app && typeof app._gmsPreferredBoardCodeSource === 'function') {
      return app._gmsPreferredBoardCodeSource(kind, codes);
    }
    return 'tonghuashun';
  }

  function roleTagsHtml(r) {
    const tags = Array.isArray(r?.role_tags) ? r.role_tags : [];
    if (!tags.length) return '';
    return tags
      .map((t) => {
        const label = t.label || t.id || '';
        const mid = String(t.id || '') === 'board_mid' || label === '中军';
        const cls = mid ? 'gms-role-tag gms-role-tag--mid' : 'gms-role-tag';
        const title = String(t.reason || '').replace(/"/g, '&quot;');
        return `<span class="${cls}" title="${title}">${label}</span>`;
      })
      .join('');
  }

  function selectedIndustryCodes() {
    const app = getScreeningApp();
    if (app && typeof app.getRpeSelectedIndustryBoardCodes === 'function') {
      return app.getRpeSelectedIndustryBoardCodes();
    }
    return Array.isArray(app?.rpeSelectedIndustryBoardCodes)
      ? app.rpeSelectedIndustryBoardCodes.filter(Boolean)
      : [];
  }

  function selectedConceptCodes() {
    const app = getScreeningApp();
    if (app && typeof app.getRpeSelectedConceptBoardCodes === 'function') {
      return app.getRpeSelectedConceptBoardCodes();
    }
    return Array.isArray(app?.rpeSelectedConceptBoardCodes)
      ? app.rpeSelectedConceptBoardCodes.filter(Boolean)
      : [];
  }

  function collectResultCodes() {
    const body = document.getElementById('rpeResultsBody');
    if (!body) return [];
    const codes = [];
    const seen = new Set();
    body.querySelectorAll('tr[data-code]').forEach((tr) => {
      if (tr.classList.contains('rpe-score-detail-row')) return;
      const c = normCode(tr.getAttribute('data-code'));
      if (!c || seen.has(c)) return;
      seen.add(c);
      codes.push(c);
    });
    return codes;
  }

  function buildRpeQuery({ adjust = 'none', extraCodes = null } = {}) {
    const scope = document.getElementById('rpeScope').value || 'cn';
    const date = document.getElementById('rpeDate').value || '';
    const entryOnly = document.getElementById('rpeEntryOnly').checked;
    const traceOnly = document.getElementById('rpeTraceOnly').checked;
    const signalType = document.getElementById('rpeSignalType').value || '';
    const stockCode = (document.getElementById('rpeStockCode').value || '').trim();
    const industryCodes = selectedIndustryCodes();
    const conceptCodes = selectedConceptCodes();

    if (scope === 'industry_board' && !industryCodes.length) {
      throw new Error('请先选择行业板块（与 GMS 相同的选择面板）');
    }
    if (scope === 'concept_board' && !conceptCodes.length) {
      throw new Error('请先选择概念板块（与 GMS 相同的选择面板）');
    }
    if (scope === 'single' && !stockCode) {
      throw new Error('单股范围需要填写股票代码');
    }

    const adjustN = adjust === 'qfq' ? 'qfq' : 'none';
    const q = new URLSearchParams({
      scope,
      entry_only: String(entryOnly),
      max_results: scope === 'industry_board' || scope === 'concept_board' ? '2000' : '200',
      adjust: adjustN,
    });
    if (date) q.set('date', date);
    if (signalType) q.set('signal_type', signalType);
    if (stockCode) q.set('stock_code', stockCode);
    if (adjustN === 'qfq') {
      q.set('factor_source', 'auto');
    } else if (traceOnly && scope === 'cn') {
      q.set('trace_only', 'true');
    }
    industryCodes.forEach((c) => q.append('industry_board_code', c));
    conceptCodes.forEach((c) => q.append('concept_board_code', c));
    if (scope === 'industry_board' && industryCodes.length) {
      q.set('board_code_source', preferredBoardCodeSource('industry', industryCodes));
    } else if (scope === 'concept_board' && conceptCodes.length) {
      q.set('board_code_source', preferredBoardCodeSource('concept', conceptCodes));
    }
    if (Array.isArray(extraCodes)) {
      extraCodes.forEach((c) => {
        const n = normCode(c);
        if (n) q.append('code', n);
      });
    }
    return { q, scope, adjustN };
  }

  function renderSignalRows(data) {
    const body = document.getElementById('rpeResultsBody');
    const rows = data.data || [];
    document.getElementById('rpeResultsCount').textContent = `共 ${rows.length} 只`;
    const metaParts = [
      `日期 ${data.search_date || '-'}`,
      `来源 ${data.source || 'live'}`,
      `config ${data.config_id || ''}`,
    ];
    if (data.price_adjust === 'qfq' || data.source === 'live_qfq') {
      metaParts.push('价格口径 前复权(不落库)');
    }
    if (data.stock_code) metaParts.push(`个股 ${data.stock_code}`);
    document.getElementById('rpeSearchMeta').textContent = metaParts.join(' · ');
    if (!rows.length) {
      const emptyMsg = data.message ? `无结果：${data.message}` : '无符合条件的结果';
      if (data.message) showErr(data.message);
      body.innerHTML = `<tr><td colspan="12" class="empty-state">${emptyMsg}</td></tr>`;
      return;
    }
    body.innerHTML = rows
      .map((r, index) => {
        let detailHtml = '<div class="gms-score-detail-inner">明细组件未加载</div>';
        if (window.RpeScoreDetail && typeof window.RpeScoreDetail.buildHtml === 'function') {
          detailHtml = window.RpeScoreDetail.buildHtml(r);
        }
        const qfqTitle = r.price_adjust === 'qfq' ? '前复权' : '';
        const roleHtml = roleTagsHtml(r);
        return `<tr data-rpe-row="${index}" data-code="${r.code || ''}">
            <td>${r.code || ''}</td>
            <td>${displayName(r)}${roleHtml ? ` ${roleHtml}` : ''}</td>
            <td>${r.sector_name || r.sector_id || '-'}</td>
            <td title="${qfqTitle}">${fmt(r.close)}</td>
            <td title="${qfqTitle}">${fmt(r.z_score, 2)}</td>
            <td>${signalLabel(r)}</td>
            <td>${yn(r.entry_signal)}</td>
            <td class="rpe-nearest-support" title="${qfqTitle}">${fmt(r.nearest_support)}</td>
            <td class="rpe-nearest-resistance" title="${qfqTitle}">${fmt(r.nearest_resistance)}</td>
            <td>${yn(r.structure_valid)}</td>
            <td>${yn(r.liquidity_ok)}</td>
            <td>
              <div class="action-links">
                <button type="button" class="gms-op-btn rpe-score-detail-toggle" data-row="${index}" title="展开/收起策略明细">明细</button>
                ${renderObserveButtonHtml(r)}
                <a class="gms-op-btn" href="stock_rpe_trace.html?code=${encodeURIComponent(r.code || '')}" target="_blank" rel="noopener">追溯</a>
              </div>
            </td>
          </tr>
          <tr class="gms-score-detail-row rpe-score-detail-row" data-detail-for="${index}" style="display:none;">
            <td colspan="12" class="gms-score-detail-cell">${detailHtml}</td>
          </tr>`;
      })
      .join('');
  }

  async function refreshSignals() {
    const loading = document.getElementById('rpeLoading');
    const body = document.getElementById('rpeResultsBody');
    showErr('');
    if (loading) loading.style.display = 'flex';
    try {
      await loadObserveMap();
      const { q, scope } = buildRpeQuery({ adjust: 'none' });
      const traceOnly = document.getElementById('rpeTraceOnly').checked;
      let data = await api(`/api/screening/rpe-strategy?${q}`);
      if (traceOnly && scope === 'cn' && (!data.data || !data.data.length)) {
        q.delete('trace_only');
        data = await api(`/api/screening/rpe-strategy?${q}`);
      }
      renderSignalRows(data);
    } catch (e) {
      showErr(e.message || String(e));
      body.innerHTML = '<tr><td colspan="12" class="empty-state">加载失败</td></tr>';
    } finally {
      if (loading) loading.style.display = 'none';
    }
  }

  // 后端可按 env 开启第三方因子限速；单请求代码数不宜过大以免超时
  const QFQ_CODE_CHUNK = 8;

  async function recomputeQfqStrategy() {
    if (typeof CommonUtils !== 'undefined' && typeof CommonUtils.checkLoginAndHandleExpiry === 'function') {
      if (!CommonUtils.checkLoginAndHandleExpiry()) return;
    }
    const btn = document.getElementById('rpeQfqLevelsBtn');
    const loading = document.getElementById('rpeLoading');
    showErr('');

    const scope = document.getElementById('rpeScope')?.value || 'cn';
    const listCodes = collectResultCodes();
    if (scope === 'cn' && !listCodes.length) {
      showErr('请先「刷新筛选」得到股票列表，再按前复权重算整策略');
      if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
        CommonUtils.showToast('请先刷新筛选得到列表', 'warning');
      }
      return;
    }

    const prevBtnText = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '前复权重算中…';
    }
    if (loading) {
      loading.style.display = 'flex';
      const span = loading.querySelector('span');
      if (span) span.textContent = '前复权整策略重算中…';
    }

    try {
      await loadObserveMap();
      let merged = [];
      let lastMeta = {};

      if (scope === 'cn') {
        for (let i = 0; i < listCodes.length; i += QFQ_CODE_CHUNK) {
          const chunk = listCodes.slice(i, i + QFQ_CODE_CHUNK);
          if (loading) {
            const span = loading.querySelector('span');
            if (span) {
              span.textContent = `前复权重算 ${Math.min(i + chunk.length, listCodes.length)}/${listCodes.length}…`;
            }
          }
          if (btn) {
            btn.textContent = `前复权 ${Math.min(i + chunk.length, listCodes.length)}/${listCodes.length}`;
          }
          const { q } = buildRpeQuery({ adjust: 'qfq', extraCodes: chunk });
          const data = await api(`/api/screening/rpe-strategy?${q}`);
          lastMeta = data;
          merged = merged.concat(data.data || []);
        }
        // 按 code 去重（后写覆盖），再按入场/|Z| 排序与后端一致
        const byCode = new Map();
        merged.forEach((r) => {
          const c = normCode(r.code);
          if (c) byCode.set(c, r);
        });
        const rows = Array.from(byCode.values()).sort((a, b) => {
          const ae = a.entry_signal ? 1 : 0;
          const be = b.entry_signal ? 1 : 0;
          if (be !== ae) return be - ae;
          return Math.abs(b.z_score || 0) - Math.abs(a.z_score || 0);
        });
        renderSignalRows({
          ...lastMeta,
          data: rows,
          total: rows.length,
          source: 'live_qfq',
          price_adjust: 'qfq',
        });
      } else {
        const { q } = buildRpeQuery({ adjust: 'qfq' });
        const data = await api(`/api/screening/rpe-strategy?${q}`);
        renderSignalRows(data);
        merged = data.data || [];
      }

      const n = (document.getElementById('rpeResultsBody')?.querySelectorAll('tr[data-code]:not(.rpe-score-detail-row)') || []).length;
      const toastMsg = `前复权整策略重算完成：${n} 只（未写入预计算）`;
      if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
        CommonUtils.showToast(toastMsg, 'success');
      }
    } catch (e) {
      showErr(e.message || String(e));
      if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
        CommonUtils.showToast(e.message || '前复权重算失败', 'error');
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prevBtnText || '按前复权计算';
      }
      if (loading) {
        loading.style.display = 'none';
        const span = loading.querySelector('span');
        if (span) span.textContent = '筛选中...';
      }
    }
  }

  async function refreshObserve() {
    const body = document.getElementById('rpeObserveBody');
    try {
      const data = await api('/api/stock/rpe-trade-observe/list');
      const rows = data.items || [];
      observeIdByCode.clear();
      rows.forEach((it) => {
        const c = normCode(it.code);
        if (c && it.id != null) observeIdByCode.set(c, it.id);
      });
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="14" class="empty-state">暂无观察股</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map((r) => {
          const snap = r.signal_snapshot || {};
          const view = {
            signal_type: snapField(snap, 'signal_type', r.signal_type),
            detail: snap.detail || r.detail,
            signal_reason: snapField(snap, 'signal_reason', null),
          };
          return `<tr>
          <td>${r.code || ''}</td>
          <td>${displayName(r) || displayName(snap) || ''}</td>
          <td>${r.signal_date || snap.date || '-'}</td>
          <td>${snapField(snap, 'sector_name', snap.sector_id) || '-'}</td>
          <td>${fmt(snapField(snap, 'z_score', null), 2)}</td>
          <td>${signalLabel(view)}</td>
          <td>${yn(snapField(snap, 'entry_signal', null))}</td>
          <td>${fmt(snapField(snap, 'close', null))}</td>
          <td>${fmt(snapField(snap, 'nearest_support', null))}</td>
          <td>${fmt(snapField(snap, 'nearest_resistance', null))}</td>
          <td>${yn(snapField(snap, 'structure_valid', null))}</td>
          <td>${yn(snapField(snap, 'liquidity_ok', null))}</td>
          <td>${yn(r.above_support)}</td>
          <td>
            <button type="button" class="refresh-btn rpe-to-formal" data-id="${r.id}">转正式</button>
            <button type="button" class="gms-btn-outline rpe-del-observe" data-id="${r.id}">移除</button>
          </td>
        </tr>`;
        })
        .join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="14" class="empty-state">${e.message}</td></tr>`;
    }
  }

  async function refreshFormal() {
    const body = document.getElementById('rpeFormalBody');
    try {
      const data = await api('/api/stock/rpe-formal-trade/list');
      const rows = data.items || [];
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="9" class="empty-state">暂无正式交易</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map((r) => {
          const live = r.live_eval || {};
          const breached = live.structure_break || live.breached ? '结构破位' : '';
          const evalTxt = breached || (live.note || r.last_eval && JSON.stringify(r.last_eval)) || '-';
          return `<tr>
            <td>${r.code}</td><td>${displayName(r)}</td><td>${r.status}</td>
            <td>${fmt(r.entry_price)}</td>
            <td>${fmt(r.structure_support)}</td><td>${fmt(r.structure_resistance)}</td>
            <td>${r.exit_reason || '-'}</td><td>${evalTxt}</td>
            <td>
              ${
                r.status === 'open'
                  ? `<button type="button" class="gms-btn-outline rpe-close-trade" data-id="${r.id}">结构破位平仓</button>`
                  : ''
              }
              <button type="button" class="gms-btn-outline rpe-del-formal" data-id="${r.id}">删除</button>
            </td>
          </tr>`;
        })
        .join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="9" class="empty-state">${e.message}</td></tr>`;
    }
  }

  function bind() {
    const root = document.getElementById('rpe-content');
    if (!root) return;

    syncScopeUI();
    document.getElementById('rpeScope')?.addEventListener('change', () => syncScopeUI());

    root.querySelectorAll('[data-rpe-sub]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const sub = btn.getAttribute('data-rpe-sub');
        switchSub(sub);
        if (sub === 'observe') refreshObserve();
        if (sub === 'formal') refreshFormal();
      });
    });

    document.getElementById('rpeRefreshBtn')?.addEventListener('click', () => refreshSignals());
    document.getElementById('rpeQfqLevelsBtn')?.addEventListener('click', () => recomputeQfqStrategy());
    document.getElementById('rpeStockCode')?.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const scope = document.getElementById('rpeScope')?.value || 'cn';
      if (scope !== 'single') return;
      e.preventDefault();
      refreshSignals();
    });
    document.getElementById('rpeObserveRefreshBtn')?.addEventListener('click', () => refreshObserve());
    document.getElementById('rpeFormalRefreshBtn')?.addEventListener('click', () => refreshFormal());

    document.getElementById('rpeResultsBody')?.addEventListener('click', async (e) => {
      const detailBtn = e.target.closest('.rpe-score-detail-toggle');
      if (detailBtn) {
        const rowIndex = detailBtn.getAttribute('data-row');
        const tbody = document.getElementById('rpeResultsBody');
        const detailRow = tbody?.querySelector(`tr.rpe-score-detail-row[data-detail-for="${rowIndex}"]`);
        if (detailRow) {
          const show = detailRow.style.display === 'none' || !detailRow.style.display;
          detailRow.style.display = show ? 'table-row' : 'none';
          detailBtn.classList.toggle('active', show);
        }
        return;
      }
      const cancelObs = e.target.closest('.rpe-cancel-observe');
      if (cancelObs) {
        const code = normCode(cancelObs.getAttribute('data-code'));
        const oid = cancelObs.getAttribute('data-id') || observeIdByCode.get(code);
        if (!oid) {
          alert('找不到观察记录，请刷新后重试');
          return;
        }
        try {
          cancelObs.disabled = true;
          cancelObs.textContent = '取消中...';
          await api(`/api/stock/rpe-trade-observe/${oid}`, { method: 'DELETE' });
          observeIdByCode.delete(code);
          setObserveButtonState(cancelObs, { observed: false, code });
        } catch (err) {
          alert(err.message);
          setObserveButtonState(cancelObs, { observed: true, observeId: oid, code });
        }
        return;
      }
      const obs = e.target.closest('.rpe-add-observe');
      if (!obs) return;
      let snap = null;
      try {
        snap = JSON.parse(decodeURIComponent(obs.getAttribute('data-snap') || '%7B%7D'));
      } catch (_) {}
      const code = normCode(obs.getAttribute('data-code'));
      try {
        obs.disabled = true;
        obs.textContent = '加入中...';
        const res = await api('/api/stock/rpe-trade-observe/add', {
          method: 'POST',
          body: JSON.stringify({
            code: obs.getAttribute('data-code'),
            name: obs.getAttribute('data-name'),
            signal_date: obs.getAttribute('data-date'),
            signal_snapshot: snap,
          }),
        });
        const oid = res.id;
        if (oid != null) observeIdByCode.set(code, oid);
        setObserveButtonState(obs, { observed: true, observeId: oid, code });
      } catch (err) {
        alert(err.message);
        setObserveButtonState(obs, { observed: observeIdByCode.has(code), code });
      }
    });

    document.getElementById('rpeObserveBody')?.addEventListener('click', async (e) => {
      const toFormal = e.target.closest('.rpe-to-formal');
      if (toFormal) {
        const price = window.prompt('请输入入场价格');
        if (!price) return;
        try {
          await api(`/api/stock/rpe-formal-trade/from-observe/${toFormal.getAttribute('data-id')}`, {
            method: 'POST',
            body: JSON.stringify({ entry_price: Number(price) }),
          });
          alert('已转入正式交易（离场仅认结构破位）');
          switchSub('formal');
          refreshFormal();
        } catch (err) {
          alert(err.message);
        }
        return;
      }
      const del = e.target.closest('.rpe-del-observe');
      if (del) {
        await api(`/api/stock/rpe-trade-observe/${del.getAttribute('data-id')}`, { method: 'DELETE' });
        await loadObserveMap();
        refreshObserve();
        // 同步选股列表按钮文案
        document.querySelectorAll('#rpeResultsBody .rpe-cancel-observe, #rpeResultsBody .rpe-add-observe').forEach((btn) => {
          const c = normCode(btn.getAttribute('data-code'));
          const oid = observeIdByCode.get(c);
          setObserveButtonState(btn, { observed: oid != null, observeId: oid, code: c });
        });
      }
    });

    document.getElementById('rpeFormalBody')?.addEventListener('click', async (e) => {
      const closeBtn = e.target.closest('.rpe-close-trade');
      if (closeBtn) {
        const px = window.prompt('平仓价格（exit_reason=structure_break）');
        if (!px) return;
        await api(`/api/stock/rpe-formal-trade/${closeBtn.getAttribute('data-id')}`, {
          method: 'PATCH',
          body: JSON.stringify({
            status: 'closed',
            exit_price: Number(px),
            exit_reason: 'structure_break',
          }),
        });
        refreshFormal();
        return;
      }
      const del = e.target.closest('.rpe-del-formal');
      if (del) {
        if (!window.confirm('确定删除？')) return;
        await api(`/api/stock/rpe-formal-trade/${del.getAttribute('data-id')}`, { method: 'DELETE' });
        refreshFormal();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
