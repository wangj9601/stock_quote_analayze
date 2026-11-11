/**
 * 市场分析资金流向视图：排行/趋势/结构规范化与瀑布步骤。
 * 运行：node test/test_market_analysis_fund_views.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const file = path.join(__dirname, '..', 'frontend', 'js', 'market_analysis.js');
const code = fs.readFileSync(file, 'utf8');
const ctx = { console, window: {} };
vm.createContext(ctx);
vm.runInContext(code, ctx);
const ma = ctx.window.MarketAnalysis;

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

assert(ma.normalizeView('stock', 'chart') === 'rank', 'chart→rank');
assert(ma.normalizeView('stock', 'trend') === 'trend', 'trend');
assert(ma.normalizeView('board', 'structure') === 'structure', 'structure');
assert(ma.normalizeView('board', 'list') === 'list', 'list');
assert(ma.normalizeView('slope', 'list') === 'list', 'slope list');
assert(ma.normalizeView('slope', 'rank') === 'chart', 'slope unknown→chart');
assert(ma.isChartView('rank') === true, 'rank is chart');
assert(ma.isChartView('list') === false, 'list not chart');
assert(ma.TREND_DAYS_BY_PERIOD.day === 20, 'trend days day');
assert(ma.TREND_DAYS_BY_PERIOD.month === 60, 'trend days month');

const steps = ma.buildStructureSteps(
  [
    { name: 'A', net_amount: 3e8 },
    { name: 'B', net_amount: 2e8 },
    { name: 'C', net_amount: -1e8 },
    { name: 'D', net_amount: -4e8 },
  ],
  'net_amount',
  (r) => r.name,
  2
);
assert(steps.length === 5, `steps len ${steps.length}`);
assert(steps[0].name === 'A' && steps[0].valueYi === 3, 'top inflow');
assert(steps[1].name === 'B', '2nd inflow');
assert(steps[2].name === 'D' && steps[2].valueYi === -4, 'most negative first');
assert(steps[3].name === 'C', '2nd outflow');
assert(steps[4].name === '结构净额', 'total label');
assert(steps[4].valueYi === 0, `total ${steps[4].valueYi}`);

console.log('test_market_analysis_fund_views: OK');
