/**
 * 板块分析：得分展示辅助逻辑冒烟（与 board_analysis.js 口径对齐）
 * 运行：node test/test_board_analysis_score_helpers.js
 */
function asFloat(v) {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function pickScore(strategy, row) {
  if (!row) return null;
  if (strategy === 'gms') return asFloat(row.score_total);
  if (strategy === 'urt') {
    for (const k of ['score_total', 'total_score', 'score']) {
      const sc = asFloat(row[k]);
      if (sc != null) return sc;
    }
    return null;
  }
  if (strategy === 'sbbr') return asFloat(row.volume_ratio);
  if (strategy === 'rpe') {
    for (const k of ['z_score', 'zscore', 'score', 'relative_z']) {
      const sc = asFloat(row[k]);
      if (sc != null) return sc;
    }
    return null;
  }
  return null;
}

function scoreDisplay(strategy, row) {
  const score = pickScore(strategy, row);
  if (strategy === 'gms') return score != null ? `总分 ${score.toFixed(1)}` : '--';
  if (strategy === 'urt') return score != null ? `得分 ${score.toFixed(1)}` : '--';
  if (strategy === 'sbbr') {
    const tags = [];
    if (row) {
      if (row.size_ok) tags.push('做小✓');
      if (row.bottom_matched) tags.push('筑底✓');
      if (row.entry_signal) tags.push('入场✓');
      if (score != null) tags.push(`量比 ${score.toFixed(2)}`);
    }
    return tags.length ? tags.join(' · ') : '--';
  }
  if (strategy === 'rpe') {
    if (score != null) return `Z=${score.toFixed(2)}`;
    return '--';
  }
  return '--';
}

function assertEq(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

assertEq(scoreDisplay('gms', { score_total: 72.5 }), '总分 72.5', 'gms');
assertEq(scoreDisplay('urt', { score: 61 }), '得分 61.0', 'urt');
assertEq(
  scoreDisplay('sbbr', { size_ok: true, entry_signal: true, volume_ratio: 1.85 }),
  '做小✓ · 入场✓ · 量比 1.85',
  'sbbr'
);
assertEq(scoreDisplay('rpe', { z_score: 1.234 }), 'Z=1.23', 'rpe');
assertEq(scoreDisplay('gms', {}), '--', 'gms empty');

/** 与 board_analysis.js GMS_HIT_MIN_SCORE / applyGmsHitScoreFloor 口径对齐 */
const GMS_HIT_MIN_SCORE = 70;
function isGmsLeftOrRightBuy(row) {
  if (!row) return false;
  if (row.left_buy_signal || row.right_buy_signal) return true;
  const bt = String(row.buy_type || '');
  return bt === '左侧' || bt === '右侧';
}
function filterGmsHits(items, thr = GMS_HIT_MIN_SCORE) {
  return (items || []).filter((row) => {
    if (!isGmsLeftOrRightBuy(row)) return false;
    const sc = asFloat(row && row.score_total);
    const sc2 = sc != null ? sc : asFloat(row && row.total_score);
    return sc2 != null && sc2 >= thr;
  });
}
const gmsFiltered = filterGmsHits([
  { code: 'a', left_buy_signal: true, score_total: 69 }, // 左侧但 <70 → 剔除
  { code: 'b', left_buy_signal: true, score_total: 70 }, // 左侧 + ≥70 → 保留
  { code: 'c', right_buy_signal: true, score_total: 71 }, // 右侧 + ≥70 → 保留
  { code: 'd', score_total: 80 }, // 高分无买点 → 剔除
  { code: 'e', left_buy_signal: true }, // 有买点无分数 → 剔除
  { code: 'f', buy_type: '左侧', total_score: 70 }, // buy_type + total_score → 保留
  { code: 'g', buy_type: '右侧', score_total: 69 }, // 右侧但 <70 → 剔除
  { code: 'h', buy_type: 'GMS', score_total: 90 }, // 非左右买点 → 剔除
]);
assertEq(gmsFiltered.map((r) => r.code).join(','), 'b,c,f', 'gms hit score+buy-side floor');

console.log('test_board_analysis_score_helpers: OK');
