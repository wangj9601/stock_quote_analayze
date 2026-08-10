/** 技术工具 · 形态识别 */
const PatternTool = {
  selectedBoards: [],
  _catalog: { industry: [], concept: [] },
  _labels: {},

  TYPE_LABELS: {
    double_bottom: '双底',
    double_top: '双顶',
    head_shoulders_top: '头肩顶',
    head_shoulders_bottom: '头肩底',
    ascending_triangle: '上升三角',
    descending_triangle: '下降三角',
    symmetrical_triangle: '对称三角',
    rising_wedge: '上升楔形',
    falling_wedge: '下降楔形',
    bull_flag: '上升旗形',
    bear_flag: '下降旗形',
  },

  init() {
    const mode = document.getElementById('patternModeSelect');
    const scope = document.getElementById('patternScanScope');
    const runBtn = document.getElementById('patternRunBtn');
    const codeInput = document.getElementById('patternStockCode');
    const watch = document.getElementById('patternWatchlist');
    const pickBtn = document.getElementById('patternBoardPickBtn');

    if (mode) mode.addEventListener('change', () => this.syncModeUi());
    if (scope) scope.addEventListener('change', () => this.syncModeUi());
    if (runBtn) runBtn.addEventListener('click', () => this.run());
    if (codeInput) {
      codeInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.run();
        }
      });
    }
    if (watch) {
      watch.addEventListener('change', () => {
        const v = (watch.value || '').trim();
        if (v && codeInput) codeInput.value = v;
      });
    }
    if (pickBtn) pickBtn.addEventListener('click', () => this.openBoardPicker());
    this.syncModeUi();
  },

  syncModeUi() {
    const mode = (document.getElementById('patternModeSelect') || {}).value || 'single';
    const scope = (document.getElementById('patternScanScope') || {}).value || 'market';
    const single = document.getElementById('patternSingleFields');
    const watch = document.getElementById('patternWatchField');
    const scan = document.getElementById('patternScanFields');
    const boardWrap = document.getElementById('patternBoardPickWrap');
    if (single) single.style.display = mode === 'single' ? '' : 'none';
    if (watch) watch.style.display = mode === 'single' ? '' : 'none';
    // contents：扫描子字段并入主行 flex，避免整列竖排
    if (scan) scan.style.display = mode === 'scan' ? 'contents' : 'none';
    if (boardWrap) boardWrap.style.display = mode === 'scan' && scope !== 'market' ? '' : 'none';
  },

  async loadWatchlist() {
    const select = document.getElementById('patternWatchlist');
    if (!select || select.dataset.loaded === '1') return;
    if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) return;
    try {
      const resp = await authFetch(`${API_BASE_URL}/api/watchlist`);
      if (!resp.ok) return;
      const payload = await resp.json();
      const items = payload.data || payload.items || payload || [];
      const list = Array.isArray(items) ? items : [];
      list.forEach((it) => {
        const code = it.stock_code || it.code || '';
        const name = it.stock_name || it.name || '';
        if (!code) return;
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = `${code} ${name}`.trim();
        select.appendChild(opt);
      });
      select.dataset.loaded = '1';
    } catch (e) {
      console.warn(e);
    }
  },

  selectedTypes() {
    const box = document.getElementById('patternTypeChecks');
    if (!box) return [];
    return Array.from(box.querySelectorAll('input[type=checkbox]:checked')).map((el) => el.value);
  },

  async ensureCatalog() {
    if (this._catalog.industry.length || this._catalog.concept.length) return;
    const fetchFn = window.authFetch || fetch;
    const [ind, con] = await Promise.all([
      fetchFn(`${API_BASE_URL}/api/market/industry_board/catalog?board_code_source=tonghuashun`),
      fetchFn(`${API_BASE_URL}/api/market/concept_board/list?board_code_source=tonghuashun`),
    ]);
    const indJson = ind.ok ? await ind.json() : {};
    const conJson = con.ok ? await con.json() : {};
    this._catalog.industry = indJson.data || indJson.items || indJson || [];
    if (!Array.isArray(this._catalog.industry)) this._catalog.industry = [];
    this._catalog.concept = conJson.data || conJson.items || conJson || [];
    if (!Array.isArray(this._catalog.concept)) this._catalog.concept = [];
  },

  openBoardPicker() {
    const scope = (document.getElementById('patternScanScope') || {}).value || 'industry';
    const kind = scope === 'concept' ? 'concept' : 'industry';
    this.ensureCatalog().then(() => {
      const list = kind === 'concept' ? this._catalog.concept : this._catalog.industry;
      const names = list
        .slice(0, 40)
        .map((b) => `${b.board_code || b.code} ${b.board_name || b.name || ''}`)
        .join('\n');
      const hint = `输入板块代码，多个用逗号分隔。\n示例（同花顺）：\n${names || '（目录为空）'}`;
      const cur = this.selectedBoards.join(',');
      const raw = window.prompt(hint, cur);
      if (raw == null) return;
      this.selectedBoards = String(raw)
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const sum = document.getElementById('patternBoardSummary');
      if (sum) {
        sum.textContent = this.selectedBoards.length
          ? `已选 ${this.selectedBoards.length} 个：${this.selectedBoards.slice(0, 5).join(',')}${this.selectedBoards.length > 5 ? '…' : ''}`
          : '未选';
      }
    });
  },

  typeLabel(t) {
    return this.TYPE_LABELS[t] || t || '--';
  },

  keyLevelsText(levels) {
    if (!levels || typeof levels !== 'object') return '--';
    const parts = [];
    ['neckline', 'upper', 'lower', 'head', 'l1', 'l2', 'h1', 'h2', 'last_close'].forEach((k) => {
      if (levels[k] != null && levels[k] !== '') parts.push(`${k}:${levels[k]}`);
    });
    return parts.slice(0, 4).join(' ') || '--';
  },

  /** 形成日：优先 formed_at；否则确认日；否则枢轴最晚日 */
  formedAtText(r) {
    if (!r || typeof r !== 'object') return '--';
    const norm = (v) => String(v == null ? '' : v).slice(0, 10);
    let d = norm(r.formed_at);
    if (d) return d;
    d = norm(r.confirm_date);
    if (d) return d;
    const dates = [];
    (r.key_dates || []).forEach((kd) => {
      const x = norm(kd && kd.date);
      if (x) dates.push(x);
    });
    (r.pivots || []).forEach((p) => {
      const x = norm(p && p.date);
      if (x) dates.push(x);
    });
    return dates.length ? dates.sort().slice(-1)[0] : '--';
  },

  formedAtTitle(r) {
    const parts = [];
    (r.key_dates || r.pivots || []).forEach((p) => {
      const role = (p && (p.role || '')) || '';
      const d = String((p && p.date) || '').slice(0, 10);
      if (d) parts.push(role ? `${role}:${d}` : d);
    });
    if (r.confirm_date) parts.push(`确认:${String(r.confirm_date).slice(0, 10)}`);
    return parts.join(' · ') || this.formedAtText(r);
  },

  renderItems(items, metaHtml) {
    const body = document.getElementById('patternResultBody');
    const wrap = document.getElementById('patternResultWrap');
    const empty = document.getElementById('patternEmpty');
    const meta = document.getElementById('patternMeta');
    if (meta) {
      meta.hidden = !metaHtml;
      meta.innerHTML = metaHtml || '';
    }
    if (!items || !items.length) {
      if (wrap) wrap.hidden = true;
      if (empty) {
        empty.hidden = false;
        empty.textContent = '未识别到选定形态（或扫描无命中）。';
      }
      return;
    }
    if (empty) empty.hidden = true;
    if (wrap) wrap.hidden = false;
    if (!body) return;
    body.innerHTML = items
      .map((r) => {
        const code = r.code || '';
        const name = r.name || '';
        const href = code ? `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}` : '#';
        const codeHtml = code
          ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${this.esc(code)}</a>`
          : '--';
        const formed = this.formedAtText(r);
        return `<tr>
          <td>${codeHtml}</td>
          <td>${this.esc(name || '--')}</td>
          <td>${this.esc(this.typeLabel(r.pattern_type))}</td>
          <td>${this.esc(r.status === 'confirmed' ? '已确认' : '形成中')}</td>
          <td title="${this.esc(this.formedAtTitle(r))}">${this.esc(formed)}</td>
          <td>${r.confidence != null ? Number(r.confidence).toFixed(2) : '--'}</td>
          <td>${this.esc(this.keyLevelsText(r.key_levels))}</td>
          <td title="${this.esc(r.reason || '')}">${this.esc((r.reason || '').slice(0, 48))}</td>
        </tr>`;
      })
      .join('');
  },

  esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },

  async run() {
    if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) return;
    const mode = (document.getElementById('patternModeSelect') || {}).value || 'single';
    const types = this.selectedTypes();
    if (!types.length) {
      CommonUtils.showToast('请至少选择一种形态类型', 'warning');
      return;
    }
    const asof = ((document.getElementById('patternAsof') || {}).value || '').trim();
    const btn = document.getElementById('patternRunBtn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '识别中…';
    }
    try {
      if (mode === 'single') {
        const code = ((document.getElementById('patternStockCode') || {}).value || '').trim();
        if (!code) {
          CommonUtils.showToast('请输入股票代码或名称', 'warning');
          return;
        }
        const q = new URLSearchParams();
        q.set('types', types.join(','));
        if (asof) q.set('asof', asof);
        const resp = await authFetch(
          `${API_BASE_URL}/api/analysis/patterns/${encodeURIComponent(code)}?${q.toString()}`
        );
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          const msg = (data.detail && (data.detail.message || data.detail)) || data.message || '识别失败';
          throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        }
        const items = (data.items || []).map((h) => ({
          ...h,
          code: data.code || code,
          name: data.name || '',
        }));
        this.renderItems(
          items,
          `个股 ${this.esc(data.code)} ${this.esc(data.name || '')} · 基准日 ${this.esc(data.asof || '--')} · 命中 ${items.length}`
        );
      } else {
        const scope = (document.getElementById('patternScanScope') || {}).value || 'market';
        const limit = parseInt((document.getElementById('patternScanLimit') || {}).value || '80', 10) || 80;
        if (scope !== 'market' && !this.selectedBoards.length) {
          CommonUtils.showToast('请先选择板块代码', 'warning');
          return;
        }
        const body = {
          scope,
          board_codes: scope === 'market' ? [] : this.selectedBoards,
          board_kind: scope === 'concept' ? 'concept' : 'industry',
          types,
          asof: asof || null,
          limit: Math.max(10, Math.min(200, limit)),
        };
        const resp = await authFetch(`${API_BASE_URL}/api/analysis/patterns/scan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          throw new Error(data.detail || data.message || '扫描失败');
        }
        const flags = [];
        if (data.truncated) flags.push('已截断');
        if (data.timed_out) flags.push('已超时');
        this.renderItems(
          data.items || [],
          `扫描 ${this.esc(data.scope)} · 已扫 ${data.scanned || 0}/${data.pool_size || 0} · 命中 ${data.hit_count || 0} · 基准日 ${this.esc(data.asof || '--')}${flags.length ? ' · ' + flags.join('/') : ''}`
        );
      }
    } catch (e) {
      console.error(e);
      if (window.CommonUtils) CommonUtils.showToast(e.message || String(e), 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '识别 / 扫描';
      }
    }
  },
};

document.addEventListener('DOMContentLoaded', () => {
  try {
    PatternTool.init();
  } catch (e) {
    console.warn(e);
  }
});
