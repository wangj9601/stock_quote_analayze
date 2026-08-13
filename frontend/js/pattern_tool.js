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

  PIVOT_ROLE_LABELS: {
    LS: '左肩',
    head: '头',
    RS: '右肩',
    L1: 'L1',
    L2: 'L2',
    H1: 'H1',
    H2: 'H2',
    neck: '颈线',
    high: '高点',
    low: '低点',
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

  /** 个股分析默认全选形态大类（与技术工具默认勾选一致） */
  DEFAULT_TYPES: ['double_extremes', 'head_shoulders', 'triangle', 'wedge_flag'],

  /** 与 levels 一致：adjust=qfq|none；UI 默认勾选前复权 */
  selectedAdjust() {
    const el = document.getElementById('patternAdjustQfq');
    return el && el.checked ? 'qfq' : 'none';
  },

  adjustLabel(adjust) {
    return adjust === 'qfq' ? '前复权 OHLC' : '不复权 OHLC';
  },

  /**
   * 个股形态识别（与技术工具「个股识别」同口径）。
   * @returns {{ items: array, code: string, name: string, asof: string, price_adjust: string, raw: object }}
   */
  async fetchSingle(code, options = {}) {
    const types = (options.types && options.types.length)
      ? options.types
      : this.DEFAULT_TYPES;
    const adjust = options.adjust === 'none' ? 'none' : (options.adjust || 'qfq');
    const q = new URLSearchParams();
    q.set('types', types.join(','));
    q.set('adjust', adjust);
    if (options.asof) q.set('asof', options.asof);
    const resp = await authFetch(
      `${API_BASE_URL}/api/analysis/patterns/${encodeURIComponent(code)}?${q.toString()}`
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = (data.detail && (data.detail.message || data.detail)) || data.message || '识别失败';
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    const priceAdjust = data.price_adjust === 'qfq' ? 'qfq' : 'none';
    const items = (data.items || []).map((h) => ({
      ...h,
      code: data.code || code,
      name: data.name || '',
    }));
    return {
      items,
      code: data.code || code,
      name: data.name || '',
      asof: data.asof || '',
      price_adjust: priceAdjust,
      raw: data,
    };
  },

  /**
   * 将个股形态结果渲染到任意容器（个股分析嵌入用）。
   * @param {HTMLElement} container
   * @param {array} items
   * @param {string} metaHtml
   * @param {string} priceAdjust
   * @param {{asof?:string, confluenceZones?:object}|undefined} options
   */
  renderEmbedded(container, items, metaHtml, priceAdjust, options) {
    if (!container) return;
    const adjust = priceAdjust === 'qfq' ? 'qfq' : 'none';
    const visible = this._activeHits(items);
    const metaBlock = metaHtml
      ? `<div class="pattern-meta">${metaHtml}</div>`
      : '';
    if (!visible.length) {
      const emptyExpert = this._buildExpertHtml([], 'single', adjust, options);
      container.innerHTML = `${metaBlock}
        <div class="kde-levels-empty">未识别到选定形态。</div>
        ${emptyExpert}`;
      return;
    }
    const rows = visible
      .map((r) => {
        const code = r.code || '';
        const name = r.name || '';
        const href = code
          ? `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`
          : '#';
        const codeHtml = code
          ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${this.esc(code)}</a>`
          : '--';
        const formed = this.formedAtText(r);
        const reasonFull = this.reasonText(r);
        return `<tr>
          <td>${codeHtml}</td>
          <td>${this.esc(name || '--')}</td>
          <td>${this.esc(this.typeLabel(r.pattern_type))}</td>
          <td>${this.esc(this.statusLabel(r.status))}</td>
          <td title="${this.esc(this.formedAtTitle(r))}">${this.esc(formed)}</td>
          <td>${r.confidence != null ? Number(r.confidence).toFixed(2) : '--'}</td>
          <td class="pattern-col-levels">${this.esc(this.keyLevelsText(r.key_levels))}</td>
          <td class="pattern-col-reason" title="${this.esc(reasonFull)}">${this.esc(reasonFull)}</td>
        </tr>`;
      })
      .join('');
    const expert = this._buildExpertHtml(visible, 'single', adjust, options);
    container.innerHTML = `${metaBlock}
      <div class="pattern-result-wrap">
        <table class="pattern-result-table">
          <thead>
            <tr>
              <th>代码</th><th>名称</th><th>形态</th><th>状态</th>
              <th>形成日</th><th>置信度</th><th>关键价</th><th>说明</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${expert}`;
  },

  /** 专家解读 HTML（供原面板与嵌入共用） */
  _buildExpertHtml(items, mode, priceAdjust, options) {
    if (!items || !items.length) return '';
    const adjustTag = `<span class="kde-levels-adjust-tag ${
      priceAdjust === 'qfq' ? 'is-qfq' : 'is-raw'
    }">${this.esc(this.adjustLabel(priceAdjust))}</span>`;
    if (mode === 'scan') {
      const n = items.length;
      const top = this._rankHits(items, options).slice(0, 3);
      const brief = top
        .map((h) => {
          const code = h.code || '';
          const label = this.typeLabel(h.pattern_type);
          const st = this.statusLabel(h.status);
          const conf = h.confidence != null ? Number(h.confidence).toFixed(2) : '--';
          return `${code} ${label}（${st} ${conf}）`;
        })
        .join('；');
      return `<div class="pattern-expert-analysis">
        <div class="pattern-expert-title">形态解读</div>
        <div class="pattern-expert-body">
          <p>本页命中 ${n} 条${brief ? `，靠前示例：${this.esc(brief)}` : ''}。扫描模式不展开长文解读，请切换至「个股识别」获取完整专家分析。 ${adjustTag}</p>
          <p class="pattern-expert-risk">风险提示：以上为日线规则模板摘要，不构成投资建议。</p>
        </div>
      </div>`;
    }
    const analysis = this.buildExpertAnalysis(items, options);
    // 与 PDF 共用 buildExpertAnalysis 字段：短/中线 + structureHtml（不再拆关键位置/交易点位）
    const structureHtml = analysis.structureHtml || analysis.tradeLevelsHtml || '';
    return `<div class="pattern-expert-analysis">
      <div class="pattern-expert-title">形态解读</div>
      <div class="pattern-expert-body">
        <p><span class="pattern-expert-label">价格口径：</span>${adjustTag}</p>
        <p><span class="pattern-expert-label">短期走势：</span>${this.esc(analysis.shortTerm)}</p>
        <p><span class="pattern-expert-label">中线格局：</span>${this.esc(analysis.mediumTerm)}</p>
        ${structureHtml}
        <p class="pattern-expert-risk">${this.esc(analysis.risk)}</p>
      </div>
    </div>`;
  },

  /**
   * 将 buildExpertAnalysis 输出拼成纯文本（PDF / 调试共用同一字段口径）。
   */
  formatExpertPlainText(analysis) {
    const a = analysis || {};
    const parts = [];
    if (a.primaryLabel) {
      const confPart =
        a.primaryConf && a.primaryConf !== '--'
          ? `（置信度 ${a.primaryConf}）`
          : '';
      parts.push(`主形态：${a.primaryLabel}${confPart}`);
    }
    if (a.shortTerm) parts.push(`短线：${a.shortTerm}`);
    if (a.mediumTerm) parts.push(`中线：${a.mediumTerm}`);
    if (a.structureText) parts.push(a.structureText);
    else if (a.tradeLevelsText) parts.push(a.tradeLevelsText);
    if (a.risk) parts.push(a.risk);
    return parts.filter(Boolean).join('\n');
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
      if (levels[k] != null && levels[k] !== '') {
        parts.push(`${k}:${this._fmtPx(levels[k])}`);
      }
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

  /**
   * 说明列：优先用 pivots 把价位与日期配对；
   * 颈线（非枢轴均价）、斜率/收敛等无日参数从 key_levels 或原 reason 补全。
   * 格式：左肩=44.97(2026-03-12)
   */
  reasonText(r) {
    if (!r || typeof r !== 'object') return '';
    const reason = String(r.reason || '');
    const pivots = Array.isArray(r.pivots) ? r.pivots : [];
    const priced = pivots.filter((p) => p && p.price != null && p.price !== '');
    if (!priced.length) return reason;

    const label = this.typeLabel(r.pattern_type);
    const simplified = /简化规则/.test(reason) ? '（简化规则）' : '';
    const parts = priced.map((p) => {
      const name = this.PIVOT_ROLE_LABELS[p.role] || p.role || '';
      const d = String(p.date || '').slice(0, 10);
      const px = this._fmtPx(p.price);
      return d ? `${name}=${px}(${d})` : `${name}=${px}`;
    });

    const levels = r.key_levels || {};
    const extras = [];
    const shrink = reason.match(/收敛约[^\s]+/);
    if (shrink) extras.push(shrink[0]);
    if (levels.neckline != null && levels.neckline !== '' && !priced.some((p) => p.role === 'neck')) {
      extras.push(`颈线≈${this._fmtPx(levels.neckline)}`);
    }
    const slopeUnit =
      levels.slope_unit ||
      (/(元\/K线索引|元\/交易日|元\/枢轴)/.test(reason) ? '' : '元/K线索引(约交易日)');
    const slopeSuffix = slopeUnit ? String(slopeUnit) : '';
    if (levels.upper_slope != null && levels.upper_slope !== '') {
      extras.push(`上沿斜率=${levels.upper_slope}${slopeSuffix}`);
    } else {
      const m = reason.match(/上沿斜率=[^\s]+/);
      if (m) extras.push(m[0]);
    }
    if (levels.lower_slope != null && levels.lower_slope !== '') {
      extras.push(`下沿斜率=${levels.lower_slope}${slopeSuffix}`);
    } else {
      const m = reason.match(/下沿斜率=[^\s]+/);
      if (m) extras.push(m[0]);
    }
    return `${label}${simplified} ${parts.join(' ')}${extras.length ? ` ${extras.join(' ')}` : ''}`.trim();
  },

  statusLabel(st) {
    if (st === 'confirmed') return '已确认';
    if (st === 'invalidated') return '失效';
    if (st === 'archived') return '已归档';
    return '形成中';
  },

  /** 列表/专家解读默认忽略失效项；归档项列表可见但不进主形态排序（见 _rankHits） */
  _activeHits(items) {
    return (items || []).filter((h) => h && h.status !== 'invalidated');
  },

  renderItems(items, metaHtml, mode, priceAdjust) {
    const body = document.getElementById('patternResultBody');
    const wrap = document.getElementById('patternResultWrap');
    const empty = document.getElementById('patternEmpty');
    const meta = document.getElementById('patternMeta');
    const adjust = priceAdjust === 'qfq' ? 'qfq' : 'none';
    const visible = this._activeHits(items);
    if (meta) {
      meta.hidden = !metaHtml;
      meta.innerHTML = metaHtml || '';
    }
    if (!visible.length) {
      if (wrap) wrap.hidden = true;
      if (empty) {
        empty.hidden = false;
        empty.textContent = '未识别到选定形态（或扫描无命中）。';
      }
      this.renderExpertAnalysis([], mode || 'single', adjust);
      return;
    }
    if (empty) empty.hidden = true;
    if (wrap) wrap.hidden = false;
    if (!body) return;
    body.innerHTML = visible
      .map((r) => {
        const code = r.code || '';
        const name = r.name || '';
        const href = code ? `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}` : '#';
        const codeHtml = code
          ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${this.esc(code)}</a>`
          : '--';
        const formed = this.formedAtText(r);
        const reasonFull = this.reasonText(r);
        return `<tr>
          <td>${codeHtml}</td>
          <td>${this.esc(name || '--')}</td>
          <td>${this.esc(this.typeLabel(r.pattern_type))}</td>
          <td>${this.esc(this.statusLabel(r.status))}</td>
          <td title="${this.esc(this.formedAtTitle(r))}">${this.esc(formed)}</td>
          <td>${r.confidence != null ? Number(r.confidence).toFixed(2) : '--'}</td>
          <td class="pattern-col-levels">${this.esc(this.keyLevelsText(r.key_levels))}</td>
          <td class="pattern-col-reason" title="${this.esc(reasonFull)}">${this.esc(reasonFull)}</td>
        </tr>`;
      })
      .join('');
    this.renderExpertAnalysis(visible, mode || 'single', adjust);
  },

  /** 空结果隐藏；个股完整解读；扫描简要提示 */
  renderExpertAnalysis(items, mode, priceAdjust) {
    const box = document.getElementById('patternExpertAnalysis');
    const body = document.getElementById('patternExpertBody');
    if (!box || !body) return;
    if (!items || !items.length) {
      box.hidden = true;
      body.innerHTML = '';
      return;
    }
    const asof = ((document.getElementById('patternAsof') || {}).value || '').trim();
    const html = this._buildExpertHtml(items, mode || 'single', priceAdjust, { asof });
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const inner = tmp.querySelector('.pattern-expert-body');
    box.hidden = false;
    body.innerHTML = inner ? inner.innerHTML : html;
  },

  BEARISH_REVERSAL: {
    double_top: true,
    head_shoulders_top: true,
  },
  BULLISH_REVERSAL: {
    double_bottom: true,
    head_shoulders_bottom: true,
  },
  CONSOLIDATION: {
    ascending_triangle: true,
    descending_triangle: true,
    symmetrical_triangle: true,
    rising_wedge: true,
    falling_wedge: true,
    bull_flag: true,
    bear_flag: true,
  },

  /** 主形态 FinalScore：confidence × W_status × exp(-λ·Δt) */
  RANK_W_CONFIRMED: 1.2,
  RANK_W_FORMING: 0.6,
  RANK_TIME_DECAY_LAMBDA: 0.012,
  /** 形成中反转超过该日历日龄不进主形态（真空兜底） */
  PRIMARY_FORMING_MAX_AGE_DAYS: 60,

  _num(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  },

  _hitClose(h) {
    const lv = (h && h.key_levels) || {};
    return this._num(lv.last_close != null ? lv.last_close : h.last_close);
  },

  _hitNeck(h) {
    const lv = (h && h.key_levels) || {};
    return this._num(lv.neckline);
  },

  _hitBounds(h) {
    const lv = (h && h.key_levels) || {};
    return { upper: this._num(lv.upper), lower: this._num(lv.lower) };
  },

  /** 收盘相对关键位：below / near / above（near 默认 ±4%） */
  _relToLevel(close, level, nearPct) {
    if (close == null || level == null || level === 0) return null;
    const pct = ((close - level) / Math.abs(level)) * 100;
    const band = nearPct != null ? nearPct : 4;
    if (Math.abs(pct) <= band) return { side: 'near', pct };
    return { side: pct < 0 ? 'below' : 'above', pct };
  },

  _parseDateMs(s) {
    const d = String(s || '').slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return null;
    const t = Date.parse(`${d}T00:00:00`);
    return Number.isFinite(t) ? t : null;
  },

  _daysBetween(fromS, toS) {
    const a = this._parseDateMs(fromS);
    const b = this._parseDateMs(toS);
    if (a == null || b == null) return null;
    return Math.max(0, Math.round((b - a) / 86400000));
  },

  _inferAsof(items, opts) {
    const o = opts || {};
    if (o.asof) return String(o.asof).slice(0, 10);
    let best = '';
    (items || []).forEach((h) => {
      const fa = String((h && (h.formed_at || h.confirm_date)) || '').slice(0, 10);
      if (fa > best) best = fa;
    });
    return best || '';
  },

  _statusWeight(st) {
    if (st === 'confirmed') return this.RANK_W_CONFIRMED;
    if (st === 'forming') return this.RANK_W_FORMING;
    return 0;
  },

  /** FinalScore ≈ confidence × W_status × exp(-λ·Δt) */
  _finalScore(h, asof) {
    if (!h) return 0;
    const conf = Number(h.confidence) || 0;
    const w = this._statusWeight(h.status);
    const formed = String(h.formed_at || h.confirm_date || '').slice(0, 10);
    const dt = this._daysBetween(formed, asof);
    const decay =
      dt == null ? 1 : Math.exp(-this.RANK_TIME_DECAY_LAMBDA * Math.max(0, dt));
    return conf * w * decay;
  },

  _rankHits(items, opts) {
    const asof = this._inferAsof(items, opts);
    const list = (items || []).filter(
      (h) => h && h.status !== 'invalidated' && h.status !== 'archived'
    );
    const boost = (h) => {
      if (!h || h.status !== 'confirmed' || !this.CONSOLIDATION[h.pattern_type]) return 0;
      const hb = this._biasOf(h.pattern_type);
      const hd = String(h.formed_at || h.confirm_date || '').slice(0, 10);
      const hasOlderOppReversal = list.some((o) => {
        if (!o || o === h || o.status !== 'confirmed') return false;
        const isRev =
          this.BEARISH_REVERSAL[o.pattern_type] || this.BULLISH_REVERSAL[o.pattern_type];
        if (!isRev) return false;
        if (!this._biasConflicts(hb, this._biasOf(o.pattern_type))) return false;
        const od = String(o.formed_at || o.confirm_date || '').slice(0, 10);
        return !od || !hd || hd >= od;
      });
      return hasOlderOppReversal ? 1 : 0;
    };
    return list.slice().sort((a, b) => {
      const sa = this._finalScore(a, asof);
      const sb = this._finalScore(b, asof);
      const sd = sb - sa;
      if (Math.abs(sd) > 1e-9) return sd;
      const bd = boost(b) - boost(a);
      if (bd) return bd;
      const rank = (st) => (st === 'confirmed' ? 2 : st === 'forming' ? 1 : 0);
      const d = rank(b.status) - rank(a.status);
      if (d) return d;
      return String(b.formed_at || '').localeCompare(String(a.formed_at || ''));
    });
  },

  /** 过期/失败 forming 反转不进主形态 */
  _isViablePrimaryCandidate(h, asof) {
    if (!h) return false;
    if (h.status === 'confirmed') return true;
    if (h.status !== 'forming') return false;
    const isRev =
      this.BEARISH_REVERSAL[h.pattern_type] || this.BULLISH_REVERSAL[h.pattern_type];
    if (!isRev) return true;
    const formed = String(h.formed_at || h.confirm_date || '').slice(0, 10);
    const dt = this._daysBetween(formed, asof);
    if (dt != null && dt > this.PRIMARY_FORMING_MAX_AGE_DAYS) return false;
    const reason = String(h.reason || '');
    if (/失败破位|已归档|生命周期已结束/.test(reason)) return false;
    return true;
  },

  _pickPrimary(ranked, asof) {
    const list = ranked || [];
    const confirmed = list.filter((h) => h && h.status === 'confirmed');
    if (confirmed.length) return confirmed[0];
    const viable = list.filter((h) => this._isViablePrimaryCandidate(h, asof));
    return viable[0] || null;
  },

  /** 最近归档反向/测幅兑现形态：仅作背景一句，不抢主形态 */
  _archivedBackgroundText(items) {
    const archived = (items || [])
      .filter((h) => h && h.status === 'archived')
      .slice()
      .sort((a, b) =>
        String(b.formed_at || b.confirm_date || '').localeCompare(
          String(a.formed_at || a.confirm_date || '')
        )
      );
    if (!archived.length) return '';
    const h = archived[0];
    const lab = this.typeLabel(h.pattern_type);
    const reason = String(h.reason || '');
    const why = /测幅目标/.test(reason)
      ? '测幅已兑现'
      : /失败破位/.test(reason)
        ? '失败破位'
        : '周期已走完';
    return `背景：近期「${lab}」${why}并已归档，仅作兑现参考，不作为当前主导形态。`;
  },

  /**
   * 近端高强度共振带一句（轻量）；无数据则空串。
   * @param {object|null} confluence confluence_zones 结构
   * @param {number|null} close
   */
  _nearConfluenceHint(confluence, close) {
    if (!confluence || typeof confluence !== 'object') return '';
    const zones = [];
    (confluence.supports || []).forEach((z) => {
      if (z && z.center != null) zones.push({ ...z, side: 'support' });
    });
    (confluence.resistances || []).forEach((z) => {
      if (z && z.center != null) zones.push({ ...z, side: 'resistance' });
    });
    const nearest =
      confluence.nearest_support_zone || confluence.nearest_resistance_zone || null;
    if (nearest && nearest.center != null) {
      zones.push({
        ...nearest,
        side: confluence.nearest_support_zone === nearest ? 'support' : 'resistance',
      });
    }
    if (!zones.length) return '';
    const scored = zones
      .map((z) => {
        const c = this._num(z.center);
        const str = this._num(z.strength) || 0;
        const dist =
          close != null && c != null ? Math.abs((close - c) / Math.abs(c || 1)) : 1;
        return { z, c, str, dist, score: str / (1 + dist * 40) };
      })
      .filter((x) => x.c != null && x.str > 0)
      .sort((a, b) => b.score - a.score);
    if (!scored.length) return '';
    const top = scored[0];
    const role = top.z.side === 'support' ? '支撑' : '压力';
    return `近端高强度共振带约在 ${this._fmtPx(top.c)}（${role}，强度 ${Number(top.str).toFixed(1)}），可作短线参考。`;
  },

  _biasOf(type) {
    if (this.BEARISH_REVERSAL[type]) return 'bear';
    if (this.BULLISH_REVERSAL[type]) return 'bull';
    if (type === 'rising_wedge' || type === 'bear_flag' || type === 'descending_triangle') return 'bearish_bias';
    if (type === 'falling_wedge' || type === 'bull_flag' || type === 'ascending_triangle') return 'bullish_bias';
    return 'neutral';
  },

  /** bias 是否冲突：已确认偏多巩固 vs 已确认偏空反转等 */
  _biasConflicts(a, b) {
    const bullish = new Set(['bull', 'bullish_bias']);
    const bearish = new Set(['bear', 'bearish_bias']);
    return (bullish.has(a) && bearish.has(b)) || (bearish.has(a) && bullish.has(b));
  },

  /** 已确认巩固形态：上破 / 下破 / 未判明 */
  _consolBreakDir(h) {
    const t = h && h.pattern_type;
    const b = this._hitBounds(h);
    const c = this._hitClose(h);
    const up = b.upper;
    const lo = b.lower;
    if (c != null && up != null && c > up * 1.005) return 'up';
    if (c != null && lo != null && c < lo * 0.995) return 'down';
    if (t === 'falling_wedge' || t === 'bull_flag' || t === 'ascending_triangle') return 'up';
    if (t === 'rising_wedge' || t === 'bear_flag' || t === 'descending_triangle') return 'down';
    return 'out';
  },

  /** 已确认巩固形态：按收盘相对上下沿判定上破/下破文案 */
  _confirmedConsolBreakText(h) {
    const t = h.pattern_type;
    const lab = this.typeLabel(t);
    const conf = h.confidence != null ? Number(h.confidence).toFixed(2) : '--';
    const b = this._hitBounds(h);
    const up = b.upper;
    const lo = b.lower;
    const dir = this._consolBreakDir(h);
    if (dir === 'up') {
      return `已确认${lab}上破（置信度 ${conf}${
        up != null ? `，上沿 ${this._fmtPx(up)}` : ''
      }），短线偏多，突破方向已定。`;
    }
    if (dir === 'down') {
      return `已确认${lab}下破（置信度 ${conf}${
        lo != null ? `，下沿 ${this._fmtPx(lo)}` : ''
      }），短线偏空，突破方向已定。`;
    }
    return `已确认${lab}（置信度 ${conf}），短线围绕其关键价位波动。`;
  },

  /**
   * 巩固类简化测幅（前端展示用；后端入库为 P2 TODO）。
   * H = upper - lower；上破 target ≈ upper + H；下破 target ≈ lower - H。
   * @returns {{dir:string,upper:number,lower:number,height:number,target:number,label:string}|null}
   */
  _consolMeasuredMove(h) {
    if (!h || h.status !== 'confirmed' || !this.CONSOLIDATION[h.pattern_type]) return null;
    const b = this._hitBounds(h);
    if (b.upper == null || b.lower == null) return null;
    const height = b.upper - b.lower;
    if (!(height > 0)) return null;
    const dir = this._consolBreakDir(h);
    if (dir === 'up') {
      return {
        dir: 'up',
        upper: b.upper,
        lower: b.lower,
        height,
        target: b.upper + height,
        label: this.typeLabel(h.pattern_type),
      };
    }
    if (dir === 'down') {
      return {
        dir: 'down',
        upper: b.upper,
        lower: b.lower,
        height,
        target: b.lower - height,
        label: this.typeLabel(h.pattern_type),
      };
    }
    return null;
  },

  /** 主导已确认巩固突破上下文（供空档文案 / 测幅） */
  _leadConsolBreakContext(items, opts) {
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof }).filter(
      (h) => h.status === 'confirmed' || this._isViablePrimaryCandidate(h, asof)
    );
    const lead =
      ranked.find((h) => h.status === 'confirmed' && this.CONSOLIDATION[h.pattern_type]) || null;
    const dir = lead ? this._consolBreakDir(lead) : null;
    const measured = lead ? this._consolMeasuredMove(lead) : null;
    const hasFormingConsol = ranked.some(
      (h) => h.status === 'forming' && this.CONSOLIDATION[h.pattern_type]
    );
    return { lead, dir, measured, hasFormingConsol };
  },

  _measuredMoveBulletText(m) {
    if (!m) return '';
    if (m.dir === 'up') {
      return `简化测幅目标 ${this._fmtPx(m.target)} 附近（按边界高度：上沿 ${this._fmtPx(
        m.upper
      )} + H≈${this._fmtPx(m.height)}）`;
    }
    return `简化测幅目标 ${this._fmtPx(m.target)} 附近（按边界高度：下沿 ${this._fmtPx(
      m.lower
    )} − H≈${this._fmtPx(m.height)}）`;
  },

  _fmtPx(n) {
    if (n == null) return '--';
    const x = Number(n);
    if (!Number.isFinite(x)) return '--';
    return x.toFixed(2);
  },

  /** 置信度偏低或形成中 → 标注「观察中」 */
  _isObserving(h) {
    if (!h) return true;
    if (h.status !== 'confirmed') return true;
    const c = Number(h.confidence);
    return Number.isFinite(c) && c < 0.55;
  },

  /**
   * 从单条 hit 提炼可操作价位（颈线/峰谷/上下沿等）。
   * @returns {{price:number,name:string,role:string,source:string,observing:boolean,confirmed:boolean,conf:number}[]}
   */
  _levelsFromHit(h) {
    if (!h || typeof h !== 'object') return [];
    const t = h.pattern_type;
    const lv = h.key_levels || {};
    const src = this.typeLabel(t);
    const observing = this._isObserving(h);
    const confirmed = h.status === 'confirmed';
    const conf = Number(h.confidence) || 0;
    const out = [];
    const add = (price, name, role) => {
      const p = this._num(price);
      if (p == null) return;
      out.push({ price: p, name, role, source: src, observing, confirmed, conf });
    };

    if (t === 'double_top') {
      add(lv.neckline, '颈线', '观察失守');
      const h1 = this._num(lv.h1);
      const h2 = this._num(lv.h2);
      if (h1 != null && h2 != null) {
        const mid = (h1 + h2) / 2;
        if (mid > 0 && Math.abs(h1 - h2) / mid <= 0.02) {
          add(mid, '双峰高点', '上方压力');
        } else {
          add(h1, 'H1', '上方压力');
          add(h2, 'H2', '上方压力');
        }
      } else {
        add(h1 != null ? h1 : h2, '双峰高点', '上方压力');
      }
    } else if (t === 'double_bottom') {
      add(lv.neckline, '颈线', '观察站稳');
      const l1 = this._num(lv.l1);
      const l2 = this._num(lv.l2);
      if (l1 != null && l2 != null) {
        const mid = (l1 + l2) / 2;
        if (mid > 0 && Math.abs(l1 - l2) / mid <= 0.02) {
          add(mid, '双谷低点', '下方支撑');
        } else {
          add(l1, 'L1', '下方支撑');
          add(l2, 'L2', '下方支撑');
        }
      } else {
        add(l1 != null ? l1 : l2, '双谷低点', '下方支撑');
      }
    } else if (t === 'head_shoulders_top') {
      add(lv.neckline, '颈线', '观察失守');
      add(lv.head, '头部高点', '上方压力');
    } else if (t === 'head_shoulders_bottom') {
      add(lv.neckline, '颈线', '观察站稳');
      add(lv.head, '头部低点', '下方支撑');
    } else if (this.CONSOLIDATION[t]) {
      let upperRole = '突破参考';
      let lowerRole = '突破参考';
      if (confirmed) {
        const dir = this._consolBreakDir(h);
        if (dir === 'up') {
          upperRole = '突破后转支撑';
          lowerRole = '下方支撑';
        } else if (dir === 'down') {
          lowerRole = '突破后转阻力';
          upperRole = '上方压力';
        }
      }
      add(lv.upper, '上沿', upperRole);
      add(lv.lower, '下沿', lowerRole);
    } else {
      // 兜底：有颈线/上下沿则带出
      add(lv.neckline, '颈线', '关键参考');
      add(lv.upper, '上沿', '突破参考');
      add(lv.lower, '下沿', '突破参考');
    }
    return out;
  },

  /**
   * 近价合并（相对 0.8% 内视为同一档）。
   * 同价多形态保留各来源语义标签（如「双底:颈线 | 下降楔形:上沿」），
   * 不再用 prefer 权重把展示名硬并成单一「颈线」；role 仍取最高优先级。
   */
  _mergeNearLevels(raw) {
    const namePrefer = {
      颈线: 3,
      双峰高点: 2,
      双谷低点: 2,
      头部高点: 2,
      头部低点: 2,
      上沿: 1,
      下沿: 1,
    };
    const rolePrefer = {
      突破后转支撑: 6,
      突破后转阻力: 6,
      观察站稳: 5,
      观察失守: 5,
      下方支撑: 4,
      上方压力: 4,
      突破参考: 2,
      关键参考: 1,
    };
    const tagKey = (lv) => `${lv.source || ''}:${lv.name || ''}`;
    const pushTag = (hit, lv) => {
      if (!hit.tags) hit.tags = [];
      const k = tagKey(lv);
      if (hit.tags.some((t) => `${t.source}:${t.name}` === k)) return;
      hit.tags.push({ source: lv.source, name: lv.name });
    };
    const syncDisplayName = (hit) => {
      if (hit.tags && hit.tags.length) {
        hit.name = hit.tags.map((t) => `${t.source}:${t.name}`).join(' | ');
      }
    };
    const bumpPrimaryName = (hit, lvName) => {
      if (!hit.primaryName) {
        hit.primaryName = lvName;
        return;
      }
      if ((namePrefer[lvName] || 0) > (namePrefer[hit.primaryName] || 0)) {
        hit.primaryName = lvName;
      }
    };
    const bumpRole = (hit, role) => {
      if ((rolePrefer[role] || 0) > (rolePrefer[hit.role] || 0)) {
        hit.role = role;
      }
    };

    const merged = [];
    (raw || [])
      .slice()
      .sort((a, b) => a.price - b.price || b.conf - a.conf)
      .forEach((lv) => {
        const hit = merged.find((m) => {
          const base = Math.abs(m.price) || 1;
          return Math.abs(m.price - lv.price) / base <= 0.008;
        });
        if (!hit) {
          merged.push({
            price: lv.price,
            name: `${lv.source}:${lv.name}`,
            primaryName: lv.name,
            role: lv.role,
            tags: [{ source: lv.source, name: lv.name }],
            sources: [lv.source],
            observing: lv.observing,
            confirmed: !!lv.confirmed,
            conf: lv.conf,
          });
          return;
        }
        pushTag(hit, lv);
        bumpPrimaryName(hit, lv.name);
        if (lv.conf > hit.conf) {
          hit.price = lv.price;
          hit.conf = lv.conf;
        }
        if (hit.observing && !lv.observing) {
          hit.observing = false;
        }
        bumpRole(hit, lv.role);
        if (!hit.sources.includes(lv.source)) hit.sources.push(lv.source);
        hit.observing = hit.observing && lv.observing;
        hit.confirmed = hit.confirmed || !!lv.confirmed;
        syncDisplayName(hit);
      });
    return merged;
  },

  /** 合并档的价位名 token（用于打分/语义，不含形态前缀） */
  _levelNameTokens(m) {
    if (!m) return [];
    if (m.tags && m.tags.length) return m.tags.map((t) => t.name).filter(Boolean);
    if (m.primaryName) return [m.primaryName];
    const n = String(m.name || '');
    if (n.includes('|') || n.includes(':')) {
      return n
        .split('|')
        .map((s) => {
          const parts = s.trim().split(':');
          return (parts.length > 1 ? parts[parts.length - 1] : parts[0] || '').trim();
        })
        .filter(Boolean);
    }
    return n ? [n] : [];
  },

  _collectMergedLevels(items, opts) {
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof });
    const raw = [];
    ranked.forEach((h) => {
      // 过期 forming 反转不进入结构防守（避免旧颈线霸榜）
      if (h.status === 'forming' && !this._isViablePrimaryCandidate(h, asof)) return;
      this._levelsFromHit(h).forEach((lv) => raw.push(lv));
    });
    return this._mergeNearLevels(raw);
  },

  /** 交易点位「意义」分：优先颈线翻支撑、峰谷/头、通道上下沿（多标签取最高分） */
  _tradeLevelScore(m, side) {
    const tokens = this._levelNameTokens(m);
    const scoreOne = (n) => {
      if (n === '颈线') return 50;
      if (n === '双谷低点' || n === '双峰高点' || n === '头部低点' || n === '头部高点') return 42;
      if (n === 'L1' || n === 'L2' || n === 'H1' || n === 'H2') return 38;
      if (side === 'support' && n === '下沿') return 36;
      if (side === 'support' && n === '上沿') return 34; // 突破后翻支撑
      if (side === 'resistance' && n === '上沿') return 36;
      if (side === 'resistance' && n === '下沿') return 28;
      return 20;
    };
    let s = tokens.length ? Math.max(...tokens.map(scoreOne)) : 20;
    if (m.confirmed) s += 12;
    if (!m.observing) s += 6;
    return s;
  },

  /**
   * 相对现价的交易角色简述（形态名+角色）。
   * 已确认且原上沿/颈线落在现价下方 →「突破后翻支撑」。
   */
  _tradeLevelExplain(m, side) {
    const tokens = this._levelNameTokens(m);
    const has = (...names) => tokens.some((t) => names.indexOf(t) >= 0);
    const display =
      m.tags && m.tags.length
        ? m.tags.map((t) => `${t.source}:${t.name}`).join(' | ')
        : `${(m.sources && m.sources.length ? m.sources.join('/') : '') || '形态'}${
            m.primaryName || m.name || '关键位'
          }`;
    let meaning = '';
    if (side === 'support') {
      if (m.confirmed && has('颈线', '上沿')) meaning = '突破后翻支撑';
      else if (has('颈线')) meaning = '颈线支撑（观察中）';
      else if (has('双谷低点', 'L1', 'L2', '头部低点')) meaning = '形态低点支撑';
      else if (has('下沿')) meaning = '通道/形态下沿支撑';
      else if (has('上沿')) meaning = '上沿翻支撑（待确认）';
      else meaning = '下方支撑';
    } else {
      if (has('颈线')) meaning = m.confirmed ? '颈线阻力' : '颈线阻力（观察中）';
      else if (has('双峰高点', 'H1', 'H2', '头部高点')) meaning = '形态高点阻力';
      else if (has('上沿')) meaning = '通道/形态上沿阻力';
      else if (has('下沿')) meaning = m.confirmed ? '下沿翻阻力' : '下沿阻力（观察中）';
      else meaning = '上方阻力';
    }
    return `${display}，${meaning}`;
  },

  /**
   * 从合并关键位中按现价分支撑/阻力，取最有意义的 1～2 档。
   * @returns {{supports:object[], resistances:object[]}}
   */
  _pickTradeLevels(merged, close) {
    if (close == null || !merged || !merged.length) {
      return { supports: [], resistances: [] };
    }
    const eps = Math.abs(close) * 0.001; // 贴近现价忽略
    const below = merged.filter((m) => m.price < close - eps);
    const above = merged.filter((m) => m.price > close + eps);

    const pick = (arr, side) => {
      const scored = arr
        .slice()
        .sort((a, b) => {
          const ds = this._tradeLevelScore(b, side) - this._tradeLevelScore(a, side);
          if (ds) return ds;
          // 同分：更靠近现价优先
          return Math.abs(a.price - close) - Math.abs(b.price - close);
        })
        .slice(0, 2);
      // 展示顺序：支撑由高到低，阻力由低到高
      return side === 'support'
        ? scored.sort((a, b) => b.price - a.price)
        : scored.sort((a, b) => a.price - b.price);
    };

    return {
      supports: pick(below, 'support'),
      resistances: pick(above, 'resistance'),
    };
  },

  /** 单侧区间文案：两档则高–低 / 低–高；一档则该价 */
  _tradeZoneText(levels, side) {
    if (!levels || !levels.length) return '';
    if (levels.length === 1) return this._fmtPx(levels[0].price);
    const a = levels[0].price;
    const b = levels[1].price;
    if (side === 'support') {
      const hi = Math.max(a, b);
      const lo = Math.min(a, b);
      return `${this._fmtPx(hi)} – ${this._fmtPx(lo)}`;
    }
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    return `${this._fmtPx(lo)} – ${this._fmtPx(hi)}`;
  },

  /**
   * 空档占位：按已确认突破方向分支，禁止上破后仍写「等待形态边界突破」。
   * 无形态边界可等（真空）时改为共振位口径；形成中巩固仍可「等待突破」。
   */
  _emptyStructureSideText(side, ctx) {
    const dir = ctx && ctx.dir;
    if (side === 'resistance') {
      if (dir === 'up') {
        return '形态边界已上破；上方暂无形态内阻力档，近端关注简化测幅目标';
      }
      if (dir === 'down') {
        return '形态边界已下破；上方形态内阻力以原边界档为准';
      }
      // 形成中巩固或主导巩固未判明突破：保留等待突破口径
      if (ctx && (ctx.hasFormingConsol || ctx.lead)) {
        return '暂无明显阻力，等待形态边界突破后再定';
      }
      return '暂无活跃形态边界，暂无明显阻力共振位';
    }
    if (dir === 'down') {
      return '形态边界已下破；下方暂无形态内支撑档，近端关注简化测幅目标';
    }
    if (dir === 'up') {
      return '形态边界已上破；下方防守见上沿翻支撑等形态内档';
    }
    if (ctx && (ctx.hasFormingConsol || ctx.lead)) {
      return '暂无明显支撑，等待形态边界突破后再定';
    }
    return '暂无活跃形态边界，暂无明显支撑共振位';
  },

  /**
   * 从多维共振带取 1～2 档支撑/阻力（真空结构兜底；不编造假价）。
   * 优先 nearest_*，再按强度/近价综合排序。
   * @returns {{supports:object[], resistances:object[]}}
   */
  _pickConfluenceTradeLevels(confluence, close) {
    if (!confluence || typeof confluence !== 'object') {
      return { supports: [], resistances: [] };
    }
    const toLevel = (z, side) => {
      if (!z || typeof z !== 'object') return null;
      const price = this._num(z.center);
      if (price == null) return null;
      return {
        price,
        low: this._num(z.low),
        high: this._num(z.high),
        strength: this._num(z.strength) || 0,
        sources: Array.isArray(z.sources) ? z.sources : [],
        fromConfluence: true,
        side,
      };
    };
    const score = (lv) => {
      const dist =
        close != null && lv.price != null
          ? Math.abs(close - lv.price) / Math.abs(lv.price || 1)
          : 0;
      return (lv.strength || 0) / (1 + dist * 40);
    };
    const mergeSide = (list, nearest, side) => {
      const out = [];
      const push = (lv) => {
        if (!lv) return;
        if (out.some((x) => Math.abs(x.price - lv.price) < 1e-6)) return;
        out.push(lv);
      };
      (list || []).forEach((z) => push(toLevel(z, side)));
      if (nearest) push(toLevel(nearest, side));
      return out
        .sort((a, b) => {
          const ds = score(b) - score(a);
          if (Math.abs(ds) > 1e-9) return ds;
          if (close == null) return 0;
          return Math.abs(a.price - close) - Math.abs(b.price - close);
        })
        .slice(0, 2);
    };
    const supports = mergeSide(
      confluence.supports,
      confluence.nearest_support_zone,
      'support'
    ).sort((a, b) => b.price - a.price);
    const resistances = mergeSide(
      confluence.resistances,
      confluence.nearest_resistance_zone,
      'resistance'
    ).sort((a, b) => a.price - b.price);
    return { supports, resistances };
  },

  _confluenceLevelExplain(m, side) {
    const role = side === 'support' ? '支撑' : '阻力';
    const str =
      m && m.strength != null && Number.isFinite(Number(m.strength))
        ? Number(m.strength).toFixed(1)
        : '--';
    return `多维共振带${role}，强度 ${str}`;
  },

  _hasConfluenceZones(confluence) {
    if (!confluence || typeof confluence !== 'object') return false;
    if ((confluence.supports || []).some((z) => z && z.center != null)) return true;
    if ((confluence.resistances || []).some((z) => z && z.center != null)) return true;
    if (confluence.nearest_support_zone && confluence.nearest_support_zone.center != null)
      return true;
    if (
      confluence.nearest_resistance_zone &&
      confluence.nearest_resistance_zone.center != null
    )
      return true;
    return false;
  },

  /**
   * 结构防守与目标（合并原「关键位置参考」+「后续交易点位参考」）。
   * 分层：防守/支撑 → 目标/近端形态阻力（含巩固简化测幅）。
   * 真空（无主形态档）时可用 opts.confluenceZones 共振带兜底；有活跃形态档时不硬盖。
   * @returns {{html:string,text:string}}
   */
  buildStructureLevelsReference(items, opts) {
    const options = opts || {};
    const asof = this._inferAsof(items, options);
    const ranked = this._rankHits(items, { asof });
    const primary = this._pickPrimary(ranked, asof);
    let close = null;
    for (let i = 0; i < ranked.length; i++) {
      close = this._hitClose(ranked[i]);
      if (close != null) break;
    }
    // 真空时 ranked 可能只剩过期 forming；再从全量 items（含归档）取收盘
    if (close == null) {
      for (let i = 0; i < (items || []).length; i++) {
        close = this._hitClose(items[i]);
        if (close != null) break;
      }
    }
    const merged = this._collectMergedLevels(items, { asof });
    let { supports, resistances } = this._pickTradeLevels(merged, close);
    const ctx = this._leadConsolBreakContext(items, { asof });
    const measured = ctx.measured;
    // 有活跃形态档用形态；真空（无主形态，或两侧皆空且无巩固突破）才共振兜底
    const useConfluenceFallback =
      !primary ||
      (!supports.length && !resistances.length && !measured && !ctx.dir);
    let supportFromConf = false;
    let resistFromConf = false;
    if (useConfluenceFallback && this._hasConfluenceZones(options.confluenceZones)) {
      const confLv = this._pickConfluenceTradeLevels(options.confluenceZones, close);
      if (!supports.length && confLv.supports.length) {
        supports = confLv.supports;
        supportFromConf = true;
      }
      if (!resistances.length && confLv.resistances.length) {
        resistances = confLv.resistances;
        resistFromConf = true;
      }
    }
    const supportZone = this._tradeZoneText(supports, 'support');
    const resistZone = this._tradeZoneText(resistances, 'resistance');

    const supportLines = [];
    const supportLis = [];
    if (!supports.length) {
      if (measured && measured.dir === 'down') {
        const note = '形态边界已下破；下方暂无形态内支撑档';
        supportLines.push(note);
        supportLis.push(note);
      } else {
        const emptySup = this._emptyStructureSideText('support', ctx);
        supportLines.push(emptySup);
        supportLis.push(null);
      }
    } else {
      supports.forEach((m, idx) => {
        const label = idx === 0 ? '直接支撑' : '强底支撑';
        const explain = m.fromConfluence
          ? this._confluenceLevelExplain(m, 'support')
          : this._tradeLevelExplain(m, 'support');
        const line = `${label}：${this._fmtPx(m.price)} 附近（${explain}）`;
        supportLines.push(line);
        supportLis.push(line);
      });
    }
    if (measured && measured.dir === 'down') {
      const line = this._measuredMoveBulletText(measured);
      supportLines.push(line);
      supportLis.push(line);
    }

    const resistLines = [];
    const resistLis = [];
    if (!resistances.length) {
      if (measured && measured.dir === 'up') {
        const note = '形态边界已上破；上方暂无形态内阻力档';
        resistLines.push(note);
        resistLis.push(note);
      } else {
        const emptyRes = this._emptyStructureSideText('resistance', ctx);
        resistLines.push(emptyRes);
        resistLis.push(null);
      }
    } else {
      resistances.forEach((m, idx) => {
        const label = idx === 0 ? '第一阻力' : '第二阻力';
        const explain = m.fromConfluence
          ? this._confluenceLevelExplain(m, 'resistance')
          : this._tradeLevelExplain(m, 'resistance');
        const line = `${label}：${this._fmtPx(m.price)} 附近（${explain}）`;
        resistLines.push(line);
        resistLis.push(line);
      });
    }
    if (measured && measured.dir === 'up') {
      const line = this._measuredMoveBulletText(measured);
      resistLines.push(line);
      resistLis.push(line);
    }

    const supportHead =
      supports.length > 0
        ? `防守/支撑：${supportZone}`
        : measured && measured.dir === 'down'
          ? '防守/支撑与下方目标：'
          : '防守/支撑：';
    const resistHead =
      resistances.length > 0
        ? resistFromConf
          ? `目标/近端共振阻力：${resistZone}`
          : `目标/近端形态阻力：${resistZone}`
        : supportFromConf && !resistances.length
          ? '目标/近端共振阻力：'
          : '目标/近端形态阻力：';
    const supportUl =
      supportLis.filter((x) => x != null).length > 0
        ? `<ul>${supportLis
            .filter((x) => x != null)
            .map((line) => `<li>${this.esc(line)}</li>`)
            .join('')}</ul>`
        : '';
    const resistUl =
      resistLis.filter((x) => x != null).length > 0
        ? `<ul>${resistLis
            .filter((x) => x != null)
            .map((line) => `<li>${this.esc(line)}</li>`)
            .join('')}</ul>`
        : '';

    const supportEmptyOnly =
      supportLis.every((x) => x == null) && supportLines.length
        ? `<p>${this.esc(supportLines[0])}</p>`
        : '';
    const resistEmptyOnly =
      resistLis.every((x) => x == null) && resistLines.length
        ? `<p>${this.esc(resistLines[0])}</p>`
        : '';

    const html = `<div class="pattern-expert-trade-levels">
      <p><span class="pattern-expert-label">结构防守与目标：</span></p>
      <p>${this.esc(supportHead)}</p>
      ${supportUl || supportEmptyOnly}
      <p>${this.esc(resistHead)}</p>
      ${resistUl || resistEmptyOnly}
    </div>`;

    const textParts = ['结构防守与目标：', supportHead];
    supportLines.forEach((ln) => textParts.push(`· ${ln}`));
    textParts.push(resistHead);
    resistLines.forEach((ln) => textParts.push(`· ${ln}`));
    const text = textParts.filter(Boolean).join('\n');

    return { html, text };
  },

  /** @deprecated 兼容旧调用：返回结构块 HTML */
  buildTradeLevelsReference(items) {
    return this.buildStructureLevelsReference(items).html;
  },

  /**
   * 汇总多形态关键位：近价去重、按价格升序、标注来源与观察中。
   * @returns {string}
   */
  buildKeyLevelsReference(items, opts) {
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof });
    const merged = this._collectMergedLevels(items, { asof });
    if (!merged.length) return '';

    merged.sort((a, b) => a.price - b.price);

    const parts = merged.map((m) => {
      // name 已含「形态:价位名」并列标签，不再重复拼接 sources
      const obs = m.observing ? ' · 观察中' : '';
      return `${this._fmtPx(m.price)} ${m.name}（${m.role}）${obs}`;
    });

    let close = null;
    for (let i = 0; i < ranked.length; i++) {
      close = this._hitClose(ranked[i]);
      if (close != null) break;
    }
    let relTxt = '';
    if (close != null && merged.length) {
      const nearest = merged
        .slice()
        .sort((a, b) => Math.abs(a.price - close) - Math.abs(b.price - close))[0];
      const pct = ((close - nearest.price) / Math.abs(nearest.price || 1)) * 100;
      const side =
        Math.abs(pct) <= 4
          ? '贴近'
          : pct > 0
            ? '上方约'
            : '下方约';
      const pctAbs = Math.abs(pct).toFixed(1);
      const nearestLabel = nearest.name || nearest.primaryName || '关键位';
      relTxt =
        Math.abs(pct) <= 4
          ? `现价 ${this._fmtPx(close)} 贴近「${nearestLabel}」${this._fmtPx(nearest.price)}。`
          : `现价 ${this._fmtPx(close)} 相对「${nearestLabel}」${this._fmtPx(nearest.price)} ${side}${pctAbs}%。`;
    }

    return `${parts.join('；')}${relTxt ? `。${relTxt}` : '。'}`;
  },

  /**
   * 前端规则引擎：根据 hits 结构化字段拼装专家口吻分析。
   * 必须直接读取 status：已确认巩固突破时禁止再写「等待边界有效突破」；
   * 已确认偏多巩固 vs 已确认偏空反转写入冲突提示。
   * @param {array} items
   * @param {{asof?:string, confluenceZones?:object}|undefined} options
   */
  buildExpertAnalysis(items, options) {
    const opts = options || {};
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof });
    const confirmed = ranked.filter((h) => h.status === 'confirmed');
    const forming = ranked.filter((h) => h.status === 'forming');
    const primary = this._pickPrimary(ranked, asof);
    const bgArchived = this._archivedBackgroundText(items);
    const closeForHint =
      (primary && this._hitClose(primary)) ||
      (ranked[0] && this._hitClose(ranked[0])) ||
      null;
    const confHint = this._nearConfluenceHint(opts.confluenceZones, closeForHint);

    if (!primary) {
      const hasConf = this._hasConfluenceZones(opts.confluenceZones);
      const shortBits = ['暂无主导形态。'];
      // P1：真空时短线轻改为结构整理期；有共振则结构块承载价位，避免与 confHint 堆砌
      if (hasConf) shortBits.push('结构整理期，跟踪多维量化共振带。');
      if (bgArchived) shortBits.push(bgArchived);
      if (!hasConf) {
        if (confHint) shortBits.push(confHint);
        else shortBits.push('短线建议结合量价与近端支撑压力谨慎观察。');
      }
      let mediumTerm = hasConf
        ? '暂无高置信活跃主导形态，结构整理期，跟踪多维量化共振带。'
        : '暂无高置信活跃主导形态，中线尚不明朗。';
      if (bgArchived) mediumTerm += bgArchived;
      if (!hasConf && confHint) mediumTerm += confHint;
      else if (!hasConf && forming.length) {
        const names = forming
          .slice(0, 3)
          .map(
            (h) =>
              `${this.typeLabel(h.pattern_type)}(${
                h.confidence != null ? Number(h.confidence).toFixed(2) : '--'
              })`
          )
          .join('、');
        mediumTerm += `形成中信号（${names}）偏旧或置信不足，不强制选作主形态。`;
      }
      const structure = this.buildStructureLevelsReference(items, {
        asof,
        confluenceZones: opts.confluenceZones,
      });
      return {
        shortTerm: shortBits.join(''),
        mediumTerm,
        keyLevelsRef: this.buildKeyLevelsReference(items, { asof }),
        structureHtml: structure.html,
        structureText: structure.text,
        tradeLevelsHtml: structure.html,
        tradeLevelsText: structure.text,
        risk:
          '风险提示：以上解读由日线形态规则自动生成，非投资建议；形态识别存在滞后与误报，请结合基本面、量能与自身风险承受能力综合判断。',
        primaryLabel: '暂无主导形态',
        primaryConf: '--',
        closeTxt: closeForHint != null ? this._fmtPx(closeForHint) : null,
        neckTxt: null,
      };
    }

    const primaryLabel = this.typeLabel(primary.pattern_type);
    const primaryConf =
      primary.confidence != null ? Number(primary.confidence).toFixed(2) : '--';
    const close = this._hitClose(primary);
    const neck = this._hitNeck(primary);
    const closeTxt = close != null ? this._fmtPx(close) : null;
    const neckTxt = neck != null ? this._fmtPx(neck) : null;

    let shortTerm = '';
    let mediumTerm = '';

    const confirmedConsol = confirmed.filter((h) => this.CONSOLIDATION[h.pattern_type]);
    const hasConfirmedConsolBreak = confirmedConsol.length > 0;

    // —— 短期：形成中 + 最近确认与现价相对关键位 ——
    const shortBits = [];
    if (confirmed.length && primary.status === 'confirmed') {
      const top = primary;
      const t = top.pattern_type;
      const c = this._hitClose(top);
      const n = this._hitNeck(top);
      const rel = this._relToLevel(c, n);
      const lab = this.typeLabel(t);
      if (this.BEARISH_REVERSAL[t]) {
        if (rel && rel.side === 'below') {
          shortBits.push(
            `已确认${lab}且收盘落在颈线（${this._fmtPx(n)}）下方，短线偏空，警惕沿跌破后的惯性下行。`
          );
        } else if (rel && rel.side === 'near') {
          shortBits.push(
            `已确认${lab}，收盘（${this._fmtPx(c)}）贴近颈线（${this._fmtPx(n)}），短线宜观察颈线是否失守；失守则空头动能增强。`
          );
        } else if (rel && rel.side === 'above') {
          shortBits.push(
            `已确认${lab}，收盘（${this._fmtPx(c)}）仍在颈线（${this._fmtPx(n)}）上方附近，短线偏防守观察：若再度跌破颈线则确认偏空，若放量站稳则警惕假破/反抽。`
          );
        } else {
          shortBits.push(`已确认${lab}，短线关注颈线得失与量能配合。`);
        }
      } else if (this.BULLISH_REVERSAL[t]) {
        if (rel && rel.side === 'above') {
          shortBits.push(
            `已确认${lab}且收盘站上颈线（${this._fmtPx(n)}），短线偏多，可关注回踩颈线是否企稳。`
          );
        } else if (rel && rel.side === 'near') {
          shortBits.push(
            `已确认${lab}，收盘贴近颈线（${this._fmtPx(n)}），短线观察能否有效突破并站稳颈线。`
          );
        } else if (rel && rel.side === 'below') {
          shortBits.push(
            `已确认${lab}，但收盘仍在颈线（${this._fmtPx(n)}）下方，短线偏谨慎，需等待突破确认。`
          );
        } else {
          shortBits.push(`已确认${lab}，短线关注颈线突破与回踩。`);
        }
      } else if (this.CONSOLIDATION[t]) {
        shortBits.push(this._confirmedConsolBreakText(top));
      } else {
        shortBits.push(`主导形态为已确认${lab}（置信度 ${primaryConf}），短线围绕其关键价位波动。`);
      }

      // 另有已确认巩固但非主导时补一句方向
      if (confirmedConsol.length && !this.CONSOLIDATION[t]) {
        shortBits.push(this._confirmedConsolBreakText(confirmedConsol[0]));
      }
    }

    const formingConsol = forming.filter((h) => this.CONSOLIDATION[h.pattern_type]);
    // 已有已确认巩固突破时，禁止再写「方向尚未定，宜等待边界有效突破」
    if (formingConsol.length && !hasConfirmedConsolBreak) {
      const names = formingConsol
        .slice(0, 3)
        .map((h) => this.typeLabel(h.pattern_type))
        .join('、');
      const sample = formingConsol[0];
      const b = this._hitBounds(sample);
      const boundHint =
        b.upper != null || b.lower != null
          ? `（关注上沿${b.upper != null ? this._fmtPx(b.upper) : '--'}/下沿${b.lower != null ? this._fmtPx(b.lower) : '--'}）`
          : '';
      shortBits.push(
        `另有形成中的${names}${boundHint}，方向尚未定，宜等待边界有效突破后再定多空。`
      );
    } else if (formingConsol.length && hasConfirmedConsolBreak) {
      const names = formingConsol
        .slice(0, 2)
        .map((h) => this.typeLabel(h.pattern_type))
        .join('、');
      shortBits.push(`另有形成中的${names}，仅作次要观察，不改写已确认突破方向。`);
    } else if (!confirmed.length && forming.length && primary.status === 'forming') {
      const f0 = primary;
      shortBits.push(
        `当前以形成中的${this.typeLabel(f0.pattern_type)}为主，形态尚未确认，短线宜等待结构完成或关键位突破。`
      );
    }

    if (bgArchived) shortBits.push(bgArchived);
    if (primary.status === 'forming' && confHint) shortBits.push(confHint);

    if (!shortBits.length) {
      shortBits.push('命中形态信息有限，短线建议结合量价与关键支撑压力谨慎观察。');
    }
    shortTerm = shortBits.join('');

    // —— 中线：压短边界/现价堆砌（点位改由「结构防守与目标」承载）——
    if (confirmed.length && primary.status === 'confirmed') {
      const lead = primary;
      const leadBias = this._biasOf(lead.pattern_type);
      const leadLab = this.typeLabel(lead.pattern_type);
      const leadConf =
        lead.confidence != null ? Number(lead.confidence).toFixed(2) : '--';
      const formed = this.formedAtText(lead);
      const formedTxt = formed && formed !== '--' ? `形成/确认参考日 ${formed}。` : '';

      let stance = '中性震荡';
      if (leadBias === 'bear') stance = '中线偏空';
      else if (leadBias === 'bull') stance = '中线偏多';
      else if (leadBias === 'bearish_bias') stance = '中线略偏防守';
      else if (leadBias === 'bullish_bias') stance = '中线略偏积极';

      mediumTerm = `以高置信已确认「${leadLab}」（置信度 ${leadConf}）为主导，${stance}。${formedTxt}`;

      // 冲突：反向已确认（含偏多巩固 vs 偏空反转）
      const opp = confirmed.find((h) => {
        if (h === lead) return false;
        return this._biasConflicts(leadBias, this._biasOf(h.pattern_type));
      });
      if (opp) {
        const oppIsRev =
          this.BEARISH_REVERSAL[opp.pattern_type] || this.BULLISH_REVERSAL[opp.pattern_type];
        if (this.CONSOLIDATION[lead.pattern_type] && oppIsRev) {
          mediumTerm += `同时存在较早已确认「${this.typeLabel(opp.pattern_type)}」（测幅/时效可能已兑现），冲突时以后续突破的「${leadLab}」为主，旧反转降权观察。`;
        } else {
          mediumTerm += `同时存在反向已确认「${this.typeLabel(opp.pattern_type)}」，冲突时以更高置信的「${leadLab}」为主，另一信号降权观察。`;
        }
      } else if (formingConsol.length && !hasConfirmedConsolBreak) {
        mediumTerm += `形成中巩固为次要，突破前不改「${leadLab}」框架。`;
      } else if (formingConsol.length && hasConfirmedConsolBreak) {
        mediumTerm += `形成中巩固仅次要观察。`;
      }
      if (bgArchived) mediumTerm += bgArchived;
    } else {
      const names = forming
        .filter((h) => this._isViablePrimaryCandidate(h, asof))
        .slice(0, 4)
        .map((h) => `${this.typeLabel(h.pattern_type)}(${h.confidence != null ? Number(h.confidence).toFixed(2) : '--'})`)
        .join('、');
      mediumTerm = `暂无高置信已确认形态，中线尚不明朗；形成中信号（${names || '若干'}）待边界突破或结构确认。`;
      if (bgArchived) mediumTerm += bgArchived;
      if (confHint) mediumTerm += confHint;
    }

    const risk =
      '风险提示：以上解读由日线形态规则自动生成，非投资建议；形态识别存在滞后与误报，请结合基本面、量能与自身风险承受能力综合判断。';

    // keyLevelsRef 仍计算供调试/兼容；UI/PDF 统一走 structure*
    const keyLevelsRef = this.buildKeyLevelsReference(items, { asof });
    const structure = this.buildStructureLevelsReference(items, {
      asof,
      confluenceZones: opts.confluenceZones,
    });

    return {
      shortTerm,
      mediumTerm,
      keyLevelsRef,
      structureHtml: structure.html,
      structureText: structure.text,
      tradeLevelsHtml: structure.html,
      tradeLevelsText: structure.text,
      risk,
      primaryLabel,
      primaryConf,
      closeTxt,
      neckTxt,
    };
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
    const adjust = this.selectedAdjust();
    const btn = document.getElementById('patternRunBtn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '识别中…';
    }
    try {
      if (mode === 'single') {
        let code = ((document.getElementById('patternStockCode') || {}).value || '').trim();
        if (!code) {
          CommonUtils.showToast('请输入股票代码或名称', 'warning');
          return;
        }
        // 「00700 腾讯」：首段为数字代码时取代码（与 levels 一致）
        const firstToken = code.split(/\s+/)[0];
        const firstBody = /^(sh|sz|bj|hk)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
        if (/^\d{4,6}$/.test(firstBody)) {
          code = firstToken;
        }
        const fetched = await this.fetchSingle(code, { types, adjust, asof: asof || undefined });
        const priceAdjust = fetched.price_adjust;
        this.renderItems(
          fetched.items,
          `个股 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准日 ${this.esc(fetched.asof || '--')} · ${this.esc(this.adjustLabel(priceAdjust))} · 命中 ${fetched.items.length}`,
          'single',
          priceAdjust
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
          adjust,
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
        const priceAdjust = data.price_adjust === 'qfq' ? 'qfq' : 'none';
        const flags = [];
        if (data.truncated) flags.push('已截断');
        if (data.timed_out) flags.push('已超时');
        this.renderItems(
          data.items || [],
          `扫描 ${this.esc(data.scope)} · 已扫 ${data.scanned || 0}/${data.pool_size || 0} · 命中 ${data.hit_count || 0} · 基准日 ${this.esc(data.asof || '--')} · ${this.esc(this.adjustLabel(priceAdjust))}${flags.length ? ' · ' + flags.join('/') : ''}`,
          'scan',
          priceAdjust
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

window.PatternTool = PatternTool;

document.addEventListener('DOMContentLoaded', () => {
  try {
    PatternTool.init();
  } catch (e) {
    console.warn(e);
  }
});
