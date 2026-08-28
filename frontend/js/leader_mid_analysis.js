/**
 * 分析频道 · 龙头中军 × 四策略命中矩阵（板块多选，交互对齐 RPE）
 */
const LeaderMidAnalysis = {
  API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
  boardKind: 'industry',
  industryCatalog: [],
  conceptCatalog: [],
  /** @type {string[]} */
  selectedBoardCodes: [],
  lastResult: null,
  lastElapsedMs: null,
  running: false,
  catalogsLoaded: false,
  _elapsedTimer: null,
  _pickerDraft: new Set(),
  _pickerStrongOnly: false,

  init() {
    this.bindEvents();
  },

  strongHelper() {
    return typeof BoardPickerStrong !== 'undefined' ? BoardPickerStrong : null;
  },

  includeNeutralSelected() {
    return !!document.getElementById('lmIncludeNeutral')?.checked;
  },

  selectOpts() {
    return { includeNeutral: this.includeNeutralSelected() };
  },

  ensureCatalogs() {
    if (!this.catalogsLoaded) {
      this.loadCatalogs();
    } else {
      this.updateBoardSummary();
    }
  },

  bindEvents() {
    document.querySelectorAll('.lm-subtab').forEach((btn) => {
      btn.addEventListener('click', () => {
        const kind = btn.getAttribute('data-lm-kind') === 'concept' ? 'concept' : 'industry';
        this.boardKind = kind;
        document.querySelectorAll('.lm-subtab').forEach((b) => {
          b.classList.toggle('active', b === btn);
        });
        this.selectedBoardCodes = [];
        this.lastResult = null;
        this._pickerStrongOnly = false;
        const strongOnly = document.getElementById('lmBoardPickerStrongOnly');
        if (strongOnly) strongOnly.checked = false;
        this.clearMeta();
        this.updateBoardSummary();
        const host = document.getElementById('lmResults');
        if (host) {
          host.innerHTML = '<p class="lm-empty">选择板块后点击「查询命中」</p>';
        }
      });
    });

    const pickBtn = document.getElementById('lmBoardPickBtn');
    if (pickBtn) {
      pickBtn.addEventListener('click', () => this.openBoardPicker());
    }
    const strongBtn = document.getElementById('lmSelectStrongBtn');
    if (strongBtn) {
      strongBtn.addEventListener('click', () => this.selectStrongBoards());
    }
    const includeNeutral = document.getElementById('lmIncludeNeutral');
    if (includeNeutral) {
      includeNeutral.addEventListener('change', () => {
        if (this._pickerStrongOnly) this.renderBoardPickerList();
      });
    }
    const runBtn = document.getElementById('lmRunBtn');
    if (runBtn) {
      runBtn.addEventListener('click', () => this.runQuery());
    }
    const exportBtn = document.getElementById('lmExportExcelBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.exportExcel());
    }

    const overlay = document.getElementById('lmBoardPickerModal');
    ['lmBoardPickerClose', 'lmBoardPickerCancel'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('click', () => this.hideBoardPicker());
      }
    });
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) this.hideBoardPicker();
      });
    }
    const searchEl = document.getElementById('lmBoardPickerSearch');
    if (searchEl) {
      searchEl.addEventListener('input', () => this.renderBoardPickerList());
    }
    const strongOnly = document.getElementById('lmBoardPickerStrongOnly');
    if (strongOnly) {
      strongOnly.addEventListener('change', () => {
        this._pickerStrongOnly = !!strongOnly.checked;
        this.renderBoardPickerList();
      });
    }
    const selAll = document.getElementById('lmBoardPickerSelectAll');
    if (selAll) {
      selAll.addEventListener('click', () => this.pickerSelectAllVisible());
    }
    const selStrong = document.getElementById('lmBoardPickerSelectStrong');
    if (selStrong) {
      selStrong.addEventListener('click', () => this.pickerSelectStrongVisible());
    }
    const clearBtn = document.getElementById('lmBoardPickerClear');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.pickerClearVisible());
    }
    const confirmBtn = document.getElementById('lmBoardPickerConfirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => this.confirmBoardPicker());
    }
    const listEl = document.getElementById('lmBoardPickerList');
    if (listEl) {
      listEl.addEventListener('change', (e) => {
        const t = e.target;
        if (!t || t.type !== 'checkbox') return;
        const code = String(t.value || '').trim();
        if (!code) return;
        if (t.checked) this._pickerDraft.add(code);
        else this._pickerDraft.delete(code);
      });
    }
  },

  async loadCatalogs() {
    const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
    try {
      const [indRes, conRes] = await Promise.all([
        fetchFn(`${this.API_BASE_URL}/api/market/industry_board/list?board_code_source=tonghuashun`),
        fetchFn(`${this.API_BASE_URL}/api/market/concept_board/list?board_code_source=tonghuashun`),
      ]);
      const ind = await indRes.json().catch(() => ({}));
      const con = await conRes.json().catch(() => ({}));
      this.industryCatalog = Array.isArray(ind.data) ? ind.data : [];
      this.conceptCatalog = Array.isArray(con.data) ? con.data : [];
      this.catalogsLoaded = true;
      this.updateBoardSummary();
    } catch (e) {
      console.error(e);
      if (window.CommonUtils) CommonUtils.showToast('加载板块列表失败', 'error');
    }
  },

  catalog() {
    return this.boardKind === 'concept' ? this.conceptCatalog : this.industryCatalog;
  },

  boardByCode(code) {
    return this.catalog().find((x) => String(x.board_code) === String(code));
  },

  updateBoardSummary() {
    const el = document.getElementById('lmBoardSummary');
    if (!el) return;
    const codes = this.selectedBoardCodes || [];
    if (!codes.length) {
      el.textContent = '未选择板块，点击「选择板块」';
      return;
    }
    if (codes.length === 1) {
      const b = this.boardByCode(codes[0]);
      const name = b ? b.board_name || codes[0] : codes[0];
      el.textContent = `已选 1 个：${name}（${codes[0]}）`;
      return;
    }
    const names = codes.slice(0, 3).map((c) => {
      const b = this.boardByCode(c);
      return b ? b.board_name || c : c;
    });
    const more = codes.length > 3 ? ` 等 ${codes.length} 个` : '';
    el.textContent = `已选 ${codes.length} 个：${names.join('、')}${more}`;
  },

  openBoardPicker() {
    if (!this.catalogsLoaded) {
      this.loadCatalogs().then(() => this.openBoardPicker());
      return;
    }
    this._pickerDraft = new Set(this.selectedBoardCodes || []);
    const titleEl = document.getElementById('lmBoardPickerTitle');
    if (titleEl) {
      titleEl.textContent =
        this.boardKind === 'concept' ? '选择概念板块（可多选）' : '选择行业板块（可多选）';
    }
    const searchEl = document.getElementById('lmBoardPickerSearch');
    if (searchEl) searchEl.value = '';
    const strongOnly = document.getElementById('lmBoardPickerStrongOnly');
    if (strongOnly) {
      strongOnly.checked = !!this._pickerStrongOnly;
    }
    this.renderBoardPickerList();
    const overlay = document.getElementById('lmBoardPickerModal');
    if (overlay) {
      overlay.style.display = 'flex';
      overlay.setAttribute('aria-hidden', 'false');
    }
  },

  hideBoardPicker() {
    const overlay = document.getElementById('lmBoardPickerModal');
    if (overlay) {
      overlay.style.display = 'none';
      overlay.setAttribute('aria-hidden', 'true');
    }
  },

  updateBoardPickerCount(total, filtered, hasFilter) {
    const countEl = document.getElementById('lmBoardPickerCount');
    if (!countEl) return;
    countEl.textContent = hasFilter
      ? `当前 ${filtered} / 共 ${total}`
      : `共 ${total} 个可选`;
  },

  visiblePickerBoards() {
    const q = (document.getElementById('lmBoardPickerSearch')?.value || '').trim().toLowerCase();
    const helper = this.strongHelper();
    let list = this.catalog().slice();
    if (this._pickerStrongOnly && helper) {
      list = helper.filterSelectable(list, this.selectOpts());
    }
    if (q) {
      list = list.filter((b) => {
        const name = String(b.board_name || '').toLowerCase();
        const code = String(b.board_code || '').toLowerCase();
        return name.includes(q) || code.includes(q);
      });
    }
    if (helper) {
      list = helper.sortByStrongThenSlope(list);
    } else {
      list.sort((a, b) =>
        String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh')
      );
    }
    return list;
  },

  renderBoardPickerList() {
    const listEl = document.getElementById('lmBoardPickerList');
    if (!listEl) return;
    const helper = this.strongHelper();
    const all = this.catalog().slice();
    const total = all.length;
    const list = this.visiblePickerBoards();
    const hasFilter =
      !!((document.getElementById('lmBoardPickerSearch')?.value || '').trim()) ||
      !!this._pickerStrongOnly;
    this.updateBoardPickerCount(total, list.length, hasFilter);
    if (!list.length) {
      listEl.innerHTML = '<div class="lm-board-picker-empty">无匹配板块</div>';
      return;
    }
    const draft = this._pickerDraft;
    listEl.innerHTML = list
      .map((b) => {
        const code = String(b.board_code || '').trim();
        const name = String(b.board_name || code).trim();
        const n = b.stock_count != null ? b.stock_count : b.member_count;
        const countTxt = n != null ? `${n}只` : '';
        const checked = draft.has(code) ? ' checked' : '';
        const envLabel = helper ? helper.formatEnvLabel(b) : '--';
        const envClass = helper ? helper.envChipClass(b) : 'unknown';
        const slopeTxt = helper ? helper.formatSlope(b) : '--';
        const title = countTxt
          ? `${name} · ${countTxt} · ${code} · ${envLabel} · 斜率${slopeTxt}`
          : `${name} · ${code} · ${envLabel} · 斜率${slopeTxt}`;
        return `<label class="lm-board-picker-item" title="${this.escAttr(title)}">
          <input type="checkbox" value="${this.escAttr(code)}"${checked}>
          <span class="lm-board-picker-item-text">
            <span class="lm-board-picker-name">${this.esc(name)}${n != null ? ` (${n})` : ''}
              <span class="ba-env-chip ${this.escAttr(envClass)}">${this.esc(envLabel)}</span>
              <span class="lm-board-picker-slope">斜率 ${this.esc(slopeTxt)}</span>
            </span>
            <span class="lm-board-picker-code">${this.esc(code)}${countTxt ? ` · ${this.esc(countTxt)}` : ''}</span>
          </span>
        </label>`;
      })
      .join('');
  },

  pickerSelectAllVisible() {
    const listEl = document.getElementById('lmBoardPickerList');
    if (!listEl) return;
    listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.checked = true;
      const code = String(cb.value || '').trim();
      if (code) this._pickerDraft.add(code);
    });
  },

  pickerSelectStrongVisible() {
    const helper = this.strongHelper();
    if (!helper) return;
    const opts = this.selectOpts();
    const byCode = new Map(
      this.visiblePickerBoards().map((b) => [String(b.board_code || '').trim(), b])
    );
    const listEl = document.getElementById('lmBoardPickerList');
    if (!listEl) return;
    listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      const code = String(cb.value || '').trim();
      const row = byCode.get(code);
      if (row && helper.isSelectableBoard(row, opts)) {
        cb.checked = true;
        this._pickerDraft.add(code);
      }
    });
  },

  pickerClearVisible() {
    const listEl = document.getElementById('lmBoardPickerList');
    if (!listEl) return;
    listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.checked = false;
      const code = String(cb.value || '').trim();
      if (code) this._pickerDraft.delete(code);
    });
  },

  applySelectedBoardCodes(codes) {
    this.selectedBoardCodes = Array.isArray(codes) ? codes.slice() : [];
    this.lastResult = null;
    this.updateBoardSummary();
    this.clearMeta();
    const host = document.getElementById('lmResults');
    if (host) {
      host.innerHTML = '<p class="lm-empty">选择板块后点击「查询命中」</p>';
    }
    if (this.selectedBoardCodes.length && window.BoardRolesPanel) {
      BoardRolesPanel.refresh({
        panelId: 'lmRolesHost',
        boardType: this.boardKind,
        boardCodes: this.selectedBoardCodes,
        boardCodeSource: 'tonghuashun',
        visible: true,
        variant: 'shortline',
        showGmsWatchlistActions: true,
        gmsWatchlistPerm: 'channel.analyze.tab.leader_mid.btn.gms_watchlist',
      });
    }
  },

  async selectStrongBoards() {
    if (!this.catalogsLoaded) {
      await this.loadCatalogs();
    }
    const helper = this.strongHelper();
    if (!helper) {
      if (window.CommonUtils) CommonUtils.showToast('走强选板模块未加载', 'error');
      return;
    }
    const opts = this.selectOpts();
    const codes = helper.selectableCodes(this.catalog(), opts);
    const label = helper.selectLabel(opts);
    if (!codes.length) {
      if (window.CommonUtils) {
        CommonUtils.showToast(
          `当前暂无${label}板块（需行情页已刷新斜率）`,
          'warning'
        );
      }
      return;
    }
    this.applySelectedBoardCodes(codes);
    if (window.CommonUtils) {
      CommonUtils.showToast(`已选中 ${codes.length} 个${label}板块`, 'success');
    }
  },

  confirmBoardPicker() {
    this.applySelectedBoardCodes(Array.from(this._pickerDraft));
    this.hideBoardPicker();
  },

  clearMeta() {
    const meta = document.getElementById('lmBoardMeta');
    if (meta) meta.innerHTML = '';
    if (window.BoardRolesPanel) {
      BoardRolesPanel.refresh({
        panelId: 'lmRolesHost',
        boardType: this.boardKind,
        boardCodes: [],
        visible: false,
        variant: 'shortline',
      });
    }
  },

  formatElapsed(ms) {
    const n = Number(ms);
    if (!Number.isFinite(n) || n < 0) return '--';
    if (n < 1000) return `${Math.round(n)} ms`;
    const sec = n / 1000;
    if (sec < 60) return `${sec.toFixed(1)} 秒`;
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(1);
    return `${m} 分 ${s} 秒`;
  },

  stopElapsedTimer() {
    if (this._elapsedTimer) {
      clearInterval(this._elapsedTimer);
      this._elapsedTimer = null;
    }
  },

  startElapsedTimer(host, multiHint) {
    this.stopElapsedTimer();
    const started = performance.now();
    const base = multiHint
      ? '正在汇总所选板块龙头中军并查询命中，耗时可能较长'
      : '正在查询龙头中军策略命中';
    const paint = () => {
      const elapsed = performance.now() - started;
      if (host) {
        host.innerHTML =
          `<p class="lm-empty">${this.esc(base)}…` +
          ` <span class="lm-elapsed">已用时 ${this.esc(this.formatElapsed(elapsed))}</span></p>`;
      }
      const btn = document.getElementById('lmRunBtn');
      if (btn && this.running) {
        btn.textContent = `查询中… ${this.formatElapsed(elapsed)}`;
      }
    };
    paint();
    this._elapsedTimer = setInterval(paint, 500);
    return started;
  },

  async runQuery() {
    if (this.running) return;
    const codes = this.selectedBoardCodes || [];
    if (!codes.length) {
      if (window.CommonUtils) CommonUtils.showToast('请先选择板块', 'warning');
      return;
    }
    this.running = true;
    this.lastElapsedMs = null;
    const btn = document.getElementById('lmRunBtn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '查询中…';
    }
    const host = document.getElementById('lmResults');
    const multiHint = codes.length > 1;
    const startedAt = this.startElapsedTimer(host, multiHint);

    const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
    const q = new URLSearchParams({
      board_kind: this.boardKind,
      board_code_source: 'tonghuashun',
      strategies: 'gms,urt,sbbr,rpe',
    });
    if (codes.length === 1) {
      q.set('board_code', codes[0]);
      const b = this.boardByCode(codes[0]);
      if (b && b.board_name) q.set('board_name', b.board_name);
    } else {
      q.set('board_codes', codes.join(','));
    }
    try {
      const res = await fetchFn(`${this.API_BASE_URL}/api/analysis/leader-mid-signals?${q}`);
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json.success) {
        throw new Error(json.message || json.detail || `请求失败(${res.status})`);
      }
      this.lastElapsedMs = performance.now() - startedAt;
      this.lastResult = json.data || {};
      this.renderMeta(this.lastResult);
      this.renderTable(this.lastResult);
    } catch (e) {
      console.error(e);
      this.lastElapsedMs = performance.now() - startedAt;
      if (host) {
        host.innerHTML =
          `<p class="lm-empty lm-error">${this.esc(e.message || '查询失败')}` +
          ` <span class="lm-elapsed">耗时 ${this.esc(this.formatElapsed(this.lastElapsedMs))}</span></p>`;
      }
      if (window.CommonUtils) CommonUtils.showToast(e.message || '查询失败', 'error');
    } finally {
      this.stopElapsedTimer();
      this.running = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = '查询命中';
      }
    }
  },

  renderMeta(data) {
    const meta = document.getElementById('lmBoardMeta');
    if (!meta) return;
    const board = data.board || {};
    const kindLabel = board.board_kind === 'concept' ? '概念' : '行业';
    const multi = !!board.multi_boards || !!board.all_boards;
    const chg = board.board_change_percent_est;
    const chgText =
      chg == null || chg === ''
        ? '--'
        : `${Number(chg) > 0 ? '+' : ''}${Number(chg).toFixed(2)}%`;
    const boardScope = multi
      ? `${kindLabel} · ${board.board_count != null ? board.board_count : '--'} 板`
      : `${kindLabel} · ${board.board_code || ''}`;
    const elapsedText =
      this.lastElapsedMs != null
        ? `<span class="lm-elapsed">耗时 ${this.esc(this.formatElapsed(this.lastElapsedMs))}</span>`
        : '';
    meta.innerHTML = `
      <div class="lm-meta-line">
        <strong>${this.esc(board.board_name || '--')}</strong>
        <span class="lm-muted">${this.esc(boardScope)}</span>
        ${multi ? '' : `<span>板涨跌估 ${this.esc(chgText)}</span>`}
        <span>龙头 ${data.leader_count != null ? data.leader_count : 0} / 中军 ${data.mid_count != null ? data.mid_count : 0}</span>
        <span>去重后 ${data.role_count != null ? data.role_count : 0} 只</span>
        ${elapsedText}
        <span class="lm-muted">${this.esc(data.asof || '')}</span>
      </div>`;
  },

  renderTable(data) {
    const host = document.getElementById('lmResults');
    if (!host) return;
    const items = Array.isArray(data.items) ? data.items : [];
    const multi = !!(data.board && (data.board.multi_boards || data.board.all_boards));
    const errors = data.errors || {};
    const errKeys = Object.keys(errors);
    let errHtml = '';
    if (errKeys.length) {
      errHtml =
        '<div class="lm-errors">' +
        errKeys
          .map((k) => `<div>${this.esc(k.toUpperCase())}: ${this.esc(errors[k])}</div>`)
          .join('') +
        '</div>';
    }
    if (!items.length) {
      host.innerHTML =
        errHtml + '<p class="lm-empty">所选板块暂无龙头/中军标签，或角色识别为空</p>';
      return;
    }
    const rows = items
      .map((row) => {
        const code = row.code || '';
        const name = row.name || '';
        const role = row.board_role_label || row.board_role || '--';
        const roleCls =
          String(row.board_role).toLowerCase() === 'leader'
            ? 'lm-role lm-role--leader'
            : 'lm-role lm-role--mid';
        const chg = row.change_percent;
        const chgText =
          chg == null || chg === ''
            ? '--'
            : `${Number(chg) > 0 ? '+' : ''}${Number(chg).toFixed(2)}%`;
        const chgCls =
          chg == null ? '' : Number(chg) > 0 ? 'lm-up' : Number(chg) < 0 ? 'lm-down' : '';
        const hits = row.hits || {};
        const ref = row.reference_levels && typeof row.reference_levels === 'object'
          ? row.reference_levels
          : {};
        const lastClose = this.fmtPrice2(row.last_close ?? ref.last_close);
        const kdeS = this.fmtPrice2(row.kde_support);
        const kdeR = this.fmtPrice2(row.kde_resistance);
        const refCell = this.refLevelsCell(ref);
        const tip = this.refHoverTip(ref, row);
        const boardCell = multi
          ? `<td class="lm-boards" title="${this.escAttr(row.board_labels || '')}">${this.esc(row.board_labels || '--')}</td>`
          : '';
        const analysisHref = (window.StockTradeLink && window.StockTradeLink.buildHref)
            ? window.StockTradeLink.buildHref(code, name, { tab: 'analysis' })
            : `stock.html?tab=analysis&code=${encodeURIComponent(code)}${name ? `&name=${encodeURIComponent(name)}` : ''}`;
        return `<tr class="${row.any_hit ? 'lm-row--hit' : ''}">
          <td><a class="ba-stock-code-link" href="${this.escAttr(analysisHref)}" target="_blank" rel="noopener noreferrer" title="打开个股分析">${this.esc(code)}</a>
            <div class="lm-muted">${this.esc(name)}</div></td>
          ${boardCell}
          <td><span class="${roleCls}">${this.esc(role)}</span></td>
          <td class="lm-num">${lastClose}</td>
          <td class="lm-num ${chgCls}">${this.esc(chgText)}</td>
          <td class="lm-num">${kdeS}</td>
          <td class="lm-num">${kdeR}</td>
          <td class="lm-ref" title="${this.escAttr(tip)}">${refCell}</td>
          ${this.hitCell(hits.gms)}
          ${this.hitCell(hits.urt)}
          ${this.hitCell(hits.sbbr)}
          ${this.hitCell(hits.rpe)}
          <td class="lm-num">${row.hit_count != null ? row.hit_count : 0}</td>
        </tr>`;
      })
      .join('');
    const boardTh = multi ? '<th>所属板块</th>' : '';
    host.innerHTML =
      errHtml +
      `<div class="lm-table-wrap"><table class="lm-table">
      <thead><tr>
        <th>股票</th>${boardTh}<th>角色</th><th>收盘价</th><th>涨跌幅</th>
        <th>KDE支撑</th><th>KDE压力</th><th>参考价 Fib/Cam/VP/合</th>
        <th>GMS</th><th>URT</th><th>SBBR</th><th>RPE</th><th>命中数</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  },

  fmtPrice2(v) {
    if (v == null || v === '' || isNaN(Number(v))) return '--';
    return Number(v).toFixed(2);
  },

  refLevelsCell(ref) {
    const fibS = this.fmtPrice2(ref.nearest_fib_support);
    const fibR = this.fmtPrice2(ref.nearest_fib_resistance);
    const camS = this.fmtPrice2(
      ref.nearest_cam_support ?? ref.camarilla?.nearest_support
    );
    const camR = this.fmtPrice2(
      ref.nearest_cam_resistance ?? ref.camarilla?.nearest_resistance
    );
    const vp = ref.volume_profile && typeof ref.volume_profile === 'object' ? ref.volume_profile : {};
    const vpS = this.fmtPrice2(ref.nearest_vp_support ?? vp.nearest_support ?? vp.val);
    const vpR = this.fmtPrice2(ref.nearest_vp_resistance ?? vp.nearest_resistance ?? vp.vah);
    const conf = ref.confluence_zones && typeof ref.confluence_zones === 'object' ? ref.confluence_zones : {};
    const confS = this.fmtPrice2(
      ref.nearest_confluence_support ?? conf.nearest_support_zone?.center
    );
    const confR = this.fmtPrice2(
      ref.nearest_confluence_resistance ?? conf.nearest_resistance_zone?.center
    );
    return `Fib ${fibS}/${fibR}<br/>Cam ${camS}/${camR}<br/>VP ${vpS}/${vpR}<br/>合 ${confS}/${confR}`;
  },

  refHoverTip(ref, row) {
    const lines = [];
    if (row && row.last_close != null) {
      lines.push(`收盘价: ${this.fmtPrice2(row.last_close)}`);
    }
    if (row && (row.kde_support != null || row.kde_resistance != null)) {
      lines.push(
        `KDE: 支撑=${this.fmtPrice2(row.kde_support)} / 压力=${this.fmtPrice2(row.kde_resistance)}`
      );
    }
    const fib = ref && ref.fibonacci;
    if (fib && (fib.swing_high != null || fib.swing_low != null)) {
      const hi = `${this.fmtPrice2(fib.swing_high)}${fib.swing_high_date ? `（${fib.swing_high_date}）` : ''}`;
      const lo = `${this.fmtPrice2(fib.swing_low)}${fib.swing_low_date ? `（${fib.swing_low_date}）` : ''}`;
      lines.push(`Fib锚点: 高 ${hi} / 低 ${lo}`);
    }
    if (ref) {
      lines.push(
        `Fib最近: ${this.fmtPrice2(ref.nearest_fib_support)} / ${this.fmtPrice2(ref.nearest_fib_resistance)}`
      );
      lines.push(
        `Cam最近: ${this.fmtPrice2(ref.nearest_cam_support ?? ref.camarilla?.nearest_support)} / ${this.fmtPrice2(ref.nearest_cam_resistance ?? ref.camarilla?.nearest_resistance)}`
      );
      const vp = ref.volume_profile || {};
      if (vp.ok) {
        lines.push(
          `VP: POC=${this.fmtPrice2(vp.poc)} VAL=${this.fmtPrice2(vp.val)} VAH=${this.fmtPrice2(vp.vah)}`
        );
      }
      const conf = ref.confluence_zones || {};
      if (conf.ok) {
        const zs = conf.nearest_support_zone;
        const zr = conf.nearest_resistance_zone;
        lines.push(
          `共振: 支撑=${this.fmtPrice2(zs && zs.center)} / 压力=${this.fmtPrice2(zr && zr.center)}`
        );
      }
      const ap = ref.atr_pivot || {};
      if (ap.atr != null) {
        lines.push(`ATR带: ATR=${this.fmtPrice2(ap.atr)} R1=${this.fmtPrice2(ap.R1)} S1=${this.fmtPrice2(ap.S1)}`);
      }
    }
    return lines.join('\n') || '暂无参考价';
  },

  hitCell(cell) {
    const c = cell && typeof cell === 'object' ? cell : {};
    if (c.hit) {
      return `<td><span class="lm-hit lm-hit--yes" title="${this.escAttr(c.label || '命中')}">${this.esc(c.label || '命中')}</span></td>`;
    }
    return '<td><span class="lm-hit lm-hit--no">--</span></td>';
  },

  /** ---------- Excel 导出（业界扁平明细 + 板块汇总 + 字段说明） ---------- */

  toast(msg, type) {
    if (window.CommonUtils) CommonUtils.showToast(msg, type || 'info');
    else if (type === 'error' || type === 'warning') alert(msg);
  },

  fmtPctNum(v) {
    if (v == null || v === '' || !Number.isFinite(Number(v))) return '';
    return Math.round(Number(v) * 100) / 100;
  },

  fmtPctText(v) {
    if (v == null || v === '' || !Number.isFinite(Number(v))) return '';
    const n = Number(v);
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(2)}%`;
  },

  hitLabel(cell) {
    const c = cell && typeof cell === 'object' ? cell : {};
    if (c.hit) return c.label || '命中';
    return '';
  },

  /** 从角色面板缓存构建明细行 */
  buildRowsFromRolesPanel() {
    if (!window.BoardRolesPanel || typeof BoardRolesPanel.getLastRolesPayloads !== 'function') {
      return { rows: [], boards: [], kindLabel: this.boardKind === 'concept' ? '概念' : '行业' };
    }
    const { payloads } = BoardRolesPanel.getLastRolesPayloads('lmRolesHost');
    const kindLabel = this.boardKind === 'concept' ? '概念' : '行业';
    const rows = [];
    const boards = [];
    (payloads || []).forEach((data) => {
      const boardCode = String(data.board_code || '').trim();
      const boardName = String(data.board_name || boardCode).trim();
      const boardChg = data.board_change_percent_est;
      const leaders = Array.isArray(data.leaders)
        ? data.leaders
        : data.leader
          ? [data.leader]
          : [];
      const mids = Array.isArray(data.mids) ? data.mids : data.mid ? [data.mid] : [];
      boards.push({
        board_code: boardCode,
        board_name: boardName,
        board_change_percent_est: boardChg,
        leader_count: leaders.length,
        mid_count: mids.length,
        stock_count: leaders.length + mids.length,
      });
      const pushStock = (s, role, roleLabel) => {
        const code = String(s.code || s.stock_code || '').trim();
        if (!code) return;
        rows.push({
          board_kind: kindLabel,
          board_code: boardCode,
          board_name: boardName,
          board_change_percent_est: boardChg,
          board_role: role,
          board_role_label: roleLabel,
          code,
          name: s.name || s.stock_name || '',
          change_percent: s.change_percent,
          role_reason: s.role_reason || '',
          board_role_score: s.role_score != null ? s.role_score : s.board_role_score,
          any_hit: false,
          hit_count: '',
          hits: {},
        });
      };
      leaders.forEach((s) => pushStock(s, 'leader', '龙头'));
      mids.forEach((s) => pushStock(s, 'mid', '中军'));
    });
    return { rows, boards, kindLabel };
  },

  /** 从「查询命中」结果构建明细行（含策略命中） */
  buildRowsFromHitResult() {
    const data = this.lastResult;
    if (!data || !Array.isArray(data.items) || !data.items.length) {
      return null;
    }
    const board = data.board || {};
    const kindLabel = board.board_kind === 'concept' ? '概念' : '行业';
    const multi = !!(board.multi_boards || board.all_boards);
    const rows = data.items.map((row) => {
      const hits = row.hits || {};
      return {
        board_kind: kindLabel,
        board_code: multi
          ? String(row.board_codes || row.board_code || '').trim()
          : String(board.board_code || row.board_code || '').trim(),
        board_name: multi
          ? String(row.board_labels || row.board_name || '').trim()
          : String(board.board_name || row.board_name || '').trim(),
        board_change_percent_est: multi ? null : board.board_change_percent_est,
        board_role: row.board_role,
        board_role_label: row.board_role_label || row.board_role || '',
        code: String(row.code || '').trim(),
        name: row.name || '',
        change_percent: row.change_percent,
        last_close: row.last_close,
        kde_support: row.kde_support,
        kde_resistance: row.kde_resistance,
        role_reason: row.role_reason || '',
        board_role_score: row.board_role_score,
        any_hit: !!row.any_hit,
        hit_count: row.hit_count != null ? row.hit_count : 0,
        hits,
        asof: data.asof || '',
      };
    });
    // 按板块汇总
    const boardMap = new Map();
    rows.forEach((r) => {
      const key = `${r.board_code}|${r.board_name}`;
      if (!boardMap.has(key)) {
        boardMap.set(key, {
          board_code: r.board_code,
          board_name: r.board_name,
          board_change_percent_est: r.board_change_percent_est,
          leader_count: 0,
          mid_count: 0,
          stock_count: 0,
          hit_stock_count: 0,
        });
      }
      const b = boardMap.get(key);
      b.stock_count += 1;
      if (String(r.board_role).toLowerCase() === 'leader') b.leader_count += 1;
      else b.mid_count += 1;
      if (r.any_hit) b.hit_stock_count += 1;
    });
    return {
      rows,
      boards: Array.from(boardMap.values()),
      kindLabel,
      withHits: true,
      asof: data.asof || '',
      meta: {
        leader_count: data.leader_count,
        mid_count: data.mid_count,
        role_count: data.role_count,
        board_name: board.board_name,
        board_count: board.board_count,
      },
    };
  },

  sortExportRows(rows) {
    return rows.slice().sort((a, b) => {
      const bn = String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh');
      if (bn !== 0) return bn;
      const ra = String(a.board_role).toLowerCase() === 'leader' ? 0 : 1;
      const rb = String(b.board_role).toLowerCase() === 'leader' ? 0 : 1;
      if (ra !== rb) return ra - rb;
      const ca = Number(a.change_percent);
      const cb = Number(b.change_percent);
      const na = Number.isFinite(ca) ? ca : -Infinity;
      const nb = Number.isFinite(cb) ? cb : -Infinity;
      if (nb !== na) return nb - na;
      return String(a.code || '').localeCompare(String(b.code || ''));
    });
  },

  setSheetCols(ws, widths) {
    ws['!cols'] = widths.map((w) => ({ wch: w }));
  },

  freezeHeader(ws) {
    ws['!views'] = [{ state: 'frozen', ySplit: 1, topLeftCell: 'A2', activePane: 'bottomLeft', workbookViewId: 0 }];
  },

  async exportExcel() {
    let pack = this.buildRowsFromHitResult();
    let source = 'hit';
    if (!pack || !pack.rows.length) {
      pack = this.buildRowsFromRolesPanel();
      source = 'roles';
    }
    if (!pack.rows.length) {
      this.toast('暂无可导出的龙头/中军，请先选择板块加载角色，或点击「查询命中」', 'warning');
      return;
    }

    const btn = document.getElementById('lmExportExcelBtn');
    const prevText = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '导出中…';
    }

    try {
      if (typeof window.ensureSheetJsLoaded === 'function') {
        await window.ensureSheetJsLoaded();
      }
      if (typeof XLSX === 'undefined') {
        throw new Error('Excel 组件未加载，请刷新页面后重试');
      }

      const rows = this.sortExportRows(pack.rows);
      const withHits = !!pack.withHits;
      const kindLabel = pack.kindLabel || (this.boardKind === 'concept' ? '概念' : '行业');
      const today = new Date();
      const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      const timeStr = `${String(today.getHours()).padStart(2, '0')}${String(today.getMinutes()).padStart(2, '0')}`;

      const leaderN = rows.filter((r) => String(r.board_role).toLowerCase() === 'leader').length;
      const midN = rows.length - leaderN;
      const boardN = pack.boards.length;

      // ---- Sheet1: 概览 ----
      const overview = [
        ['龙头中军导出报告'],
        [],
        ['导出时间', `${dateStr} ${String(today.getHours()).padStart(2, '0')}:${String(today.getMinutes()).padStart(2, '0')}`],
        ['板块类型', kindLabel === '概念' ? '概念板块' : '行业板块'],
        ['数据来源', source === 'hit' ? '查询命中结果（含策略命中）' : '短线角色面板（龙头/中军）'],
        ['基准日', pack.asof || ''],
        ['板块数', boardN],
        ['股票数（去重前明细行）', rows.length],
        ['其中龙头', leaderN],
        ['其中中军', midN],
        [],
        ['说明', '「明细」按板块→角色（龙头优先）→涨跌幅降序排列；「板块汇总」按板块汇总龙头/中军数量。'],
      ];
      const wsOverview = XLSX.utils.aoa_to_sheet(overview);
      this.setSheetCols(wsOverview, [18, 48]);

      // ---- Sheet2: 明细 ----
      const detailHeaders = withHits
        ? [
            '序号',
            '板块类型',
            '板块名称',
            '板块代码',
            '角色',
            '股票代码',
            '股票名称',
            '涨跌幅(%)',
            '收盘价',
            'KDE支撑',
            'KDE压力',
            'GMS',
            'URT',
            'SBBR',
            'RPE',
            '命中数',
            '角色说明',
          ]
        : [
            '序号',
            '板块类型',
            '板块名称',
            '板块代码',
            '角色',
            '股票代码',
            '股票名称',
            '涨跌幅(%)',
            '板涨跌估(%)',
            '角色说明',
          ];
      const detailAoa = [detailHeaders];
      rows.forEach((r, idx) => {
        const codeCell = '\u2060' + String(r.code || '');
        if (withHits) {
          const hits = r.hits || {};
          detailAoa.push([
            idx + 1,
            r.board_kind || kindLabel,
            r.board_name || '',
            r.board_code || '',
            r.board_role_label || (String(r.board_role).toLowerCase() === 'leader' ? '龙头' : '中军'),
            codeCell,
            r.name || '',
            this.fmtPctNum(r.change_percent),
            r.last_close != null && Number.isFinite(Number(r.last_close))
              ? Math.round(Number(r.last_close) * 100) / 100
              : '',
            r.kde_support != null && Number.isFinite(Number(r.kde_support))
              ? Math.round(Number(r.kde_support) * 100) / 100
              : '',
            r.kde_resistance != null && Number.isFinite(Number(r.kde_resistance))
              ? Math.round(Number(r.kde_resistance) * 100) / 100
              : '',
            this.hitLabel(hits.gms),
            this.hitLabel(hits.urt),
            this.hitLabel(hits.sbbr),
            this.hitLabel(hits.rpe),
            r.hit_count !== '' && r.hit_count != null ? r.hit_count : 0,
            r.role_reason || '',
          ]);
        } else {
          detailAoa.push([
            idx + 1,
            r.board_kind || kindLabel,
            r.board_name || '',
            r.board_code || '',
            r.board_role_label || (String(r.board_role).toLowerCase() === 'leader' ? '龙头' : '中军'),
            codeCell,
            r.name || '',
            this.fmtPctNum(r.change_percent),
            this.fmtPctNum(r.board_change_percent_est),
            r.role_reason || '',
          ]);
        }
      });
      const wsDetail = XLSX.utils.aoa_to_sheet(detailAoa);
      this.freezeHeader(wsDetail);
      this.setSheetCols(
        wsDetail,
        withHits
          ? [6, 10, 18, 12, 8, 12, 12, 10, 10, 10, 10, 10, 10, 10, 10, 8, 28]
          : [6, 10, 18, 12, 8, 12, 12, 10, 12, 28]
      );

      // ---- Sheet3: 板块汇总 ----
      const sumHeaders = withHits
        ? ['序号', '板块名称', '板块代码', '龙头数', '中军数', '合计', '命中策略股数', '板涨跌估(%)']
        : ['序号', '板块名称', '板块代码', '龙头数', '中军数', '合计', '板涨跌估(%)'];
      const sumAoa = [sumHeaders];
      const boardsSorted = (pack.boards || []).slice().sort((a, b) =>
        String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh')
      );
      boardsSorted.forEach((b, idx) => {
        if (withHits) {
          sumAoa.push([
            idx + 1,
            b.board_name || '',
            b.board_code || '',
            b.leader_count || 0,
            b.mid_count || 0,
            b.stock_count || 0,
            b.hit_stock_count || 0,
            this.fmtPctNum(b.board_change_percent_est),
          ]);
        } else {
          sumAoa.push([
            idx + 1,
            b.board_name || '',
            b.board_code || '',
            b.leader_count || 0,
            b.mid_count || 0,
            b.stock_count || 0,
            this.fmtPctNum(b.board_change_percent_est),
          ]);
        }
      });
      // 合计行
      const totL = boardsSorted.reduce((s, b) => s + (b.leader_count || 0), 0);
      const totM = boardsSorted.reduce((s, b) => s + (b.mid_count || 0), 0);
      const totH = boardsSorted.reduce((s, b) => s + (b.hit_stock_count || 0), 0);
      if (withHits) {
        sumAoa.push(['合计', '', '', totL, totM, totL + totM, totH, '']);
      } else {
        sumAoa.push(['合计', '', '', totL, totM, totL + totM, '']);
      }
      const wsSum = XLSX.utils.aoa_to_sheet(sumAoa);
      this.freezeHeader(wsSum);
      this.setSheetCols(wsSum, withHits ? [6, 20, 14, 8, 8, 8, 12, 12] : [6, 20, 14, 8, 8, 8, 12]);

      // ---- Sheet4: 字段说明 ----
      const legend = [
        ['字段名', '说明'],
        ['板块类型', '行业板块或概念板块'],
        ['板块名称 / 板块代码', '同花顺口径板块标识'],
        ['角色', '龙头=板块短线领涨核心；中军=板块核心跟涨力量'],
        ['股票代码', 'A 股六位代码（文本格式，保留前导零）'],
        ['涨跌幅(%)', '相对前收盘涨跌幅，数值列便于筛选排序'],
        ['板涨跌估(%)', '板块强度估算（成分涨跌加权近似）'],
        ['收盘价 / KDE支撑 / KDE压力', '仅「查询命中」导出时提供；结构位与分析页同口径'],
        ['GMS / URT / SBBR / RPE', '仅「查询命中」导出时提供；空=未命中，有文案=命中标签'],
        ['命中数', '上述四策略命中个数合计'],
        ['角色说明', '角色识别原因摘要（若有）'],
        ['排列规则', '明细按：板块名称 → 角色（龙头优先）→ 涨跌幅降序 → 代码'],
      ];
      const wsLegend = XLSX.utils.aoa_to_sheet(legend);
      this.freezeHeader(wsLegend);
      this.setSheetCols(wsLegend, [22, 56]);

      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, wsOverview, '概览');
      XLSX.utils.book_append_sheet(wb, wsDetail, '明细');
      XLSX.utils.book_append_sheet(wb, wsSum, '板块汇总');
      XLSX.utils.book_append_sheet(wb, wsLegend, '字段说明');

      const kindTag = kindLabel === '概念' ? '概念' : '行业';
      const filename = `龙头中军_${kindTag}_${dateStr}_${timeStr}.xlsx`;
      XLSX.writeFile(wb, filename);
      this.toast(
        `已导出 ${rows.length} 条明细 / ${boardN} 个板块（${source === 'hit' ? '含策略命中' : '角色列表'}）`,
        'success'
      );
    } catch (e) {
      console.error(e);
      this.toast((e && e.message) || '导出失败', 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prevText || '导出 Excel';
      }
    }
  },

  esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },

  escAttr(s) {
    return this.esc(s).replace(/'/g, '&#39;');
  },
};

window.LeaderMidAnalysis = LeaderMidAnalysis;
