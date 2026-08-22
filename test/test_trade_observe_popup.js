/**
 * 交易观察：个股分析弹出链接与 URL 参数冒烟
 * 运行：node test/test_trade_observe_popup.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { URL, URLSearchParams } = require('url');

function assertEq(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const src = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'js', 'trade_observe.js'), 'utf8');
const opened = [];
const sandbox = {
  console,
  document: {
    readyState: 'complete',
    getElementById() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    addEventListener() {},
  },
  location: { href: 'https://icemaplecity.com/analysis.html' },
  open(url, name, features) {
    opened.push({ url, name, features });
    return { opener: {}, focus() {} };
  },
  URL,
  URLSearchParams,
};
sandbox.window = sandbox;
sandbox.window.document = sandbox.document;
vm.createContext(sandbox);
vm.runInContext(src, sandbox);

const UTO = sandbox.UnifiedTradeObserve;
assert(UTO, 'UnifiedTradeObserve 未挂载');

const href = UTO.analysisHref('000938', '紫光股份');
assert(href.indexOf('tab=stock-ai') >= 0, 'tab');
assert(href.indexOf('code=000938') >= 0, 'code');
assert(href.indexOf('popup=') < 0, 'href 默认不含 popup，Ctrl+点击走新标签完整页');

const popupHref = UTO.analysisHref('000938', '紫光股份', true);
assert(popupHref.indexOf('popup=1') >= 0, 'popup href');

const fakeEvent = {
  defaultPrevented: false,
  button: 0,
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  altKey: false,
  preventDefault() {
    this.defaultPrevented = true;
  },
};
UTO.openAnalysisPopup(href, fakeEvent);
assert(fakeEvent.defaultPrevented, '左键应 preventDefault');
assertEq(opened.length, 1, '应弹出一次');
assert(String(opened[0].url).indexOf('popup=1') >= 0, '弹窗 URL 含 popup=1');
assertEq(opened[0].name, 'uto_stock_ai', '复用同一弹窗名');
assert(String(opened[0].features).indexOf('width=1280') >= 0, '弹窗尺寸');

opened.length = 0;
const ctrlEvent = {
  defaultPrevented: false,
  button: 0,
  ctrlKey: true,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  preventDefault() {
    this.defaultPrevented = true;
  },
};
UTO.openAnalysisPopup(href, ctrlEvent);
assertEq(opened.length, 0, 'Ctrl+点击不拦截');
assert(!ctrlEvent.defaultPrevented, 'Ctrl+点击不 preventDefault');

console.log('OK: trade observe analysis popup');
