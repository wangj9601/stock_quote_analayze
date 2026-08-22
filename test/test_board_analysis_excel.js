/**
 * 板块分析 Excel 导出：flatten / 明细行 / 板块汇总冒烟
 * 运行：node test/test_board_analysis_excel.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function assertEq(actual, expected, msg) {
  const same = actual === expected || (Number.isNaN(actual) && Number.isNaN(expected));
  if (!same) {
    throw new Error(`${msg}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const src = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'js', 'board_analysis.js'), 'utf8');
const sandbox = {
  console,
  document: {
    getElementById() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(src, sandbox);

const BA = sandbox.BoardAnalysis;
assert(BA, 'BoardAnalysis 未挂到 window');

assertEq(BA.excelNum(12.345), 12.35, 'excelNum round');
assertEq(BA.excelNum(null), '', 'excelNum null');
assertEq(BA.excelNum('--'), '', 'excelNum invalid');
assertEq(BA.excelCode('000001').replace(/^\u2060/, ''), '000001', 'excelCode keeps digits');
assert(BA.excelCode('000001').startsWith('\u2060'), 'excelCode word-joiner prefix');

BA.boardKind = 'industry';
BA.selectedBoardCodes = ['BK0481'];
BA.industryCatalog = [{ board_code: 'BK0481', board_name: '半导体' }];
BA.conceptCatalog = [];

const payload = {
  asof: '2026-08-22',
  board: {
    board_name: '半导体',
    board_code: 'BK0481',
    stock_count: 2,
  },
  strategies: {
    gms: {
      total: 1,
      items: [
        {
          code: '688981',
          name: '中芯国际',
          last_close: 88.12,
          buy_type: '右侧',
          score_total: 72.5,
          role_tags: [{ id: 'leader', label: '龙头' }],
          boards: [{ board_code: 'BK0481', board_name: '半导体' }],
          board_labels: '半导体',
          trade_advice: {
            summary: '回踩支撑关注；跌破防守离场',
            buy_zone: { label: '回踩 86 附近' },
            stop_zone: { label: '跌破 82' },
            kde_support: 85.5,
            kde_resistance: 92.0,
            reference_levels: {
              last_close: 88.12,
              nearest_fib_support: 84.1,
              nearest_fib_resistance: 93.2,
            },
          },
        },
      ],
    },
    sbbr: {
      total: 0,
      items: [],
      watch_items: [
        {
          code: '002371',
          name: '北方华创',
          last_close: 401.2,
          bottom_matched: true,
          volume_ratio: 1.85,
          boards: [{ board_code: 'BK0481', board_name: '半导体' }],
        },
      ],
    },
  },
};

const rows = BA.collectExcelRows(payload);
assertEq(rows.length, 2, 'hit + watch rows');
assertEq(rows[0].strategyLabel, 'GMS', 'gms label');
assertEq(rows[0].listType, '命中', 'gms list type');
assertEq(rows[0].code, '688981', 'gms code');
assertEq(rows[0].hit, '右侧', 'gms hit');
assertEq(rows[0].score, 72.5, 'gms score');
assertEq(rows[0].kde_s, 85.5, 'kde support');
assertEq(rows[1].strategyLabel, 'SBBR', 'sbbr label');
assertEq(rows[1].listType, '筑底关注', 'sbbr watch type');
assertEq(rows[1].hit, '筑底', 'sbbr watch hit');

const aoa = BA.excelRowToAoa(rows[0], 0);
assertEq(aoa[0], 1, 'seq');
assertEq(aoa[1], 'GMS', 'strategy col');
assertEq(aoa[3], BA.excelCode('688981'), 'code col');
assertEq(aoa.length, BA.excelDetailHeaders().length, 'header/row width');

const sums = BA.buildExcelBoardSummary(rows);
assert(sums.length >= 1, 'board summary');
const semi = sums.find((b) => b.board_code === 'BK0481' || b.board_name === '半导体');
assert(semi, '半导体汇总行');
assertEq(semi.gms, 1, 'gms count');
assertEq(semi.sbbr_watch, 1, 'sbbr watch count');
assertEq(semi.sbbr, 0, 'sbbr hit count');

console.log('OK: board analysis excel helpers');
