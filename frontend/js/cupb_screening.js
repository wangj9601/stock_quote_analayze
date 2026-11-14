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

  function qualityFlagText(row) {
    const qf = (row && row.detail && row.detail.quality_flags) || (row && row.quality_flags);
    if (!qf) return '';
    if (Array.isArray(qf)) return qf.map((x) => String(x)).filter(Boolean).join('、');
    if (typeof qf === 'object') {
      return Object.entries(qf)
        .filter(([, v]) => Boolean(v))
        .map(([k]) => String(k))
        .join('、');
    }
    return String(qf);
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

  function descRows(pairs) {
    return pairs.map(([label, value]) => (
      `<tr><th>${esc(label)}</th><td>${value}</td></tr>`
    )).join('');
  }

  function tag(kind, label) {
    const key = String(kind || 'none').toLowerCase();
    return `<span class="sepa-tag sepa-tag--${esc(key)}">${esc(label || key)}</span>`;
  }

  function detailHtml(row) {
    const st = String(row.status || '').toLowerCase();
    const stCls = st === 'confirmed' ? 'breakout' : 'forming';
    const volRows = volumeFlagRows(row);
    const volBody = volRows.length
      ? descRows(volRows.map((item) => [
        item.label,
        tag(item.ok ? 'breakout' : 'quiet', item.ok ? '通过' : '未过'),
      ]))
      : descRows([['—', '暂无量价明细']]);
    const quality = qualityFlagText(row);
    const qualityBlock = quality
      ? `<h4>质量标记</h4><p class="cupb-detail-quality">${esc(quality)}</p>`
      : '';
    return `
      <div class="cupb-detail-panel">
        <h4>基本信息</h4>
        <table class="cupb-desc-table"><tbody>${descRows([
          ['代码', esc(row.code || '—')],
          ['名称', esc(row.name || '—')],
          ['状态', tag(stCls, statusLabel(row.status))],
          ['曾确认', row.ever_confirmed ? '是' : '否'],
          ['历史确认日', esc(fmtVal(row.first_confirm_date))],
          ['等级', esc(fmtVal(row.grade))],
          ['量价得分', esc(fmtVal(row.volume_score))],
          ['所属板块', esc(formatBoardLabels(row.board_labels))],
          ['复权方式', esc(priceAdjustLabel(row.price_adjust))],
        ])}</tbody></table>

        <h4>量价检查</h4>
        <table class="cupb-desc-table"><tbody>${volBody}</tbody></table>

        <h4>形态价位</h4>
        <table class="cupb-desc-table"><tbody>${descRows([
          ['收盘', `<span class="sepa-num">${esc(fmtVal(row.last_close))}</span>`],
          ['左沿', `<span class="sepa-num">${esc(fmtVal(row.left_rim_price))}</span>`],
          ['杯底', `<span class="sepa-num">${esc(fmtVal(row.cup_bottom_price))}</span>`],
          ['右沿', `<span class="sepa-num">${esc(fmtVal(row.right_rim_price))}</span>`],
          ['柄低', `<span class="sepa-num">${esc(fmtVal(row.handle_low_price))}</span>`],
          ['杯口', `<span class="sepa-num">${esc(fmtVal(row.rim))}</span>`],
          ['杯深%', `<span class="sepa-num">${esc(fmtVal(row.cup_depth_pct))}</span>`],
          ['柄回撤%', `<span class="sepa-num">${esc(fmtVal(row.handle_retrace_pct))}</span>`],
        ])}</tbody></table>

        <h4>关键日期</h4>
        <table class="cupb-desc-table"><tbody>${descRows([
          ['左沿日', esc(fmtVal(row.left_rim_date))],
          ['杯底日', esc(fmtVal(row.cup_bottom_date))],
          ['右沿日', esc(fmtVal(row.right_rim_date))],
          ['柄低日', esc(fmtVal(row.handle_low_date))],
          ['确认日', esc(fmtVal(row.confirm_date))],
        ])}</tbody></table>
        ${qualityBlock}
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
    body.innerHTML = rows.map((row, index) => {
      const code = esc(row.code);
      const name = esc(row.name || '');
      const href = `stock.html?code=${encodeURIComponent(row.code || '')}&name=${encodeURIComponent(row.name || '')}`;
      const st = String(row.status || '').toLowerCase();
      const stCls = st === 'confirmed' ? 'sepa-tag--breakout' : 'sepa-tag--forming';
      return `
        <tr class="cupb-row" data-index="${index}">
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
            <a class="gms-op-btn" href="${href}" target="_blank" rel="noopener noreferrer">详情</a>
          </td>
        </tr>
        <tr class="cupb-detail-row" hidden>
          <td colspan="9">${detailHtml(row)}</td>
        </tr>`;
    }).join('');
  }

  function exportCsv() {
    if (!lastRows.length) return;
    const header = [
      '代码', '名称', '状态', '曾确认', '历史确认日', '等级', '量价',
      '所属板块', '复权', '收盘', '左沿', '杯底', '右沿', '柄低', '杯口',
      '杯深%', '柄回撤%', '左沿日', '杯底日', '右沿日', '柄低日', '确认日', '质量标记',
    ];
    const lines = [header.join(',')];
    lastRows.forEach((row) => {
      const cells = [
        row.code, row.name, statusLabel(row.status),
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
  }

  window.CupbScreening = { init, load };
  init();
})();
