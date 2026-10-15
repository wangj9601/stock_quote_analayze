/**
 * 指数分析面板挂载：详情页 / 分析 Tab 共用 DOM 区块 id（isa*）。
 */
(function (global) {
    const SCRIPT_DEPS = [
        'js/kde_levels_tool.js?v=20261015-idxlv',
        'js/pattern_tool.js',
        'js/market_structure_tool.js',
        'js/gann_trend_tool.js',
        'js/board_analysis_pdf.js',
        'js/index_analysis_pdf.js',
        'js/vendor/html2canvas.min.js',
        'js/stock_analysis_png.js',
        'js/index_analysis.js',
    ];

    function loadScript(src) {
        const v = global.__INDEX_ANALYSIS_PANEL_V__ || Date.now();
        const url = src.indexOf('?') >= 0 ? `${src}&v=${v}` : `${src}?v=${v}`;
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src^="${src}"]`)) {
                resolve();
                return;
            }
            const el = document.createElement('script');
            el.src = url;
            el.onload = () => resolve();
            el.onerror = () => reject(new Error(`加载失败: ${src}`));
            document.body.appendChild(el);
        });
    }

    async function ensureScripts() {
        for (const src of SCRIPT_DEPS) {
            await loadScript(src);
        }
    }

    const IndexAnalysisPanel = {
        async mountAndRun(mountEl, opts) {
            await ensureScripts();
            if (global.IndexAnalysis) IndexAnalysis.init();
            const options = opts || {};
            if (options.code) {
                await IndexAnalysis.run({
                    code: options.code,
                    date: options.date || '',
                    useRealtime: !!options.useRealtime,
                });
            }
        },

        async ensureReady() {
            await ensureScripts();
            if (global.IndexAnalysis) IndexAnalysis.init();
        },
    };

    global.IndexAnalysisPanel = IndexAnalysisPanel;
})(typeof window !== 'undefined' ? window : globalThis);
