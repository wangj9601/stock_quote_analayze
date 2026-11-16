/**
 * 指数分析编排：环境研判 + 广度/贡献 + 价格行为 + 江恩；PNG / PDF 导出。
 * 独立于 StockMultiStrategy，避免污染个股通道。
 */
(function (global) {
    const QUICK_INDICES = [
        { code: '000001', name: '上证指数' },
        { code: '399001', name: '深证成指' },
        { code: '399006', name: '创业板指' },
        { code: '000300', name: '沪深300' },
    ];

    const IndexAnalysis = {
        API_BASE_URL: (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : ''),
        lastBundle: null,
        lastCode: '',
        lastName: '',
        _bound: false,

        init() {
            if (this._bound) return;
            this._bound = true;
            this._bindWorkbench();
            this.redirectDeepLinkIfNeeded();
        },

        redirectDeepLinkIfNeeded() {
            try {
                const params = new URLSearchParams(global.location.search || '');
                const tab = (params.get('tab') || '').trim();
                const index = (params.get('index') || params.get('code') || '').trim();
                if (tab === 'index-ai' && index) {
                    const popup = params.get('popup') === '1' ? '&popup=1' : '';
                    global.location.replace(`index_detail.html?index=${encodeURIComponent(index)}${popup}`);
                    return true;
                }
            } catch (e) { /* ignore */ }
            return false;
        },

        _bindWorkbench() {
            const quick = document.getElementById('isaQuickIndices');
            if (quick && !quick.dataset.bound) {
                quick.dataset.bound = '1';
                quick.innerHTML = QUICK_INDICES.map(
                    (x) =>
                        `<button type="button" class="btn btn-secondary btn-sm isa-quick-btn" data-code="${x.code}">${x.name}</button>`
                ).join('');
                quick.addEventListener('click', (e) => {
                    const btn = e.target && e.target.closest ? e.target.closest('.isa-quick-btn') : null;
                    if (!btn) return;
                    const code = btn.getAttribute('data-code') || '';
                    const input = document.getElementById('isaIndexCode');
                    if (input) input.value = code;
                });
            }
            const analyzeBtn = document.getElementById('isaAnalyzeBtn');
            if (analyzeBtn && !analyzeBtn.dataset.bound) {
                analyzeBtn.dataset.bound = '1';
                analyzeBtn.addEventListener('click', () => this.runFromWorkbench(false));
            }
            const rtBtn = document.getElementById('isaRealtimeAnalyzeBtn');
            if (rtBtn && !rtBtn.dataset.bound) {
                rtBtn.dataset.bound = '1';
                rtBtn.addEventListener('click', () => this.runFromWorkbench(true));
            }
            const pngBtn = document.getElementById('isaExportPngBtn');
            if (pngBtn && !pngBtn.dataset.bound) {
                pngBtn.dataset.bound = '1';
                pngBtn.addEventListener('click', () => this.exportPng());
            }
            const pdfBtn = document.getElementById('isaExportPdfBtn');
            if (pdfBtn && !pdfBtn.dataset.bound) {
                pdfBtn.dataset.bound = '1';
                pdfBtn.addEventListener('click', () => this.exportPdf());
            }
        },

        async runFromWorkbench(useRealtime) {
            const input = document.getElementById('isaIndexCode');
            const dateEl = document.getElementById('isaTradeDate');
            const code = ((input && input.value) || '').trim();
            if (!code) {
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast('请先选择常用指数，或输入 6 位指数代码', 'warning');
                }
                return;
            }
            const date = (dateEl && dateEl.value) || '';
            await this.run({ code, date, useRealtime: !!useRealtime });
        },

        async run(opts) {
            const options = opts || {};
            const code = String(options.code || '').trim();
            if (!code) throw new Error('缺少指数代码');
            const date = options.date || '';
            const useRealtime = !!options.useRealtime;
            this._setBusy(true);
            try {
                const data = await this.fetchBundle(code, { date, useRealtime });
                this.lastBundle = data;
                this.lastCode = (data.index && data.index.code) || code;
                this.lastName = (data.index && data.index.name) || '';
                this.render(data);
                this._enableExport(true);
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast(`${this.lastName || this.lastCode} 分析完成`, 'success');
                }
            } catch (e) {
                console.error('[IndexAnalysis]', e);
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast(e.message || '分析失败，请稍后重试', 'error');
                }
                this._enableExport(false);
            } finally {
                this._setBusy(false);
            }
        },

        async fetchBundle(code, opts) {
            const options = opts || {};
            const q = new URLSearchParams({ code });
            if (options.date && !options.useRealtime) q.set('date', String(options.date).slice(0, 10));
            if (options.useRealtime) q.set('use_realtime', 'true');
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/analysis/index-analysis-bundle?${q.toString()}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
            }
            return payload.data || {};
        },

        render(data) {
            if (!global.PaAnalysisView) {
                console.error('PaAnalysisView 未加载');
                return;
            }
            PaAnalysisView.render(data, {
                prefix: 'isa',
                showSectorContrib: true,
                assetType: 'index',
                patternMetaLabel: '指数',
            });
        },


        hasExportableResult() {
            return !!(this.lastBundle && this.lastCode);
        },

        pngFilename() {
            const d = (this.lastBundle && this.lastBundle.trade_date) || '';
            return `指数分析_${this.lastCode || 'index'}_${d || 'latest'}.png`;
        },

        pdfFilename() {
            const d = (this.lastBundle && this.lastBundle.trade_date) || '';
            return `指数分析_${this.lastCode || 'index'}_${d || 'latest'}.pdf`;
        },

        async exportPng() {
            if (!this.hasExportableResult()) {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('请先完成分析再导出', 'warning');
                return;
            }
            if (typeof StockAnalysisPng === 'undefined' || typeof StockAnalysisPng.exportFromHost !== 'function') {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('PNG 导出组件未加载', 'error');
                return;
            }
            // 临时把导出根节点 id 对齐个股 PNG（StockAnalysisPng 固定读 ssaExportRoot）
            const isaRoot = document.getElementById('isaExportRoot');
            const ssaRoot = document.getElementById('ssaExportRoot');
            let swapped = false;
            try {
                if (isaRoot && (!ssaRoot || ssaRoot !== isaRoot)) {
                    isaRoot.id = 'ssaExportRoot';
                    if (ssaRoot) ssaRoot.id = 'isaExportRoot__tmp';
                    swapped = true;
                }
                const host = {
                    hasExportableResult: () => this.hasExportableResult(),
                    pngFilename: () => this.pngFilename(),
                };
                const name = await StockAnalysisPng.exportFromHost(host);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(`已导出 ${name}`, 'success');
            } catch (e) {
                console.error(e);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(e.message || 'PNG 导出失败', 'error');
            } finally {
                if (swapped) {
                    const a = document.getElementById('ssaExportRoot');
                    const b = document.getElementById('isaExportRoot__tmp');
                    if (a) a.id = 'isaExportRoot';
                    if (b) b.id = 'ssaExportRoot';
                }
            }
        },

        async exportPdf() {
            if (!this.hasExportableResult()) {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('请先完成分析再导出', 'warning');
                return;
            }
            if (typeof IndexAnalysisPdf === 'undefined' || typeof IndexAnalysisPdf.exportFromHost !== 'function') {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('PDF 导出组件未加载，请刷新页面', 'error');
                return;
            }
            try {
                const name = await IndexAnalysisPdf.exportFromHost(this);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(`已导出 ${name}`, 'success');
            } catch (e) {
                console.error(e);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(e.message || 'PDF 导出失败', 'error');
            }
        },

        _setBusy(busy) {
            ['isaAnalyzeBtn', 'isaRealtimeAnalyzeBtn'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.disabled = !!busy;
            });
        },

        _enableExport(on) {
            ['isaExportPngBtn', 'isaExportPdfBtn'].forEach((id) => {
                const btn = document.getElementById(id);
                if (btn) btn.disabled = !on;
            });
        },

    };

    global.IndexAnalysis = IndexAnalysis;
})(typeof window !== 'undefined' ? window : globalThis);
