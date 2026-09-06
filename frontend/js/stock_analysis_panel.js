/**
 * 个股详情 · 嵌入式交易分析面板（复用 analysis 页 StockMultiStrategy 模块）
 */
(function (global) {
    const SCRIPT_DEPS = [
        'js/kde_levels_tool.js',
        'js/pattern_tool.js',
        'js/market_structure_tool.js',
        'js/gann_trend_tool.js',
        'js/board_analysis_pdf.js',
        'js/stock_analysis_pdf.js',
        'js/vendor/html2canvas.min.js',
        'js/stock_analysis_png.js',
        'js/stock_trade_plan.js',
        'js/stock_multi_strategy.js',
    ];

    const PANEL_HTML = `
<div class="ssa-panel ssa-panel--embedded stock-trade-analysis-panel">
  <div class="ssa-toolbar ssa-toolbar--embedded">
    <div class="form-row ssa-form-row">
      <div class="form-group">
        <label for="ssaTradeDate">基准日（可选）</label>
        <input type="date" id="ssaTradeDate">
      </div>
      <div class="form-group ssa-actions">
        <label>&nbsp;</label>
        <div class="ssa-action-btns">
          <button type="button" class="btn btn-primary" id="ssaAnalyzeBtn"
            data-perm="channel.analyze.tab.stock_ai.btn.analyze">刷新</button>
          <button type="button" class="btn btn-secondary" id="ssaRealtimeAnalyzeBtn"
            data-perm="channel.analyze.tab.stock_ai.btn.analyze"
            title="拉取最新实时价后重算">实时分析</button>
          <button type="button" class="btn btn-secondary" id="ssaExportPdfBtn"
            data-perm="channel.analyze.tab.stock_ai.btn.analyze"
            title="导出 PDF" disabled>导出 PDF</button>
          <button type="button" class="btn btn-secondary" id="ssaExportPngBtn"
            data-perm="channel.analyze.tab.stock_ai.btn.analyze"
            title="导出 PNG" disabled>导出 PNG</button>
          <button type="button" class="btn btn-secondary" id="ssaTradeObserveBtn"
            data-perm="channel.analyze.tab.trade_observe"
            title="加入交易观察" disabled>交易观察</button>
          <button type="button" class="btn btn-secondary" id="ssaWatchlistBtn"
            data-perm="channel.watchlist.tab.default.btn.add"
            title="将当前股票加入或移出自选股" disabled>加自选</button>
        </div>
      </div>
    </div>
  </div>
  <input type="hidden" id="ssaStockCode" value="">
  <div class="ssa-candidates" id="ssaCandidates" hidden>
    <div class="ssa-candidates-title">匹配到多只股票，请选择：</div>
    <ul id="ssaCandidateList"></ul>
  </div>
  <div id="ssaExportRoot" class="ssa-export-root">
    <div class="ssa-meta" id="ssaMeta" hidden></div>
    <section class="ssa-block ssa-trade-plan-block" id="ssaTradePlanBlock" hidden>
      <h4 class="ssa-block-title">综合交易策略</h4>
      <div class="ssa-block-status" id="ssaTradePlanStatus"></div>
      <div id="ssaTradePlanHost"></div>
    </section>
    <section class="ssa-block" id="ssaStrategyBlock" hidden>
      <h4 class="ssa-block-title">策略分析</h4>
      <div class="ssa-results" id="ssaResults"></div>
    </section>
    <section class="ssa-block" id="ssaRsBlock" hidden>
      <div class="ssa-block-header">
        <h4 class="ssa-block-title">股价相对强度（RS Rating）</h4>
        <a class="btn btn-secondary btn-sm" id="ssaRsTraceLink" href="stock_rs_trace.html" target="_blank" rel="noopener noreferrer" hidden>历史追溯</a>
      </div>
      <div class="ssa-block-status" id="ssaRsStatus"></div>
      <div class="ssa-rs-host" id="ssaRsHost"></div>
    </section>
    <section class="ssa-block" id="ssaLevelsBlock" hidden>
      <h4 class="ssa-block-title">阻力支撑位</h4>
      <div class="ssa-block-status" id="ssaLevelsStatus"></div>
      <div class="ssa-levels-host" id="ssaLevelsHost"></div>
    </section>
    <section class="ssa-block ssa-block--collapsible" id="ssaPatternBlock" hidden>
      <details class="ssa-details">
        <summary class="ssa-block-title">形态识别</summary>
        <div class="ssa-block-status" id="ssaPatternStatus"></div>
        <div class="ssa-pattern-host" id="ssaPatternHost"></div>
      </details>
    </section>
    <section class="ssa-block ssa-block--collapsible" id="ssaSwingBlock" hidden>
      <details class="ssa-details">
        <summary class="ssa-block-title">波段与趋势</summary>
        <div class="ssa-block-status" id="ssaSwingStatus"></div>
        <div class="ssa-swing-host" id="ssaSwingHost"></div>
      </details>
    </section>
    <section class="ssa-block ssa-block--collapsible" id="ssaGannBlock" hidden>
      <details class="ssa-details">
        <summary class="ssa-block-header ssa-block-header--summary">
          <span class="ssa-block-title">江恩趋势预测</span>
          <button type="button" class="btn btn-secondary btn-sm" id="ssaGannTradeObserveBtn"
            data-perm="channel.analyze.tab.trade_observe"
            title="加入交易观察（江恩）" disabled>交易观察</button>
        </summary>
        <div class="ssa-block-status" id="ssaGannStatus"></div>
        <div class="ssa-gann-host" id="ssaGannHost"></div>
      </details>
    </section>
  </div>
  <div class="ssa-empty" id="ssaEmpty" hidden>正在加载交易分析…</div>
</div>`;

    function loadScript(src) {
        const v = global.__STOCK_ANALYSIS_PANEL_V__ || Date.now();
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

    const StockAnalysisPanel = {
        mounted: false,
        lastCode: null,
        _loadingScripts: null,

        async ensureScripts() {
            if (global.StockMultiStrategy && typeof global.StockMultiStrategy.analyzeForCode === 'function') {
                return;
            }
            if (!this._loadingScripts) {
                this._loadingScripts = ensureScripts().finally(() => {
                    this._loadingScripts = null;
                });
            }
            await this._loadingScripts;
        },

        mount(container) {
            const host =
                typeof container === 'string' ? document.querySelector(container) : container;
            if (!host) return false;
            if (host.dataset.sapMounted === '1') return true;
            host.innerHTML = PANEL_HTML;
            host.dataset.sapMounted = '1';
            this.mounted = true;
            return true;
        },

        async initPanel() {
            await this.ensureScripts();
            const api = global.StockMultiStrategy;
            if (!api) throw new Error('StockMultiStrategy 未加载');
            if (typeof api.initEmbedded === 'function') {
                api.initEmbedded();
            } else if (typeof api.init === 'function') {
                api.init();
            }
            if (global.PermissionEngine && typeof global.PermissionEngine.applyToPage === 'function') {
                global.PermissionEngine.loadFromCache();
                const root = document.querySelector('.stock-trade-analysis-panel');
                if (root) {
                    root.querySelectorAll('[data-perm]').forEach((el) => {
                        const code = el.getAttribute('data-perm');
                        if (!global.PermissionEngine.has(code)) {
                            el.style.display = 'none';
                            el.setAttribute('aria-hidden', 'true');
                        } else {
                            el.style.removeProperty('display');
                            el.removeAttribute('aria-hidden');
                        }
                    });
                }
            }
        },

        /**
         * @param {{ code: string, name?: string, container?: string|Element, autoRun?: boolean, force?: boolean }} opts
         */
        async run(opts) {
            const code = (opts && opts.code || '').trim();
            const name = (opts && opts.name || '').trim();
            const container = (opts && opts.container) || '#stockTradeAnalysisMount';
            if (!code) return;

            if (!this.mount(container)) {
                throw new Error('交易分析容器未找到');
            }
            await this.initPanel();

            const api = global.StockMultiStrategy;
            const force = !!(opts && opts.force);
            if (force && api && typeof api.clearExportState === 'function') {
                api.clearExportState();
            }
            if (!force && this.lastCode === code && api.lastStrategy) {
                return;
            }
            this.lastCode = code;

            if (opts && opts.autoRun !== false) {
                await api.analyzeForCode(code, name);
            }
        },

        resetForNewCode(code) {
            if (this.lastCode && code && this.lastCode !== code) {
                this.lastCode = null;
                const api = global.StockMultiStrategy;
                if (api && typeof api.clearExportState === 'function') {
                    api.clearExportState();
                }
            }
        },
    };

    global.StockAnalysisPanel = StockAnalysisPanel;
})(typeof window !== 'undefined' ? window : globalThis);
