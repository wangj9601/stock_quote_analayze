/**
 * 走强选板辅助：纯函数单测（与 frontend/js/board_picker_strong.js 对齐）
 * 运行：node test/test_board_picker_strong.js
 */
const path = require('path');
const BoardPickerStrong = require(path.join(
  __dirname,
  '..',
  'frontend',
  'js',
  'board_picker_strong.js'
));

function assertEq(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

function assertDeepEq(actual, expected, msg) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    throw new Error(`${msg}: expected=${b} actual=${a}`);
  }
}

assertEq(BoardPickerStrong.isStrongBoard({ board_env: 'strong' }), true, 'env strong');
assertEq(BoardPickerStrong.isStrongBoard({ board_strong: true }), true, 'board_strong');
assertEq(BoardPickerStrong.isStrongBoard({ board_env: 'weak' }), false, 'env weak');
assertEq(BoardPickerStrong.isStrongBoard({ board_env: 'neutral' }), false, 'env neutral');
assertEq(BoardPickerStrong.isStrongBoard({}), false, 'empty');

assertEq(BoardPickerStrong.formatEnvLabel({ board_env_label: '走强' }), '走强', 'label field');
assertEq(BoardPickerStrong.formatEnvLabel({ board_env: 'strong' }), '走强', 'label from env');
assertEq(BoardPickerStrong.formatEnvLabel({ board_env: 'weak' }), '走弱', 'weak label');
assertEq(BoardPickerStrong.envChipClass({ board_env: 'strong' }), 'strong', 'chip strong');
assertEq(BoardPickerStrong.envChipClass({ board_env: 'neutral' }), 'ok', 'chip ok');
assertEq(BoardPickerStrong.formatSlope({ sector_slope: 0.01234 }), '0.0123', 'slope');
assertEq(BoardPickerStrong.formatSlope({}), '--', 'slope empty');

const rows = [
  { board_code: 'A', board_name: '弱板', board_env: 'weak', sector_slope: 0.02 },
  { board_code: 'B', board_name: '强高', board_env: 'strong', sector_slope: 0.05 },
  { board_code: 'C', board_name: '强低', board_env: 'strong', sector_slope: 0.01 },
  { board_code: 'D', board_name: '正常', board_env: 'neutral', sector_slope: 0.03 },
  { board_code: 'E', board_name: '未知', sector_slope: null },
];

const strong = BoardPickerStrong.filterStrong(rows);
assertDeepEq(
  strong.map((r) => r.board_code),
  ['B', 'C'],
  'filterStrong'
);

const sorted = BoardPickerStrong.sortByStrongThenSlope(rows);
assertDeepEq(
  sorted.map((r) => r.board_code),
  ['B', 'C', 'D', 'A', 'E'],
  'sortByStrongThenSlope'
);

assertDeepEq(BoardPickerStrong.strongCodes(rows), ['B', 'C'], 'strongCodes');

console.log('test_board_picker_strong.js: all passed');
