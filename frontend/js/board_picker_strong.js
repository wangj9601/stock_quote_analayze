/**
 * 分析频道选板：走强判定 / 过滤 / 排序（与行情页 board_env 口径一致）
 */
(function (root) {
  'use strict';

  function boardEnv(row) {
    if (!row) return '';
    if (row.board_env) return String(row.board_env);
    if (row.board_strong) return 'strong';
    if (row.board_weak) return 'weak';
    return '';
  }

  function isStrongBoard(row) {
    const env = boardEnv(row);
    if (env === 'strong') return true;
    return !!(row && row.board_strong);
  }

  function filterStrong(rows) {
    const list = Array.isArray(rows) ? rows : [];
    return list.filter((r) => isStrongBoard(r));
  }

  function envSortRank(row) {
    const env = boardEnv(row);
    if (env === 'strong') return 0;
    if (env === 'neutral') return 1;
    if (env === 'weak') return 2;
    return 3;
  }

  function slopeNum(row) {
    if (!row || row.sector_slope == null || row.sector_slope === '') return null;
    const n = Number(row.sector_slope);
    return Number.isFinite(n) ? n : null;
  }

  /**
   * 走强 → 正常 → 走弱 → 未知；同档斜率降序；再按名称。
   */
  function sortByStrongThenSlope(rows) {
    const list = Array.isArray(rows) ? rows.slice() : [];
    list.sort((a, b) => {
      const ra = envSortRank(a);
      const rb = envSortRank(b);
      if (ra !== rb) return ra - rb;
      const na = slopeNum(a);
      const nb = slopeNum(b);
      if (na == null && nb == null) {
        return String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh');
      }
      if (na == null) return 1;
      if (nb == null) return -1;
      if (nb !== na) return nb - na;
      return String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh');
    });
    return list;
  }

  function formatEnvLabel(row) {
    if (!row) return '--';
    if (row.board_env_label) return String(row.board_env_label);
    const env = boardEnv(row);
    if (env === 'strong') return '走强';
    if (env === 'weak') return '走弱';
    if (env === 'neutral') return '正常';
    return '--';
  }

  function envChipClass(row) {
    const env = boardEnv(row);
    if (env === 'strong') return 'strong';
    if (env === 'weak') return 'weak';
    if (env === 'neutral') return 'ok';
    return 'unknown';
  }

  function formatSlope(row) {
    const n = slopeNum(row);
    if (n == null) return '--';
    return n.toFixed(4);
  }

  function strongCodes(rows) {
    return filterStrong(rows)
      .map((r) => String(r.board_code || '').trim())
      .filter(Boolean);
  }

  const BoardPickerStrong = {
    boardEnv,
    isStrongBoard,
    filterStrong,
    sortByStrongThenSlope,
    formatEnvLabel,
    envChipClass,
    formatSlope,
    strongCodes,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = BoardPickerStrong;
  }
  root.BoardPickerStrong = BoardPickerStrong;
})(typeof globalThis !== 'undefined' ? globalThis : this);
