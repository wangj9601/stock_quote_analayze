/**
 * SBBR 做小做底 — 信号历史页（交互对齐 URT stock_urt_trace）
 */
(function () {
  const apiBase = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
    ? (Config.getApiBaseUrl() || '')
    : '';

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmt(v, n) {
    if (v == null || v === '') return '--';
    const x = Number(v);
    return Number.isFinite(x) ? x.toFixed(n == null ? 2 : n) : String(v);
  }

  function yn(v, yesClass) {
    if (v === true) return `<span class="${yesClass || 'buy-yes'}">是</span>`;
    if (v === false) return '否';
    return '--';
  }

  class StockSbbrTracePage {
    constructor() {
      const params = new URLSearchParams(window.location.search);
      this.code = (params.get('code') || '').trim();
      this.name = decodeURIComponent(params.get('name') || '');
      this.configId = params.get('config_id') ? Number(params.get('config_id')) : null;
      this.configOptions = [];
      this.allData = [];
      this.currentPage = 1;
      this.pageSize = 30;
      this.totalPages = 0;

      document.getElementById('stockDisplay').textContent =
        this.code ? `${this.code} ${this.name}` : '--';
      this.setDefaultDates();
      const startEl = document.getElementById('startDate');
      const endEl = document.getElementById('endDate');
      if (startEl && params.get('start_date')) startEl.value = params.get('start_date');
      if (endEl && params.get('end_date')) endEl.value = params.get('end_date');
      if (params.get('source') === 'trace') {
        const src = document.getElementById('sourceSelect');
        if (src) src.value = 'trace';
      }

      document.getElementById('searchBtn').addEventListener('click', () => this.fetchData());
      document.getElementById('configSelect').addEventListener('change', () => {
        this.configId = Number(document.getElementById('configSelect').value) || null;
        this.fetchData();
      });
      document.getElementById('firstPage').addEventListener('click', () => this.goToPage(1));
      document.getElementById('prevPage').addEventListener('click', () => this.goToPage(this.currentPage - 1));
      document.getElementById('nextPage').addEventListener('click', () => this.goToPage(this.currentPage + 1));
      document.getElementById('lastPage').addEventListener('click', () => this.goToPage(this.totalPages));

      const tbody = document.querySelector('#traceTable tbody');
      if (tbody) {
        tbody.addEventListener('click', (e) => {
          const btn = e.target.closest('.sbbr-score-detail-toggle');
          if (!btn) return;
          e.preventDefault();
          const idx = btn.getAttribute('data-row');
          const detailRow = tbody.querySelector(`tr.gms-score-detail-row[data-detail-for="${idx}"]`);
          if (detailRow) {
            detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
          }
        });
      }
      this.updatePagination();
      if (this.code) this.fetchData();
    }

    setDefaultDates() {
      const today = new Date();
      const threeMonthsAgo = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000);
      const startEl = document.getElementById('startDate');
      const endEl = document.getElementById('endDate');
      if (startEl) startEl.value = this.formatDate(threeMonthsAgo);
      if (endEl) endEl.value = this.formatDate(today);
    }

    formatDate(d) {
      return d.toISOString().slice(0, 10);
    }

    renderTable() {
      const tbody = document.querySelector('#traceTable tbody');
      if (!tbody) return;
      const start = (this.currentPage - 1) * this.pageSize;
      const pageData = this.allData.slice(start, start + this.pageSize);
      if (!pageData.length) {
        tbody.innerHTML = '';
        return;
      }
      tbody.innerHTML = pageData.map((r, index) => {
        let detailHtml = '<div class="gms-score-detail-inner">明细组件未加载</div>';
        if (window.SbbrScoreDetail && typeof window.SbbrScoreDetail.buildHtml === 'function') {
          detailHtml = window.SbbrScoreDetail.buildHtml(r);
        }
        const rowClass = r.entry_signal ? 'urt-row-score-high' : (r.bottom_matched ? 'urt-row-score-mid' : '');
        return `<tr class="${rowClass}">
          <td>${escapeHtml(r.date || '--')}</td>
          <td>${yn(r.size_ok)}</td>
          <td>${yn(r.bottom_matched)}</td>
          <td>${yn(r.entry_signal, 'buy-yes')}</td>
          <td>${escapeHtml(r.bottom_mode || '--')}</td>
          <td>${fmt(r.close)}</td>
          <td>${fmt(r.ma20)}</td>
          <td>${fmt(r.box_support)}</td>
          <td>${fmt(r.box_resistance)}</td>
          <td>${fmt(r.nearest_support)}</td>
          <td>${fmt(r.nearest_resistance)}</td>
          <td>${fmt(r.defense_low)}</td>
          <td>${fmt(r.volume_ratio)}</td>
          <td><button type="button" class="gms-op-btn sbbr-score-detail-toggle" data-row="${index}">明细</button></td>
        </tr>
        <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
          <td colspan="14" class="gms-score-detail-cell">${detailHtml}</td>
        </tr>`;
      }).join('');
    }

    updatePagination() {
      const total = this.allData.length;
      this.totalPages = total > 0 ? Math.max(1, Math.ceil(total / this.pageSize)) : 0;
      const pageInfo = document.getElementById('pageInfo');
      if (pageInfo) {
        pageInfo.textContent = total > 0
          ? `第 ${this.currentPage} / ${this.totalPages} 页，共 ${total} 条`
          : '共 0 条';
      }
      const atStart = this.currentPage <= 1 || total === 0;
      const atEnd = this.currentPage >= this.totalPages || total === 0;
      ['firstPage', 'prevPage'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = atStart;
      });
      ['nextPage', 'lastPage'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = atEnd;
      });
    }

    goToPage(p) {
      if (!this.totalPages || p < 1 || p > this.totalPages) return;
      this.currentPage = p;
      this.renderTable();
      this.updatePagination();
    }

    async fetchData() {
      const loading = document.getElementById('loadingMsg');
      const empty = document.getElementById('emptyMsg');
      const meta = document.getElementById('metaMsg');
      const tbody = document.querySelector('#traceTable tbody');
      if (!this.code) {
        empty.textContent = '请从选股页通过「历史」进入并带 code 参数';
        empty.style.display = '';
        return;
      }
      loading.style.display = '';
      empty.style.display = 'none';
      if (meta) meta.textContent = '';
      tbody.innerHTML = '';
      this.allData = [];
      this.currentPage = 1;
      this.totalPages = 0;
      this.updatePagination();

      try {
        const startDate = (document.getElementById('startDate')?.value || '').trim();
        const endDate = (document.getElementById('endDate')?.value || '').trim();
        if (!startDate || !endDate) {
          empty.textContent = '请填写开始与结束日期';
          empty.style.display = '';
          return;
        }
        if (startDate > endDate) {
          empty.textContent = '开始日期不能晚于结束日期';
          empty.style.display = '';
          return;
        }
        const source = document.getElementById('sourceSelect')?.value || 'live';
        const entryOnly = !!document.getElementById('entryOnly')?.checked;
        const requireBottom = !!document.getElementById('requireBottom')?.checked;
        const q = new URLSearchParams({
          code: this.code,
          start_date: startDate,
          end_date: endDate,
        });
        if (this.configId) q.set('config_id', String(this.configId));
        if (entryOnly) q.set('entry_only', 'true');
        if (requireBottom && source === 'live') q.set('require_bottom', 'true');

        const path = source === 'trace'
          ? `/api/stock/sbbr-signal-trace?${q}`
          : `/api/stock/sbbr-signal-history?${q}`;
        const res = await fetch(`${apiBase}${path}`);
        const json = await res.json().catch(() => ({}));
        if (!res.ok || json.success === false) {
          const detail = json.detail;
          let errMsg = json.message || res.statusText || '加载失败';
          if (typeof detail === 'string') errMsg = detail;
          else if (Array.isArray(detail)) errMsg = detail.map((d) => d.msg || d).join('; ');
          throw new Error(errMsg);
        }

        const configs = json.configs || [];
        this.configOptions = configs;
        const sel = document.getElementById('configSelect');
        if (sel) {
          sel.innerHTML = configs.map((c) =>
            `<option value="${c.id}" ${c.id === json.config_id ? 'selected' : ''}>${escapeHtml(c.name)}${c.is_default ? ' (默认)' : ''}</option>`
          ).join('') || '<option value="">默认</option>';
        }
        this.configId = json.config_id;

        this.allData = json.data || [];
        if (requireBottom && source === 'trace') {
          this.allData = this.allData.filter((r) => !!r.bottom_matched);
        }
        if (meta) {
          const srcLabel = json.source_label || (source === 'trace' ? '预计算' : '实时回溯');
          const bits = [
            `来源 ${srcLabel}`,
            json.end_date_effective ? `有效止日 ${json.end_date_effective}` : '',
            json.trade_days != null ? `区间交易日 ${json.trade_days}` : '',
            `返回 ${json.total != null ? json.total : this.allData.length} 条`,
          ].filter(Boolean);
          meta.textContent = bits.join(' · ');
        }

        if (!this.allData.length) {
          empty.textContent = source === 'trace'
            ? '所选日期范围内暂无预计算信号（可改「现算回溯」或缩短区间后重试）'
            : '所选日期范围内暂无符合筛选的信号日';
          empty.style.display = '';
          this.updatePagination();
          return;
        }
        this.totalPages = Math.max(1, Math.ceil(this.allData.length / this.pageSize));
        this.currentPage = 1;
        this.renderTable();
        this.updatePagination();
      } catch (e) {
        empty.textContent = '加载失败: ' + (e.message || e);
        empty.style.display = '';
        this.allData = [];
        this.updatePagination();
      } finally {
        loading.style.display = 'none';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.sbbrTracePage = new StockSbbrTracePage();
  });
})();
