/**
 * 杯底 CUPB 个股历史：只读 /api/stock/cupb/signal-history
 */
(function () {
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function apiBase() {
    if (typeof Config !== 'undefined' && Config && typeof Config.getApiBaseUrl === 'function') {
      return String(Config.getApiBaseUrl() || '').replace(/\/+$/, '');
    }
    return '';
  }

  function statusLabel(s) {
    const k = String(s || '').toLowerCase();
    if (k === 'confirmed') return '已确认';
    if (k === 'forming') return '形成中';
    return s || '—';
  }

  function num(v, digits) {
    if (v == null || v === '') return '—';
    const x = Number(v);
    if (!Number.isFinite(x)) return '—';
    return x.toFixed(digits == null ? 2 : digits);
  }

  function setHidden(el, hidden) {
    if (!el) return;
    el.hidden = hidden;
  }

  const params = new URLSearchParams(window.location.search || '');
  const codeEl = document.getElementById('stockCode');
  const startEl = document.getElementById('startDate');
  const endEl = document.getElementById('endDate');
  const nameEl = document.getElementById('stockDisplay');
  const metaEl = document.getElementById('metaMsg');
  const loadingEl = document.getElementById('loadingMsg');
  const emptyEl = document.getElementById('emptyMsg');
  const tbody = document.querySelector('#traceTable tbody');
  const stockLink = document.getElementById('stockLink');

  const initialCode = (params.get('code') || '').trim();
  const initialName = params.get('name') || '';
  if (codeEl && initialCode) codeEl.value = initialCode;
  if (nameEl) nameEl.textContent = initialName || '--';
  if (startEl && params.get('start')) startEl.value = params.get('start');
  if (endEl && params.get('end')) endEl.value = params.get('end');

  function render(items) {
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '';
      setHidden(emptyEl, false);
      return;
    }
    setHidden(emptyEl, true);
    tbody.innerHTML = items.map((row) => {
      const st = String(row.status || '').toLowerCase();
      return `<tr>
        <td>${esc(row.date || '—')}</td>
        <td>${esc(statusLabel(st))}</td>
        <td>${esc(row.grade || '—')}</td>
        <td>${row.volume_score == null ? '—' : esc(row.volume_score)}</td>
        <td>${num(row.last_close)}</td>
        <td>${num(row.rim)}</td>
        <td>${num(row.cup_depth_pct, 1)}</td>
        <td>${esc(row.confirm_date || '—')}</td>
      </tr>`;
    }).join('');
  }

  async function fetchHistory() {
    const code = String((codeEl && codeEl.value) || '').trim();
    if (!code) {
      if (metaEl) metaEl.textContent = '请填写股票代码';
      return;
    }
    setHidden(loadingEl, false);
    setHidden(emptyEl, true);
    if (metaEl) metaEl.textContent = '';
    const q = new URLSearchParams();
    q.set('code', code);
    if (startEl && startEl.value) q.set('start_date', startEl.value);
    if (endEl && endEl.value) q.set('end_date', endEl.value);
    try {
      const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
      const res = await fetchFn(`${apiBase()}/api/stock/cupb/signal-history?${q.toString()}`);
      const body = await res.json().catch(() => ({}));
      if (!res.ok || body.success === false) {
        const msg = body.message || body.detail || '查询失败';
        throw new Error(typeof msg === 'string' ? msg : '查询失败');
      }
      const data = body.data || {};
      if (nameEl) nameEl.textContent = data.name || initialName || '--';
      if (startEl && data.start_date && !startEl.value) startEl.value = data.start_date;
      if (endEl && data.end_date && !endEl.value) endEl.value = data.end_date;
      if (data.start_date && startEl && data.start_date !== startEl.value) startEl.value = data.start_date;
      if (data.end_date && endEl && data.end_date !== endEl.value) endEl.value = data.end_date;
      const items = data.items || [];
      if (metaEl) {
        const span = data.start_date && data.end_date ? `${data.start_date} 至 ${data.end_date}` : '';
        metaEl.textContent = `${data.code || code}${data.name ? ' ' + data.name : ''} · ${span} · ${data.total || items.length} 条`;
      }
      if (stockLink) {
        const href = `stock.html?code=${encodeURIComponent(data.code || code)}&name=${encodeURIComponent(data.name || '')}`;
        stockLink.href = href;
        stockLink.hidden = false;
      }
      render(items);
    } catch (err) {
      render([]);
      setHidden(emptyEl, true);
      if (metaEl) metaEl.textContent = err && err.message ? err.message : '查询失败';
    } finally {
      setHidden(loadingEl, true);
    }
  }

  document.getElementById('cupbTraceForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    void fetchHistory();
  });

  if (initialCode) void fetchHistory();
})();
