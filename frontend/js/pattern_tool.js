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
      return d ? `${name}=${p.price}(${d})` : `${name}=${p.price}`;
    });

    const levels = r.key_levels || {};
    const extras = [];
    const shrink = reason.match(/收敛约[^\s]+/);
    if (shrink) extras.push(shrink[0]);
    if (levels.neckline != null && levels.neckline !== '' && !priced.some((p) => p.role === 'neck')) {
      extras.push(`颈线≈${levels.neckline}`);
    }
    if (levels.upper_slope != null && levels.upper_slope !== '') {
      extras.push(`上沿斜率=${levels.upper_slope}`);
    } else {
      const m = reason.match(/上沿斜率=[^\s]+/);
      if (m) extras.push(m[0]);
    }
    if (levels.lower_slope != null && levels.lower_slope !== '') {
      extras.push(`下沿斜率=${levels.lower_slope}`);
    } else {
      const m = reason.match(/下沿斜率=[^\s]+/);
      if (m) extras.push(m[0]);
    }
    return `${label}${simplified} ${parts.join(' ')}${extras.length ? ` ${extras.join(' ')}` : ''}`.trim();
  },

  renderItems(items, metaHtml, mode) {
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
      this.renderExpertAnalysis([], mode || 'single');
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
        const reasonFull = this.reasonText(r);
        return `<tr>
          <td>${codeHtml}</td>
          <td>${this.esc(name || '--')}</td>
          <td>${this.esc(this.typeLabel(r.pattern_type))}</td>
          <td>${this.esc(r.status === 'confirmed' ? '已确认' : '形成中')}</td>
          <td title="${this.esc(this.formedAtTitle(r))}">${this.esc(formed)}</td>
          <td>${r.confidence != null ? Number(r.confidence).toFixed(2) : '--'}</td>
          <td class="pattern-col-levels">${this.esc(this.keyLevelsText(r.key_levels))}</td>
          <td class="pattern-col-reason" title="${this.esc(reasonFull)}">${this.esc(reasonFull)}</td>
        </tr>`;
      })
      .join('');
    this.renderExpertAnalysis(items, mode || 'single');
  },

  /** 空结果隐藏；个股完整解读；扫描简要提示 */
  renderExpertAnalysis(items, mode) {
    const box = document.getElementById('patternExpertAnalysis');
    const body = document.getElementById('patternExpertBody');
    if (!box || !body) return;
    if (!items || !items.length) {
      box.hidden = true;
      body.innerHTML = '';
      return;
    }
    box.hidden = false;
    if (mode === 'scan') {
      const n = items.length;
      const top = this._rankHits(items).slice(0, 3);
      const brief = top
        .map((h) => {
          const code = h.code || '';
          const label = this.typeLabel(h.pattern_type);
          const st = h.status === 'confirmed' ? '已确认' : '形成中';
          const conf = h.confidence != null ? Number(h.confidence).toFixed(2) : '--';
          return `${code} ${label}（${st} ${conf}）`;
        })
        .join('；');
      body.innerHTML = `<p>本页命中 ${n} 条${brief ? `，靠前示例：${this.esc(brief)}` : ''}。扫描模式不展开长文解读，请切换至「个股识别」获取完整专家分析。</p>
        <p class="pattern-expert-risk">风险提示：以上为日线规则模板摘要，不构成投资建议。</p>`;
      return;
    }
    const analysis = this.buildExpertAnalysis(items);
    const levelsHtml = analysis.keyLevelsRef
      ? `<p><span class="pattern-expert-label">关键位置参考：</span>${this.esc(analysis.keyLevelsRef)}</p>`
      : '';
    const tradeHtml = analysis.tradeLevelsHtml || '';
    body.innerHTML = `
      <p><span class="pattern-expert-label">短期走势：</span>${this.esc(analysis.shortTerm)}</p>
      <p><span class="pattern-expert-label">中线格局：</span>${this.esc(analysis.mediumTerm)}</p>
      ${levelsHtml}
      ${tradeHtml}
      <p class="pattern-expert-risk">${this.esc(analysis.risk)}</p>`;
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

  _rankHits(items) {
    return (items || []).slice().sort((a, b) => {
      const ac = a.status === 'confirmed' ? 1 : 0;
      const bc = b.status === 'confirmed' ? 1 : 0;
      if (bc !== ac) return bc - ac;
      return (Number(b.confidence) || 0) - (Number(a.confidence) || 0);
    });
  },

  _biasOf(type) {
    if (this.BEARISH_REVERSAL[type]) return 'bear';
    if (this.BULLISH_REVERSAL[type]) return 'bull';
    if (type === 'rising_wedge' || type === 'bear_flag' || type === 'descending_triangle') return 'bearish_bias';
    if (type === 'falling_wedge' || type === 'bull_flag' || type === 'ascending_triangle') return 'bullish_bias';
    return 'neutral';
  },

  _fmtPx(n) {
    if (n == null) return '--';
    const x = Number(n);
    if (!Number.isFinite(x)) return '--';
    return Math.abs(x) >= 100 ? x.toFixed(1) : x.toFixed(2);
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
      add(lv.upper, '上沿', '突破参考');
      add(lv.lower, '下沿', '突破参考');
    } else {
      // 兜底：有颈线/上下沿则带出
      add(lv.neckline, '颈线', '关键参考');
      add(lv.upper, '上沿', '突破参考');
      add(lv.lower, '下沿', '突破参考');
    }
    return out;
  },

  /** 近价合并（相对 0.8% 内视为同一档） */
  _mergeNearLevels(raw) {
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
            name: lv.name,
            role: lv.role,
            sources: [lv.source],
            observing: lv.observing,
            confirmed: !!lv.confirmed,
            conf: lv.conf,
          });
          return;
        }
        if (lv.conf > hit.conf) {
          hit.price = lv.price;
          hit.conf = lv.conf;
        }
        if (!hit.observing && lv.observing) {
          /* 已有确认档，保留非观察中 */
        } else if (hit.observing && !lv.observing) {
          hit.observing = false;
          hit.name = lv.name;
          hit.role = lv.role;
        } else if (hit.observing === lv.observing) {
          const prefer = { 颈线: 3, 双峰高点: 2, 双谷低点: 2, 头部高点: 2, 头部低点: 2, 上沿: 1, 下沿: 1 };
          if ((prefer[lv.name] || 0) > (prefer[hit.name] || 0)) {
            hit.name = lv.name;
            hit.role = lv.role;
          }
        }
        if (!hit.sources.includes(lv.source)) hit.sources.push(lv.source);
        hit.observing = hit.observing && lv.observing;
        hit.confirmed = hit.confirmed || !!lv.confirmed;
      });
    return merged;
  },

  _collectMergedLevels(items) {
    const ranked = this._rankHits(items);
    const raw = [];
    ranked.forEach((h) => {
      this._levelsFromHit(h).forEach((lv) => raw.push(lv));
    });
    return this._mergeNearLevels(raw);
  },

  /** 交易点位「意义」分：优先颈线翻支撑、峰谷/头、通道上下沿 */
  _tradeLevelScore(m, side) {
    let s = 0;
    const n = m.name || '';
    if (n === '颈线') s += 50;
    else if (n === '双谷低点' || n === '双峰高点' || n === '头部低点' || n === '头部高点') s += 42;
    else if (n === 'L1' || n === 'L2' || n === 'H1' || n === 'H2') s += 38;
    else if (side === 'support' && n === '下沿') s += 36;
    else if (side === 'support' && n === '上沿') s += 34; // 突破后翻支撑
    else if (side === 'resistance' && n === '上沿') s += 36;
    else if (side === 'resistance' && n === '下沿') s += 28;
    else s += 20;
    if (m.confirmed) s += 12;
    if (!m.observing) s += 6;
    return s;
  },

  /**
   * 相对现价的交易角色简述（形态名+角色）。
   * 已确认且原上沿/颈线落在现价下方 →「突破后翻支撑」。
   */
  _tradeLevelExplain(m, side) {
    const src = (m.sources && m.sources.length ? m.sources.join('/') : '') || '形态';
    const n = m.name || '关键位';
    let meaning = '';
    if (side === 'support') {
      if (m.confirmed && (n === '颈线' || n === '上沿')) meaning = '突破后翻支撑';
      else if (n === '颈线') meaning = '颈线支撑（观察中）';
      else if (n === '双谷低点' || n === 'L1' || n === 'L2' || n === '头部低点') meaning = '形态低点支撑';
      else if (n === '下沿') meaning = '通道/形态下沿支撑';
      else if (n === '上沿') meaning = '上沿翻支撑（待确认）';
      else meaning = '下方支撑';
    } else {
      if (n === '颈线') meaning = m.confirmed ? '颈线阻力' : '颈线阻力（观察中）';
      else if (n === '双峰高点' || n === 'H1' || n === 'H2' || n === '头部高点') meaning = '形态高点阻力';
      else if (n === '上沿') meaning = '通道/形态上沿阻力';
      else if (n === '下沿') meaning = m.confirmed ? '下沿翻阻力' : '下沿阻力（观察中）';
      else meaning = '上方阻力';
    }
    return `${src}${n}，${meaning}`;
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
   * 后续交易点位参考 HTML（个股模式）。
   * 以 last_close 分界；每侧最多 2 档 bullet。
   */
  buildTradeLevelsReference(items) {
    const ranked = this._rankHits(items);
    let close = null;
    for (let i = 0; i < ranked.length; i++) {
      close = this._hitClose(ranked[i]);
      if (close != null) break;
    }
    const merged = this._collectMergedLevels(items);
    const { supports, resistances } = this._pickTradeLevels(merged, close);

    const supportZone = this._tradeZoneText(supports, 'support');
    const resistZone = this._tradeZoneText(resistances, 'resistance');

    let supportBlock = '';
    if (!supports.length) {
      supportBlock = `<p>下方核心支撑区：暂无明显支撑，等待形态边界突破后再定</p>`;
    } else {
      const bullets = supports.map((m, idx) => {
        const label = idx === 0 ? '直接支撑' : '强底支撑';
        return `<li>${label}：${this.esc(this._fmtPx(m.price))} 附近（${this.esc(this._tradeLevelExplain(m, 'support'))}）</li>`;
      });
      supportBlock = `<p>下方核心支撑区：${this.esc(supportZone)}</p><ul>${bullets.join('')}</ul>`;
    }

    let resistBlock = '';
    if (!resistances.length) {
      resistBlock = `<p>上方核心阻力区：暂无明显阻力，等待形态边界突破后再定</p>`;
    } else {
      const bullets = resistances.map((m, idx) => {
        const label = idx === 0 ? '第一阻力' : '第二阻力';
        return `<li>${label}：${this.esc(this._fmtPx(m.price))} 附近（${this.esc(this._tradeLevelExplain(m, 'resistance'))}）</li>`;
      });
      resistBlock = `<p>上方核心阻力区：${this.esc(resistZone)}</p><ul>${bullets.join('')}</ul>`;
    }

    return `<div class="pattern-expert-trade-levels">
      <p><span class="pattern-expert-label">后续交易点位参考：</span></p>
      ${supportBlock}
      ${resistBlock}
    </div>`;
  },

  /**
   * 汇总多形态关键位：近价去重、按价格升序、标注来源与观察中。
   * @returns {string}
   */
  buildKeyLevelsReference(items) {
    const ranked = this._rankHits(items);
    const merged = this._collectMergedLevels(items);
    if (!merged.length) return '';

    merged.sort((a, b) => a.price - b.price);

    const parts = merged.map((m) => {
      const src = m.sources.join('/');
      const obs = m.observing ? ' · 观察中' : '';
      return `${this._fmtPx(m.price)} ${m.name}（${m.role}）· ${src}${obs}`;
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
      relTxt =
        Math.abs(pct) <= 4
          ? `现价 ${this._fmtPx(close)} 贴近「${nearest.name}」${this._fmtPx(nearest.price)}。`
          : `现价 ${this._fmtPx(close)} 相对「${nearest.name}」${this._fmtPx(nearest.price)} ${side}${pctAbs}%。`;
    }

    return `${parts.join('；')}${relTxt ? `。${relTxt}` : '。'}`;
  },

  /**
   * 前端规则引擎：根据 hits 结构化字段拼装专家口吻分析。
   * 优先已确认 + 高置信；形成中巩固形态等待突破；冲突时以更高置信确认形态为主。
   */
  buildExpertAnalysis(items) {
    const ranked = this._rankHits(items);
    const confirmed = ranked.filter((h) => h.status === 'confirmed');
    const forming = ranked.filter((h) => h.status !== 'confirmed');
    const primary = confirmed[0] || ranked[0];
    const primaryLabel = this.typeLabel(primary.pattern_type);
    const primaryConf =
      primary.confidence != null ? Number(primary.confidence).toFixed(2) : '--';
    const formedAt = this.formedAtText(primary);
    const close = this._hitClose(primary);
    const neck = this._hitNeck(primary);
    const closeTxt = close != null ? this._fmtPx(close) : null;
    const neckTxt = neck != null ? this._fmtPx(neck) : null;

    let shortTerm = '';
    let mediumTerm = '';

    // —— 短期：形成中 + 最近确认与现价相对关键位 ——
    const shortBits = [];
    if (confirmed.length) {
      const top = confirmed[0];
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
      } else {
        shortBits.push(`主导形态为已确认${lab}（置信度 ${primaryConf}），短线围绕其关键价位波动。`);
      }
    }

    const formingConsol = forming.filter((h) => this.CONSOLIDATION[h.pattern_type]);
    if (formingConsol.length) {
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
    } else if (!confirmed.length && forming.length) {
      const f0 = forming[0];
      shortBits.push(
        `当前以形成中的${this.typeLabel(f0.pattern_type)}为主，形态尚未确认，短线宜等待结构完成或关键位突破。`
      );
    }

    if (!shortBits.length) {
      shortBits.push('命中形态信息有限，短线建议结合量价与关键支撑压力谨慎观察。');
    }
    shortTerm = shortBits.join('');

    // —— 中线：高置信已确认 + 颈线/边界 ——
    if (confirmed.length) {
      const lead = confirmed[0];
      const leadBias = this._biasOf(lead.pattern_type);
      const leadLab = this.typeLabel(lead.pattern_type);
      const leadConf =
        lead.confidence != null ? Number(lead.confidence).toFixed(2) : '--';
      const leadNeck = this._hitNeck(lead);
      const leadClose = this._hitClose(lead);
      const lv = lead.key_levels || {};
      const levelParts = [];
      if (leadNeck != null) levelParts.push(`颈线 ${this._fmtPx(leadNeck)}`);
      if (lv.h1 != null || lv.h2 != null) {
        levelParts.push(
          `峰位 H1/H2≈${this._fmtPx(lv.h1 != null ? lv.h1 : lv.h2)}${lv.h2 != null && lv.h1 != null ? '/' + this._fmtPx(lv.h2) : ''}`
        );
      }
      if (lv.l1 != null || lv.l2 != null) {
        levelParts.push(
          `谷位 L1/L2≈${this._fmtPx(lv.l1 != null ? lv.l1 : lv.l2)}${lv.l2 != null && lv.l1 != null ? '/' + this._fmtPx(lv.l2) : ''}`
        );
      }
      if (lv.head != null) levelParts.push(`头部 ${this._fmtPx(lv.head)}`);
      const levelTxt = levelParts.length ? `关键位：${levelParts.join('，')}。` : '';
      const formed = this.formedAtText(lead);
      const formedTxt = formed && formed !== '--' ? `形成/确认参考日 ${formed}。` : '';

      let stance = '中性震荡';
      if (leadBias === 'bear') stance = '中线偏空';
      else if (leadBias === 'bull') stance = '中线偏多';
      else if (leadBias === 'bearish_bias') stance = '中线略偏防守';
      else if (leadBias === 'bullish_bias') stance = '中线略偏积极';

      mediumTerm = `以高置信已确认「${leadLab}」（置信度 ${leadConf}）为主导，${stance}。${levelTxt}${formedTxt}`;
      if (leadClose != null) mediumTerm += `现价/收盘参考 ${this._fmtPx(leadClose)}。`;

      // 冲突：另有反向已确认
      const opp = confirmed.find((h) => {
        const b = this._biasOf(h.pattern_type);
        if (leadBias === 'bear' && b === 'bull') return true;
        if (leadBias === 'bull' && b === 'bear') return true;
        return false;
      });
      if (opp) {
        mediumTerm += `同时存在反向已确认「${this.typeLabel(opp.pattern_type)}」，冲突时以更高置信的「${leadLab}」为主。`;
      } else if (formingConsol.length) {
        mediumTerm += `形成中的巩固/楔旗形为次要信号，突破前不改变以「${leadLab}」为核心的中线框架。`;
      }
    } else {
      const names = forming
        .slice(0, 4)
        .map((h) => `${this.typeLabel(h.pattern_type)}(${h.confidence != null ? Number(h.confidence).toFixed(2) : '--'})`)
        .join('、');
      mediumTerm = `暂无高置信已确认反转形态，中线格局尚不明朗；当前形成中信号（${names || '若干'}）需等待边界突破或结构确认后再评估趋势级别。`;
    }

    const risk =
      '风险提示：以上解读由日线形态规则自动生成，非投资建议；形态识别存在滞后与误报，请结合基本面、量能与自身风险承受能力综合判断。';

    const keyLevelsRef = this.buildKeyLevelsReference(items);
    const tradeLevelsHtml = this.buildTradeLevelsReference(items);

    return {
      shortTerm,
      mediumTerm,
      keyLevelsRef,
      tradeLevelsHtml,
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
          `个股 ${this.esc(data.code)} ${this.esc(data.name || '')} · 基准日 ${this.esc(data.asof || '--')} · 命中 ${items.length}`,
          'single'
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
          `扫描 ${this.esc(data.scope)} · 已扫 ${data.scanned || 0}/${data.pool_size || 0} · 命中 ${data.hit_count || 0} · 基准日 ${this.esc(data.asof || '--')}${flags.length ? ' · ' + flags.join('/') : ''}`,
          'scan'
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
