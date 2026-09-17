/**
 * 板块详情独立页：不应仅用 window.MarketsPage 判断模块是否加载
 *（markets.js 为 const，不会自动挂到 window）。
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const assert = (cond, msg) => {
    if (!cond) throw new Error(msg);
};

const html = fs.readFileSync(path.join(root, 'frontend', 'board_detail.html'), 'utf8');
const detailJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'board_detail.js'), 'utf8');
const marketsJs = fs.readFileSync(path.join(root, 'frontend', 'js', 'markets.js'), 'utf8');

assert(html.includes('js/markets.js'), 'board_detail.html 应引入 markets.js');
assert(html.includes('js/board_detail.js'), 'board_detail.html 应引入 board_detail.js');
assert(html.includes('board-detail-page'), '独立页 body 应有 board-detail-page');

assert(marketsJs.includes('window.MarketsPage = MarketsPage'), 'markets.js 应显式挂到 window');
assert(detailJs.includes("typeof MarketsPage !== 'undefined'"), 'board_detail 应按标识符检测 MarketsPage');
assert(!/if\s*\(\s*!window\.MarketsPage\s*\|\|/.test(detailJs), '不应仅用 !window.MarketsPage 短路误判');
assert(detailJs.includes('showSectorDetail'), '应调用 showSectorDetail');

const daily = fs.readFileSync(path.join(root, 'frontend', 'js', 'daily_review.js'), 'utf8');
assert(daily.includes('board_detail.html'), '每日复盘应链到 board_detail.html');
assert(daily.includes('boardDetailHref'), '每日复盘应有 boardDetailHref');

console.log('test_board_detail_page.js: all passed');
