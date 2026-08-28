/**
 * 个股分析 PNG 导出：文件名、缩放、忽略元素、页面入口冒烟
 * 运行：node test/test_stock_analysis_png.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function assertEq(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}: expected=${JSON.stringify(expected)} actual=${JSON.stringify(actual)}`);
  }
}

const root = path.join(__dirname, '..');
const pngSrc = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_analysis_png.js'), 'utf8');
const sandbox = { console, StockAnalysisPng: undefined };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.runInNewContext(pngSrc, sandbox);
const api = sandbox.StockAnalysisPng;
assert(api, 'StockAnalysisPng 未挂载');

assertEq(api.pickCaptureScale(800, 600, 2), 2, '常规尺寸保持 2x');
assert(api.pickCaptureScale(20000, 100, 2) < 2, '超宽应降缩放');
assert(api.pickCaptureScale(100, 20000, 2) < 2, '超高应降缩放');
assert(api.pickCaptureScale(800, 600, 2) * 800 <= api.MAX_CANVAS, '缩放后宽不超限');

assertEq(
  api.pngFilenameFromHost({ pngFilename: () => '个股分析_600519_茅台_20260824.png' }),
  '个股分析_600519_茅台_20260824.png',
  '优先 pngFilename'
);
assertEq(
  api.pngFilenameFromHost({ pdfFilename: () => '个股分析_600519.pdf' }),
  '个股分析_600519.png',
  '可由 pdf 文件名改后缀'
);
assertEq(api.pngFilenameFromHost({}), '个股分析.png', '缺省文件名');

assert(api.isPngIgnoreElement({ id: 'ssaGannTradeObserveBtn' }), '忽略江恩交易观察按钮');
assert(
  api.isPngIgnoreElement({ id: '', classList: { contains: (c) => c === 'ssa-card-links' } }),
  '忽略策略卡片链接'
);
assert(
  api.isPngIgnoreElement({
    id: '',
    tagName: 'A',
    classList: { contains: (c) => c === 'ssa-link' },
  }),
  '忽略 ssa-link'
);
assert(!api.isPngIgnoreElement({ id: 'ssaResults', classList: { contains: () => false } }), '结果区应导出');
assert(typeof api.flattenDetailsForCapture === 'function', '应导出 flattenDetailsForCapture');
assert(typeof api.fixSvgLayout === 'function', '应导出 fixSvgLayout');

const html = fs.readFileSync(path.join(root, 'frontend', 'analysis.html'), 'utf8');
assert(html.includes('id="ssaExportPngBtn"'), 'analysis.html 应有导出 PNG 按钮');
assert(html.includes('导出 PNG'), '按钮文案为 导出 PNG');
assert(html.includes('id="ssaExportRoot"'), '应有截图根节点 ssaExportRoot');
assert(html.includes('id="ssaTradePlanBlock"'), '应有综合交易策略区块');
assert(html.includes('js/stock_trade_link.js'), '应加载深链脚本');
assert(html.includes('ssa-deeplink-hint'), '应有深链迁移提示');
assert(html.includes('id="ssaWatchlistPickBtn"'), '应有选择自选按钮');
assert(html.includes('id="ssaWatchlistPickerModal"'), '应有自选股选择弹窗');
assert(html.includes('id="ssaWatchlistPickerSelectAll"'), '应有自选股全选按钮');
assert(html.includes('id="ssaStockTabs"'), '应有个股分析 Tab 栏');
assert(html.includes('js/stock_trade_plan.js'), '应加载综合交易策略脚本');
assert(html.includes('js/stock_analysis_png.js'), '应加载 PNG 导出脚本');
assert(html.includes('js/vendor/html2canvas.min.js') || fs.existsSync(path.join(root, 'frontend', 'js', 'vendor', 'html2canvas.min.js')), '应提供 html2canvas');

const css = fs.readFileSync(path.join(root, 'frontend', 'css', 'analysis.css'), 'utf8');
assert(css.includes('.ssa-png-title'), '应有 PNG 标题样式');
assert(css.includes('ssa-png-capturing'), '应有截图时隐藏控件的样式');
assert(css.includes('ms-details-static'), '截图时应把 details 展平为静态块');
assert(css.includes('overflow: visible'), '折线图容器截图时不应裁切');
assert(css.includes('.ssa-plan-wrap'), '应有综合交易策略样式');

const js = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_multi_strategy.js'), 'utf8');
assert(js.includes('exportPng()'), '个股分析应绑定 exportPng');
assert(js.includes('pngFilename()'), '应提供 png 文件名');
assert(js.includes("getElementById('ssaExportPngBtn')"), '应绑定 PNG 按钮');
assert(js.includes('analyzeWatchlistBatch'), '应支持自选股批量分析');
assert(js.includes('WATCHLIST_BATCH_SOFT_LIMIT'), '应支持批量分析软上限选项');
assert(js.includes('_fetchAnalysisBundle'), '批量应并行拉取各股数据');
assert(html.includes('id="ssaAnalyzeAllSelected"'), '应有一次分析全部勾选选项');
assert(js.includes('_closeStockTab'), '个股分析 Tab 应支持关闭');
assert(js.includes('ssa-stock-tab-close'), 'Tab 应有关闭按钮');
assert(js.includes('openWatchlistPicker'), '应打开自选股弹窗');
assert(js.includes('confirmWatchlistPicker'), '应确认自选股选择');

const panelJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_analysis_panel.js'), 'utf8');
assert(panelJs.includes('StockAnalysisPanel'), '应导出 StockAnalysisPanel');
assert(panelJs.includes('ssaTradePlanBlock'), '面板应含综合交易策略区块');

const stockHtml = fs.readFileSync(path.join(root, 'frontend', 'stock.html'), 'utf8');
assert(stockHtml.includes('交易分析'), '详情页 Tab 应为交易分析');
assert(stockHtml.includes('stockTradeAnalysisMount'), '详情页应有交易分析挂载点');
assert(stockHtml.includes('id="stockHistoryLink"'), '详情页应有历史行情链接');
assert(stockHtml.includes('stock_history.html'), '历史链接应指向 stock_history.html');
assert(js.includes('lastTradePlan'), '应缓存综合交易策略结果');

const planJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'stock_trade_plan.js'), 'utf8');
assert(planJs.includes('StockTradePlan'), '应导出 StockTradePlan');
assert(planJs.includes('render(host'), '应提供 render 方法');

const ms = fs.readFileSync(path.join(root, 'frontend', 'js', 'market_structure_tool.js'), 'utf8');
assert(/<details class="ms-weekly-details" open>/.test(ms), '周线明细默认展开');
assert(ms.includes('ms-weekly-body'), '周线明细应有正文容器');
assert(/width="\$\{w\}" height="\$\{h\}"/.test(ms), 'ZigZag SVG 应带宽高以免截图叠层');
assert(pngSrc.includes('flattenDetailsForCapture(root)'), '截图克隆时应展平 details');

console.log('test_stock_analysis_png.js: all passed');
