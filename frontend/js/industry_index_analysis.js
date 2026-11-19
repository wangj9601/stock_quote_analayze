/**
 * 行业指数分析编排：工作台与板块详情共用结果区（iia*）。
 */
(function (global) {
    const SCRIPT_DEPS = [
        'js/kde_levels_tool.js',
        'js/pattern_tool.js',
        'js/market_structure_tool.js',
        'js/gann_trend_tool.js',
        'js/board_analysis_pdf.js',
        'js/index_analysis_pdf.js',
        'js/vendor/html2canvas.min.js',
        'js/stock_analysis_png.js',
        'js/pa_analysis_view.js',
        'js/board_flow_focus.js?v=20261119-flow2',
    ];

    function loadScript(src) {
        const path = src.split('?')[0];
        if (document.querySelector(`script[src="${src}"], script[src^="${path}?"]`)) {
            return Promise.resolve();
        }
        return new Promise((resolve, reject) => {
            const el = document.createElement('script');
            el.src = src;
            el.onload = () => resolve();
            el.onerror = () => reject(new Error('加载失败: ' + src));
            document.body.appendChild(el);
        });
    }

    function resultSectionsHtml() {
        return `
            <div id="iiaEmpty" class="ssa-empty">点击「分析」查看该行业指数的环境与价格行为</div>
            <div id="iiaExportRoot" class="ssa-export-root" hidden>
                <div class="ssa-meta" id="iiaMeta" hidden></div>
                <section class="ssa-block" id="iiaMarketViewBlock" hidden>
                    <h4 class="ssa-block-title">行业环境研判</h4>
                    <div class="ssa-block-status" id="iiaMarketViewStatus"></div>
                    <div id="iiaMarketViewHost"></div>
                </section>
                <section class="ssa-block" id="iiaBreadthBlock" hidden>
                    <h4 class="ssa-block-title">成分广度与领涨领跌</h4>
                    <div id="iiaBreadthHost"></div>
                </section>
                <section class="ssa-block" id="iiaFlowBlock" hidden>
                    <h4 class="ssa-block-title">资金与相对轮动</h4>
                    <p class="ssa-flow-hint">只描述当前板块。资金看当日主力净流入在同行业里的名次，轮动看相对沪深300的象限和近 15 日轨迹。</p>
                    <div id="iiaFlowHost"></div>
                </section>
                <section class="ssa-pa-section" id="iiaPaSection" hidden>
                    <div class="ssa-pa-section__head">
                        <h4 class="ssa-pa-section__title">价格行为</h4>
                        <p class="ssa-pa-section__hint">行业指数日线、不复权；实时分析不改写当日 K。</p>
                    </div>
                    <section class="ssa-block ssa-block--collapsible" id="iiaSwingBlock" hidden>
                        <details class="ssa-details" open>
                            <summary class="ssa-block-title">1. 波段与趋势（含 SMC）</summary>
                            <div class="ssa-block-status" id="iiaSwingStatus"></div>
                            <div class="ssa-swing-host" id="iiaSwingHost"></div>
                        </details>
                    </section>
                    <section class="ssa-block ssa-block--collapsible" id="iiaPatternBlock" hidden>
                        <details class="ssa-details" open>
                            <summary class="ssa-block-title">2. 形态识别</summary>
                            <div class="ssa-block-status" id="iiaPatternStatus"></div>
                            <div class="ssa-pattern-host" id="iiaPatternHost"></div>
                        </details>
                    </section>
                    <section class="ssa-block" id="iiaLevelsBlock" hidden>
                        <h4 class="ssa-block-title">3. 阻力支撑位</h4>
                        <div class="ssa-block-status" id="iiaLevelsStatus"></div>
                        <div class="ssa-levels-host" id="iiaLevelsHost"></div>
                    </section>
                </section>
                <section class="ssa-block ssa-block--collapsible" id="iiaGannBlock" hidden>
                    <details class="ssa-details">
                        <summary class="ssa-block-title">江恩趋势预测</summary>
                        <div class="ssa-block-status" id="iiaGannStatus"></div>
                        <div class="ssa-gann-host" id="iiaGannHost"></div>
                    </details>
                </section>
            </div>`;
    }

    const IndustryIndexAnalysis = {
        API_BASE_URL: (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : ''),
        lastBundle: null,
        lastCode: '',
        lastName: '',
        _bound: false,
        _catalog: null,
        _pickedCode: '',
        _listOpen: false,
        _detailCode: '',

        async ensureScripts() {
            for (const src of SCRIPT_DEPS) {
                await loadScript(src);
            }
        },

        init() {
            if (this._bound) return;
            if (!document.getElementById('iiaAnalyzeBtn') && !document.getElementById('iiaBoardQuery')) return;
            this._bound = true;
            this._bindWorkbench();
            this.loadCatalog();
        },

        _bindWorkbench() {
            const analyzeBtn = document.getElementById('iiaAnalyzeBtn');
            if (analyzeBtn && !analyzeBtn.dataset.bound) {
                analyzeBtn.dataset.bound = '1';
                analyzeBtn.addEventListener('click', () => this.runFromWorkbench(false));
            }
            const rtBtn = document.getElementById('iiaRealtimeAnalyzeBtn');
            if (rtBtn && !rtBtn.dataset.bound) {
                rtBtn.dataset.bound = '1';
                rtBtn.addEventListener('click', () => this.runFromWorkbench(true));
            }
            const pngBtn = document.getElementById('iiaExportPngBtn');
            if (pngBtn && !pngBtn.dataset.bound) {
                pngBtn.dataset.bound = '1';
                pngBtn.addEventListener('click', () => this.exportPng());
            }
            const pdfBtn = document.getElementById('iiaExportPdfBtn');
            if (pdfBtn && !pdfBtn.dataset.bound) {
                pdfBtn.dataset.bound = '1';
                pdfBtn.addEventListener('click', () => this.exportPdf());
            }
            const query = document.getElementById('iiaBoardQuery');
            if (query && !query.dataset.bound) {
                query.dataset.bound = '1';
                query.addEventListener('focus', () => this._openList());
                query.addEventListener('input', () => {
                    this._listOpen = true;
                    this._filterCatalog(query.value);
                });
                query.addEventListener('keydown', (event) => this._onQueryKey(event));
            }
            if (!this._outsideBound) {
                this._outsideBound = true;
                document.addEventListener('pointerdown', (event) => {
                    const field = document.querySelector('#industry-index-ai .iia-board-field');
                    if (!field || field.contains(event.target)) return;
                    this._closeList();
                });
            }
        },

        async loadCatalog() {
            const pick = document.getElementById('iiaBoardPick');
            if (!pick) return;
            pick.innerHTML = '<p class="iia-board-pick__status">正在加载行业列表…</p>';
            try {
                const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
                const resp = await fetchFn(
                    `${this.API_BASE_URL}/api/market/industry_board/list?board_code_source=tonghuashun`
                );
                const payload = await resp.json().catch(() => ({}));
                const rawRows = Array.isArray(payload.data) ? payload.data : [];
                if (!resp.ok || payload.success === false) {
                    throw new Error(payload.message || payload.detail || '行业列表加载失败');
                }
                this._catalog = rawRows
                    .map((row) => ({
                        code: String(row.board_code || row.code || '').trim(),
                        name: String(row.board_name || row.name || '').trim(),
                    }))
                    .filter((row) => row.code);
                const query = document.getElementById('iiaBoardQuery');
                this._filterCatalog(query ? query.value : '');
                this._closeList();
            } catch (e) {
                console.error(e);
                this._catalog = [];
                this._showChosen('行业列表加载失败', true);
                pick.innerHTML = '<p class="iia-board-pick__status">行业列表加载失败</p>';
            }
        },

        _openList() {
            this._listOpen = true;
            const query = document.getElementById('iiaBoardQuery');
            this._filterCatalog(query ? query.value : '');
        },

        _closeList() {
            this._listOpen = false;
            const pick = document.getElementById('iiaBoardPick');
            const query = document.getElementById('iiaBoardQuery');
            if (pick) {
                pick.classList.remove('is-open');
                pick.hidden = true;
            }
            if (query) query.setAttribute('aria-expanded', 'false');
        },

        _pickedRow() {
            const code = String(this._pickedCode || '');
            if (!code || !Array.isArray(this._catalog)) return null;
            return this._catalog.find((row) => row.code === code) || null;
        },

        _showChosen(text, isError) {
            const el = document.getElementById('iiaBoardChosen');
            if (!el) return;
            if (!text) {
                el.hidden = true;
                el.textContent = '';
                el.classList.remove('is-error');
                return;
            }
            el.hidden = false;
            el.textContent = text;
            el.classList.toggle('is-error', !!isError);
        },

        _syncChosen() {
            const row = this._pickedRow();
            if (!row) {
                this._showChosen('');
                return;
            }
            this._showChosen(`已选 ${row.name || row.code} ${row.code}`);
        },

        _choose(code) {
            const row = (this._catalog || []).find((item) => item.code === code);
            if (!row) return;
            this._pickedCode = row.code;
            const query = document.getElementById('iiaBoardQuery');
            if (query) query.value = row.name || row.code;
            this._syncChosen();
            this._closeList();
        },

        _onQueryKey(event) {
            if (event.key === 'Escape') {
                this._closeList();
                return;
            }
            if (event.key !== 'Enter') return;
            event.preventDefault();
            const pick = document.getElementById('iiaBoardPick');
            const first = pick && pick.querySelector('.iia-board-pick__item');
            if (first) this._choose(first.getAttribute('data-code') || '');
        },

        _filterCatalog(raw) {
            const pick = document.getElementById('iiaBoardPick');
            if (!pick || !Array.isArray(this._catalog)) return;
            const q = String(raw || '').trim().toLowerCase();
            const rows = this._catalog.filter((row) => {
                if (!q) return true;
                return row.name.toLowerCase().indexOf(q) >= 0 || row.code.toLowerCase().indexOf(q) >= 0;
            }).slice(0, 80);
            const exact = q
                ? this._catalog.find((row) => row.code.toLowerCase() === q || row.name.toLowerCase() === q)
                : null;
            if (exact) this._pickedCode = exact.code;
            else if (this._pickedCode) {
                const current = this._pickedRow();
                const name = current ? String(current.name || '').toLowerCase() : '';
                const code = current ? String(current.code || '').toLowerCase() : '';
                if (q !== name && q !== code) this._pickedCode = '';
            }
            this._syncChosen();
            const query = document.getElementById('iiaBoardQuery');
            if (this._listOpen) {
                pick.hidden = false;
                pick.classList.add('is-open');
                if (query) query.setAttribute('aria-expanded', 'true');
            }
            if (!rows.length) {
                pick.innerHTML = '<p class="iia-board-pick__status">无匹配行业</p>';
                return;
            }
            pick.innerHTML = rows.map((row) => {
                const selected = row.code === this._pickedCode ? ' is-selected' : '';
                const label = `${row.name || row.code} ${row.code}`;
                return `<button type="button" class="iia-board-pick__item${selected}" role="option" data-code="${this._esc(row.code)}" aria-selected="${selected ? 'true' : 'false'}">${this._esc(label)}</button>`;
            }).join('');
            if (!pick.dataset.bound) {
                pick.dataset.bound = '1';
                pick.addEventListener('mousedown', (event) => event.preventDefault());
                pick.addEventListener('click', (event) => {
                    const btn = event.target && event.target.closest
                        ? event.target.closest('.iia-board-pick__item')
                        : null;
                    if (!btn) return;
                    this._choose(btn.getAttribute('data-code') || '');
                });
            }
        },

        selectedCode() {
            if (this._detailCode) return this._detailCode;
            return String(this._pickedCode || '').trim();
        },

        async runFromWorkbench(useRealtime) {
            const code = this.selectedCode();
            if (!code) {
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast('请先从列表点选行业板块', 'warning');
                }
                return;
            }
            const dateEl = document.getElementById('iiaTradeDate');
            const date = dateEl && dateEl.value ? dateEl.value : '';
            await this.run({ code, date, useRealtime });
        },

        async run(opts) {
            const options = opts || {};
            const code = String(options.code || '').trim();
            if (!code) return;
            const picked = this._pickedRow();
            const busyName = (picked && (picked.name || picked.code)) || this.lastName || code;
            this._closeList();
            this._setBusy(true, busyName);
            try {
                await this.ensureScripts();
                const data = await this.fetchBundle(code, options);
                this.lastBundle = data;
                this.lastCode = (data.index && data.index.code) || code;
                this.lastName = (data.index && data.index.name) || '';
                this.render(data);
                this._enableExport(true);
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast(`${this.lastName || this.lastCode} 分析完成`, 'success');
                }
            } catch (e) {
                console.error('[IndustryIndexAnalysis]', e);
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
            const q = new URLSearchParams({ board_code: code });
            if (options.date && !options.useRealtime) q.set('date', String(options.date).slice(0, 10));
            if (options.useRealtime) q.set('use_realtime', 'true');
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/analysis/industry-index-analysis-bundle?${q.toString()}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
            }
            return payload.data || {};
        },

        render(data) {
            if (!global.PaAnalysisView) return;
            PaAnalysisView.render(data, {
                prefix: 'iia',
                showSectorContrib: false,
                assetType: 'industry_index',
                patternMetaLabel: '行业指数',
                emptyBreadthText: '库内暂无该行业成分，广度从略；价格行为仍可用。',
            });
            if (global.BoardFlowFocus) BoardFlowFocus.render(data, 'iia');
        },

        detailSectionHtml() {
            return `
            <div class="sector-detail-section" id="iiaDetailSection">
                <div class="sector-detail-section-head">
                    <h3>行业指数分析</h3>
                    <div class="sector-detail-actions">
                        <button type="button" class="btn btn-primary" id="iiaAnalyzeBtn">分析</button>
                        <button type="button" class="btn btn-secondary" id="iiaRealtimeAnalyzeBtn" title="刷新现价与广度，不改写当日K">实时分析</button>
                        <button type="button" class="btn btn-secondary" id="iiaExportPdfBtn" disabled>导出 PDF</button>
                        <button type="button" class="btn btn-secondary" id="iiaExportPngBtn" disabled>导出 PNG</button>
                    </div>
                </div>
                ${resultSectionsHtml()}
            </div>`;
        },

        mountDetail(opts) {
            const options = opts || {};
            this._detailCode = String(options.code || '').trim();
            this._bound = false;
            this._bindWorkbench();
            this._bound = true;
            if (options.auto && this._detailCode) {
                const dateEl = document.getElementById('iiaTradeDate');
                this.run({
                    code: this._detailCode,
                    date: dateEl && dateEl.value ? dateEl.value : '',
                    useRealtime: false,
                });
            }
        },

        hasExportableResult() {
            return !!(this.lastBundle && this.lastCode);
        },

        pngFilename() {
            const d = (this.lastBundle && this.lastBundle.trade_date) || '';
            return `行业指数分析_${this.lastCode || 'board'}_${d || 'latest'}.png`;
        },

        pdfFilename() {
            const d = (this.lastBundle && this.lastBundle.trade_date) || '';
            return `行业指数分析_${this.lastCode || 'board'}_${d || 'latest'}.pdf`;
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
            const root = document.getElementById('iiaExportRoot');
            const ssaRoot = document.getElementById('ssaExportRoot');
            let swapped = false;
            try {
                if (root && (!ssaRoot || ssaRoot !== root)) {
                    root.id = 'ssaExportRoot';
                    if (ssaRoot) ssaRoot.id = 'iiaExportRoot__tmp';
                    swapped = true;
                }
                const name = await StockAnalysisPng.exportFromHost({
                    hasExportableResult: () => this.hasExportableResult(),
                    pngFilename: () => this.pngFilename(),
                });
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(`已导出 ${name}`, 'success');
            } catch (e) {
                console.error(e);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(e.message || 'PNG 导出失败', 'error');
            } finally {
                if (swapped) {
                    const now = document.getElementById('ssaExportRoot');
                    const tmp = document.getElementById('iiaExportRoot__tmp');
                    if (now) now.id = 'iiaExportRoot';
                    if (tmp) tmp.id = 'ssaExportRoot';
                }
            }
        },

        async exportPdf() {
            if (!this.hasExportableResult()) {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('请先完成分析再导出', 'warning');
                return;
            }
            await this.ensureScripts();
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

        _setBusy(busy, name) {
            const analyze = document.getElementById('iiaAnalyzeBtn');
            const realtime = document.getElementById('iiaRealtimeAnalyzeBtn');
            if (analyze) {
                analyze.disabled = !!busy;
                analyze.textContent = busy ? '分析中…' : '分析';
            }
            if (realtime) {
                realtime.disabled = !!busy;
                realtime.textContent = busy ? '分析中…' : '实时分析';
            }
            const status = document.getElementById('iiaAnalyzeStatus');
            if (status) {
                status.hidden = !busy;
                status.textContent = busy ? `正在分析${name ? ' ' + name : ''}…` : '';
            }
        },

        _enableExport(on) {
            ['iiaExportPngBtn', 'iiaExportPdfBtn'].forEach((id) => {
                const btn = document.getElementById(id);
                if (btn) btn.disabled = !on;
            });
        },

        _esc(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        },
    };

    global.IndustryIndexAnalysis = IndustryIndexAnalysis;
})(typeof window !== 'undefined' ? window : globalThis);
