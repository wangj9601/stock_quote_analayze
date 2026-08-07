/**
 * 做小做底（SBBR）选股页交互：选股 / 观察 / 正式交易 / 储备箱
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
    const el = document.getElementById('sbbrError');
    if (!el) return;
    el.style.display = msg ? 'block' : 'none';
    el.textContent = msg || '';
  }

  function switchSub(name) {
    document.querySelectorAll('#sbbr-content [data-sbbr-sub]').forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-sbbr-sub') === name);
    });
    ['signals', 'observe', 'formal', 'reserve'].forEach((k) => {
      const panel = document.getElementById(`sbbr-sub-${k}`);
      if (panel) panel.style.display = k === name ? 'block' : 'none';
    });
  }

  function fmt(v, n) {
    if (v == null || v === '') return '-';
    const x = Number(v);
    return Number.isFinite(x) ? x.toFixed(n == null ? 2 : n) : String(v);
  }

  function canPerm(code) {
    return !(window.Permission && typeof window.Permission.has === 'function') || window.Permission.has(code);
  }

  let lastSignalRows = [];

  function renderSignalRows(rows) {
    const body = document.getElementById('sbbrResultsBody');
    if (!body) return;
    lastSignalRows = rows || [];
    document.getElementById('sbbrResultsCount').textContent = `共 ${lastSignalRows.length} 只`;
    if (!lastSignalRows.length) {
      body.innerHTML = '<tr><td colspan="14" class="empty-state">无符合条件的结果</td></tr>';
      return;
    }
    body.innerHTML = lastSignalRows
      .map((r, index) => {
        const snap = encodeURIComponent(JSON.stringify(r));
        const ops = [];
        ops.push(
          `<button type="button" class="gms-op-btn sbbr-score-detail-toggle" data-row="${index}" title="展开/收起策略明细">明细</button>`
        );
        if (canPerm('channel.screening.tab.sbbr.btn.add_observe')) {
          ops.push(
            `<button type="button" class="gms-btn-outline sbbr-add-observe" data-perm="channel.screening.tab.sbbr.btn.add_observe" data-code="${r.code}" data-name="${r.name || ''}" data-date="${r.date || ''}" data-snap="${snap}">观察</button>`
          );
        }
        if (canPerm('channel.screening.tab.sbbr.btn.add_reserve')) {
          ops.push(
            `<button type="button" class="gms-btn-outline sbbr-add-reserve" data-perm="channel.screening.tab.sbbr.btn.add_reserve" data-code="${r.code}" data-name="${r.name || ''}">储备</button>`
          );
        }
        let detailHtml = '<div class="gms-score-detail-inner">明细组件未加载</div>';
        if (window.SbbrScoreDetail && typeof window.SbbrScoreDetail.buildHtml === 'function') {
          detailHtml = window.SbbrScoreDetail.buildHtml(r);
        }
        return `<tr data-sbbr-row="${index}">
            <td>${r.code || ''}</td>
            <td>${r.name || ''}</td>
            <td>${fmt(r.total_mv)}</td>
            <td>${fmt(r.circ_shares_yi)}</td>
            <td>${r.bottom_mode || '-'}</td>
            <td>${r.entry_signal ? '是' : '否'}</td>
            <td>${fmt(r.close)}</td>
            <td>${fmt(r.box_support)}</td>
            <td>${fmt(r.box_resistance)}</td>
            <td>${fmt(r.nearest_support)}</td>
            <td>${fmt(r.nearest_resistance)}</td>
            <td>${fmt(r.defense_low)}</td>
            <td>${fmt(r.volume_ratio)}</td>
            <td><div class="action-links">${ops.join(' ')}</div></td>
          </tr>
          <tr class="gms-score-detail-row sbbr-score-detail-row" data-detail-for="${index}" style="display:none;">
            <td colspan="14" class="gms-score-detail-cell">${detailHtml}</td>
          </tr>`;
      })
      .join('');
  }

  function getScreeningApp() {
    if (typeof ScreeningPage !== 'undefined') return ScreeningPage;
    if (typeof window !== 'undefined') return window.ScreeningPage || null;
    return null;
  }

  function syncScopeUI() {
    const scope = document.getElementById('sbbrScope')?.value || 'market';
    const indWrap = document.getElementById('sbbrIndustryBoardWrap');
    const conWrap = document.getElementById('sbbrConceptBoardWrap');
    if (indWrap) indWrap.style.display = scope === 'industry_board' ? 'flex' : 'none';
    if (conWrap) conWrap.style.display = scope === 'concept_board' ? 'flex' : 'none';
  }

  function selectedIndustryCodes() {
    const app = getScreeningApp();
    if (app && typeof app.getSbbrSelectedIndustryBoardCodes === 'function') {
      return app.getSbbrSelectedIndustryBoardCodes();
    }
    return Array.isArray(app?.sbbrSelectedIndustryBoardCodes)
      ? app.sbbrSelectedIndustryBoardCodes.filter(Boolean)
      : [];
  }

  function selectedConceptCodes() {
    const app = getScreeningApp();
    if (app && typeof app.getSbbrSelectedConceptBoardCodes === 'function') {
      return app.getSbbrSelectedConceptBoardCodes();
    }
    return Array.isArray(app?.sbbrSelectedConceptBoardCodes)
      ? app.sbbrSelectedConceptBoardCodes.filter(Boolean)
      : [];
  }

  function selectedBoardSegment() {
    const el = document.querySelector('input[name="sbbrCnBoardSegment"]:checked');
    return el ? String(el.value || 'ALL').trim().toUpperCase() : 'ALL';
  }

  async function refreshSignals() {
    const loading = document.getElementById('sbbrLoading');
    const body = document.getElementById('sbbrResultsBody');
    showErr('');
    if (loading) loading.style.display = 'flex';
    try {
      const scope = document.getElementById('sbbrScope').value || 'market';
      const date = document.getElementById('sbbrDate').value || '';
      const entryOnly = document.getElementById('sbbrEntryOnly').checked;
      const traceOnly = document.getElementById('sbbrTraceOnly').checked;
      const industryCodes = selectedIndustryCodes();
      const conceptCodes = selectedConceptCodes();
      const boardSeg = selectedBoardSegment();

      if (scope === 'industry_board' && !industryCodes.length) {
        throw new Error('请先选择行业板块（与 GMS/RPE 相同的选择面板）');
      }
      if (scope === 'concept_board' && !conceptCodes.length) {
        throw new Error('请先选择概念板块（与 GMS/RPE 相同的选择面板）');
      }

      const q = new URLSearchParams({
        scope,
        entry_only: String(entryOnly),
        require_bottom: 'true',
        require_size: 'true',
        max_results: scope === 'industry_board' || scope === 'concept_board' ? '2000' : '200',
      });
      if (date) q.set('date', date);
      if (traceOnly && scope === 'market') q.set('trace_only', 'true');
      if (boardSeg && boardSeg !== 'ALL') q.set('cn_board_segment', boardSeg);
      industryCodes.forEach((c) => q.append('industry_board_code', c));
      conceptCodes.forEach((c) => q.append('concept_board_code', c));

      let data = await api(`/api/screening/sbbr-strategy?${q}`);
      if (traceOnly && scope === 'market' && (!data.data || !data.data.length)) {
        q.delete('trace_only');
        data = await api(`/api/screening/sbbr-strategy?${q}`);
      }
      const rows = data.data || [];
      const asof = data.asof_date || data.search_date || '-';
      const srcLabel =
        data.source_label ||
        (data.source === 'trace' ? '预计算' : data.source === 'live' ? '实时计算' : data.source || 'live');
      const metaParts = [
        `回溯基准日 ${asof}`,
        `数据来源 ${srcLabel}`,
        `config ${data.config_id || ''}`,
      ];
      if (data.requested_date && data.requested_date !== asof) {
        metaParts.splice(1, 0, `请求日 ${data.requested_date}→已对齐`);
      }
      if (data.data_max_date) {
        metaParts.push(`行情最新日 ${data.data_max_date}`);
      }
      if (data.cn_board_segment) metaParts.push(`板型 ${data.cn_board_segment}`);
      if (data.industry_board_codes && data.industry_board_codes.length) {
        metaParts.push(`行业 ${data.industry_board_codes.join(',')}`);
      }
      if (data.concept_board_codes && data.concept_board_codes.length) {
        metaParts.push(`概念 ${data.concept_board_codes.join(',')}`);
      }
      if (data.message) {
        showErr(data.message);
      }
      document.getElementById('sbbrSearchMeta').textContent = metaParts.join(' · ');
      const hint = document.getElementById('sbbrDataDateHint');
      if (hint) {
        const isLatest = !data.data_max_date || asof === data.data_max_date;
        hint.textContent = isLatest
          ? '（当前为最新行情日）'
          : `（历史回溯：仅使用 ≤${asof} 的 K 线）`;
      }
      // 若服务端对齐了交易日，回写到日期框便于用户确认
      const dateEl = document.getElementById('sbbrDate');
      if (dateEl && asof && asof !== '-' && (!date || data.date_snapped)) {
        dateEl.value = asof;
      }
      renderSignalRows(rows);
    } catch (e) {
      showErr(e.message || String(e));
      lastSignalRows = [];
      body.innerHTML = '<tr><td colspan="14" class="empty-state">加载失败</td></tr>';
    } finally {
      if (loading) loading.style.display = 'none';
    }
  }

  async function refreshQfqLevels() {
    if (!lastSignalRows.length) {
      showErr('请先刷新筛选，再按前复权重算 KDE 支撑/阻力');
      return;
    }
    const btn = document.getElementById('sbbrQfqLevelsBtn');
    const loading = document.getElementById('sbbrLoading');
    const prevText = btn ? btn.textContent : '';
    const CHUNK = 8;
    showErr('');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '前复权重算中…';
    }
    if (loading) {
      loading.style.display = 'flex';
      const span = loading.querySelector('span');
      if (span) span.textContent = '前复权支撑/阻力重算中…';
    }
    const codes = [
      ...new Set(
        lastSignalRows
          .map((r) => String(r.code || '').trim().replace(/^(SH|SZ)/i, ''))
          .filter(Boolean)
      ),
    ];
    const byCode = new Map();
    let okCount = 0;
    let failCount = 0;
    try {
      for (let i = 0; i < codes.length; i += CHUNK) {
        const chunk = codes.slice(i, i + CHUNK);
        if (loading) {
          const span = loading.querySelector('span');
          if (span) {
            span.textContent = `前复权支撑/阻力 ${Math.min(i + chunk.length, codes.length)}/${codes.length}…`;
          }
        }
        if (btn) {
          btn.textContent = `前复权 ${Math.min(i + chunk.length, codes.length)}/${codes.length}`;
        }
        const data = await api('/api/analysis/levels/batch', {
          method: 'POST',
          body: JSON.stringify({
            codes: chunk,
            adjust: 'qfq',
            max_levels: 8,
            refresh_factor: false,
            factor_source: 'auto',
          }),
        });
        (data.items || []).forEach((it) => {
          const c = String(it.code || '').trim();
          if (!c) return;
          byCode.set(c, it);
          if (it.success) okCount += 1;
          else failCount += 1;
        });
      }
      lastSignalRows.forEach((row) => {
        const c = String(row.code || '').trim().replace(/^(SH|SZ)/i, '');
        const it = byCode.get(c);
        if (!it || !it.success) return;
        row.nearest_support = it.nearest_support;
        row.nearest_resistance = it.nearest_resistance;
        row.support_levels = Array.isArray(it.support_levels) ? it.support_levels : [];
        row.resistance_levels = Array.isArray(it.resistance_levels) ? it.resistance_levels : [];
        row.price_adjust = it.price_adjust || 'qfq';
        row.kde_ok = true;
      });
      renderSignalRows(lastSignalRows);
      const meta = document.getElementById('sbbrSearchMeta');
      if (meta) {
        meta.textContent = `${meta.textContent || ''} · 前复权KDE 成功${okCount}/失败${failCount}`;
      }
    } catch (e) {
      showErr(e.message || String(e));
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prevText || '按前复权计算';
      }
      if (loading) {
        loading.style.display = 'none';
        const span = loading.querySelector('span');
        if (span) span.textContent = '筛选中...';
      }
    }
  }

  async function refreshObserve() {
    const body = document.getElementById('sbbrObserveBody');
    try {
      const data = await api('/api/sbbr/trade-observe/list');
      const rows = data.items || [];
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="4" class="empty-state">暂无观察股</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map(
          (r) => `<tr>
          <td>${r.code}</td><td>${r.name || ''}</td><td>${r.signal_date || '-'}</td>
          <td>
            <button type="button" class="refresh-btn sbbr-to-formal" data-id="${r.id}" data-code="${r.code}" data-name="${r.name || ''}">转正式</button>
            <button type="button" class="gms-btn-outline sbbr-del-observe" data-id="${r.id}">移除</button>
          </td>
        </tr>`
        )
        .join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="4" class="empty-state">${e.message}</td></tr>`;
    }
  }

  async function refreshFormal() {
    const body = document.getElementById('sbbrFormalBody');
    try {
      const data = await api('/api/sbbr/formal-trades/list');
      const rows = data.items || [];
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="10" class="empty-state">暂无正式交易</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map((r) => {
          const live = r.live_eval || {};
          const breach = live.defense_breach && live.defense_breach.breached ? '破位' : '';
          const flags = (live.exit_flags && live.exit_flags.flags) || [];
          const evalTxt = [breach, flags.join(',')].filter(Boolean).join(' / ') || '-';
          const sc = live.support_confirm || {};
          let confirmTxt = '-';
          if (sc && typeof sc === 'object' && ('confirmed' in sc || sc.reason)) {
            confirmTxt = sc.confirmed ? '是' : `否(${sc.reason || '-'})`;
          }
          return `<tr>
            <td>${r.code}</td><td>${r.name || ''}</td><td>${r.status}</td><td>${r.stage || ''}</td>
            <td>${fmt(r.entry_price)}</td><td>${fmt(r.allocated_pct, 0)}</td>
            <td>${fmt(r.defense_anchor_low)}</td><td>${confirmTxt}</td><td>${evalTxt}</td>
            <td>
              ${
                r.status === 'open'
                  ? `<button type="button" class="gms-btn-outline sbbr-add-stage" data-id="${r.id}" data-alloc="${r.allocated_pct || 50}">加仓30%</button>
                     <button type="button" class="gms-btn-outline sbbr-close-trade" data-id="${r.id}">平仓</button>`
                  : ''
              }
              <button type="button" class="gms-btn-outline sbbr-del-formal" data-id="${r.id}">删除</button>
            </td>
          </tr>`;
        })
        .join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="10" class="empty-state">${e.message}</td></tr>`;
    }
  }

  async function refreshReserve() {
    const body = document.getElementById('sbbrReserveBody');
    try {
      const data = await api('/api/sbbr/reserve-box');
      const rows = data.items || [];
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="4" class="empty-state">储备箱为空</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map(
          (r) => `<tr>
          <td>${r.stock_code}</td><td>${r.stock_name || ''}</td><td>${r.status}</td>
          <td><button type="button" class="gms-btn-outline sbbr-del-reserve" data-id="${r.id}">删除</button></td>
        </tr>`
        )
        .join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="4" class="empty-state">${e.message}</td></tr>`;
    }
  }

  function bind() {
    const root = document.getElementById('sbbr-content');
    if (!root) return;

    syncScopeUI();
    document.getElementById('sbbrScope')?.addEventListener('change', () => syncScopeUI());

    root.querySelectorAll('[data-sbbr-sub]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const sub = btn.getAttribute('data-sbbr-sub');
        switchSub(sub);
        if (sub === 'observe') refreshObserve();
        if (sub === 'formal') refreshFormal();
        if (sub === 'reserve') refreshReserve();
      });
    });

    document.getElementById('sbbrRefreshBtn')?.addEventListener('click', () => refreshSignals());
    document.getElementById('sbbrQfqLevelsBtn')?.addEventListener('click', () => refreshQfqLevels());
    document.getElementById('sbbrObserveRefreshBtn')?.addEventListener('click', () => refreshObserve());
    document.getElementById('sbbrFormalRefreshBtn')?.addEventListener('click', () => refreshFormal());
    document.getElementById('sbbrReserveRefreshBtn')?.addEventListener('click', () => refreshReserve());
    document.getElementById('sbbrReserveAddBtn')?.addEventListener('click', async () => {
      const code = document.getElementById('sbbrReserveCode').value.trim();
      const name = document.getElementById('sbbrReserveName').value.trim();
      if (!code) return alert('请输入代码');
      try {
        await api('/api/sbbr/reserve-box', {
          method: 'POST',
          body: JSON.stringify({ stock_code: code, stock_name: name || null }),
        });
        refreshReserve();
      } catch (e) {
        alert(e.message);
      }
    });

    document.getElementById('sbbrResultsBody')?.addEventListener('click', async (e) => {
      const detailBtn = e.target.closest('.sbbr-score-detail-toggle');
      if (detailBtn) {
        e.preventDefault();
        const rowIndex = detailBtn.getAttribute('data-row');
        const tbody = document.getElementById('sbbrResultsBody');
        const detailRow = tbody?.querySelector(`tr.sbbr-score-detail-row[data-detail-for="${rowIndex}"]`);
        if (detailRow) {
          const show = detailRow.style.display === 'none' || !detailRow.style.display;
          detailRow.style.display = show ? 'table-row' : 'none';
          detailBtn.classList.toggle('active', show);
        }
        return;
      }
      const obs = e.target.closest('.sbbr-add-observe');
      if (obs) {
        let snap = null;
        try {
          snap = JSON.parse(decodeURIComponent(obs.getAttribute('data-snap') || '%7B%7D'));
        } catch (_) {}
        try {
          await api('/api/sbbr/trade-observe/add', {
            method: 'POST',
            body: JSON.stringify({
              code: obs.getAttribute('data-code'),
              name: obs.getAttribute('data-name'),
              signal_date: obs.getAttribute('data-date'),
              signal_snapshot: snap,
            }),
          });
          alert('已加入交易观察');
        } catch (err) {
          alert(err.message);
        }
        return;
      }
      const resv = e.target.closest('.sbbr-add-reserve');
      if (resv) {
        try {
          await api('/api/sbbr/reserve-box', {
            method: 'POST',
            body: JSON.stringify({
              stock_code: resv.getAttribute('data-code'),
              stock_name: resv.getAttribute('data-name'),
            }),
          });
          alert('已加入储备箱');
        } catch (err) {
          alert(err.message);
        }
      }
    });

    document.getElementById('sbbrObserveBody')?.addEventListener('click', async (e) => {
      const toFormal = e.target.closest('.sbbr-to-formal');
      if (toFormal) {
        const price = window.prompt('请输入入场价格');
        if (!price) return;
        try {
          await api(`/api/sbbr/formal-trades/from-observe/${toFormal.getAttribute('data-id')}`, {
            method: 'POST',
            body: JSON.stringify({ entry_price: Number(price), allocated_pct: 50 }),
          });
          alert('已转入正式交易（试探 50%）');
          switchSub('formal');
          refreshFormal();
        } catch (err) {
          alert(err.message);
        }
        return;
      }
      const del = e.target.closest('.sbbr-del-observe');
      if (del) {
        await api(`/api/sbbr/trade-observe/${del.getAttribute('data-id')}`, { method: 'DELETE' });
        refreshObserve();
      }
    });

    document.getElementById('sbbrFormalBody')?.addEventListener('click', async (e) => {
      const add = e.target.closest('.sbbr-add-stage');
      if (add) {
        const cur = Number(add.getAttribute('data-alloc') || 50);
        const next = Math.min(80, cur + 30);
        await api(`/api/sbbr/formal-trades/${add.getAttribute('data-id')}`, {
          method: 'PATCH',
          body: JSON.stringify({ allocated_pct: next, stage: 'add' }),
        });
        refreshFormal();
        return;
      }
      const closeBtn = e.target.closest('.sbbr-close-trade');
      if (closeBtn) {
        const px = window.prompt('平仓价格');
        if (!px) return;
        await api(`/api/sbbr/formal-trades/${closeBtn.getAttribute('data-id')}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'closed', exit_price: Number(px), exit_reason: 'manual' }),
        });
        refreshFormal();
        return;
      }
      const del = e.target.closest('.sbbr-del-formal');
      if (del) {
        if (!window.confirm('确定删除？')) return;
        await api(`/api/sbbr/formal-trades/${del.getAttribute('data-id')}`, { method: 'DELETE' });
        refreshFormal();
      }
    });

    document.getElementById('sbbrReserveBody')?.addEventListener('click', async (e) => {
      const del = e.target.closest('.sbbr-del-reserve');
      if (del) {
        await api(`/api/sbbr/reserve-box/${del.getAttribute('data-id')}`, { method: 'DELETE' });
        refreshReserve();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
