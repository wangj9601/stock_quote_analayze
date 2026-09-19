/**
 * 板块斜率图：对数斜率 → 窗口约合涨跌幅、环境分档。
 * 运行：node test/test_market_analysis_slope_chart.js
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

function close(a, b, eps, msg) {
  assert(Math.abs(a - b) < eps, `${msg}: ${a} vs ${b}`);
}

const r60 = ma.slopeWindowReturn(0.0062, 60);
close(r60, Math.exp(0.0062 * 60) - 1, 1e-9, '60d return');
assert(r60 > 0.44 && r60 < 0.46, '0.0062 over 60d is about +45%');

const th = ma.slopeWindowReturn(ma.SLOPE_STRONG_DAILY, 60);
close(th, Math.exp(0.001 * 60) - 1, 1e-9, 'strong threshold 60d');
assert(th > 0.06 && th < 0.065, 'strong line about +6%');

assert(ma.slopeWindowReturn(null, 60) == null, 'null slope');
assert(ma.slopeWindowReturn(0.01, 0) == null, 'bad window');
assert(ma.fmtWindowPct(0.451) === '+45.1%', 'pct format');
assert(ma.fmtWindowPct(-0.032) === '-3.20%', 'neg pct');

assert(ma.slopeEnvKey({ board_env: 'strong' }) === 'strong', 'env strong');
assert(ma.slopeEnvKey({ board_env_label: '走弱' }) === 'weak', 'label weak');
assert(ma.slopeEnvKey({ board_env_label: '正常' }) === 'neutral', 'label neutral');
assert(ma.slopeEnvKey({ sector_slope: -0.002 }) === 'weak', 'fallback weak');
assert(ma.slopeEnvKey({ sector_slope: 0.002 }) === 'neutral', 'fallback not strong without env');
assert(ma.SLOPE_ENV_COLOR.strong === '#dc2626', 'strong color');
assert(ma.SLOPE_ENV_COLOR.weak === '#16a34a', 'weak color');

console.log('test_market_analysis_slope_chart: OK');
