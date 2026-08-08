/**
 * 分析频道 · 板块优先多策略工作台
 */
const BoardAnalysis = {
  API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
  boardKind: 'industry',
  industryCatalog: [],
  conceptCatalog: [],
  selectedBoard: null,
  lastResult: null,
  running: false,

  init() {
    this.bindEvents();
    this.loadCatalogs();
  },

  bindEvents() {
    document.querySelectorAll('input[name="baBoardKind"]').forEach((el) => {
      el.addEventListener('change', () => {
        this.boardKind = el.value === 'concept' ? 'concept' : 'industry';
        this.renderBoardSelect();
        this.selectedBoard = null;
        this.clearMeta();
      });
    });
    const sel = document.getElementById('baBoardSelect');
    if (sel) {
      sel.addEventListener('change', () => this.onBoardPicked());
    }
    const search = document.getElementById('baBoardSearch');
    if (search) {
      search.addEventListener('input', () => this.renderBoardSelect());
    }
    const runBtn = document.getElementById('baRunBtn');
    if (runBtn) {
      runBtn.addEventListener('click', () => this.runAnalysis());
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
      this.renderBoardSelect();
    } catch (e) {
      console.error(e);
      if (window.CommonUtils) CommonUtils.showToast('加载板块列表失败', 'error');
    }
  },

  catalog() {
    return this.boardKind === 'concept' ? this.conceptCatalog : this.industryCatalog;
  },

  renderBoardSelect() {
    const sel = document.getElementById('baBoardSelect');
    if (!sel) return;
    const q = (document.getElementById('baBoardSearch')?.value || '').trim().toLowerCase();
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
    const prev = sel.value;
    sel.innerHTML =
      '<option value="">请选择板块</option>' +
      list
        .map((b) => {
          const code = String(b.board_code || '');
          const name = String(b.board_name || code);
          const n = b.stock_count != null ? b.stock_count : b.member_count;
          const label = n != null ? `${name} (${code}) · ${n}只` : `${name} (${code})`;
          return `<option value="${this.escAttr(code)}">${this.esc(label)}</option>`;
        })
        .join('');
    if (prev && [...sel.options].some((o) => o.value === prev)) sel.value = prev;
  },

  onBoardPicked() {
    const sel = document.getElementById('baBoardSelect');
    const code = sel?.value || '';
    const b = this.catalog().find((x) => String(x.board_code) === code);
    this.selectedBoard = b
      ? {
          board_code: String(b.board_code),
          board_name: b.board_name || String(b.board_code),
          board_code_source: b.board_code_source || 'tonghuashun',
        }
      : null;
    this.clearMeta();
    if (this.selectedBoard && window.BoardRolesPanel) {
      BoardRolesPanel.refresh({
        panelId: 'baRolesHost',
        boardType: this.boardKind,
        boardCodes: [this.selectedBoard.board_code],
        boardCodeSource: this.selectedBoard.board_code_source,
        visible: true,
        variant: 'shortline',
      });
    }
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
    if (!this.selectedBoard) {
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
    if (results) results.innerHTML = '<p class="ba-empty">正在计算策略信号，请稍候（板内成分较多时可能需数十秒）…</p>';

    try {
      const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
      const q = new URLSearchParams({
        board_kind: this.boardKind,
        board_code: this.selectedBoard.board_code,
        board_code_source: this.selectedBoard.board_code_source || 'tonghuashun',
        board_name: this.selectedBoard.board_name || '',
        strategies: strategies.join(','),
      });
      const res = await fetchFn(`${this.API_BASE_URL}/api/analysis/board-signals?${q}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.message || data.detail || `分析失败 ${res.status}`);
      }
      this.lastResult = data.data || {};
      const board = this.lastResult.board || {};
      this.renderMeta(board);
      if (window.BoardRolesPanel) {
        BoardRolesPanel.refresh({
          panelId: 'baRolesHost',
          boardType: this.boardKind,
          boardCodes: [board.board_code || this.selectedBoard.board_code],
          boardCodeSource: this.selectedBoard.board_code_source,
          visible: true,
          variant: 'shortline',
          data: board,
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
    const slope = board.sector_slope != null ? Number(board.sector_slope).toFixed(4) : '--';
    const env = board.board_env_label || '--';
    meta.innerHTML = `
      <div class="ba-meta-card">
        <strong>${this.esc(board.board_name || '')}</strong>
        <span class="ba-muted">${this.esc(board.board_code || '')}</span>
        <span>斜率 ${slope}</span>
        <span class="ba-env">${this.esc(env)}</span>
        <span>成分 ${board.stock_count != null ? board.stock_count : (this.lastResult?.member_count ?? '--')}</span>
      </div>`;
  },

  renderResults(payload) {
    const host = document.getElementById('baResults');
    if (!host) return;
    const strategies = payload.strategies || {};
    const errors = payload.errors || {};
    const order = ['gms', 'urt', 'sbbr', 'rpe'];
    const labels = { gms: 'GMS', urt: 'URT', sbbr: 'SBBR', rpe: 'RPE' };
    let html = '';
    for (const key of order) {
      if (!strategies[key]) continue;
      const block = strategies[key];
      const err = errors[key];
      html += `<section class="ba-strategy-block" data-strategy="${key}">
        <h3>${labels[key]} 命中 <span class="ba-muted">${block.total || 0}</span>
          ${err ? `<span class="ba-error">（${this.esc(err)}）</span>` : ''}
        </h3>
        ${this.renderTable(key, block.items || [])}
        ${
          key === 'sbbr' && (block.watch_items || []).length
            ? `<details class="ba-watch"><summary>筑底关注 ${block.watch_total || 0}</summary>${this.renderTable(key, block.watch_items || [], true)}</details>`
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

  renderTable(strategy, items, watchOnly) {
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
        const pivS = this.fmtPrice2(ref.nearest_pivot_support);
        const pivR = this.fmtPrice2(ref.nearest_pivot_resistance);
        const action = advice.action || 'watch';
        const tip = this.refHoverTip(ref, advice.summary);
        return `<tr>
          <td><a href="stock.html?code=${encodeURIComponent(code)}">${this.esc(code)}</a><div class="ba-muted">${this.esc(name)}</div></td>
          <td class="ba-num">${lastClose}</td>
          <td class="ba-role-cell">${roles}</td>
          <td><span class="ba-hit ba-hit--${this.escAttr(action)}">${this.esc(hit)}</span></td>
          <td class="ba-advice">${this.esc(buy)}</td>
          <td class="ba-advice">${this.esc(sell)}</td>
          <td class="ba-num">${kdeS}</td>
          <td class="ba-num">${kdeR}</td>
          <td class="ba-ref" title="${this.escAttr(tip)}">Fib ${fibS}/${fibR}<br/>Pivot ${pivS}/${pivR}</td>
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
        <th>股票</th><th>最新收盘</th><th>角色</th><th>命中</th><th>买点建议</th><th>卖点/防守</th>
        <th>KDE结构支撑</th><th>KDE结构阻力</th><th>参考价 Fib/Pivot</th><th>操作</th>
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
      if (fib.swing_high != null || fib.swing_low != null) {
        const hi = `${this.fmtPrice2(fib.swing_high)}${fib.swing_high_date ? `（${fib.swing_high_date}）` : ''}`;
        const lo = `${this.fmtPrice2(fib.swing_low)}${fib.swing_low_date ? `（${fib.swing_low_date}）` : ''}`;
        lines.push(`Fib锚点: 高点 ${hi} / 低点 ${lo}`);
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
    const p = ref && ref.pivot;
    if (p && p.P != null) {
      lines.push(
        `Pivot: P=${this.fmtPrice2(p.P)} R1=${this.fmtPrice2(p.R1)} R2=${this.fmtPrice2(p.R2)} R3=${this.fmtPrice2(p.R3)} S1=${this.fmtPrice2(p.S1)} S2=${this.fmtPrice2(p.S2)} S3=${this.fmtPrice2(p.S3)}`
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
