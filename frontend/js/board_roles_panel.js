/**
 * 选股页：行业/概念板龙头与中军摘要面板（GMS/URT/SBBR/RPE 共用）
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
    const code = esc(s.code || '');
    const name = esc(s.name || '');
    const chg = s.change_percent != null && Number.isFinite(Number(s.change_percent))
      ? Number(s.change_percent).toFixed(2) + '%'
      : '--';
    const title = esc(s.role_reason || '');
    const href = `stock.html?code=${encodeURIComponent(s.code || '')}&name=${encodeURIComponent(s.name || '')}`;
    return `<a class="gms-board-role-chip" href="${href}" target="_blank" rel="noopener noreferrer" title="${title}">${code} ${name} <span class="gms-board-role-chg">${chg}</span></a>`;
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

  /**
   * @param {object} opts
   * @param {string} opts.panelId - 容器元素 id
   * @param {string} opts.boardType - industry | concept
   * @param {string[]} opts.boardCodes
   * @param {string} [opts.boardCodeSource]
   * @param {boolean} [opts.visible]
   */
  async function refreshBoardRolesPanel(opts) {
    const panel = document.getElementById(opts.panelId);
    if (!panel) return;
    const codes = (opts.boardCodes || []).map((c) => String(c || '').trim()).filter(Boolean);
    const visible = opts.visible !== false && codes.length > 0;
    panel.style.display = visible ? 'block' : 'none';
    if (!visible) {
      panel.innerHTML = '';
      return;
    }
    panel.innerHTML = '<div class="gms-board-roles-loading">加载龙头/中军…</div>';
    const source = opts.boardCodeSource || 'tonghuashun';
    const parts = [];
    for (const code of codes.slice(0, 8)) {
      try {
        const data = await fetchBoardRoles(opts.boardType, code, source);
        parts.push(renderBoardBlock(data));
      } catch (e) {
        parts.push(
          `<div class="gms-board-roles-block"><div class="gms-board-roles-title">${esc(code)}</div>` +
            `<div class="gms-muted">${esc(e.message || String(e))}</div></div>`
        );
      }
    }
    if (codes.length > 8) {
      parts.push(`<div class="gms-muted">仅展示前 8 个已选板块的龙头/中军</div>`);
    }
    panel.innerHTML = parts.join('') || '<div class="gms-muted">暂无龙头/中军数据</div>';
  }

  global.BoardRolesPanel = {
    refresh: refreshBoardRolesPanel,
    fetchBoardRoles,
  };
})(typeof window !== 'undefined' ? window : globalThis);
