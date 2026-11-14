/**
 * CUPB 选股页：只读 cupb_signal_trace（日终预计算）。
 */
(function () {
  let bound = false;
  let lastRows = [];
  let lastMeta = null;
  let pageOffset = 0;

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
    if (!Number.isFinite(x)) return '—';
    return x.toFixed(digits == null ? 2 : digits);
  }

  function statusLabel(s) {
    const k = String(s || '').toLowerCase();
    if (k === 'confirmed') return '已确认';
    if (k === 'forming') return '形成中';
    return s || '—';
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

  function buildQuery() {
    const params = new URLSearchParams();
    const date = (document.getElementById('cupbDate') || {}).value || '';
    if (date) params.set('trade_date', date);
    const status = (document.getElementById('cupbStatus') || {}).value || 'both';
    if (status && status !== 'both') params.set('status', status);
    const code = String((document.getElementById('cupbCode') || {}).value || '').trim();
    if (code) params.set('code', code);
    params.set('limit', String(pageSize()));
    params.set('offset', String(Math.max(0, pageOffset)));
    return params.toString();
  }

  function renderMeta(data) {
    const total = data.total || 0;
    const limit = data.limit || pageSize();
    const offset = data.offset || 0;
    const count = document.getElementById('cupbCount');
    if (count) {
      count.textContent = `共 ${total} 条 · 本页 ${(data.items || []).length} 条`;
    }
    const dateEl = document.getElementById('cupbTradeDate');
    if (dateEl) {
      dateEl.textContent = data.trade_date
        ? `基准日 ${data.trade_date} · 配置 #${data.config_id || '—'}`
        : '';
    }
    const hint = document.getElementById('cupbPoolHint');
    if (hint) {
      hint.textContent = '结果来自每日收盘流程节点 cupb_signals_cn（A股全市场、不复权、forming+confirmed）。';
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
      body.innerHTML = '<tr><td colspan="9" class="empty-state">没有符合条件的杯底信号</td></tr>';
      return;
    }
    body.innerHTML = rows.map((row) => {
      const code = esc(row.code);
      const name = esc(row.name || '');
      const href = `stock.html?code=${encodeURIComponent(row.code || '')}&name=${encodeURIComponent(row.name || '')}`;
      const st = String(row.status || '').toLowerCase();
      const stCls = st === 'confirmed' ? 'sepa-tag--breakout' : 'sepa-tag--forming';
      return `<tr>
        <td><a href="${href}" target="_blank" rel="noopener noreferrer">${code}</a></td>
        <td>${name}</td>
        <td><span class="sepa-tag ${stCls}">${esc(statusLabel(row.status))}</span></td>
        <td>${esc(row.grade || '—')}</td>
        <td class="sepa-num">${row.volume_score == null ? '—' : esc(row.volume_score)}</td>
        <td class="sepa-num">${num(row.cup_depth_pct, 1)}</td>
        <td>${esc(row.confirm_date || '—')}</td>
        <td class="sepa-num">${num(row.last_close)}</td>
        <td class="sepa-actions">
          <a class="gms-op-btn" href="${href}" target="_blank" rel="noopener noreferrer">详情</a>
        </td>
      </tr>`;
    }).join('');
  }

  function exportCsv() {
    if (!lastRows.length) return;
    const header = ['代码', '名称', '状态', '等级', '量价', '杯深%', '确认日', '收盘'];
    const lines = [header.join(',')];
    lastRows.forEach((row) => {
      const cells = [
        row.code, row.name, statusLabel(row.status), row.grade, row.volume_score,
        row.cup_depth_pct, row.confirm_date, row.last_close,
      ].map((v) => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`);
      lines.push(cells.join(','));
    });
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    const day = (lastMeta && lastMeta.trade_date) || 'cupb';
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
      lastRows = payload.items || [];
      lastMeta = payload;
      if (payload.trade_date && !(document.getElementById('cupbDate') || {}).value) {
        const dateInput = document.getElementById('cupbDate');
        if (dateInput) dateInput.value = payload.trade_date;
      }
      renderMeta(payload);
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
  }

  window.CupbScreening = { init, load };
  init();
})();
