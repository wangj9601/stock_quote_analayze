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

  init() {
    this.bindEvents();
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
    const runBtn = document.getElementById('lmRunBtn');
    if (runBtn) {
      runBtn.addEventListener('click', () => this.runQuery());
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
    const selAll = document.getElementById('lmBoardPickerSelectAll');
    if (selAll) {
      selAll.addEventListener('click', () => this.pickerSelectAllVisible());
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
        fetchFn(`${this.API_BASE_URL}/api/market/industry_board/catalog?board_code_source=tonghuashun`),
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

  renderBoardPickerList() {
    const listEl = document.getElementById('lmBoardPickerList');
    if (!listEl) return;
    const q = (document.getElementById('lmBoardPickerSearch')?.value || '').trim().toLowerCase();
    let list = this.catalog().slice();
    if (q) {
      list = list.filter((b) => {
        const name = String(b.board_name || '').toLowerCase();
        const code = String(b.board_code || '').toLowerCase();
        return name.includes(q) || code.includes(q);
      });
    }
    list.sort((a, b) =>
      String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh')
    );
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
        const title = countTxt ? `${name} · ${countTxt} · ${code}` : `${name} · ${code}`;
        return `<label class="lm-board-picker-item" title="${this.escAttr(title)}">
          <input type="checkbox" value="${this.escAttr(code)}"${checked}>
          <span class="lm-board-picker-item-text">
            <span class="lm-board-picker-name">${this.esc(name)}${n != null ? ` (${n})` : ''}</span>
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

  pickerClearVisible() {
    const listEl = document.getElementById('lmBoardPickerList');
    if (!listEl) return;
    listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.checked = false;
      const code = String(cb.value || '').trim();
      if (code) this._pickerDraft.delete(code);
    });
  },

  confirmBoardPicker() {
    this.selectedBoardCodes = Array.from(this._pickerDraft);
    this.updateBoardSummary();
    this.hideBoardPicker();
    this.clearMeta();
    if (this.selectedBoardCodes.length && window.BoardRolesPanel) {
      BoardRolesPanel.refresh({
        panelId: 'lmRolesHost',
        boardType: this.boardKind,
        boardCodes: this.selectedBoardCodes.slice(0, 8),
        boardCodeSource: 'tonghuashun',
        visible: true,
        variant: 'shortline',
        showGmsWatchlistActions: true,
        gmsWatchlistPerm: 'channel.analyze.tab.leader_mid.btn.gms_watchlist',
      });
    }
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
        return `<tr class="${row.any_hit ? 'lm-row--hit' : ''}">
          <td><a href="stock.html?code=${encodeURIComponent(code)}">${this.esc(code)}</a>
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
