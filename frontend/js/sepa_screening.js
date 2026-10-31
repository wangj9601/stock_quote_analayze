/**
 * SEPA 选股页：趋势模板 + VCP 收缩 + 枢轴买点。
 */
(function () {
  let bound = false;
  let lastRows = [];
  let lastMeta = null;

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

  function signedPct(v) {
    if (v == null || v === '') return '—';
    const x = Number(v);
    if (!Number.isFinite(x)) return '—';
    const text = (x > 0 ? '+' : '') + x.toFixed(2) + '%';
    return text;
  }

  function amountText(v) {
    const n = Number(v);
    if (!Number.isFinite(n) || n <= 0) return '不限成交额';
    if (n >= 1e8) return (n / 1e8).toFixed(2).replace(/\.00$/, '') + ' 亿元';
    return Math.round(n / 1e4).toLocaleString('zh-CN') + ' 万元';
  }

  function setError(msg) {
    const el = document.getElementById('sepaError');
    if (!el) return;
    el.style.display = msg ? 'block' : 'none';
    el.textContent = msg || '';
  }

  function tag(kind, label) {
    const key = String(kind || 'none').toLowerCase();
    return `<span class="sepa-tag sepa-tag--${esc(key)}">${esc(label || key)}</span>`;
  }

  function buildQuery() {
    const params = new URLSearchParams();
    const date = (document.getElementById('sepaDate') || {}).value || '';
    if (date) params.set('trade_date', date);
    const status = (document.getElementById('sepaStatus') || {}).value || '';
    if (status) params.set('status', status);
    const top = parseInt((document.getElementById('sepaTop') || {}).value, 10);
    params.set('top', String(Number.isFinite(top) ? Math.min(200, Math.max(1, top)) : 30));
    const limit = parseInt((document.getElementById('sepaLimit') || {}).value, 10);
    params.set('limit_codes', String(Number.isFinite(limit) ? Math.min(4000, Math.max(0, limit)) : 0));
    if ((document.getElementById('sepaForming') || {}).checked) params.set('include_forming', 'true');
    if ((document.getElementById('sepaExtended') || {}).checked) params.set('include_extended', 'true');
    return params.toString();
  }

  function renderFunnel(data) {
    const funnel = data.funnel || {};
    const pool = data.pool || {};
    const hint = document.getElementById('sepaPoolHint');
    if (hint) {
      hint.textContent = `本次股票池 ${data.universe || 0} 只：排除 ST / 退市，近 20 日均成交额不低于 ${amountText(pool.min_avg_amount)}。`;
    }
    const line = document.getElementById('sepaFunnel');
    if (line) {
      line.textContent = [
        `趋势通过 ${funnel.trend_pass || 0}`,
        `就位 ${funnel.ready || 0}`,
        `未放量越过 ${funnel.quiet || 0}`,
        `放量突破 ${funnel.breakout || 0}`,
        `远离枢轴 ${funnel.extended || 0}`,
        `收缩中 ${funnel.forming || 0}`,
      ].join(' · ');
    }
    const count = document.getElementById('sepaCount');
    if (count) count.textContent = `列出 ${data.count || 0} 只`;
    const dateEl = document.getElementById('sepaTradeDate');
    if (dateEl) dateEl.textContent = data.trade_date ? `基准日 ${data.trade_date}` : '';
    const disclaimer = document.getElementById('sepaDisclaimer');
    if (disclaimer) disclaimer.textContent = data.disclaimer || '';
  }

  function detailHtml(row) {
    const checks = (row.trend_checks || []).map((item) => {
      const ok = !!item.ok;
      return `<li class="${ok ? 'is-ok' : 'is-fail'}"><span>${ok ? '通过' : '未过'}</span>${esc(item.label)}</li>`;
    }).join('');
    const legs = (row.contractions || []).map((leg, i) => (
      `<tr><td>${i + 1}</td><td class="sepa-num">${num(leg.depth_pct)}%</td><td class="sepa-num">${esc(leg.days)}</td>`
      + `<td class="sepa-num">${num(leg.hi)}</td><td class="sepa-num">${num(leg.lo)}</td>`
      + `<td>${esc(leg.hi_date || '')}</td><td>${esc(leg.lo_date || '')}</td></tr>`
    )).join('');
    const flags = row.flags ? `<p class="sepa-flags">${esc(row.flags)}</p>` : '';
    return `
      <div class="sepa-detail-panel">
        <div class="sepa-metrics">
          <span>收盘 <b class="sepa-num">${num(row.close)}</b></span>
          <span>得分 <b class="sepa-num">${num(row.score, 1)}</b></span>
          <span>量比 <b class="sepa-num">${num(row.vol_ratio)}</b></span>
          <span>近10日振幅 <b class="sepa-num">${num(row.tight_range_pct)}%</b></span>
          <span>突破前振幅 <b class="sepa-num">${num(row.base_tight_range_pct)}%</b></span>
          <span>偏离50日 <b class="sepa-num">${signedPct(row.extended_pct)}</b></span>
          <span>距52周高 <b class="sepa-num">${signedPct(row.off_high_pct)}</b></span>
          <span>MA50/150/200 <b class="sepa-num">${num(row.ma50)} / ${num(row.ma150)} / ${num(row.ma200)}</b></span>
        </div>
        ${flags}
        <div class="sepa-detail-grid">
          <section>
            <h4>趋势八条</h4>
            <ul class="sepa-checks">${checks || '<li>趋势明细未返回</li>'}</ul>
          </section>
          <section>
            <h4>收缩序列</h4>
            <table class="sepa-legs">
              <thead><tr><th>#</th><th>深度</th><th>天数</th><th>高点</th><th>低点</th><th>高点日</th><th>低点日</th></tr></thead>
              <tbody>${legs || '<tr><td colspan="7">没有收缩腿</td></tr>'}</tbody>
            </table>
            <p class="param-hint">失效价 ${num(row.invalidation)}，跌破最后一段低点则形态失效。</p>
          </section>
          <section>
            <h4>两融旁证</h4>
            <p>${tag(row.margin_status, row.margin_status_label)}
              余额回撤 <b class="sepa-num">${signedPct(row.drawdown_pct)}</b>
              · 近端变化 <b class="sepa-num">${signedPct(row.reflow_pct)}</b>
              · 拥挤度 <b class="sepa-num">${row.crowd_pct == null ? '—' : num(row.crowd_pct) + '%'}</b>
            </p>
            <p class="param-hint">${esc((row.margin_notes || []).join('、') || '无额外备注')}</p>
          </section>
        </div>
      </div>`;
  }

  function renderRows(rows) {
    const body = document.getElementById('sepaTableBody');
    if (!body) return;
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="11" class="empty-state">这个基准日没有符合当前形态的股票。可以勾选「收缩中」或「远离枢轴」再看一层。</td></tr>';
      return;
    }
    body.innerHTML = rows.map((row, index) => {
      const code = esc(row.code);
      const name = esc(row.name || '');
      const href = `stock.html?code=${encodeURIComponent(row.code || '')}&name=${encodeURIComponent(row.name || '')}`;
      const hist = `stock_history.html?code=${encodeURIComponent(row.code || '')}`;
      const dist = signedPct(row.dist_to_pivot_pct);
      const distCls = Number(row.dist_to_pivot_pct) > 0 ? 'is-up' : (Number(row.dist_to_pivot_pct) < 0 ? 'is-down' : '');
      return `
        <tr class="sepa-row" data-index="${index}">
          <td>${tag(row.tier, row.tier_label)}</td>
          <td class="sepa-num">${code}</td>
          <td>${name || '—'}</td>
          <td>${tag(row.vcp_status, row.vcp_status_label)}</td>
          <td class="sepa-num ${distCls}">${dist}</td>
          <td class="sepa-num">${num(row.pivot)}</td>
          <td class="sepa-num">${num(row.invalidation)}</td>
          <td class="sepa-num">${esc(row.vcp_count == null ? '—' : row.vcp_count)}</td>
          <td class="sepa-num">${num(row.rs_rank, 1)}</td>
          <td>${tag(row.margin_status, row.margin_status_label)}</td>
          <td class="sepa-actions">
            <button type="button" class="gms-op-btn sepa-detail-btn" data-index="${index}" aria-expanded="false">明细</button>
            <a class="gms-op-btn" href="${href}" target="_blank" rel="noopener noreferrer">详情</a>
            <a class="gms-op-btn" href="${hist}" target="_blank" rel="noopener noreferrer">历史</a>
          </td>
        </tr>
        <tr class="sepa-detail-row" hidden>
          <td colspan="11">${detailHtml(row)}</td>
        </tr>`;
    }).join('');
  }

  function exportCsv() {
    if (!lastRows.length) return;
    const header = ['代码', '名称', '分级', '形态', '收盘', '枢轴', '距枢轴%', '失效价', '收缩次数', 'RS', '两融', '得分', '标记'];
    const lines = [header.join(',')];
    lastRows.forEach((row) => {
      const cells = [
        row.code, row.name, row.tier_label, row.vcp_status_label, row.close, row.pivot,
        row.dist_to_pivot_pct, row.invalidation, row.vcp_count, row.rs_rank,
        row.margin_status_label, row.score, row.flags,
      ].map((v) => `"${String(v == null ? '' : v).replace(/"/g, '""')}"`);
      lines.push(cells.join(','));
    });
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    const day = (lastMeta && lastMeta.trade_date) || 'sepa';
    a.href = URL.createObjectURL(blob);
    a.download = `sepa-${day}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function load() {
    const loading = document.getElementById('sepaLoading');
    const refresh = document.getElementById('refreshBtn-sepa');
    const exportBtn = document.getElementById('sepaExportBtn');
    if (loading) loading.style.display = 'flex';
    if (refresh) refresh.disabled = true;
    if (exportBtn) exportBtn.style.display = 'none';
    setError('');
    try {
      const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
      const res = await fetchFn(`${apiBase()}/api/stock/sepa/screen?${buildQuery()}`, {
        headers: authHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.success === false) {
        const msg = data.message || data.detail || res.statusText || '请求失败';
        throw new Error(typeof msg === 'string' ? msg : '筛选失败');
      }
      const payload = data.data || {};
      lastRows = payload.rows || [];
      lastMeta = payload;
      renderFunnel(payload);
      renderRows(lastRows);
      if (exportBtn && lastRows.length) exportBtn.style.display = '';
    } catch (err) {
      lastRows = [];
      renderRows([]);
      const count = document.getElementById('sepaCount');
      if (count) count.textContent = '筛选没有完成';
      setError(`筛选没有完成：${err && err.message ? err.message : '网络错误'}。请稍后重试。`);
    } finally {
      if (loading) loading.style.display = 'none';
      if (refresh) refresh.disabled = false;
    }
  }

  function onTableClick(event) {
    const btn = event.target.closest('.sepa-detail-btn');
    if (!btn) return;
    const row = btn.closest('tr');
    const detail = row && row.nextElementSibling;
    if (!detail) return;
    const open = detail.hasAttribute('hidden');
    detail.toggleAttribute('hidden', !open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.classList.toggle('active', open);
  }

  function init() {
    if (bound) return;
    const refresh = document.getElementById('refreshBtn-sepa');
    const body = document.getElementById('sepaTableBody');
    if (!refresh || !body) return;
    bound = true;
    refresh.addEventListener('click', () => { void load(); });
    const exportBtn = document.getElementById('sepaExportBtn');
    if (exportBtn) exportBtn.addEventListener('click', exportCsv);
    body.addEventListener('click', onTableClick);
  }

  window.SepaScreening = { init, load };
  init();
})();
