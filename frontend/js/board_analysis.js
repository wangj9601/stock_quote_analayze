/**
 * 分析频道 · 板块优先多策略工作台（板块多选，交互对齐龙头中军）
 */
const BoardAnalysis = {
  API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
  /** 板块分析「GMS 命中」最低总分（与后端 BOARD_GMS_HIT_MIN_SCORE 对齐） */
  GMS_HIT_MIN_SCORE: 70,
  boardKind: 'industry',
  industryCatalog: [],
  conceptCatalog: [],
  /** @type {string[]} */
  selectedBoardCodes: [],
  lastResult: null,
  running: false,
  catalogsLoaded: false,
  _pickerDraft: new Set(),
  _pickerStrongOnly: false,

  init() {
    this.bindEvents();
    this.loadCatalogs();
  },

  strongHelper() {
    return typeof BoardPickerStrong !== 'undefined' ? BoardPickerStrong : null;
  },

  includeNeutralSelected() {
    return !!document.getElementById('baIncludeNeutral')?.checked;
  },

  selectOpts() {
    return { includeNeutral: this.includeNeutralSelected() };
  },

  /**
   * 是否已明确判定为左侧或右侧买点（与后端 _gms_is_left_or_right_buy 对齐）。
   */
  isGmsLeftOrRightBuy(row) {
    if (!row) return false;
    if (row.left_buy_signal || row.right_buy_signal) return true;
    const bt = String(row.buy_type || '');
    return bt === '左侧' || bt === '右侧';
  },

  /**
   * 前端兜底：板块分析 GMS 命中须总分 ≥ GMS_HIT_MIN_SCORE 且明确左/右买点，并同步 total。
   * 不影响 URT/SBBR/RPE。
   */
  applyGmsHitScoreFloor(payload) {
    const strategies = payload && payload.strategies;
    if (!strategies || !strategies.gms) return payload;
    const thr = Number(this.GMS_HIT_MIN_SCORE) || 70;
    const block = strategies.gms;
    const items = Array.isArray(block.items) ? block.items : [];
    const kept = items.filter((row) => {
      if (!this.isGmsLeftOrRightBuy(row)) return false;
      const sc = this.asFloat(row && row.score_total);
      const sc2 = sc != null ? sc : this.asFloat(row && row.total_score);
      return sc2 != null && sc2 >= thr;
    });
    block.items = kept;
    block.total = kept.length;
    return payload;
  },

  bindEvents() {
    document.querySelectorAll('input[name="baBoardKind"]').forEach((el) => {
      el.addEventListener('change', () => {
        this.boardKind = el.value === 'concept' ? 'concept' : 'industry';
        this.selectedBoardCodes = [];
        this._pickerStrongOnly = false;
        const strongOnly = document.getElementById('baBoardPickerStrongOnly');
        if (strongOnly) strongOnly.checked = false;
        this.updateBoardSummary();
        this.clearMeta();
      });
    });
    const pickBtn = document.getElementById('baBoardPickBtn');
    if (pickBtn) {
      pickBtn.addEventListener('click', () => this.openBoardPicker());
    }
    const strongBtn = document.getElementById('baSelectStrongBtn');
    if (strongBtn) {
      strongBtn.addEventListener('click', () => this.selectStrongBoards());
    }
    const includeNeutral = document.getElementById('baIncludeNeutral');
    if (includeNeutral) {
      includeNeutral.addEventListener('change', () => {
        if (this._pickerStrongOnly) this.renderBoardPickerList();
      });
    }
    const runBtn = document.getElementById('baRunBtn');
    if (runBtn) {
      runBtn.addEventListener('click', () => this.runAnalysis());
    }
    const exportBtn = document.getElementById('baExportPdfBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.exportPdf());
    }
    const exportExcelBtn = document.getElementById('baExportExcelBtn');
    if (exportExcelBtn) {
      exportExcelBtn.addEventListener('click', () => this.exportExcel());
    }

    const overlay = document.getElementById('baBoardPickerModal');
    ['baBoardPickerClose', 'baBoardPickerCancel'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('click', () => this.hideBoardPicker());
    });
    if (overlay) {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) this.hideBoardPicker();
      });
    }
    const searchEl = document.getElementById('baBoardPickerSearch');
    if (searchEl) {
      searchEl.addEventListener('input', () => this.renderBoardPickerList());
    }
    const strongOnly = document.getElementById('baBoardPickerStrongOnly');
    if (strongOnly) {
      strongOnly.addEventListener('change', () => {
        this._pickerStrongOnly = !!strongOnly.checked;
        this.renderBoardPickerList();
      });
    }
    const selAll = document.getElementById('baBoardPickerSelectAll');
    if (selAll) {
      selAll.addEventListener('click', () => this.pickerSelectAllVisible());
    }
    const selStrong = document.getElementById('baBoardPickerSelectStrong');
    if (selStrong) {
      selStrong.addEventListener('click', () => this.pickerSelectStrongVisible());
    }
    const clearBtn = document.getElementById('baBoardPickerClear');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.pickerClearVisible());
    }
    const confirmBtn = document.getElementById('baBoardPickerConfirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => this.confirmBoardPicker());
    }
    const listEl = document.getElementById('baBoardPickerList');
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
    const el = document.getElementById('baBoardSummary');
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
    const titleEl = document.getElementById('baBoardPickerTitle');
    if (titleEl) {
      titleEl.textContent =
        this.boardKind === 'concept' ? '选择概念板块（可多选）' : '选择行业板块（可多选）';
    }
    const searchEl = document.getElementById('baBoardPickerSearch');
    if (searchEl) searchEl.value = '';
    const strongOnly = document.getElementById('baBoardPickerStrongOnly');
    if (strongOnly) {
      strongOnly.checked = !!this._pickerStrongOnly;
    }
    this.renderBoardPickerList();
    const overlay = document.getElementById('baBoardPickerModal');
    if (overlay) {
      overlay.style.display = 'flex';
      overlay.setAttribute('aria-hidden', 'false');
    }
  },

  hideBoardPicker() {
    const overlay = document.getElementById('baBoardPickerModal');
    if (overlay) {
      overlay.style.display = 'none';
      overlay.setAttribute('aria-hidden', 'true');
    }
  },

  updateBoardPickerCount(total, filtered, hasFilter) {
    const countEl = document.getElementById('baBoardPickerCount');
    if (!countEl) return;
    countEl.textContent = hasFilter
      ? `当前 ${filtered} / 共 ${total}`
      : `共 ${total} 个可选`;
  },

  visiblePickerBoards() {
    const q = (document.getElementById('baBoardPickerSearch')?.value || '').trim().toLowerCase();
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
    const listEl = document.getElementById('baBoardPickerList');
    if (!listEl) return;
    const helper = this.strongHelper();
    const all = this.catalog().slice();
    const total = all.length;
    const list = this.visiblePickerBoards();
    const hasFilter =
      !!((document.getElementById('baBoardPickerSearch')?.value || '').trim()) ||
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
    const listEl = document.getElementById('baBoardPickerList');
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
    const listEl = document.getElementById('baBoardPickerList');
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
    const listEl = document.getElementById('baBoardPickerList');
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
    if (this.selectedBoardCodes.length && window.BoardRolesPanel) {
      BoardRolesPanel.refresh({
        panelId: 'baRolesHost',
        boardType: this.boardKind,
        boardCodes: this.selectedBoardCodes,
        boardCodeSource: 'tonghuashun',
        visible: true,
        variant: 'shortline',
        showGmsWatchlistActions: true,
        gmsWatchlistPerm: 'channel.analyze.tab.board.btn.gms_watchlist',
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
    const meta = document.getElementById('baBoardMeta');
    if (meta) meta.innerHTML = '';
    if (window.BoardRolesPanel) {
      BoardRolesPanel.refresh({
        panelId: 'baRolesHost',
        boardType: this.boardKind,
        boardCodes: [],
        visible: false,
      });
    }
    const results = document.getElementById('baResults');
    if (results) {
      results.innerHTML = '<p class="ba-empty">选择板块并勾选策略后点击「开始分析」</p>';
    }
  },

  selectedStrategies() {
    return [...document.querySelectorAll('input[name="baStrategy"]:checked')].map((x) => x.value);
  },

  async runAnalysis() {
    if (this.running) return;
    const codes = this.selectedBoardCodes || [];
    if (!codes.length) {
      if (window.CommonUtils) CommonUtils.showToast('请先选择板块', 'warning');
      return;
    }
    const strategies = this.selectedStrategies();
    if (!strategies.length) {
      if (window.CommonUtils) CommonUtils.showToast('请至少勾选一个策略', 'warning');
      return;
    }
    const btn = document.getElementById('baRunBtn');
    this.running = true;
    if (btn) {
      btn.disabled = true;
      btn.textContent = '分析中…';
    }
    const results = document.getElementById('baResults');
    if (results) {
      results.innerHTML =
        '<p class="ba-empty">正在计算策略信号，请稍候（多板或成分较多时可能需数十秒）…</p>';
    }

    try {
      const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
      const first = this.boardByCode(codes[0]) || {};
      const q = new URLSearchParams({
        board_kind: this.boardKind,
        board_code_source: first.board_code_source || 'tonghuashun',
        strategies: strategies.join(','),
      });
      if (codes.length === 1) {
        q.set('board_code', codes[0]);
        q.set('board_name', first.board_name || '');
      } else {
        q.set('board_codes', codes.join(','));
      }
      const res = await fetchFn(`${this.API_BASE_URL}/api/analysis/board-signals?${q}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.message || data.detail || `分析失败 ${res.status}`);
      }
      this.lastResult = this.applyGmsHitScoreFloor(data.data || {});
      const board = this.lastResult.board || {};
      this.renderMeta(board);
      const roleCodes =
        Array.isArray(board.selected_board_codes) && board.selected_board_codes.length
          ? board.selected_board_codes
          : codes;
      if (window.BoardRolesPanel) {
        BoardRolesPanel.refresh({
          panelId: 'baRolesHost',
          boardType: this.boardKind,
          boardCodes: roleCodes,
          boardCodeSource: first.board_code_source || 'tonghuashun',
          visible: true,
          variant: 'shortline',
          data: board.multi_boards ? undefined : board,
          showGmsWatchlistActions: true,
          gmsWatchlistPerm: 'channel.analyze.tab.board.btn.gms_watchlist',
        });
      }
      this.renderResults(this.lastResult);
      if (window.CommonUtils) CommonUtils.showToast('板块分析完成', 'success');
    } catch (e) {
      console.error(e);
      if (results) results.innerHTML = `<p class="ba-empty ba-error">${this.esc(e.message || '分析失败')}</p>`;
      if (window.CommonUtils) CommonUtils.showToast(e.message || '分析失败', 'error');
    } finally {
      this.running = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = '开始分析';
      }
    }
  },

  renderMeta(board) {
    const meta = document.getElementById('baBoardMeta');
    if (!meta) return;
    const multi = !!board.multi_boards;
    const slope = board.sector_slope != null ? Number(board.sector_slope).toFixed(4) : '--';
    const env = board.board_env_label || '--';
    const memberN =
      board.stock_count != null ? board.stock_count : this.lastResult?.member_count ?? '--';
    if (multi) {
      const n = board.board_count != null ? board.board_count : (board.selected_board_codes || []).length;
      meta.innerHTML = `
        <div class="ba-meta-card">
          <strong>${this.esc(board.board_name || `已选 ${n} 个板块`)}</strong>
          <span>板块 ${n}</span>
          <span>成分并集 ${memberN}</span>
        </div>`;
      return;
    }
    meta.innerHTML = `
      <div class="ba-meta-card">
        <strong>${this.esc(board.board_name || '')}</strong>
        <span class="ba-muted">${this.esc(board.board_code || '')}</span>
        <span>斜率 ${slope}</span>
        <span class="ba-env">${this.esc(env)}</span>
        <span>成分 ${memberN}</span>
      </div>`;
  },

  defaultBoardLabel(payload) {
    const board = (payload && payload.board) || (this.lastResult && this.lastResult.board) || {};
    return board.board_name || board.board_code || '';
  },

  boardLabelForRow(row, fallback) {
    const fromRow = row && (row.board_labels || row.board_name);
    if (fromRow) return String(fromRow);
    if (Array.isArray(row && row.boards) && row.boards.length) {
      return row.boards
        .map((b) => b.board_name || b.board_code || '')
        .filter(Boolean)
        .join('、');
    }
    return fallback || '--';
  },

  renderResults(payload) {
    const host = document.getElementById('baResults');
    if (!host) return;
    const strategies = payload.strategies || {};
    const errors = payload.errors || {};
    const boardFallback = this.defaultBoardLabel(payload);
    const order = ['gms', 'urt', 'sbbr', 'rpe'];
    const labels = {
      gms: 'GMS 策略命中',
      urt: 'URT 策略命中',
      sbbr: 'SBBR 策略命中',
      rpe: 'RPE 策略命中',
    };
    let html = '';
    for (const key of order) {
      if (!strategies[key]) continue;
      const block = strategies[key];
      const err = errors[key];
      const blockCls =
        key === 'gms' ? 'ba-strategy-block ba-strategy-block--gms' : 'ba-strategy-block';
      html += `<section class="${blockCls}" data-strategy="${key}">
        <h3>${labels[key]} <span class="ba-muted">${block.total || 0}</span>
          ${err ? `<span class="ba-error">（${this.esc(err)}）</span>` : ''}
        </h3>
        ${this.renderTable(key, block.items || [], false, boardFallback)}
        ${
          key === 'sbbr' && (block.watch_items || []).length
            ? `<details class="ba-watch"><summary>筑底关注 ${block.watch_total || 0}</summary>${this.renderTable(key, block.watch_items || [], true, boardFallback)}</details>`
            : ''
        }
      </section>`;
    }
    if (!html) html = '<p class="ba-empty">无策略结果</p>';
    host.innerHTML = html;
    host.querySelectorAll('[data-observe]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const strategy = btn.getAttribute('data-strategy');
        const code = btn.getAttribute('data-code');
        const name = btn.getAttribute('data-name') || '';
        this.addObserve(strategy, code, name, btn);
      });
    });
  },

  renderTable(strategy, items, watchOnly, boardFallback) {
    if (!items.length) {
      return '<p class="ba-empty">暂无命中</p>';
    }
    const rows = items
      .map((row) => {
        const code = row.code || row.stock_code || '';
        const name = row.name || row.stock_name || '';
        const advice = row.trade_advice || {};
        const ref = advice.reference_levels || {};
        const roles = this.renderRoleTags(row.role_tags);
        const hit = this.hitLabel(strategy, row);
        const scoreDisp = this.scoreDisplay(strategy, row);
        const scoreTip = this.scoreHoverTip(strategy, row, hit);
        const lastClose = this.fmtPrice2(
          row.last_close ?? row.close ?? ref.last_close ?? row.latest_price
        );
        const buy = advice.buy_zone?.label || advice.summary?.split('；')[0] || '--';
        const sell =
          advice.stop_zone?.label ||
          (advice.sell_triggers || []).map((x) => x.label).join('；') ||
          '--';
        const st = row.structure && typeof row.structure === 'object' ? row.structure : {};
        const kdeS = this.fmtPrice2(
          advice.kde_support ?? row.nearest_support ?? st.nearest_support
        );
        const kdeR = this.fmtPrice2(
          advice.kde_resistance ?? row.nearest_resistance ?? st.nearest_resistance
        );
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
        const action = advice.action || 'watch';
        const tip = this.refHoverTip(ref, advice.summary);
        const boardName = this.boardLabelForRow(row, boardFallback);
        const scoreHint =
          scoreDisp && scoreDisp !== '--'
            ? `<span class="ba-hit-score">${this.esc(scoreDisp)}</span>`
            : '';
        const analysisHref = (window.StockTradeLink && window.StockTradeLink.buildHref)
            ? window.StockTradeLink.buildHref(code, name, { tab: 'analysis' })
            : `stock.html?tab=analysis&code=${encodeURIComponent(code)}${name ? `&name=${encodeURIComponent(name)}` : ''}`;
        return `<tr title="${this.escAttr(scoreTip)}">
          <td><a class="ba-stock-code-link" href="${this.escAttr(analysisHref)}" target="_blank" rel="noopener noreferrer" title="打开个股分析">${this.esc(code)}</a><div class="ba-muted">${this.esc(name)}</div></td>
          <td class="ba-boards" title="${this.escAttr(boardName)}">${this.esc(boardName || '--')}</td>
          <td class="ba-num">${lastClose}</td>
          <td class="ba-role-cell">${roles}</td>
          <td>
            <span class="ba-hit-wrap" title="${this.escAttr(scoreTip)}">
              <span class="ba-hit ba-hit--${this.escAttr(action)}">${this.esc(hit)}</span>
              ${scoreHint}
            </span>
          </td>
          <td class="ba-advice">${this.esc(buy)}</td>
          <td class="ba-advice">${this.esc(sell)}</td>
          <td class="ba-num">${kdeS}</td>
          <td class="ba-num">${kdeR}</td>
          <td class="ba-ref" title="${this.escAttr(tip)}">Fib ${fibS}/${fibR}<br/>Cam ${camS}/${camR}<br/>VP ${vpS}/${vpR}<br/>合 ${confS}/${confR}</td>
          <td>
            <button type="button" class="btn btn-secondary btn-sm" data-observe
              data-strategy="${this.escAttr(strategy)}" data-code="${this.escAttr(code)}" data-name="${this.escAttr(name)}"
              data-perm="channel.analyze.tab.board.btn.observe"
              ${watchOnly ? 'title="筑底关注也可加入观察"' : ''}>加入观察</button>
          </td>
        </tr>`;
      })
      .join('');
    return `<div class="ba-table-wrap"><table class="ba-table">
      <thead><tr>
        <th>股票</th><th>板块名</th><th>最新收盘</th><th>角色</th><th>命中</th><th>买点建议</th><th>卖点/防守</th>
        <th>KDE结构支撑</th><th>KDE结构阻力</th><th>参考价 Fib/Cam/VP/合</th><th>操作</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  },

  fmtPrice2(v) {
    if (v == null || v === '' || isNaN(Number(v))) return '--';
    return Number(v).toFixed(2);
  },

  /** 表格「角色」列：龙头红底 / 中军橙边，对齐短线角色标签 */
  renderRoleTags(tags) {
    const list = Array.isArray(tags) ? tags : [];
    if (!list.length) return '<span class="ba-muted">--</span>';
    return list
      .map((t) => {
        const id = typeof t === 'string' ? t : t.id || t.label || '';
        const label = typeof t === 'string' ? t : t.label || t.id || '';
        const sid = String(id).toLowerCase();
        const text = String(label || id);
        let cls = 'ba-role-pill ba-role-pill--sm';
        if (sid === 'leader' || text === '龙头') cls += ' ba-role-pill--leader';
        else if (sid === 'mid' || sid === 'board_mid' || text === '中军') cls += ' ba-role-pill--mid';
        else cls += ' ba-role-pill--other';
        return `<span class="${cls}">${this.esc(text)}</span>`;
      })
      .join(' ');
  },

  refHoverTip(ref, summary) {
    const lines = [];
    if (summary) lines.push(String(summary));
    const fib = ref && ref.fibonacci;
    if (fib) {
      const method = fib.anchor_method === 'zigzag_fractal' ? 'ZigZag' : fib.anchor_method || '';
      if (fib.swing_high != null || fib.swing_low != null) {
        const hi = `${this.fmtPrice2(fib.swing_high)}${fib.swing_high_date ? `（${fib.swing_high_date}）` : ''}`;
        const lo = `${this.fmtPrice2(fib.swing_low)}${fib.swing_low_date ? `（${fib.swing_low_date}）` : ''}`;
        lines.push(`Fib锚点${method ? `(${method})` : ''}: 高点 ${hi} / 低点 ${lo}`);
      }
      if (fib.depth_pct != null) {
        lines.push(`ZigZag深度: ${(Number(fib.depth_pct) * 100).toFixed(1)}%`);
      }
      if (fib.bar_span != null || fib.min_swing_bars != null) {
        lines.push(
          `ZigZag波段跨度: ${fib.bar_span != null ? fib.bar_span : '--'} 根` +
            (fib.min_swing_bars != null ? `（下限 ${fib.min_swing_bars}）` : '') +
            (fib.skipped_short_leg ? '；已跳过过短腿' : '')
        );
      }
      if (Array.isArray(fib.retracements) && fib.retracements.length) {
        const parts = fib.retracements.map(
          (x) => `${x.ratio}=${this.fmtPrice2(x.price)}`
        );
        lines.push('Fib回撤: ' + parts.join(', '));
      }
      if (Array.isArray(fib.extensions) && fib.extensions.length) {
        lines.push(
          'Fib扩展: ' + fib.extensions.map((x) => `${x.ratio}=${this.fmtPrice2(x.price)}`).join(', ')
        );
      }
    }
    const cam = ref && ref.camarilla;
    if (cam) {
      lines.push(
        `Camarilla: R4=${this.fmtPrice2(cam.R4)} R3=${this.fmtPrice2(cam.R3)} R2=${this.fmtPrice2(cam.R2)} R1=${this.fmtPrice2(cam.R1)}` +
          ` S1=${this.fmtPrice2(cam.S1)} S2=${this.fmtPrice2(cam.S2)} S3=${this.fmtPrice2(cam.S3)} S4=${this.fmtPrice2(cam.S4)}`
      );
    }
    const p = ref && ref.pivot;
    if (p && p.P != null) {
      lines.push(
        `经典Pivot: P=${this.fmtPrice2(p.P)} R1=${this.fmtPrice2(p.R1)} R2=${this.fmtPrice2(p.R2)} R3=${this.fmtPrice2(p.R3)} S1=${this.fmtPrice2(p.S1)} S2=${this.fmtPrice2(p.S2)} S3=${this.fmtPrice2(p.S3)}`
      );
    }
    const ap = ref && ref.atr_pivot;
    if (ap && ap.atr != null) {
      lines.push(
        `ATR带: ATR=${this.fmtPrice2(ap.atr)} R1=${this.fmtPrice2(ap.R1)} S1=${this.fmtPrice2(ap.S1)} R2=${this.fmtPrice2(ap.R2)} S2=${this.fmtPrice2(ap.S2)}`
      );
    }
    const vp = ref && ref.volume_profile;
    if (vp && vp.ok) {
      lines.push(
        `VP: POC=${this.fmtPrice2(vp.poc)} VAL=${this.fmtPrice2(vp.val)} VAH=${this.fmtPrice2(vp.vah)}` +
          ` 最近支撑=${this.fmtPrice2(ref.nearest_vp_support ?? vp.nearest_support)}` +
          ` 最近压力=${this.fmtPrice2(ref.nearest_vp_resistance ?? vp.nearest_resistance)}` +
          (vp.lookback != null ? `（回看${vp.lookback}日）` : '')
      );
    }
    const conf = ref && ref.confluence_zones;
    if (conf && conf.ok) {
      const fmtZ = (z) =>
        z
          ? `${this.fmtPrice2(z.center)}[${this.fmtPrice2(z.low)}–${this.fmtPrice2(z.high)}]·${(z.sources || []).join('+')}`
          : '--';
      lines.push(
        `共振带: 支撑 ${fmtZ(conf.nearest_support_zone)} / 压力 ${fmtZ(conf.nearest_resistance_zone)}`
      );
    }
    return lines.join('\n') || '暂无参考价';
  },

  hitLabel(strategy, row) {
    if (strategy === 'gms') {
      return row.buy_type || (row.left_buy_signal ? '左侧' : row.right_buy_signal ? '右侧' : 'GMS');
    }
    if (strategy === 'urt') return row.buy_signal ? '买点' : '--';
    if (strategy === 'sbbr') {
      if (row.entry_signal) return '入场';
      if (row.bottom_matched) return '筑底';
      return 'SBBR';
    }
    if (strategy === 'rpe') {
      const t = row.signal_type || '';
      if (row.watch_only || t === 'lead') return '领涨观察';
      if (row.entry_signal || t === 'catch_up') return '补涨';
      return t || 'RPE';
    }
    return strategy;
  },

  asFloat(v) {
    if (v == null || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  },

  pickScore(strategy, row) {
    if (!row) return null;
    if (strategy === 'gms') return this.asFloat(row.score_total);
    if (strategy === 'urt') {
      for (const k of ['score_total', 'total_score', 'score']) {
        const sc = this.asFloat(row[k]);
        if (sc != null) return sc;
      }
      return null;
    }
    if (strategy === 'sbbr') return this.asFloat(row.volume_ratio);
    if (strategy === 'rpe') {
      for (const k of ['z_score', 'zscore', 'score', 'relative_z']) {
        const sc = this.asFloat(row[k]);
        if (sc != null) return sc;
      }
      return null;
    }
    return null;
  },

  scoreDisplay(strategy, row) {
    const score = this.pickScore(strategy, row);
    if (strategy === 'gms') return score != null ? `总分 ${score.toFixed(1)}` : '--';
    if (strategy === 'urt') return score != null ? `得分 ${score.toFixed(1)}` : '--';
    if (strategy === 'sbbr') {
      const tags = [];
      if (row) {
        if (row.size_ok) tags.push('做小✓');
        else if (row.size_ok === false) tags.push('做小✗');
        if (row.bottom_matched) tags.push('筑底✓');
        if (row.entry_signal) tags.push('入场✓');
        if (score != null) tags.push(`量比 ${score.toFixed(2)}`);
      }
      return tags.length ? tags.join(' · ') : '--';
    }
    if (strategy === 'rpe') {
      if (score != null) return `Z=${score.toFixed(2)}`;
      if (row && row.signal_type) return String(row.signal_type);
      return '--';
    }
    return score != null ? String(score) : '--';
  },

  scoreHoverTip(strategy, row, hitLabel) {
    const lines = [];
    if (hitLabel) lines.push(`命中：${hitLabel}`);
    const score = this.pickScore(strategy, row);
    if (strategy === 'gms') {
      if (score != null) lines.push(`GMS 总分：${score.toFixed(1)}`);
      const acc = this.asFloat(row && row.score_accumulation);
      const mom = this.asFloat(row && row.score_momentum);
      if (acc != null) lines.push(`蓄势分：${acc.toFixed(1)}`);
      if (mom != null) lines.push(`动量分：${mom.toFixed(1)}`);
      const strength = row && row.signal_strength;
      if (strength != null && strength !== '') lines.push(`信号强度：${strength}`);
    } else if (strategy === 'urt') {
      if (score != null) lines.push(`URT 得分：${score.toFixed(1)}`);
    } else if (strategy === 'sbbr') {
      lines.push(this.scoreDisplay('sbbr', row));
    } else if (strategy === 'rpe') {
      lines.push(this.scoreDisplay('rpe', row));
    }
    if (lines.length <= 1 && score == null) lines.push('暂无得分字段');
    return lines.filter(Boolean).join('\n');
  },

  pdfFilename() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `板块分析_${y}${m}${day}.pdf`;
  },

  roleTextForPdf(row) {
    const tags = Array.isArray(row.role_tags) ? row.role_tags : [];
    if (!tags.length) return '--';
    return tags
      .map((t) => (typeof t === 'string' ? t : t.label || t.id || ''))
      .filter(Boolean)
      .join('/');
  },

  buildPdfStrategyTable(strategy, items, boardFallback) {
    if (!items.length) return '<p class="ba-pdf-empty">暂无命中</p>';
    const rows = items
      .map((row) => {
        const code = row.code || row.stock_code || '';
        const name = row.name || row.stock_name || '';
        const boardName = this.boardLabelForRow(row, boardFallback);
        const hit = this.hitLabel(strategy, row);
        const score = this.scoreDisplay(strategy, row);
        const lastClose = this.fmtPrice2(
          row.last_close ?? row.close ?? row.trade_advice?.reference_levels?.last_close ?? row.latest_price
        );
        const roles = this.roleTextForPdf(row);
        const advice = row.trade_advice || {};
        const buy = advice.buy_zone?.label || advice.summary?.split('；')[0] || '--';
        const sell =
          advice.stop_zone?.label ||
          (advice.sell_triggers || []).map((x) => x.label).join('；') ||
          '--';
        return `<tr>
          <td>${this.esc(code)}<br/><span class="m">${this.esc(name)}</span></td>
          <td>${this.esc(boardName || '--')}</td>
          <td>${this.esc(hit)}</td>
          <td>${this.esc(score)}</td>
          <td>${lastClose}</td>
          <td>${this.esc(roles)}</td>
          <td>${this.esc(buy)}</td>
          <td>${this.esc(sell)}</td>
        </tr>`;
      })
      .join('');
    return `<table>
      <thead><tr>
        <th>股票</th><th>板块名</th><th>命中</th><th>得分</th><th>最新收盘</th><th>角色</th><th>买点建议</th><th>卖点/防守</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  },

  buildPdfHtml() {
    const payload = this.lastResult || {};
    const board = payload.board || {};
    const boardFallback = this.defaultBoardLabel(payload);
    const kindLabel = this.boardKind === 'concept' ? '概念板块' : '行业板块';
    const strategies = payload.strategies || {};
    const errors = payload.errors || {};
    const order = ['gms', 'urt', 'sbbr', 'rpe'];
    const labels = { gms: 'GMS', urt: 'URT', sbbr: 'SBBR', rpe: 'RPE' };
    const metaParts = [];
    metaParts.push(`类型：${kindLabel}`);
    if (board.multi_boards) {
      const n = board.board_count != null ? board.board_count : (board.selected_board_codes || []).length;
      metaParts.push(`已选板块：${n}`);
    } else {
      metaParts.push(`板块：${board.board_name || board.board_code || '--'}`);
      if (board.board_code) metaParts.push(`代码：${board.board_code}`);
    }
    const memberN =
      board.stock_count != null ? board.stock_count : payload.member_count != null ? payload.member_count : '--';
    metaParts.push(`成分池：${memberN}`);
    if (board.board_env_label) metaParts.push(`环境：${board.board_env_label}`);
    if (payload.asof) metaParts.push(`分析时间：${payload.asof}`);

    const selectedNames = (this.selectedBoardCodes || [])
      .map((c) => {
        const b = this.boardByCode(c);
        return b ? `${b.board_name || c}（${c}）` : c;
      })
      .join('、');

    const rolesHost = document.getElementById('baRolesHost');
    let rolesHtml = '';
    if (rolesHost && rolesHost.innerHTML.trim()) {
      // 纯文本友好：去掉链接，保留文字
      const clone = rolesHost.cloneNode(true);
      clone.querySelectorAll('a').forEach((a) => {
        const span = document.createElement('span');
        span.textContent = a.textContent || '';
        a.replaceWith(span);
      });
      rolesHtml = clone.innerHTML;
    } else {
      rolesHtml = '<p class="ba-pdf-empty">暂无短线角色</p>';
    }

    let strategyHtml = '';
    for (const key of order) {
      if (!strategies[key]) continue;
      const block = strategies[key];
      const err = errors[key];
      strategyHtml += `<section class="sec">
        <h2>${labels[key]} 策略命中（${block.total || 0}）
          ${err ? `<span class="err">（${this.esc(err)}）</span>` : ''}
        </h2>
        ${this.buildPdfStrategyTable(key, block.items || [], boardFallback)}
        ${
          key === 'sbbr' && (block.watch_items || []).length
            ? `<h3>筑底关注（${block.watch_total || 0}）</h3>${this.buildPdfStrategyTable(key, block.watch_items || [], boardFallback)}`
            : ''
        }
      </section>`;
    }
    if (!strategyHtml) strategyHtml = '<p class="ba-pdf-empty">无策略结果</p>';

    const title = this.pdfFilename().replace(/\.pdf$/i, '');
    return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"/>
<title>${this.esc(title)}</title>
<style>
  @page { size: A4 landscape; margin: 10mm; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    color: #0f172a;
    font-size: 11px;
    line-height: 1.45;
    padding: 12px 16px;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  h1 { font-size: 18px; margin: 0 0 8px; }
  h2 { font-size: 13px; margin: 14px 0 6px; color: #1e40af; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px; }
  h3 { font-size: 12px; margin: 10px 0 6px; color: #475569; }
  .meta { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; line-height: 1.55; }
  .meta div { margin: 2px 0; }
  .roles { border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; }
  .roles .ba-short-roles { margin-bottom: 6px; }
  .roles .ba-role-pill { display: inline-block; margin: 2px 4px 2px 0; padding: 1px 6px; border: 1px solid #ddd; border-radius: 3px; }
  .roles .ba-short-roles-board { font-weight: 700; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 8px; table-layout: fixed; font-size: 10px; }
  th, td { border: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; word-wrap: break-word; overflow-wrap: anywhere; }
  th { background: #f1f5f9; font-weight: 600; }
  .m { color: #64748b; font-size: 10px; }
  .err { color: #b91c1c; font-weight: normal; }
  .ba-pdf-empty { color: #94a3b8; }
  .sec { page-break-inside: avoid; }
  .print-hint {
    margin: 0 0 10px;
    padding: 8px 10px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    color: #1e3a8a;
    font-size: 12px;
  }
  @media print {
    body { padding: 0; }
    .print-hint { display: none !important; }
    .sec { page-break-inside: auto; }
    tr { page-break-inside: avoid; }
    thead { display: table-header-group; }
  }
</style></head><body>
  <p class="print-hint">请在打印对话框中选择「另存为 PDF / Microsoft Print to PDF」，纸张建议横向 A4。关闭本页不影响分析结果。</p>
  <h1>板块分析结果</h1>
  <div class="meta">
    ${metaParts.map((p) => `<div>${this.esc(p)}</div>`).join('')}
    ${selectedNames ? `<div>所选：${this.esc(selectedNames)}</div>` : ''}
  </div>
  <h2>各板短线角色</h2>
  <div class="roles">${rolesHtml}</div>
  ${strategyHtml}
</body></html>`;
  },

  /**
   * 兜底：新窗口打开完整 HTML，走系统打印 →「另存为 PDF」。
   * 仅在结构化 jsPDF 导出失败时使用。
   */
  exportViaPrint(html, filename) {
    const w = window.open('', '_blank');
    if (!w) {
      if (window.CommonUtils) {
        CommonUtils.showToast('浏览器拦截了弹窗，请允许后重试，再点「导出 PDF」', 'warning');
      }
      return false;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.document.title = filename.replace(/\.pdf$/i, '');
    // 等样式与字体就绪后再调打印，减少空白首页
    const triggerPrint = () => {
      try {
        w.focus();
        w.print();
      } catch (e) {
        console.warn(e);
      }
    };
    if (w.document.fonts && w.document.fonts.ready) {
      w.document.fonts.ready.then(() => setTimeout(triggerPrint, 80)).catch(() => setTimeout(triggerPrint, 350));
    } else {
      setTimeout(triggerPrint, 350);
    }
    return true;
  },

  async exportPdf() {
    if (!this.lastResult || !this.lastResult.strategies) {
      if (window.CommonUtils) CommonUtils.showToast('请先完成板块分析再导出', 'warning');
      return;
    }
    const btn = document.getElementById('baExportPdfBtn');
    const filename = this.pdfFilename();
    if (btn) {
      btn.disabled = true;
      btn.classList.add('ba-exporting');
      btn.textContent = '导出中…';
    }
    try {
      if (!window.BoardAnalysisPdf || typeof BoardAnalysisPdf.exportFromHost !== 'function') {
        throw new Error('PDF 导出模块未加载');
      }
      const saved = await BoardAnalysisPdf.exportFromHost(this);
      if (window.CommonUtils) CommonUtils.showToast(`已导出 ${saved || filename}`, 'success');
    } catch (e) {
      console.warn('结构化 PDF 导出失败，回退打印', e);
      const html = this.buildPdfHtml();
      const ok = this.exportViaPrint(html, filename);
      const reason = (e && e.message) || String(e || '未知错误');
      if (window.CommonUtils) {
        if (ok) {
          CommonUtils.showToast(`结构化导出失败（${reason}），已打开打印预览作兜底`, 'warning');
        } else {
          CommonUtils.showToast(`导出失败：${reason}`, 'error');
        }
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.classList.remove('ba-exporting');
        btn.textContent = '导出 PDF';
      }
    }
  },

  excelFilename() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const kindTag = this.boardKind === 'concept' ? '概念' : '行业';
    return `板块分析_${kindTag}_${y}-${m}-${day}_${hh}${mm}.xlsx`;
  },

  excelNum(v) {
    if (v == null || v === '' || isNaN(Number(v))) return '';
    return Math.round(Number(v) * 100) / 100;
  },

  excelCode(code) {
    return '\u2060' + String(code || '');
  },

  setSheetCols(ws, widths) {
    ws['!cols'] = widths.map((w) => ({ wch: w }));
  },

  freezeHeader(ws) {
    ws['!views'] = [{ state: 'frozen', ySplit: 1, topLeftCell: 'A2', activePane: 'bottomLeft', workbookViewId: 0 }];
  },

  flattenExportRow(strategy, row, listType, boardFallback) {
    const code = row.code || row.stock_code || '';
    const name = row.name || row.stock_name || '';
    const advice = row.trade_advice || {};
    const ref = advice.reference_levels || {};
    const st = row.structure && typeof row.structure === 'object' ? row.structure : {};
    const vp = ref.volume_profile && typeof ref.volume_profile === 'object' ? ref.volume_profile : {};
    const conf = ref.confluence_zones && typeof ref.confluence_zones === 'object' ? ref.confluence_zones : {};
    const boards = Array.isArray(row.boards) ? row.boards : [];
    const score = this.pickScore(strategy, row);
    const labels = { gms: 'GMS', urt: 'URT', sbbr: 'SBBR', rpe: 'RPE' };
    return {
      strategy,
      strategyLabel: labels[strategy] || String(strategy).toUpperCase(),
      listType,
      code,
      name,
      board_name: this.boardLabelForRow(row, boardFallback),
      boards,
      last_close: this.excelNum(
        row.last_close ?? row.close ?? ref.last_close ?? row.latest_price
      ),
      roles: this.roleTextForPdf(row),
      hit: this.hitLabel(strategy, row),
      score_text: this.scoreDisplay(strategy, row),
      score: score != null ? Math.round(score * 100) / 100 : '',
      buy: advice.buy_zone?.label || (advice.summary || '').split('；')[0] || '',
      sell:
        advice.stop_zone?.label ||
        (advice.sell_triggers || []).map((x) => x.label).join('；') ||
        '',
      kde_s: this.excelNum(advice.kde_support ?? row.nearest_support ?? st.nearest_support),
      kde_r: this.excelNum(advice.kde_resistance ?? row.nearest_resistance ?? st.nearest_resistance),
      fib_s: this.excelNum(ref.nearest_fib_support),
      fib_r: this.excelNum(ref.nearest_fib_resistance),
      cam_s: this.excelNum(ref.nearest_cam_support ?? ref.camarilla?.nearest_support),
      cam_r: this.excelNum(ref.nearest_cam_resistance ?? ref.camarilla?.nearest_resistance),
      vp_s: this.excelNum(ref.nearest_vp_support ?? vp.nearest_support ?? vp.val),
      vp_r: this.excelNum(ref.nearest_vp_resistance ?? vp.nearest_resistance ?? vp.vah),
      conf_s: this.excelNum(ref.nearest_confluence_support ?? conf.nearest_support_zone?.center),
      conf_r: this.excelNum(ref.nearest_confluence_resistance ?? conf.nearest_resistance_zone?.center),
      summary: advice.summary || '',
    };
  },

  collectExcelRows(payload) {
    const strategies = (payload && payload.strategies) || {};
    const boardFallback = this.defaultBoardLabel(payload);
    const order = ['gms', 'urt', 'sbbr', 'rpe'];
    const rows = [];
    for (const key of order) {
      if (!strategies[key]) continue;
      const block = strategies[key];
      (block.items || []).forEach((row) => {
        rows.push(this.flattenExportRow(key, row, '命中', boardFallback));
      });
      if (key === 'sbbr') {
        (block.watch_items || []).forEach((row) => {
          rows.push(this.flattenExportRow(key, row, '筑底关注', boardFallback));
        });
      }
    }
    return rows;
  },

  excelDetailHeaders() {
    return [
      '序号',
      '策略',
      '名单类型',
      '股票代码',
      '股票名称',
      '板块名',
      '最新收盘',
      '角色',
      '命中',
      '得分说明',
      '得分数',
      '买点建议',
      '卖点/防守',
      'KDE结构支撑',
      'KDE结构阻力',
      'Fib支撑',
      'Fib阻力',
      'Cam支撑',
      'Cam阻力',
      'VP支撑',
      'VP阻力',
      '共振支撑',
      '共振阻力',
      '建议摘要',
    ];
  },

  excelDetailWidths() {
    return [6, 8, 10, 12, 12, 22, 10, 10, 10, 18, 10, 22, 22, 12, 12, 10, 10, 10, 10, 10, 10, 10, 10, 36];
  },

  excelRowToAoa(r, idx) {
    return [
      idx + 1,
      r.strategyLabel,
      r.listType,
      this.excelCode(r.code),
      r.name || '',
      r.board_name || '',
      r.last_close,
      r.roles && r.roles !== '--' ? r.roles : '',
      r.hit && r.hit !== '--' ? r.hit : '',
      r.score_text && r.score_text !== '--' ? r.score_text : '',
      r.score,
      r.buy || '',
      r.sell || '',
      r.kde_s,
      r.kde_r,
      r.fib_s,
      r.fib_r,
      r.cam_s,
      r.cam_r,
      r.vp_s,
      r.vp_r,
      r.conf_s,
      r.conf_r,
      r.summary || '',
    ];
  },

  buildExcelBoardSummary(rows) {
    const map = new Map();
    const ensure = (code, name) => {
      const key = String(code || name || '').trim() || '--';
      if (!map.has(key)) {
        map.set(key, {
          board_code: code || '',
          board_name: name || code || '',
          gms: 0,
          urt: 0,
          sbbr: 0,
          sbbr_watch: 0,
          rpe: 0,
        });
      }
      return map.get(key);
    };
    (this.selectedBoardCodes || []).forEach((c) => {
      const b = this.boardByCode(c);
      ensure(c, b ? b.board_name || c : c);
    });
    rows.forEach((r) => {
      const boards = Array.isArray(r.boards) && r.boards.length
        ? r.boards
        : [{ board_name: r.board_name, board_code: '' }];
      boards.forEach((b) => {
        const rec = ensure(b.board_code || '', b.board_name || b.board_code || r.board_name || '');
        if (r.listType === '筑底关注') rec.sbbr_watch += 1;
        else if (r.strategy === 'gms') rec.gms += 1;
        else if (r.strategy === 'urt') rec.urt += 1;
        else if (r.strategy === 'sbbr') rec.sbbr += 1;
        else if (r.strategy === 'rpe') rec.rpe += 1;
      });
    });
    return [...map.values()].sort((a, b) =>
      String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh')
    );
  },

  async exportExcel() {
    if (!this.lastResult || !this.lastResult.strategies) {
      if (window.CommonUtils) CommonUtils.showToast('请先完成板块分析再导出', 'warning');
      return;
    }
    const btn = document.getElementById('baExportExcelBtn');
    const prevText = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.classList.add('ba-exporting');
      btn.textContent = '导出中…';
    }
    try {
      if (typeof window.ensureSheetJsLoaded === 'function') {
        await window.ensureSheetJsLoaded();
      }
      if (typeof XLSX === 'undefined') {
        throw new Error('Excel 组件未加载，请刷新页面后重试');
      }

      const payload = this.lastResult;
      const board = payload.board || {};
      const rows = this.collectExcelRows(payload);
      const kindLabel = this.boardKind === 'concept' ? '概念板块' : '行业板块';
      const today = new Date();
      const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      const timeStr = `${String(today.getHours()).padStart(2, '0')}:${String(today.getMinutes()).padStart(2, '0')}`;
      const selectedNames = (this.selectedBoardCodes || [])
        .map((c) => {
          const b = this.boardByCode(c);
          return b ? `${b.board_name || c}（${c}）` : c;
        })
        .join('、');
      const memberN =
        board.stock_count != null
          ? board.stock_count
          : payload.member_count != null
            ? payload.member_count
            : '';
      const strategyCounts = ['gms', 'urt', 'sbbr', 'rpe']
        .filter((k) => payload.strategies && payload.strategies[k])
        .map((k) => {
          const block = payload.strategies[k];
          const n = (block.items || []).length;
          const w = k === 'sbbr' ? (block.watch_items || []).length : 0;
          return w ? `${k.toUpperCase()} ${n}（筑底关注 ${w}）` : `${k.toUpperCase()} ${n}`;
        })
        .join('；');

      const overview = [
        ['板块分析结果'],
        [],
        ['导出时间', `${dateStr} ${timeStr}`],
        ['板块类型', kindLabel],
        ['已选板块', selectedNames || board.board_name || ''],
        ['板块数', board.board_count != null ? board.board_count : (this.selectedBoardCodes || []).length],
        ['成分池', memberN],
        ['板环境', board.board_env_label || ''],
        ['分析时间', payload.asof || ''],
        ['明细行数', rows.length],
        ['各策略命中', strategyCounts],
        [],
        ['说明', '「明细」含已勾选策略的命中股；SBBR 筑底关注单独标注。价格与结构位与页面表格同口径，便于筛选排序。'],
      ];
      const wsOverview = XLSX.utils.aoa_to_sheet(overview);
      this.setSheetCols(wsOverview, [16, 72]);

      const detailAoa = [this.excelDetailHeaders()];
      rows.forEach((r, idx) => detailAoa.push(this.excelRowToAoa(r, idx)));
      const wsDetail = XLSX.utils.aoa_to_sheet(detailAoa);
      this.freezeHeader(wsDetail);
      this.setSheetCols(wsDetail, this.excelDetailWidths());

      const boards = this.buildExcelBoardSummary(rows);
      const sumAoa = [
        ['序号', '板块名称', '板块代码', 'GMS命中', 'URT命中', 'SBBR命中', 'SBBR筑底关注', 'RPE命中', '合计'],
      ];
      let totG = 0;
      let totU = 0;
      let totS = 0;
      let totW = 0;
      let totR = 0;
      boards.forEach((b, idx) => {
        const hitSum = (b.gms || 0) + (b.urt || 0) + (b.sbbr || 0) + (b.rpe || 0);
        totG += b.gms || 0;
        totU += b.urt || 0;
        totS += b.sbbr || 0;
        totW += b.sbbr_watch || 0;
        totR += b.rpe || 0;
        sumAoa.push([
          idx + 1,
          b.board_name || '',
          b.board_code || '',
          b.gms || 0,
          b.urt || 0,
          b.sbbr || 0,
          b.sbbr_watch || 0,
          b.rpe || 0,
          hitSum,
        ]);
      });
      sumAoa.push(['合计', '', '', totG, totU, totS, totW, totR, totG + totU + totS + totR]);
      const wsSum = XLSX.utils.aoa_to_sheet(sumAoa);
      this.freezeHeader(wsSum);
      this.setSheetCols(wsSum, [6, 20, 14, 10, 10, 10, 14, 10, 8]);

      const legend = [
        ['字段名', '说明'],
        ['策略', 'GMS / URT / SBBR / RPE，与页面勾选及命中分区一致'],
        ['名单类型', '命中=策略信号；筑底关注=SBBR 尚未入场的筑底观察'],
        ['股票代码', 'A 股代码（文本格式，保留前导零）'],
        ['板块名', '成分所属板块；多板并集时可能为多个名称'],
        ['最新收盘 / 结构位 / 参考价', '与页面表格同口径；空表示当时无有效数值'],
        ['角色', '短线龙头/中军等标签'],
        ['命中 / 得分说明 / 得分数', '命中标签与页面一致；得分数便于排序（GMS/URT 为分，SBBR 为量比，RPE 为 Z）'],
        ['买点建议 / 卖点/防守', '以策略与 KDE/箱体为主'],
        ['Fib / Cam / VP / 共振', '参考价，不作为主买卖依据'],
        ['板块汇总合计', '同一股票若同属多板，会在各板分别计数'],
      ];
      const wsLegend = XLSX.utils.aoa_to_sheet(legend);
      this.freezeHeader(wsLegend);
      this.setSheetCols(wsLegend, [22, 64]);

      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, wsOverview, '概览');
      XLSX.utils.book_append_sheet(wb, wsDetail, '明细');
      XLSX.utils.book_append_sheet(wb, wsSum, '板块汇总');
      XLSX.utils.book_append_sheet(wb, wsLegend, '字段说明');

      const filename = this.excelFilename();
      XLSX.writeFile(wb, filename);
      if (window.CommonUtils) {
        CommonUtils.showToast(`已导出 ${rows.length} 条明细（${filename}）`, 'success');
      }
    } catch (e) {
      console.error(e);
      if (window.CommonUtils) CommonUtils.showToast((e && e.message) || '导出失败', 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.classList.remove('ba-exporting');
        btn.textContent = prevText || '导出 Excel';
      }
    }
  },

  async addObserve(strategy, code, name, btn) {
    if (!code) return;
    const items = this.findRow(strategy, code);
    const snap = items ? { ...items, trade_advice: items.trade_advice } : {};
    const advice = snap.trade_advice || {};
    try {
      const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
      const res = await fetchFn(`${this.API_BASE_URL}/api/analysis/board-signals/observe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy,
          code,
          name,
          market: 'CN',
          signal_date: snap.search_date || snap.signal_date || snap.date || null,
          note: advice.summary || '',
          snapshot: snap,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.success === false) {
        throw new Error(data.message || data.detail || `加入失败 ${res.status}`);
      }
      if (btn) {
        btn.disabled = true;
        btn.textContent = data.duplicated ? '已观察' : '已加入';
      }
      if (window.CommonUtils) {
        CommonUtils.showToast(data.duplicated ? '已在观察池中' : '已加入交易观察', 'success');
      }
    } catch (e) {
      if (window.CommonUtils) CommonUtils.showToast(e.message || '加入观察失败', 'error');
    }
  },

  findRow(strategy, code) {
    const block = (this.lastResult && this.lastResult.strategies && this.lastResult.strategies[strategy]) || {};
    const all = [...(block.items || []), ...(block.watch_items || [])];
    return all.find((r) => String(r.code || r.stock_code) === String(code));
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

window.BoardAnalysis = BoardAnalysis;
