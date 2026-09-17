/**
 * 个股分析统一入口：前端契约冒烟
 * 运行：node test/test_stock_analysis_bundle_frontend.js
 */
const fs = require('fs');
const path = require('path');

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const root = path.join(__dirname, '..');
const js = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_multi_strategy.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'frontend', 'analysis.html'), 'utf8');

assert(js.includes('/api/analysis/stock-analysis-bundle'), '应调用统一 bundle 接口');
assert(js.includes('_normalizeServerBundle'), '应有服务端包归一化');
assert(js.includes('_applyAnalysisBundle'), '应有 UI 应用函数');

const fetchStart = js.indexOf('async _fetchAnalysisBundle');
const fetchEnd = js.indexOf('_normalizeServerBundle');
assert(fetchStart >= 0 && fetchEnd > fetchStart, '_fetchAnalysisBundle 应存在');
const fetchFn = js.slice(fetchStart, fetchEnd);
assert(
  !fetchFn.includes('/api/analysis/multi-strategy-check'),
  '_fetchAnalysisBundle 不应再直调 multi-strategy-check'
);
assert(
  !fetchFn.includes('/api/analysis/stock-integrated-trade-plan'),
  '_fetchAnalysisBundle 不应再 POST trade-plan'
);
assert(
  !fetchFn.includes('/api/stock_fund_flow/daily'),
  '_fetchAnalysisBundle 不应再直调资金流明细接口'
);

const coreStart = js.indexOf('async _runAnalyzeCore');
const coreEnd = js.indexOf('async analyze(opts)');
assert(coreStart >= 0 && coreEnd > coreStart, '_runAnalyzeCore 应存在');
const coreFn = js.slice(coreStart, coreEnd);
assert(coreFn.includes('_fetchAnalysisBundle'), '_runAnalyzeCore 应走 bundle');
assert(coreFn.includes('_applyAnalysisBundle'), '_runAnalyzeCore 应应用到 UI');
assert(
  !coreFn.includes('loadRsRatingSection'),
  '_runAnalyzeCore 主路径不应并行 loadRsRatingSection'
);
assert(
  !coreFn.includes('Promise.all(['),
  '_runAnalyzeCore 主路径不应 Promise.all 拉明细'
);

assert(
  html.includes('js/stock_multi_strategy.js'),
  'analysis.html 应加载 stock_multi_strategy.js'
);

console.log('test_stock_analysis_bundle_frontend.js: OK');
