/**
 * 选股页：行业/概念板龙头与中军摘要面板（GMS/URT/SBBR/RPE 共用）
 * 分析频道可开启 showGmsWatchlistActions：单只/本板全部加入 GMS 策略观察股
 */
(function (global) {
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function apiBase() {
    if (typeof global.API_BASE_URL === 'string' && global.API_BASE_URL) {
      return global.API_BASE_URL.replace(/\/+$/, '');
    }
    if (typeof Config !== 'undefined' && Config && typeof Config.getApiBaseUrl === 'function') {
      return String(Config.getApiBaseUrl() || '').replace(/\/+$/, '');
    }
    return '';
  }

  function stockChip(s) {
    const code = esc(s.code || s.stock_code || '');
    const name = esc(s.name || s.stock_name || '');
    const chg = s.change_percent != null && Number.isFinite(Number(s.change_percent))
      ? Number(s.change_percent).toFixed(2) + '%'
      : '--';
    const title = esc(s.role_reason || '');
    const rawCode = s.code || s.stock_code || '';
    const rawName = s.name || s.stock_name || '';
    const href = `stock.html?code=${encodeURIComponent(rawCode)}&name=${encodeURIComponent(rawName)}`;
    return `<a class="gms-board-role-chip" href="${href}" target="_blank" rel="noopener noreferrer" title="${title}">${code} ${name} <span class="gms-board-role-chg">${chg}</span></a>`;
  }

  /** 分析频道等：对齐后台成分页「短线角色」红/橙标签 */
  function formatPct(v) {
    if (v == null || !Number.isFinite(Number(v))) return '';
    const n = Number(v);
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(2)}%`;
  }

  function shortlinePill(kind, s, opts) {
    const rawCode = s.code || s.stock_code || '';
    const rawName = s.name || s.stock_name || '';
    const label = kind === 'leader' ? '龙头' : '中军';
    const cls =
      kind === 'leader' ? 'ba-role-pill ba-role-pill--leader' : 'ba-role-pill ba-role-pill--mid';
    const pct = formatPct(s.change_percent);
    const pctHtml = pct ? ` (${esc(pct)})` : '';
    const title = esc(s.role_reason || label);
    const href = `stock.html?code=${encodeURIComponent(rawCode)}&name=${encodeURIComponent(rawName)}`;
    let show;
    if (rawCode && rawName) show = `${esc(rawCode)} ${esc(rawName)}`;
    else show = esc(rawName || rawCode || '--');
    const pill = `<a class="${cls}" href="${href}" target="_blank" rel="noopener noreferrer" title="${title}">${label} ${show}${pctHtml}</a>`;
    if (!opts || !opts.showGmsWatchlistActions || !rawCode) return pill;
    const perm = esc(opts.gmsWatchlistPerm || 'channel.analyze.tab.board.btn.gms_watchlist');
    return `<span class="ba-role-item">
      ${pill}
      <button type="button" class="btn btn-secondary btn-sm ba-gms-wl-add"
        data-code="${esc(rawCode)}" data-name="${esc(rawName)}" data-role="${esc(kind)}"
        data-perm="${perm}" title="加入 GMS 策略观察股">+观察股</button>
    </span>`;
  }

  function renderShortlineRoles(data, opts) {
    const leaders = normalizeRoleList(data, 'leaders', 'leader');
    const mids = normalizeRoleList(data, 'mids', 'mid');
    const pills = [
      ...leaders.map((s) => shortlinePill('leader', s, opts)),
      ...mids.map((s) => shortlinePill('mid', s, opts)),
    ];
    const body = pills.length
      ? pills.join('')
      : '<span class="ba-muted">暂无</span>';
    const boardName = String(data.board_name || data.board_code || '').trim();
    const boardCode = String(data.board_code || '').trim();
    const boardLabel = boardName
      ? `<span class="ba-short-roles-board" title="${esc(boardCode)}">${esc(boardName)}</span>`
      : '';
    let actions = '';
    if (opts && opts.showGmsWatchlistActions && pills.length) {
      const perm = esc(opts.gmsWatchlistPerm || 'channel.analyze.tab.board.btn.gms_watchlist');
      actions = `<button type="button" class="btn btn-secondary btn-sm ba-gms-wl-add-all"
        data-perm="${perm}"
        data-board-code="${esc(boardCode)}" data-board-name="${esc(boardName)}"
        title="将本板块龙头与中军全部加入 GMS 策略观察股">龙头+中军全部加入</button>`;
    }
    return `<div class="ba-short-roles" data-board-code="${esc(boardCode)}" data-board-name="${esc(boardName)}">
      <span class="ba-short-roles-label">短线角色${boardLabel ? '' : '：'}</span>
      ${boardLabel ? `${boardLabel}<span class="ba-short-roles-label">：</span>` : ''}
      ${body}
      ${actions}
    </div>`;
  }

  /** 优先 leaders/mids 全量数组，兼容旧 leader/mid 单对象；不做条数截断。 */
  function normalizeRoleList(data, listKey, singularKey) {
    if (Array.isArray(data[listKey])) return data[listKey];
    const nested = data.roles && Array.isArray(data.roles[listKey]) ? data.roles[listKey] : null;
    if (nested) return nested;
    const one = data[singularKey];
    if (one && (one.code || one.name)) return [one];
    const nestedOne = data.roles && data.roles[singularKey];
    if (nestedOne && (nestedOne.code || nestedOne.name)) return [nestedOne];
    return [];
  }

  function renderBoardBlock(data) {
    const leaders = normalizeRoleList(data, 'leaders', 'leader');
    const mids = normalizeRoleList(data, 'mids', 'mid');
    const name = esc(data.board_name || data.board_code || '');
    const est = data.board_change_percent_est != null && Number.isFinite(Number(data.board_change_percent_est))
      ? Number(data.board_change_percent_est).toFixed(2) + '%'
      : '--';
    const leaderHtml = leaders.length
      ? leaders.map(stockChip).join('')
      : '<span class="gms-muted">暂无</span>';
    const midHtml = mids.length
      ? mids.map(stockChip).join('')
      : '<span class="gms-muted">暂无</span>';
    return `<div class="gms-board-roles-block">
      <div class="gms-board-roles-title">${name} <span class="gms-muted">板强度估 ${est}</span></div>
      <div class="gms-board-roles-line"><span class="gms-role-tag">龙头</span> ${leaderHtml}</div>
      <div class="gms-board-roles-line"><span class="gms-role-tag gms-role-tag--mid">中军</span> ${midHtml}</div>
    </div>`;
  }

  async function fetchBoardRoles(boardType, boardCode, boardCodeSource) {
    const kind = boardType === 'concept' ? 'concept_board' : 'industry_board';
    const q = new URLSearchParams();
    if (boardCodeSource) q.set('board_code_source', boardCodeSource);
    const url = `${apiBase()}/api/market/${kind}/${encodeURIComponent(boardCode)}/roles?${q}`;
    const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
    const res = await fetchFn(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.success) {
      throw new Error(data.message || data.detail || `加载角色失败 ${res.status}`);
    }
    return data.data || {};
  }

  function toast(msg, type) {
    if (typeof global.CommonUtils !== 'undefined' && CommonUtils.showToast) {
      CommonUtils.showToast(msg, type || 'info');
    }
  }

  async function addToGmsStrategyWatchlist(stocks, meta) {
    const list = (stocks || [])
      .map((s) => ({
        code: String(s.code || s.stock_code || '').trim(),
        name: s.name || s.stock_name || '',
        market: s.market || 'CN',
        role: s.role || null,
      }))
      .filter((s) => s.code);
    if (!list.length) {
      toast('没有可加入的龙头/中军', 'warning');
      return null;
    }
    const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
    const res = await fetchFn(`${apiBase()}/api/analysis/gms-strategy-watchlist/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stocks: list,
        board_code: (meta && meta.board_code) || '',
        board_name: (meta && meta.board_name) || '',
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      const detail = data.detail || data.message || `加入失败 ${res.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function summarizeAddResult(data) {
    if (!data) return;
    const added = data.added || 0;
    const skipped = data.skipped || 0;
    const failed = data.failed || 0;
    if (failed > 0 && added === 0 && skipped === 0) {
      toast(data.message || '加入失败', 'error');
      return;
    }
    if (added > 0 && skipped === 0 && failed === 0) {
      toast(added === 1 ? '已加入 GMS 策略观察股' : `已加入 ${added} 只 GMS 策略观察股`, 'success');
      return;
    }
    const parts = [];
    if (added) parts.push(`新增 ${added}`);
    if (skipped) parts.push(`跳过 ${skipped}`);
    if (failed) parts.push(`失败 ${failed}`);
    toast(parts.join('，') || data.message || '完成', failed ? 'warning' : 'success');
  }

  function bindGmsWatchlistActions(panel) {
    if (!panel || panel._baGmsWlBound) return;
    panel._baGmsWlBound = true;
    panel.addEventListener('click', async (e) => {
      const addAll = e.target.closest('.ba-gms-wl-add-all');
      const addOne = e.target.closest('.ba-gms-wl-add');
      if (!addAll && !addOne) return;
      e.preventDefault();
      e.stopPropagation();
      const btn = addAll || addOne;
      if (btn.disabled) return;
      const row = btn.closest('.ba-short-roles');
      const boardCode = (btn.getAttribute('data-board-code') || (row && row.getAttribute('data-board-code')) || '').trim();
      const boardName = (btn.getAttribute('data-board-name') || (row && row.getAttribute('data-board-name')) || '').trim();
      let stocks = [];
      if (addAll) {
        const scope = row || panel;
        stocks = [...scope.querySelectorAll('.ba-gms-wl-add')].map((el) => ({
          code: el.getAttribute('data-code') || '',
          name: el.getAttribute('data-name') || '',
          role: el.getAttribute('data-role') || '',
          market: 'CN',
        }));
      } else {
        stocks = [
          {
            code: btn.getAttribute('data-code') || '',
            name: btn.getAttribute('data-name') || '',
            role: btn.getAttribute('data-role') || '',
            market: 'CN',
          },
        ];
      }
      const prev = btn.textContent;
      btn.disabled = true;
      btn.textContent = '加入中…';
      try {
        const data = await addToGmsStrategyWatchlist(stocks, {
          board_code: boardCode,
          board_name: boardName,
        });
        summarizeAddResult(data);
        if (addOne && data && data.added > 0) {
          btn.textContent = '已加入';
          return;
        }
        if (addOne && data && data.skipped > 0 && data.added === 0) {
          btn.textContent = '已在池中';
          return;
        }
        btn.textContent = prev;
        btn.disabled = false;
      } catch (err) {
        toast((err && err.message) || '加入 GMS 策略观察股失败', 'error');
        btn.textContent = prev;
        btn.disabled = false;
      }
    });
  }

  /**
   * @param {object} opts
   * @param {string} opts.panelId - 容器元素 id
   * @param {string} opts.boardType - industry | concept
   * @param {string[]} opts.boardCodes
   * @param {string} [opts.boardCodeSource]
   * @param {boolean} [opts.visible]
   * @param {'default'|'shortline'} [opts.variant]
   * @param {object} [opts.data] - 已有 roles 数据时跳过请求（单板）
   * @param {boolean} [opts.showGmsWatchlistActions]
   * @param {string} [opts.gmsWatchlistPerm]
   */
  async function refreshBoardRolesPanel(opts) {
    const panel = document.getElementById(opts.panelId);
    if (!panel) return;
    const variant = opts.variant === 'shortline' ? 'shortline' : 'default';
    const actionOpts = {
      showGmsWatchlistActions: !!opts.showGmsWatchlistActions,
      gmsWatchlistPerm: opts.gmsWatchlistPerm || 'channel.analyze.tab.board.btn.gms_watchlist',
    };
    const codes = (opts.boardCodes || []).map((c) => String(c || '').trim()).filter(Boolean);
    const visible = opts.visible !== false && (codes.length > 0 || opts.data);
    panel.style.display = visible ? 'block' : 'none';
    if (!visible) {
      panel.innerHTML = '';
      return;
    }
    if (opts.data && typeof opts.data === 'object') {
      const data = Object.assign({}, opts.data);
      if (!data.board_name && !data.board_code && codes[0]) data.board_code = codes[0];
      panel.innerHTML =
        variant === 'shortline' ? renderShortlineRoles(data, actionOpts) : renderBoardBlock(data);
      if (actionOpts.showGmsWatchlistActions) {
        bindGmsWatchlistActions(panel);
        if (typeof PermissionEngine !== 'undefined' && PermissionEngine.applyToPage) {
          PermissionEngine.applyToPage();
        }
      }
      return;
    }
    panel.innerHTML =
      variant === 'shortline'
        ? '<div class="ba-short-roles"><span class="ba-muted">加载短线角色…</span></div>'
        : '<div class="gms-board-roles-loading">加载龙头/中军…</div>';
    const source = opts.boardCodeSource || 'tonghuashun';
    // 与已选对齐展示；超大选中量时截断并提示，避免一次请求过多
    const MAX_BOARD_ROLES = 200;
    const displayCodes = codes.slice(0, MAX_BOARD_ROLES);
    const parts = [];
    for (const code of displayCodes) {
      try {
        const data = await fetchBoardRoles(opts.boardType, code, source);
        if (!data.board_code) data.board_code = code;
        if (!data.board_name) data.board_name = code;
        parts.push(
          variant === 'shortline' ? renderShortlineRoles(data, actionOpts) : renderBoardBlock(data)
        );
      } catch (e) {
        parts.push(
          variant === 'shortline'
            ? `<div class="ba-short-roles"><span class="ba-short-roles-board">${esc(code)}</span><span class="ba-muted"> ${esc(e.message || String(e))}</span></div>`
            : `<div class="gms-board-roles-block"><div class="gms-board-roles-title">${esc(code)}</div>` +
                `<div class="gms-muted">${esc(e.message || String(e))}</div></div>`
        );
      }
    }
    if (codes.length > MAX_BOARD_ROLES) {
      parts.push(
        `<div class="gms-muted">已选 ${codes.length} 个板块，仅展示前 ${MAX_BOARD_ROLES} 个的龙头/中军</div>`
      );
    }
    const body = parts.join('') || '<div class="gms-muted">暂无龙头/中军数据</div>';
    panel.innerHTML =
      displayCodes.length > 8
        ? `<div class="board-roles-scroll">${body}</div>`
        : body;
    if (actionOpts.showGmsWatchlistActions) {
      bindGmsWatchlistActions(panel);
      if (typeof PermissionEngine !== 'undefined' && PermissionEngine.applyToPage) {
        PermissionEngine.applyToPage();
      }
    }
  }

  global.BoardRolesPanel = {
    refresh: refreshBoardRolesPanel,
    fetchBoardRoles,
    renderShortlineRoles,
    addToGmsStrategyWatchlist,
  };
})(typeof window !== 'undefined' ? window : globalThis);
