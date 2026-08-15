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
      this.forceComputeRunning = false;
      this.forceComputePollTimer = null;
      this.forceComputeTaskId = '';
      this.forceComputePollCount = 0;
      this.maxForceComputePolls = 3600;

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

      document.getElementById('searchBtn').addEventListener('click', () => {
        if (this.forceComputeRunning) return;
        this.fetchData();
      });
      const forceBtn = document.getElementById('forceComputeBtn');
      if (forceBtn) {
        forceBtn.addEventListener('click', () => this.forceCompute());
      }
      document.getElementById('configSelect').addEventListener('change', () => {
        if (this.forceComputeRunning) return;
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

    getActiveConfigLabel() {
      const opt = (this.configOptions || []).find((o) => String(o.id) === String(this.configId));
      if (!opt) return '当前策略版本';
      const name = opt.name || `配置${opt.id}`;
      return opt.is_default ? `${name} (默认)` : name;
    }

    setForceComputeRunning(running) {
      this.forceComputeRunning = !!running;
      const btn = document.getElementById('forceComputeBtn');
      const searchBtn = document.getElementById('searchBtn');
      const sel = document.getElementById('configSelect');
      const src = document.getElementById('sourceSelect');
      if (btn) {
        btn.disabled = this.forceComputeRunning;
        btn.textContent = this.forceComputeRunning ? '正在重新计算…' : '强制重新计算';
      }
      if (searchBtn) searchBtn.disabled = this.forceComputeRunning;
      if (sel) sel.disabled = this.forceComputeRunning;
      if (src) src.disabled = this.forceComputeRunning;
      ['startDate', 'endDate', 'entryOnly', 'requireBottom'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = this.forceComputeRunning;
      });
      ['firstPage', 'prevPage', 'nextPage', 'lastPage'].forEach((id) => {
        const el = document.getElementById(id);
        if (el && this.forceComputeRunning) el.disabled = true;
      });
      if (!this.forceComputeRunning) this.updatePagination();
    }

    clearForceComputePoll() {
      if (this.forceComputePollTimer) {
        clearInterval(this.forceComputePollTimer);
        this.forceComputePollTimer = null;
      }
      this.forceComputePollCount = 0;
    }

    renderForceComputeProgress(task) {
      const area = document.getElementById('forceComputeProgress');
      if (!area) return;
      area.style.display = 'block';
      const pct = task.progress != null ? Math.min(100, Math.max(0, Number(task.progress))) : 0;
      const msg = task.message || '';
      const saved = task.saved_count != null ? Number(task.saved_count) : null;
      const cur = (task.status === 'completed' && saved != null && !Number.isNaN(saved))
        ? saved
        : (task.current || 0);
      const tot = (task.status === 'completed' && saved != null && !Number.isNaN(saved))
        ? saved
        : task.total;
      const total = tot != null && tot > 0 ? ` · ${cur}/${tot}` : '';
      const statusLabel = task.status === 'completed' ? '已完成'
        : (task.status === 'failed' ? '失败' : '计算中');
      area.innerHTML = `
        <div>SBBR 信号重算: <strong>${escapeHtml(statusLabel)}</strong>${msg ? ` · ${escapeHtml(String(msg))}${total}` : ''}</div>
        <div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:${pct}%"></div></div>
      `;
    }

    forceCompute() {
      if (this.forceComputeRunning) return;
      if (!this.code) {
        alert('请先选择股票');
        return;
      }
      const label = this.getActiveConfigLabel();
      if (!confirm(`将按「${label}」重新计算该股全部历史行情的 SBBR 信号并写入预计算表（仅影响该策略版本，耗时可能较长），是否继续？`)) {
        return;
      }
      void this.startForceComputeTask();
    }

    async startForceComputeTask() {
      this.clearForceComputePoll();
      this.setForceComputeRunning(true);
      const area = document.getElementById('forceComputeProgress');
      if (area) {
        area.style.display = 'block';
        area.innerHTML = '<div>正在提交重算任务…</div><div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:5%"></div></div>';
      }
      const loading = document.getElementById('loadingMsg');
      if (loading) loading.style.display = 'none';

      try {
        const resp = await fetch(`${apiBase}/api/stock/sbbr-signal-trace/recompute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: this.code,
            config_id: this.configId,
          }),
        });
        const json = await resp.json().catch(() => ({}));
        if (!resp.ok || !json.success) {
          const detail = json.detail;
          let errMsg = json.message || resp.statusText;
          if (typeof detail === 'string') errMsg = detail;
          else if (Array.isArray(detail)) errMsg = detail.map((d) => d.msg || d).join('; ');
          throw new Error(errMsg || '提交失败');
        }
        this.forceComputeTaskId = json.data?.task_id || '';
        if (!this.forceComputeTaskId) {
          throw new Error('未返回任务 ID');
        }
        if (json.data?.config_id != null) {
          this.configId = json.data.config_id;
        }
        if (json.data?.already_running) {
          this.renderForceComputeProgress({
            status: 'running',
            progress: 0,
            message: json.message || '任务进行中',
          });
        }
        await this.pollForceComputeOnce();
        this.forceComputePollTimer = setInterval(() => this.pollForceComputeOnce(), 1000);
      } catch (e) {
        this.clearForceComputePoll();
        this.setForceComputeRunning(false);
        if (area) {
          area.style.display = 'block';
          area.innerHTML = `<span class="gms-recompute-error">提交失败: ${escapeHtml(e.message || String(e))}</span>`;
        }
      }
    }

    async pollForceComputeOnce() {
      if (!this.forceComputeTaskId) return;
      this.forceComputePollCount += 1;
      if (this.forceComputePollCount > this.maxForceComputePolls) {
        this.clearForceComputePoll();
        this.setForceComputeRunning(false);
        const area = document.getElementById('forceComputeProgress');
        if (area) {
          area.innerHTML = '<span class="gms-recompute-error">等待超时，请刷新页面后重试</span>';
        }
        return;
      }
      const url = `${apiBase}/api/stock/sbbr-signal-trace/recompute/${encodeURIComponent(this.forceComputeTaskId)}`;
      try {
        const resp = await fetch(url);
        const json = await resp.json().catch(() => ({}));
        if (!resp.ok || !json.success) {
          const detail = json.detail;
          let errMsg = json.message || resp.statusText;
          if (typeof detail === 'string') errMsg = detail;
          else if (Array.isArray(detail)) errMsg = detail.map((d) => d.msg || d).join('; ');
          throw new Error(errMsg || '查询进度失败');
        }
        const task = json.data;
        if (!task) return;
        this.renderForceComputeProgress(task);
        const st = task.status;
        if (st === 'completed' || st === 'failed') {
          this.clearForceComputePoll();
          this.setForceComputeRunning(false);
          if (st === 'completed') {
            const src = document.getElementById('sourceSelect');
            if (src) src.value = 'trace';
            if (window.CommonUtils && task.message) {
              CommonUtils.showToast(task.message, 'success');
            }
            await this.fetchData();
            if (task.message) {
              this.renderForceComputeProgress({ ...task, progress: 100 });
            }
          } else {
            const area = document.getElementById('forceComputeProgress');
            if (area) {
              area.innerHTML = `<span class="gms-recompute-error">${escapeHtml(task.error || task.message || '计算失败')}</span>`;
            }
          }
        }
      } catch (e) {
        this.clearForceComputePoll();
        this.setForceComputeRunning(false);
        const area = document.getElementById('forceComputeProgress');
        if (area) {
          area.innerHTML = `<span class="gms-recompute-error">查询进度失败: ${escapeHtml(e.message || String(e))}</span>`;
        }
      }
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
            ? '所选日期范围内暂无预计算信号（可点「强制重新计算」入库，或改「现算回溯」）'
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
