/**
 * 个股交易分析深链：统一跳转个股详情页「交易分析」Tab
 * V2：替代 analysis.html?tab=stock-ai&code=...
 */
(function (global) {
    function buildHref(code, name, opts) {
        const options = opts || {};
        const c = String(code || '').trim();
        const n = String(name || '').trim();
        const q = new URLSearchParams();
        if (c) q.set('code', c);
        if (n) q.set('name', n);
        q.set('tab', options.tab || 'analysis');
        if (options.popup) q.set('popup', '1');
        return `stock.html?${q.toString()}`;
    }

    /** 分析频道旧深链 → 详情页交易分析（保留 legacy=1 时不跳转） */
    function redirectFromAnalysisDeepLink() {
        try {
            const params = new URLSearchParams(global.location.search || '');
            const tab = (params.get('tab') || '').trim();
            const code = (params.get('code') || '').trim();
            if (tab !== 'stock-ai' || !code) return false;
            if (params.get('legacy') === '1') return false;
            const name = (params.get('name') || '').trim();
            const popup = params.get('popup') === '1';
            global.location.replace(buildHref(code, name, { tab: 'analysis', popup }));
            return true;
        } catch (e) {
            return false;
        }
    }

    function applyPopupDocumentClass() {
        try {
            const params = new URLSearchParams(global.location.search || '');
            if (params.get('popup') === '1') {
                document.documentElement.classList.add('stock-popup-window');
                if (document.body) document.body.classList.add('stock-popup-window');
            }
        } catch (e) {
            /* ignore */
        }
    }

    const StockTradeLink = {
        buildHref,
        redirectFromAnalysisDeepLink,
        applyPopupDocumentClass,
    };

    global.StockTradeLink = StockTradeLink;
})(typeof window !== 'undefined' ? window : globalThis);
