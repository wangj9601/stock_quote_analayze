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
      const q = new URLSearchParams({
        scope,
        entry_only: String(entryOnly),
        require_bottom: 'true',
        require_size: 'true',
        max_results: '200',
      });
      if (date) q.set('date', date);
      if (traceOnly && scope === 'market') q.set('trace_only', 'true');

      let data = await api(`/api/screening/sbbr-strategy?${q}`);
      if (traceOnly && scope === 'market' && (!data.data || !data.data.length)) {
        q.delete('trace_only');
        data = await api(`/api/screening/sbbr-strategy?${q}`);
      }
      const rows = data.data || [];
      document.getElementById('sbbrResultsCount').textContent = `共 ${rows.length} 只`;
      document.getElementById('sbbrSearchMeta').textContent =
        `日期 ${data.search_date || '-'} · 来源 ${data.source || 'live'} · config ${data.config_id || ''}`;
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="10" class="empty-state">无符合条件的结果</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map((r) => {
          const snap = encodeURIComponent(JSON.stringify(r));
          return `<tr>
            <td>${r.code || ''}</td>
            <td>${r.name || ''}</td>
            <td>${fmt(r.total_mv)}</td>
            <td>${fmt(r.circ_mv)}</td>
            <td>${r.bottom_mode || '-'}</td>
            <td>${r.entry_signal ? '是' : '否'}</td>
            <td>${fmt(r.close)}</td>
            <td>${fmt(r.defense_low)}</td>
            <td>${fmt(r.volume_ratio)}</td>
            <td>
              <button type="button" class="gms-btn-outline sbbr-add-observe"
                data-code="${r.code}" data-name="${r.name || ''}" data-date="${r.date || ''}" data-snap="${snap}">观察</button>
              <button type="button" class="gms-btn-outline sbbr-add-reserve"
                data-code="${r.code}" data-name="${r.name || ''}">储备</button>
            </td>
          </tr>`;
        })
        .join('');
    } catch (e) {
      showErr(e.message || String(e));
      body.innerHTML = '<tr><td colspan="10" class="empty-state">加载失败</td></tr>';
    } finally {
      if (loading) loading.style.display = 'none';
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
        body.innerHTML = '<tr><td colspan="9" class="empty-state">暂无正式交易</td></tr>';
        return;
      }
      body.innerHTML = rows
        .map((r) => {
          const live = r.live_eval || {};
          const breach = live.defense_breach && live.defense_breach.breached ? '破位' : '';
          const flags = (live.exit_flags && live.exit_flags.flags) || [];
          const evalTxt = [breach, flags.join(',')].filter(Boolean).join(' / ') || '-';
          return `<tr>
            <td>${r.code}</td><td>${r.name || ''}</td><td>${r.status}</td><td>${r.stage || ''}</td>
            <td>${fmt(r.entry_price)}</td><td>${fmt(r.allocated_pct, 0)}</td>
            <td>${fmt(r.defense_anchor_low)}</td><td>${evalTxt}</td>
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
      body.innerHTML = `<tr><td colspan="9" class="empty-state">${e.message}</td></tr>`;
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
