/**
 * 个股交易分析深链：buildHref / 旧链接重定向冒烟
 * 运行：node test/test_stock_trade_link.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { URLSearchParams } = require('url');

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function assertEq(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

const root = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_trade_link.js'), 'utf8');

function makeSandbox(search, replaceCalls) {
  const calls = replaceCalls || [];
  const sandbox = {
    console,
    document: {
      documentElement: { classList: { add() {} } },
      body: { classList: { add() {} } },
    },
    location: {
      search,
      replace(url) {
        calls.push(url);
      },
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.URLSearchParams = URLSearchParams;
  vm.runInNewContext(src, sandbox);
  return { api: sandbox.StockTradeLink, calls };
}

const { api: link1 } = makeSandbox('');
assert(link1, 'StockTradeLink 应挂载');

assertEq(
  link1.buildHref('600519', '贵州茅台'),
  'stock.html?code=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&tab=analysis',
  'buildHref 默认 tab=analysis'
);

assert(
  link1.buildHref('00700', '腾讯控股', { popup: true }).indexOf('popup=1') >= 0,
  'buildHref 支持 popup'
);

const { api: link2, calls: redirectCalls } = makeSandbox('?tab=stock-ai&code=000938&name=test');
assert(link2.redirectFromAnalysisDeepLink() === true, '旧深链应触发重定向');
assert(redirectCalls.length === 1, '应 replace 一次');
assert(redirectCalls[0].indexOf('stock.html') >= 0, '应跳转到详情页');
assert(redirectCalls[0].indexOf('tab=analysis') >= 0, '应带 tab=analysis');
assert(redirectCalls[0].indexOf('code=000938') >= 0, '应保留 code');

const { api: link3, calls: legacyCalls } = makeSandbox('?tab=stock-ai&code=000938&legacy=1');
assert(link3.redirectFromAnalysisDeepLink() === false, 'legacy=1 不重定向');
assertEq(legacyCalls.length, 0, 'legacy 模式不 replace');

const { api: link4, calls: noCodeCalls } = makeSandbox('?tab=stock-ai');
assert(link4.redirectFromAnalysisDeepLink() === false, '无 code 不重定向');
assertEq(noCodeCalls.length, 0, '无 code 不 replace');

assert(typeof link1.normalizeBatchStocks === 'function', '应提供 normalizeBatchStocks');
assert(typeof link1.openBatchAnalysis === 'function', '应提供 openBatchAnalysis');
assertEq(link1.BATCH_STORAGE_KEY, 'ssa_trade_analysis_batch', '批量载荷 key');

const norm = link1.normalizeBatchStocks([
  { code: '600519', name: '贵州茅台' },
  { stock_code: '600519', stock_name: '重复' },
  { code: '000001', name: '平安银行' },
  { code: '' },
]);
assertEq(norm.length, 2, '批量股票应按 code 去重');
assertEq(norm[0].code, '600519', '保留首次');
assertEq(norm[0].name, '贵州茅台', '保留首次名称');
assertEq(norm[1].code, '000001', '第二只');

const openCalls = [];
const store = {};
const sandboxOpen = {
  console,
  document: {
    documentElement: { classList: { add() {} } },
    body: { classList: { add() {} } },
  },
  location: { search: '', href: '', replace() {} },
  localStorage: {
    setItem(k, v) {
      store[k] = v;
    },
    getItem(k) {
      return store[k] || null;
    },
    removeItem(k) {
      delete store[k];
    },
  },
  open(url) {
    openCalls.push(url);
    return { closed: false };
  },
  CommonUtils: { showToast() {} },
  confirm() {
    return true;
  },
};
sandboxOpen.window = sandboxOpen;
sandboxOpen.globalThis = sandboxOpen;
sandboxOpen.URLSearchParams = URLSearchParams;
vm.runInNewContext(src, sandboxOpen);
assert(
  sandboxOpen.StockTradeLink.openBatchAnalysis([]) === false,
  '空列表不打开'
);
assert(
  sandboxOpen.StockTradeLink.openBatchAnalysis([
    { code: '002230', name: '科大讯飞' },
    { code: '603228', name: '景旺电子' },
  ]) === true,
  '有股票应打开'
);
assert(openCalls.length === 1, '应 window.open 一次');
assert(openCalls[0].indexOf('batch=selected') >= 0, 'URL 应带 batch=selected');
assert(openCalls[0].indexOf('tab=stock-ai') >= 0, 'URL 应打开个股分析 Tab');
assert(openCalls[0].indexOf('002230') >= 0, 'URL 应带 codes 兜底');
assert(store.ssa_trade_analysis_batch, '应写入 localStorage');
const payload = JSON.parse(store.ssa_trade_analysis_batch);
assertEq(payload.stocks.length, 2, '载荷含 2 只');

const stockJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock.js'), 'utf8');
assert(stockJs.includes('bootstrapTabFromUrl'), 'stock.js 应支持 URL tab 引导');
assert(stockJs.includes("this.currentTab === 'analysis'"), '仅 analysis Tab 自动加载面板');

const stockHtml = fs.readFileSync(path.join(root, 'frontend', 'stock.html'), 'utf8');
assert(stockHtml.includes('stock-popup-window'), '详情页应支持弹出窗样式类');

const css = fs.readFileSync(path.join(root, 'frontend', 'css', 'stock.css'), 'utf8');
assert(css.includes('html.stock-popup-window'), 'stock.css 应有弹出窗规则');

const analysisHtml = fs.readFileSync(path.join(root, 'frontend', 'analysis.html'), 'utf8');
assert(analysisHtml.includes('baTradeAnalysisBtn'), '板块分析应有交易分析按钮');
assert(analysisHtml.includes('lmTradeAnalysisBtn'), '龙头中军应有交易分析按钮');
assert(analysisHtml.includes('baSelectAllRolesBtn'), '板块分析应有全选龙头中军');
assert(analysisHtml.includes('lmSelectAllRolesBtn'), '龙头中军应有全选龙头中军');

const rolesJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'board_roles_panel.js'), 'utf8');
assert(rolesJs.includes('selectableRoles'), '角色面板支持多选');
assert(rolesJs.includes('ba-role-select'), '角色复选框 class');
assert(rolesJs.includes('getSelectedStocks'), '应导出 getSelectedStocks');

const multiJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_multi_strategy.js'), 'utf8');
assert(multiJs.includes("batch === 'selected'"), '个股分析应支持 batch=selected');

console.log('test_stock_trade_link.js: all passed');
