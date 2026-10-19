/**
 * CSB 通道突破 — 信号历史页（对齐 SBBR trace）
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

  function setRegion(el, shown, display) {
    if (!el) return;
    if (shown) {
      el.hidden = false;
      if (display) el.style.display = display;
    } else {
      el.hidden = true;
      el.style.display = '';
    }
  }

  function yn(v, yesClass) {
    if (v === true) return `<span class="${yesClass || 'buy-yes'}">是</span>`;
    if (v === false) return '否';
    return '--';
  }

  function signalTypeLabel(t) {
    const s = String(t || '').trim();
    const map = {
      CSB_SETUP: 'SETUP',
      CSB_PROBE: 'PROBE',
      CSB_BREAKOUT: 'BREAKOUT',
      CSB_LPS: 'LPS',
      CSB_FALSE_BREAK: '假突破',
      CSB_STOP: '止损',
      CSB_TRAIL: '跟踪',
      CSB_DISTRIBUTE: '派发',
    };
    return map[s] || s || '--';
  }

  class StockCsbTracePage {
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

      this.showName(this.name);
      const codeEl = document.getElementById('stockCode');
      if (codeEl && this.code) codeEl.value = this.code;
      this.setDefaultDates();
      const startEl = document.getElementById('startDate');
      const endEl = document.getElementById('endDate');
      if (startEl && params.get('start')) startEl.value = params.get('start');
      if (endEl && params.get('end')) endEl.value = params.get('end');

      document.getElementById('csbTraceForm')?.addEventListener('submit', (e) => {
        e.preventDefault();
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
          const recomputeBtn = e.target.closest('.csb-recompute-stock');
          if (recomputeBtn) {
            e.preventDefault();
            const scope = recomputeBtn.getAttribute('data-scope') || 'all';
            const day = (recomputeBtn.getAttribute('data-date') || '').trim();
            if (scope === 'day') {
              this.forceComputeRange(day, day, `只重算 ${day} 这一天的 CSB 信号，其它日期保留。是否继续？`);
            } else {
              this.forceComputeRange('', '', '将重新计算该股全部历史 CSB 信号并覆盖预计算。可能需要几分钟。是否继续？');
            }
            return;
          }
          const detailBtn = e.target.closest('.csb-score-detail-toggle');
          if (!detailBtn) return;
          e.preventDefault();
          const rowIndex = detailBtn.getAttribute('data-row');
          const detailRow = tbody.querySelector(`tr.csb-score-detail-row[data-detail-for="${rowIndex}"]`);
          if (!detailRow) return;
          const show = detailRow.style.display === 'none' || !detailRow.style.display;
          detailRow.style.display = show ? 'table-row' : 'none';
          detailBtn.classList.toggle('active', show);
        });
      }

      this.updatePagination();
      if (this.code) this.fetchData();
    }

    showName(name) {
      const text = String(name || '').trim();
      this.name = text;
      const display = document.getElementById('stockDisplay');
      if (display) display.textContent = text || '--';
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
      if (btn) {
        btn.disabled = this.forceComputeRunning;
        btn.textContent = this.forceComputeRunning ? '正在重新计算…' : '强制重新计算';
      }
      if (searchBtn) searchBtn.disabled = this.forceComputeRunning;
      if (sel) sel.disabled = this.forceComputeRunning;
      ['startDate', 'endDate', 'entryOnly'].forEach((id) => {
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
      setRegion(area, true, 'block');
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
        <div>CSB 信号重算: <strong>${escapeHtml(statusLabel)}</strong>${msg ? ` · ${escapeHtml(String(msg))}${total}` : ''}</div>
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
      const startDate = (document.getElementById('startDate')?.value || '').trim();
      const endDate = (document.getElementById('endDate')?.value || '').trim();
      const span = startDate || endDate ? `${startDate || '最早'}～${endDate || '最新'}` : '全部历史';
      if (!confirm(`将按「${label}」重新计算该股 ${span} 的 CSB 信号并写入预计算。区间外的记录保留。是否继续？`)) {
        return;
      }
      void this.startForceComputeTask();
    }

    forceComputeRange(startDate, endDate, message) {
      if (this.forceComputeRunning) return;
      if (!this.code) {
        alert('请先选择股票');
        return;
      }
      if (message && !confirm(message)) return;
      void this.startForceComputeTask({ start: startDate || '', end: endDate || '' });
    }

    async startForceComputeTask(range) {
      this.clearForceComputePoll();
      this.setForceComputeRunning(true);
      const area = document.getElementById('forceComputeProgress');
      if (area) {
        setRegion(area, true, 'block');
        area.innerHTML = '<div>正在提交重算任务…</div><div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:5%"></div></div>';
      }
      setRegion(document.getElementById('loadingMsg'), false);

      const startDate = range
        ? String(range.start || '').trim()
        : (document.getElementById('startDate')?.value || '').trim();
      const endDate = range
        ? String(range.end || '').trim()
        : (document.getElementById('endDate')?.value || '').trim();

      try {
        const resp = await fetch(`${apiBase}/api/stock/csb/recompute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: this.code,
            config_id: this.configId,
            start_date: startDate || null,
            end_date: endDate || null,
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
        if (json.message) {
          const meta = document.getElementById('metaMsg');
          if (meta) meta.textContent = json.message;
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
          setRegion(area, true, 'block');
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
      const url = `${apiBase}/api/stock/csb/recompute/${encodeURIComponent(this.forceComputeTaskId)}`;
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
        const rowClass = r.entry_signal ? 'urt-row-score-high' : (r.setup_ok ? 'urt-row-score-mid' : '');
        let detailHtml = '<div class="gms-score-detail-inner">明细组件未加载</div>';
        if (window.CsbScoreDetail && typeof window.CsbScoreDetail.buildHtml === 'function') {
          detailHtml = window.CsbScoreDetail.buildHtml(r);
        }
        return `<tr class="${rowClass}" data-csb-row="${index}">
          <td>${escapeHtml(r.date || r.trade_date || r.signal_date || '--')}</td>
          <td>${escapeHtml(signalTypeLabel(r.signal_type))}</td>
          <td>${yn(r.setup_ok)}</td>
          <td>${yn(r.entry_signal, 'buy-yes')}</td>
          <td>${fmt(r.score, 1)}</td>
          <td>${fmt(r.close)}</td>
          <td>${fmt(r.channel_lower)}</td>
          <td>${fmt(r.channel_upper)}</td>
          <td>${r.squeeze_days != null ? String(r.squeeze_days) : '--'}</td>
          <td>${r.touch_count != null ? String(r.touch_count) : '--'}</td>
          <td>${fmt(r.entry_low)}</td>
          <td>${escapeHtml(r.row_source === 'recompute' ? '补算' : '预计算')}</td>
          <td><button type="button" class="gms-op-btn csb-score-detail-toggle" data-row="${index}" title="展开/收起信号计算明细">明细</button></td>
        </tr>
        <tr class="gms-score-detail-row csb-score-detail-row" data-detail-for="${index}" style="display:none;">
          <td colspan="13" class="gms-score-detail-cell">${detailHtml}</td>
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
      const typed = (document.getElementById('stockCode')?.value || '').trim();
      if (typed && typed !== this.code) {
        this.code = typed;
        this.showName('');
      } else if (typed) {
        this.code = typed;
      }
      const card = document.querySelector('.gms-trace-card');
      if (!this.code) {
        empty.textContent = '请填写股票代码';
        setRegion(empty, true);
        setRegion(loading, false);
        return;
      }
      if (card) card.setAttribute('aria-busy', 'true');
      setRegion(loading, true);
      setRegion(empty, false);
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
          setRegion(empty, true);
          return;
        }
        if (startDate > endDate) {
          empty.textContent = '开始日期不能晚于结束日期';
          setRegion(empty, true);
          return;
        }
        const entryOnly = !!document.getElementById('entryOnly')?.checked;
        const q = new URLSearchParams({
          code: this.code,
          start: startDate,
          end: endDate,
        });
        if (this.configId) q.set('config_id', String(this.configId));
        if (entryOnly) q.set('entry_only', 'true');
        q.set('fill_missing', 'true');

        const res = await fetch(`${apiBase}/api/stock/csb/signal-history?${q}`);
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
        if (json.config_warning) {
          const url = new URL(window.location.href);
          if (url.searchParams.has('config_id')) {
            url.searchParams.delete('config_id');
            window.history.replaceState(null, '', url);
          }
        }
        const rowName = (json.data || []).map((r) => r && r.name).find((n) => String(n || '').trim());
        this.showName(json.name || rowName || '');

        this.allData = json.data || [];
        if (meta) {
          const bits = [
            `来源 ${json.source_label || '预计算'}`,
            json.trade_days != null ? `交易日 ${json.trade_days}` : '',
            json.cached_days != null ? `已有预计算 ${json.cached_days} 日` : '',
            json.recomputed_days != null ? `补算 ${json.recomputed_days} 日` : '',
            `信号 ${json.total != null ? json.total : this.allData.length} 条`,
          ].filter(Boolean);
          if (json.config_warning) bits.unshift(json.config_warning);
          meta.textContent = bits.join(' · ');
        }

        if (!this.allData.length) {
          empty.textContent = '所选日期范围内没有符合条件的信号（已读预计算，缺口已补算）';
          setRegion(empty, true);
          this.updatePagination();
          return;
        }
        this.totalPages = Math.max(1, Math.ceil(this.allData.length / this.pageSize));
        this.currentPage = 1;
        this.renderTable();
        this.updatePagination();
      } catch (e) {
        empty.textContent = '加载失败: ' + (e.message || e);
        setRegion(empty, true);
        this.allData = [];
        this.updatePagination();
      } finally {
        setRegion(loading, false);
        document.querySelector('.gms-trace-card')?.setAttribute('aria-busy', 'false');
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.csbTracePage = new StockCsbTracePage();
  });
})();
