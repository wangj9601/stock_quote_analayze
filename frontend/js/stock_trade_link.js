/**
 * 个股交易分析深链：统一跳转个股详情页「交易分析」Tab
 * V2：替代 analysis.html?tab=stock-ai&code=...
 * 批量：板块分析 / 龙头中军勾选后 → analysis.html?tab=stock-ai&batch=selected
 */
(function (global) {
    /** 与 stock_multi_strategy / watchlist 批量载荷对齐的跨标签页 key */
    const BATCH_STORAGE_KEY = 'ssa_trade_analysis_batch';

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

    /**
     * 规范化批量分析股票列表（按 code 去重，保留首次出现的 name）。
     * @returns {{code:string,name:string}[]}
     */
    function normalizeBatchStocks(stocks) {
        const map = new Map();
        (stocks || []).forEach((s) => {
            const code = String((s && (s.code || s.stock_code)) || '').trim();
            if (!code || map.has(code)) return;
            const name = String((s && (s.name || s.stock_name)) || '').trim();
            map.set(code, { code, name });
        });
        return Array.from(map.values());
    }

    /**
     * 新标签打开分析频道「个股分析」，每只一个 Tab 跑交易分析。
     * @param {Array<{code:string,name?:string}>} stocks
     * @param {{confirmLarge?:boolean,toastPrefix?:string}} [opts]
     * @returns {boolean} 是否已打开（含当前页回退）
     */
    function openBatchAnalysis(stocks, opts) {
        const options = opts || {};
        const list = normalizeBatchStocks(stocks);
        if (!list.length) {
            if (global.CommonUtils && CommonUtils.showToast) {
                CommonUtils.showToast('请先勾选至少一只龙头或中军', 'warning');
            }
            return false;
        }
        if (options.confirmLarge !== false && list.length >= 40) {
            const ok = global.confirm(
                `将分析 ${list.length} 只股票（每只一个 Tab），耗时可能较长，是否继续？`
            );
            if (!ok) return false;
        }
        try {
            global.localStorage.setItem(
                BATCH_STORAGE_KEY,
                JSON.stringify({ ts: Date.now(), stocks: list })
            );
        } catch (e) {
            console.warn('写入批量交易分析载荷失败', e);
            if (global.CommonUtils && CommonUtils.showToast) {
                CommonUtils.showToast('无法写入分析参数，请检查浏览器存储权限', 'error');
            }
            return false;
        }
        const codesQs = list.map((s) => encodeURIComponent(s.code)).join(',');
        const url = `analysis.html?tab=stock-ai&batch=selected&popup=1&codes=${codesQs}`;
        const win = global.open(url, '_blank');
        if (!win) {
            global.location.href = url;
        } else if (global.CommonUtils && CommonUtils.showToast) {
            const prefix = options.toastPrefix || '已打开交易分析';
            CommonUtils.showToast(`${prefix}：${list.length} 只`, 'success');
        }
        return true;
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
        BATCH_STORAGE_KEY,
        buildHref,
        normalizeBatchStocks,
        openBatchAnalysis,
        redirectFromAnalysisDeepLink,
        applyPopupDocumentClass,
    };

    global.StockTradeLink = StockTradeLink;
})(typeof window !== 'undefined' ? window : globalThis);
