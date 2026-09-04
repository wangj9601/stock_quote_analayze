/**
 * 分析频道 · 个股综合分析（RPE / SBBR / GMS / URT + 阻力支撑 + 形态 + 波段趋势 + 江恩）
 */
const StockMultiStrategy = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
    running: false,
    exporting: false,
    observing: false,
    gannObserving: false,
    lastStrategy: null,
    lastStrategyError: null,
    lastStock: null,
    lastTradeDate: null,
    lastLevels: null,
    lastRs: null,
    lastPattern: null,
    lastSwing: null,
    lastGann: null,
    lastTradePlan: null,
    lastUseRealtime: false,
    lastRealtime: null,
    embeddedMode: false,
    MAX_WATCHLIST_BATCH: 0,
    /** 未勾选「一次分析全部」时的建议上限；0 表示不限制 */
    WATCHLIST_BATCH_SOFT_LIMIT: 15,
    stockSessions: {},
    activeSessionKey: null,
    watchlistStocks: [],
    industryBoardCatalog: [],
    conceptBoardCatalog: [],
    leaderStockOptions: [],
    industryLeaderStockOptions: [],
    conceptLeaderStockOptions: [],
    _industryCatalogLoaded: false,
    _conceptCatalogLoaded: false,

    init() {
        const btn = document.getElementById('ssaAnalyzeBtn');
        if (btn) {
            btn.addEventListener('click', () => this.analyze());
        }
        const rtBtn = document.getElementById('ssaRealtimeAnalyzeBtn');
        if (rtBtn) {
            rtBtn.addEventListener('click', () => this.analyze({ useRealtime: true }));
        }
        const exportBtn = document.getElementById('ssaExportPdfBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPdf());
        }
        const exportPngBtn = document.getElementById('ssaExportPngBtn');
        if (exportPngBtn) {
            exportPngBtn.addEventListener('click', () => this.exportPng());
        }
        const observeBtn = document.getElementById('ssaTradeObserveBtn');
        if (observeBtn) {
            observeBtn.addEventListener('click', () => this.addTradeObserve());
        }
        const gannObserveBtn = document.getElementById('ssaGannTradeObserveBtn');
        if (gannObserveBtn) {
            gannObserveBtn.addEventListener('click', () => this.addGannTradeObserve());
        }
        const codeInput = document.getElementById('ssaStockCode');
        if (codeInput) {
            codeInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.analyze();
                }
            });
            codeInput.addEventListener('input', () => {
                this.updateTradeObserveBtn();
                this.updateGannTradeObserveBtn();
            });
        }
        this.bindWatchlistPanel();
        this.bindLeaderPanel();
        const dateEl = document.getElementById('ssaTradeDate');
        if (dateEl) {
            dateEl.addEventListener('change', () => this.updateTradeObserveBtn());
        }
        this.updateExportBtn();
        this.updateTradeObserveBtn();
        this.bindScrollFab();
    },

    /** 个股详情页嵌入式面板：无代码输入框，按钮文案为「刷新」。 */
    initEmbedded() {
        if (this._embeddedInited) return;
        this._embeddedInited = true;
        this.embeddedMode = true;
        const btn = document.getElementById('ssaAnalyzeBtn');
        if (btn) {
            btn.textContent = '刷新';
            btn.addEventListener('click', () => this.analyze());
        }
        const rtBtn = document.getElementById('ssaRealtimeAnalyzeBtn');
        if (rtBtn) {
            rtBtn.addEventListener('click', () => this.analyze({ useRealtime: true }));
        }
        const exportBtn = document.getElementById('ssaExportPdfBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPdf());
        }
        const exportPngBtn = document.getElementById('ssaExportPngBtn');
        if (exportPngBtn) {
            exportPngBtn.addEventListener('click', () => this.exportPng());
        }
        const observeBtn = document.getElementById('ssaTradeObserveBtn');
        if (observeBtn) {
            observeBtn.addEventListener('click', () => this.addTradeObserve());
        }
        const gannObserveBtn = document.getElementById('ssaGannTradeObserveBtn');
        if (gannObserveBtn) {
            gannObserveBtn.addEventListener('click', () => this.addGannTradeObserve());
        }
        const dateEl = document.getElementById('ssaTradeDate');
        if (dateEl) {
            dateEl.addEventListener('change', () => this.updateTradeObserveBtn());
        }
        this.updateExportBtn();
        this.updateTradeObserveBtn();
    },

    /** 嵌入模式：由详情页传入 code/name 触发分析。 */
    async analyzeForCode(code, name) {
        const codeInput = document.getElementById('ssaStockCode');
        if (!codeInput) {
            this._pendingQuery = { code: String(code || '').trim(), name: String(name || '').trim() };
            return this.analyze();
        }
        const c = String(code || '').trim();
        const n = String(name || '').trim();
        codeInput.value = n ? `${c} ${n}` : c;
        this.embeddedMode = true;
        return this.analyze();
    },

    _resolveAnalyzeQuery() {
        const codeInput = document.getElementById('ssaStockCode');
        if (codeInput && (codeInput.value || '').trim()) {
            let query = (codeInput.value || '').trim();
            const firstToken = query.split(/\s+/)[0];
            const firstBody = /^(sh|sz|bj|hk)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
            if (/^\d{4,6}$/.test(firstBody)) query = firstToken;
            return { query, firstToken };
        }
        if (this._pendingQuery && this._pendingQuery.code) {
            const c = this._pendingQuery.code;
            const n = this._pendingQuery.name || '';
            return { query: n ? `${c} ${n}` : c, firstToken: c.split(/\s+/)[0] };
        }
        return null;
    },

    /**
     * 从 URL 启动分析（仅执行一次）：
     * - ?batch=watchlist：自选股「全部交易分析」，每只一个 Tab
     * - ?code=&name=：单只自动分析
     */
    bootstrapFromUrl() {
        if (this._urlBootstrapped) return;
        let params;
        try {
            params = new URLSearchParams(window.location.search || '');
        } catch (e) {
            return;
        }
        const batch = (params.get('batch') || '').trim();
        if (batch === 'watchlist') {
            this._urlBootstrapped = true;
            void this._bootstrapWatchlistBatch(params);
            return;
        }
        const code = (params.get('code') || '').trim();
        const name = (params.get('name') || '').trim();
        if (!code) return;
        this._urlBootstrapped = true;
        const input = document.getElementById('ssaStockCode');
        if (input) {
            input.value = name ? `${code} ${name}` : code;
        }
        void this.analyze();
    },

    /** 读取并清除自选批量分析载荷（跨标签页 localStorage） */
    _consumeWatchlistBatchStorage() {
        const key = 'ssa_watchlist_batch';
        let raw = null;
        try {
            raw = localStorage.getItem(key);
            if (raw != null) localStorage.removeItem(key);
        } catch (e) {
            return [];
        }
        if (!raw) return [];
        try {
            const data = JSON.parse(raw);
            const ts = Number(data && data.ts) || 0;
            if (ts && (Date.now() - ts) > 5 * 60 * 1000) return [];
            const stocks = Array.isArray(data && data.stocks) ? data.stocks : [];
            return stocks
                .map((s) => ({
                    code: String((s && s.code) || '').trim(),
                    name: String((s && s.name) || '').trim(),
                }))
                .filter((s) => s.code);
        } catch (e) {
            return [];
        }
    },

    /**
     * 自选股批量入口：勾选「一次分析全部」、按只建 Tab 并并行分析。
     */
    async _bootstrapWatchlistBatch(params) {
        const allowAllEl = document.getElementById('ssaAnalyzeAllSelected');
        if (allowAllEl) allowAllEl.checked = true;

        let stocks = this._consumeWatchlistBatchStorage();
        if (!stocks.length) {
            const codesRaw = (params.get('codes') || '').trim();
            const codes = codesRaw
                ? codesRaw.split(/[,，\s]+/).map((c) => c.trim()).filter(Boolean)
                : [];
            await this.loadWatchlistOptions();
            const byCode = new Map(
                (this.watchlistStocks || []).map((s) => [String(s.code), s])
            );
            stocks = codes.map((code) => {
                const hit = byCode.get(code);
                return { code, name: (hit && hit.name) || '' };
            });
        }
        if (!stocks.length) {
            if (window.CommonUtils) {
                CommonUtils.showToast('未找到待分析的自选股', 'warning');
            }
            return;
        }

        this._watchlistSelectedCodes = new Set(stocks.map((s) => String(s.code)));
        this.updateWatchlistSummary();
        await this.analyzeWatchlistBatch(stocks, { skipLargeConfirm: true });
    },

    bindScrollFab() {
        const btn = document.getElementById('ssaScrollToggleBtn');
        if (!btn || btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => this.onScrollFabClick());
        const sync = () => this.syncScrollFab();
        window.addEventListener('scroll', sync, { passive: true });
        window.addEventListener('resize', sync, { passive: true });
        this.syncScrollFab();
    },

    _scrollMetrics() {
        const doc = document.documentElement;
        const body = document.body;
        const scrollTop = window.pageYOffset
            || (doc && doc.scrollTop)
            || (body && body.scrollTop)
            || 0;
        const viewport = window.innerHeight || (doc && doc.clientHeight) || 0;
        const scrollHeight = Math.max(
            doc ? doc.scrollHeight : 0,
            body ? body.scrollHeight : 0,
            doc ? doc.offsetHeight : 0,
            body ? body.offsetHeight : 0
        );
        return { scrollTop, viewport, scrollHeight };
    },

    /** 靠近底部时显示 Top，其余显示 Bottom */
    syncScrollFab() {
        const btn = document.getElementById('ssaScrollToggleBtn');
        if (!btn) return;
        const { scrollTop, viewport, scrollHeight } = this._scrollMetrics();
        const nearBottom = scrollTop + viewport >= scrollHeight - 80;
        const mode = nearBottom ? 'top' : 'bottom';
        btn.dataset.mode = mode;
        if (mode === 'top') {
            btn.textContent = 'Top';
            btn.title = '回到顶部';
            btn.setAttribute('aria-label', '回到顶部');
        } else {
            btn.textContent = 'Bottom';
            btn.title = '直达底部';
            btn.setAttribute('aria-label', '直达底部');
        }
    },

    onScrollFabClick() {
        const btn = document.getElementById('ssaScrollToggleBtn');
        const mode = (btn && btn.dataset.mode) || 'bottom';
        if (mode === 'top') {
            this.scrollPageTop();
        } else {
            this.scrollPageBottom();
        }
    },

    scrollPageTop() {
        window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
        // smooth 滚动中主动刷新文案
        window.setTimeout(() => this.syncScrollFab(), 350);
    },

    scrollPageBottom() {
        const { scrollHeight } = this._scrollMetrics();
        window.scrollTo({ top: scrollHeight, left: 0, behavior: 'smooth' });
        window.setTimeout(() => this.syncScrollFab(), 350);
    },

    bindWatchlistPanel() {
        if (this._watchlistBound || this.embeddedMode) return;
        const pickBtn = document.getElementById('ssaWatchlistPickBtn');
        const overlay = document.getElementById('ssaWatchlistPickerModal');
        if (!pickBtn || !overlay) return;
        this._watchlistBound = true;
        this._watchlistSelectedCodes = new Set();
        this._watchlistPickerDraft = new Set();

        pickBtn.addEventListener('click', () => {
            void this.openWatchlistPicker();
        });
        ['ssaWatchlistPickerClose', 'ssaWatchlistPickerCancel'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', () => this.hideWatchlistPicker());
        });
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.hideWatchlistPicker();
        });
        const searchEl = document.getElementById('ssaWatchlistPickerSearch');
        if (searchEl) {
            searchEl.addEventListener('input', () => this.renderWatchlistPickerList());
            searchEl.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    this.hideWatchlistPicker();
                }
            });
        }
        const selAll = document.getElementById('ssaWatchlistPickerSelectAll');
        if (selAll) {
            selAll.addEventListener('click', () => this.watchlistPickerSelectAllVisible());
        }
        const clearBtn = document.getElementById('ssaWatchlistPickerClear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.watchlistPickerClearVisible());
        }
        const confirmBtn = document.getElementById('ssaWatchlistPickerConfirm');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmWatchlistPicker());
        }
        const listEl = document.getElementById('ssaWatchlistPickerList');
        if (listEl) {
            listEl.addEventListener('change', (e) => {
                const t = e.target;
                if (!t || !t.matches('input[type="checkbox"][data-code]')) return;
                const code = t.getAttribute('data-code') || '';
                if (!code) return;
                if (t.checked) this._watchlistPickerDraft.add(code);
                else this._watchlistPickerDraft.delete(code);
                this.updateWatchlistPickerCount();
            });
        }
        this.updateWatchlistSummary();
    },

    async openWatchlistPicker() {
        await this.loadWatchlistOptions();
        this._watchlistPickerDraft = new Set(this._watchlistSelectedCodes || []);
        const searchEl = document.getElementById('ssaWatchlistPickerSearch');
        if (searchEl) searchEl.value = '';
        this.renderWatchlistPickerList();
        const overlay = document.getElementById('ssaWatchlistPickerModal');
        if (overlay) {
            overlay.style.display = 'flex';
            overlay.setAttribute('aria-hidden', 'false');
        }
        if (searchEl) window.setTimeout(() => searchEl.focus(), 0);
    },

    hideWatchlistPicker() {
        const overlay = document.getElementById('ssaWatchlistPickerModal');
        if (overlay) {
            overlay.style.display = 'none';
            overlay.setAttribute('aria-hidden', 'true');
        }
    },

    _filteredWatchlistItems() {
        const q = String(document.getElementById('ssaWatchlistPickerSearch')?.value || '')
            .trim()
            .toLowerCase();
        const items = this.watchlistStocks || [];
        if (!q) return items.slice();
        return items.filter((item) => {
            const text = `${item.code || ''} ${item.name || ''}`.toLowerCase();
            return text.includes(q);
        });
    },

    updateWatchlistPickerCount() {
        const countEl = document.getElementById('ssaWatchlistPickerCount');
        if (!countEl) return;
        const total = (this.watchlistStocks || []).length;
        const filtered = this._filteredWatchlistItems().length;
        const selected = (this._watchlistPickerDraft || new Set()).size;
        const q = String(document.getElementById('ssaWatchlistPickerSearch')?.value || '').trim();
        if (q) {
            countEl.textContent = `匹配 ${filtered} / 共 ${total} · 已勾选 ${selected}`;
        } else {
            countEl.textContent = `共 ${total} 个可选 · 已勾选 ${selected}`;
        }
    },

    renderWatchlistPickerList() {
        const listEl = document.getElementById('ssaWatchlistPickerList');
        if (!listEl) return;
        const items = this._filteredWatchlistItems();
        this.updateWatchlistPickerCount();
        if (!(this.watchlistStocks || []).length) {
            listEl.innerHTML = '<div class="lm-board-picker-empty">暂无自选股，请先在自选页添加</div>';
            return;
        }
        if (!items.length) {
            listEl.innerHTML = '<div class="lm-board-picker-empty">无匹配股票</div>';
            return;
        }
        const draft = this._watchlistPickerDraft || new Set();
        listEl.innerHTML = items.map((item) => {
            const code = item.code || '';
            const name = item.name || '';
            const checked = draft.has(code) ? ' checked' : '';
            const title = name ? `${code} ${name}` : code;
            return `<label class="lm-board-picker-item" title="${this.escAttr(title)}">
                <input type="checkbox" data-code="${this.escAttr(code)}" data-name="${this.escAttr(name)}"${checked}>
                <span class="lm-board-picker-item-text">
                    <span class="lm-board-picker-name">${this.esc(name || code)}</span>
                    <span class="lm-board-picker-code">${this.esc(code)}</span>
                </span>
            </label>`;
        }).join('');
    },

    watchlistPickerSelectAllVisible() {
        this._filteredWatchlistItems().forEach((item) => {
            if (item.code) this._watchlistPickerDraft.add(item.code);
        });
        this.renderWatchlistPickerList();
    },

    watchlistPickerClearVisible() {
        this._filteredWatchlistItems().forEach((item) => {
            if (item.code) this._watchlistPickerDraft.delete(item.code);
        });
        this.renderWatchlistPickerList();
    },

    confirmWatchlistPicker() {
        this._watchlistSelectedCodes = new Set(this._watchlistPickerDraft || []);
        this.updateWatchlistSummary();
        this.hideWatchlistPicker();
    },

    updateWatchlistSummary() {
        const el = document.getElementById('ssaWatchlistSummary');
        if (!el) return;
        const selected = this.getSelectedWatchlistStocks();
        const n = selected.length;
        const total = (this.watchlistStocks || []).length;
        if (!n) {
            el.textContent = total
                ? `未选择自选股（共 ${total} 只），点击「选择自选」`
                : '未选择自选股，点击「选择自选」';
            return;
        }
        if (n <= 3) {
            el.textContent = `已选 ${n} 只：${selected.map((s) => (s.name ? `${s.code} ${s.name}` : s.code)).join('、')}`;
            return;
        }
        const preview = selected.slice(0, 2).map((s) => (s.name ? `${s.code} ${s.name}` : s.code)).join('、');
        el.textContent = `已选 ${n} 只：${preview} 等`;
    },

    getSelectedWatchlistStocks() {
        const codes = this._watchlistSelectedCodes || new Set();
        if (!codes.size) return [];
        const byCode = new Map((this.watchlistStocks || []).map((s) => [s.code, s]));
        return Array.from(codes).map((code) => {
            const hit = byCode.get(code);
            return { code, name: (hit && hit.name) || '' };
        }).filter((item) => item.code);
    },

    async loadWatchlistOptions() {
        if (this._watchlistLoaded) return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        try {
            const resp = await authFetch(`${this.API_BASE_URL}/api/watchlist`);
            if (!resp.ok) return;
            const payload = await resp.json();
            const raw = Array.isArray(payload)
                ? payload
                : (payload.data || payload.items || payload.stocks || []);
            if (!Array.isArray(raw)) return;
            const seen = new Set();
            const items = [];
            raw.forEach((item) => {
                const code = String(item.code || item.stock_code || '').trim();
                if (!code || seen.has(code)) return;
                seen.add(code);
                const name = String(item.name || item.stock_name || '').trim();
                items.push({ code, name });
            });
            this.watchlistStocks = items;
            this._watchlistLoaded = true;
            this.updateWatchlistSummary();
        } catch (e) {
            console.warn('加载自选股失败', e);
        }
    },


    bindLeaderPanel() {
        if (this._leaderBound || this.embeddedMode) return;
        const industryBtn = document.getElementById('ssaLeaderPickBtn');
        const conceptBtn = document.getElementById('ssaConceptLeaderPickBtn');
        const overlay = document.getElementById('ssaLeaderPickerModal');
        if (!overlay || (!industryBtn && !conceptBtn)) return;
        this._leaderBound = true;
        this._leaderBoardKind = 'industry';
        this._industryLeaderSelectedBoardCodes = [];
        this._conceptLeaderSelectedBoardCodes = [];
        this._industryLeaderSelectedCodes = new Set();
        this._conceptLeaderSelectedCodes = new Set();
        this.industryLeaderStockOptions = [];
        this.conceptLeaderStockOptions = [];
        this._leaderBoardDraft = new Set();
        this._leaderStockDraft = new Set();
        this.leaderStockOptions = [];

        if (industryBtn) {
            industryBtn.addEventListener('click', () => {
                void this.openLeaderPicker('industry');
            });
        }
        if (conceptBtn) {
            conceptBtn.addEventListener('click', () => {
                void this.openLeaderPicker('concept');
            });
        }
        ['ssaLeaderPickerClose', 'ssaLeaderPickerCancel', 'ssaLeaderStockCancel'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', () => this.hideLeaderPicker());
        });
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.hideLeaderPicker();
        });

        const boardSearch = document.getElementById('ssaLeaderBoardSearch');
        if (boardSearch) {
            boardSearch.addEventListener('input', () => this.renderLeaderBoardList());
            boardSearch.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    this.hideLeaderPicker();
                }
            });
        }
        const stockSearch = document.getElementById('ssaLeaderStockSearch');
        if (stockSearch) {
            stockSearch.addEventListener('input', () => this.renderLeaderStockList());
        }
        const boardSelAll = document.getElementById('ssaLeaderBoardSelectAll');
        if (boardSelAll) {
            boardSelAll.addEventListener('click', () => this.leaderBoardSelectAllVisible());
        }
        const boardClear = document.getElementById('ssaLeaderBoardClear');
        if (boardClear) {
            boardClear.addEventListener('click', () => this.leaderBoardClearVisible());
        }
        const onLoad = () => {
            void this.loadLeaderStocksFromBoards();
        };
        const loadBtn = document.getElementById('ssaLeaderLoadStocksBtn');
        if (loadBtn) loadBtn.addEventListener('click', onLoad);
        const loadBtnTop = document.getElementById('ssaLeaderLoadStocksBtnTop');
        if (loadBtnTop) loadBtnTop.addEventListener('click', onLoad);
        const backBtn = document.getElementById('ssaLeaderBackToBoards');
        if (backBtn) {
            backBtn.addEventListener('click', () => this.showLeaderBoardStep());
        }
        const stockSelAll = document.getElementById('ssaLeaderStockSelectAll');
        if (stockSelAll) {
            stockSelAll.addEventListener('click', () => this.leaderStockSelectAllVisible());
        }
        const stockClear = document.getElementById('ssaLeaderStockClear');
        if (stockClear) {
            stockClear.addEventListener('click', () => this.leaderStockClearVisible());
        }
        const onConfirm = () => this.confirmLeaderPicker();
        const confirmBtn = document.getElementById('ssaLeaderStockConfirm');
        if (confirmBtn) confirmBtn.addEventListener('click', onConfirm);
        const confirmBtnTop = document.getElementById('ssaLeaderStockConfirmTop');
        if (confirmBtnTop) confirmBtnTop.addEventListener('click', onConfirm);

        const boardList = document.getElementById('ssaLeaderBoardList');
        if (boardList) {
            boardList.addEventListener('change', (e) => {
                const t = e.target;
                if (!t || !t.matches('input[type="checkbox"][data-board-code]')) return;
                const code = t.getAttribute('data-board-code') || '';
                if (!code) return;
                if (t.checked) this._leaderBoardDraft.add(code);
                else this._leaderBoardDraft.delete(code);
                this.updateLeaderBoardCount();
            });
        }
        const stockList = document.getElementById('ssaLeaderStockList');
        if (stockList) {
            stockList.addEventListener('change', (e) => {
                const t = e.target;
                if (!t || !t.matches('input[type="checkbox"][data-code]')) return;
                const code = t.getAttribute('data-code') || '';
                if (!code) return;
                if (t.checked) this._leaderStockDraft.add(code);
                else this._leaderStockDraft.delete(code);
                this.updateLeaderStockCount();
            });
        }
        this.updateLeaderSummary('industry');
        this.updateLeaderSummary('concept');
    },

    _normalizeLeaderKind(kind) {
        return kind === 'concept' ? 'concept' : 'industry';
    },

    _leaderKindLabel(kind) {
        return this._normalizeLeaderKind(kind) === 'concept' ? '概念' : '行业';
    },

    _leaderIncludeMidChecked(kind) {
        const id = this._normalizeLeaderKind(kind) === 'concept'
            ? 'ssaConceptLeaderIncludeMid'
            : 'ssaLeaderIncludeMid';
        return !!document.getElementById(id)?.checked;
    },

    async openLeaderPicker(kind) {
        this._leaderBoardKind = this._normalizeLeaderKind(kind);
        await this.loadBoardCatalog(this._leaderBoardKind);
        const savedBoards = this._leaderBoardKind === 'concept'
            ? (this._conceptLeaderSelectedBoardCodes || [])
            : (this._industryLeaderSelectedBoardCodes || []);
        const savedCodes = this._leaderBoardKind === 'concept'
            ? (this._conceptLeaderSelectedCodes || new Set())
            : (this._industryLeaderSelectedCodes || new Set());
        this.leaderStockOptions = this._leaderBoardKind === 'concept'
            ? (this.conceptLeaderStockOptions || [])
            : (this.industryLeaderStockOptions || []);
        this._leaderBoardDraft = new Set(savedBoards);
        this._leaderStockDraft = new Set(savedCodes);
        const boardSearch = document.getElementById('ssaLeaderBoardSearch');
        if (boardSearch) boardSearch.value = '';
        const stockSearch = document.getElementById('ssaLeaderStockSearch');
        if (stockSearch) stockSearch.value = '';
        this.showLeaderBoardStep();
        this.renderLeaderBoardList();
        const overlay = document.getElementById('ssaLeaderPickerModal');
        if (overlay) {
            overlay.style.display = 'flex';
            overlay.setAttribute('aria-hidden', 'false');
        }
        if (boardSearch) window.setTimeout(() => boardSearch.focus(), 0);
    },

    hideLeaderPicker() {
        const overlay = document.getElementById('ssaLeaderPickerModal');
        if (overlay) {
            overlay.style.display = 'none';
            overlay.setAttribute('aria-hidden', 'true');
        }
    },

    showLeaderBoardStep() {
        const boards = document.getElementById('ssaLeaderStepBoards');
        const stocks = document.getElementById('ssaLeaderStepStocks');
        if (boards) boards.hidden = false;
        if (stocks) stocks.hidden = true;
        const label = this._leaderKindLabel(this._leaderBoardKind);
        const hint = document.getElementById('ssaLeaderPickerHint');
        if (hint) {
            hint.textContent =
                `步骤 1：勾选${label}板块 →「加载龙头」；步骤 2：勾选股票后确定。可选「含中军」。`;
        }
        const title = document.getElementById('ssaLeaderPickerTitle');
        if (title) title.textContent = `选择${label}龙头股 · 选板块`;
    },

    showLeaderStockStep() {
        const boards = document.getElementById('ssaLeaderStepBoards');
        const stocks = document.getElementById('ssaLeaderStepStocks');
        if (boards) boards.hidden = true;
        if (stocks) stocks.hidden = false;
        const label = this._leaderKindLabel(this._leaderBoardKind);
        const hint = document.getElementById('ssaLeaderPickerHint');
        if (hint) {
            const n = (this.leaderStockOptions || []).length;
            const includeMid = this._leaderIncludeMidChecked(this._leaderBoardKind);
            hint.textContent =
                `步骤 2：已加载 ${n} 只（${includeMid ? '龙头+中军' : '仅龙头'}），勾选后确定。`;
        }
        const title = document.getElementById('ssaLeaderPickerTitle');
        if (title) title.textContent = `选择${label}龙头股 · 选股票`;
    },

    async loadBoardCatalog(kind) {
        const k = this._normalizeLeaderKind(kind);
        if (k === 'concept') {
            if (this._conceptCatalogLoaded) return;
        } else if (this._industryCatalogLoaded) {
            return;
        }
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        const path = k === 'concept' ? 'concept_board' : 'industry_board';
        const label = this._leaderKindLabel(k);
        try {
            const resp = await authFetch(
                `${this.API_BASE_URL}/api/market/${path}/list?board_code_source=tonghuashun`
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const payload = await resp.json();
            const list = Array.isArray(payload.data) ? payload.data : [];
            if (k === 'concept') {
                this.conceptBoardCatalog = list;
                this._conceptCatalogLoaded = true;
            } else {
                this.industryBoardCatalog = list;
                this._industryCatalogLoaded = true;
            }
        } catch (e) {
            console.warn(`加载${label}板块失败`, e);
            CommonUtils.showToast(`加载${label}板块失败`, 'error');
        }
    },

    async loadIndustryBoardCatalog() {
        return this.loadBoardCatalog('industry');
    },

    _leaderBoardCatalog() {
        return this._leaderBoardKind === 'concept'
            ? (this.conceptBoardCatalog || [])
            : (this.industryBoardCatalog || []);
    },

    _filteredLeaderBoards() {
        const q = String(document.getElementById('ssaLeaderBoardSearch')?.value || '')
            .trim()
            .toLowerCase();
        const items = this._leaderBoardCatalog();
        if (!q) return items.slice();
        return items.filter((b) => {
            const text = `${b.board_code || ''} ${b.board_name || ''}`.toLowerCase();
            return text.includes(q);
        });
    },

    updateLeaderBoardCount() {
        const countEl = document.getElementById('ssaLeaderBoardCount');
        if (!countEl) return;
        const total = this._leaderBoardCatalog().length;
        const filtered = this._filteredLeaderBoards().length;
        const selected = (this._leaderBoardDraft || new Set()).size;
        const q = String(document.getElementById('ssaLeaderBoardSearch')?.value || '').trim();
        countEl.textContent = q
            ? `匹配 ${filtered} / 共 ${total} · 已勾选 ${selected}`
            : `共 ${total} 个可选 · 已勾选 ${selected}`;
    },

    renderLeaderBoardList() {
        const listEl = document.getElementById('ssaLeaderBoardList');
        if (!listEl) return;
        const items = this._filteredLeaderBoards();
        const label = this._leaderKindLabel(this._leaderBoardKind);
        this.updateLeaderBoardCount();
        if (!this._leaderBoardCatalog().length) {
            listEl.innerHTML = `<div class="lm-board-picker-empty">暂无${label}板块数据</div>`;
            return;
        }
        if (!items.length) {
            listEl.innerHTML = '<div class="lm-board-picker-empty">无匹配板块</div>';
            return;
        }
        const draft = this._leaderBoardDraft || new Set();
        listEl.innerHTML = items.map((b) => {
            const code = String(b.board_code || '').trim();
            const name = String(b.board_name || '').trim();
            const checked = draft.has(code) ? ' checked' : '';
            const title = name ? `${name}（${code}）` : code;
            return `<label class="lm-board-picker-item" title="${this.escAttr(title)}">
                <input type="checkbox" data-board-code="${this.escAttr(code)}"${checked}>
                <span class="lm-board-picker-item-text">
                    <span class="lm-board-picker-name">${this.esc(name || code)}</span>
                    <span class="lm-board-picker-code">${this.esc(code)}</span>
                </span>
            </label>`;
        }).join('');
    },

    leaderBoardSelectAllVisible() {
        this._filteredLeaderBoards().forEach((b) => {
            const code = String(b.board_code || '').trim();
            if (code) this._leaderBoardDraft.add(code);
        });
        this.renderLeaderBoardList();
    },

    leaderBoardClearVisible() {
        this._filteredLeaderBoards().forEach((b) => {
            const code = String(b.board_code || '').trim();
            if (code) this._leaderBoardDraft.delete(code);
        });
        this.renderLeaderBoardList();
    },

    async loadLeaderStocksFromBoards() {
        const boardCodes = Array.from(this._leaderBoardDraft || []);
        const label = this._leaderKindLabel(this._leaderBoardKind);
        if (!boardCodes.length) {
            CommonUtils.showToast(`请先勾选至少一个${label}板块`, 'warning');
            return;
        }
        if (boardCodes.length > 40) {
            const ok = window.confirm(
                `已选 ${boardCodes.length} 个板块，加载龙头可能较慢，是否继续？`
            );
            if (!ok) return;
        }
        const includeMid = this._leaderIncludeMidChecked(this._leaderBoardKind);
        const boardPath = this._leaderBoardKind === 'concept' ? 'concept_board' : 'industry_board';
        const loadBtns = [
            document.getElementById('ssaLeaderLoadStocksBtn'),
            document.getElementById('ssaLeaderLoadStocksBtnTop'),
        ].filter(Boolean);
        loadBtns.forEach((btn) => {
            btn.disabled = true;
            btn.textContent = '加载中…';
        });
        try {
            const byCode = new Map();
            const concurrency = 6;
            let idx = 0;
            const catalog = this._leaderBoardCatalog();
            const worker = async () => {
                while (idx < boardCodes.length) {
                    const i = idx;
                    idx += 1;
                    const boardCode = boardCodes[i];
                    const board = catalog.find(
                        (x) => String(x.board_code) === String(boardCode)
                    );
                    const boardName = board ? (board.board_name || boardCode) : boardCode;
                    try {
                        const url =
                            `${this.API_BASE_URL}/api/market/${boardPath}/` +
                            `${encodeURIComponent(boardCode)}/roles?board_code_source=tonghuashun`;
                        const resp = await authFetch(url);
                        if (!resp.ok) continue;
                        const payload = await resp.json();
                        const data = payload.data || {};
                        const leaders = Array.isArray(data.leaders) ? data.leaders : [];
                        const mids = includeMid && Array.isArray(data.mids) ? data.mids : [];
                        [...leaders, ...mids].forEach((item) => {
                            const code = String(item.code || item.stock_code || '').trim();
                            if (!code) return;
                            const name = String(item.name || item.stock_name || '').trim();
                            const role = String(item.board_role || '').toLowerCase() === 'mid'
                                ? 'mid'
                                : 'leader';
                            const prev = byCode.get(code);
                            if (!prev) {
                                byCode.set(code, {
                                    code,
                                    name,
                                    role,
                                    board_name: boardName,
                                    board_code: boardCode,
                                    board_kind: this._leaderBoardKind,
                                });
                                return;
                            }
                            if (prev.role !== 'leader' && role === 'leader') {
                                prev.role = 'leader';
                            }
                            if (boardName && !(prev.board_name || '').includes(boardName)) {
                                prev.board_name = prev.board_name
                                    ? `${prev.board_name}、${boardName}`
                                    : boardName;
                            }
                        });
                    } catch (e) {
                        console.warn('加载板块龙头失败', boardCode, e);
                    }
                }
            };
            await Promise.all(
                Array.from({ length: Math.min(concurrency, boardCodes.length) }, () => worker())
            );
            this.leaderStockOptions = Array.from(byCode.values()).sort((a, b) =>
                String(a.code).localeCompare(String(b.code))
            );
            if (this._leaderBoardKind === 'concept') {
                this.conceptLeaderStockOptions = this.leaderStockOptions.slice();
                this._conceptLeaderSelectedBoardCodes = boardCodes.slice();
            } else {
                this.industryLeaderStockOptions = this.leaderStockOptions.slice();
                this._industryLeaderSelectedBoardCodes = boardCodes.slice();
            }
            const prevSelected = this._leaderBoardKind === 'concept'
                ? (this._conceptLeaderSelectedCodes || new Set())
                : (this._industryLeaderSelectedCodes || new Set());
            this._leaderStockDraft = new Set(
                prevSelected.size
                    ? Array.from(prevSelected).filter((c) => byCode.has(c))
                    : this.leaderStockOptions.map((s) => s.code)
            );
            if (!this.leaderStockOptions.length) {
                CommonUtils.showToast(`所选${label}板块暂无龙头/中军数据`, 'warning');
                return;
            }
            this.showLeaderStockStep();
            this.renderLeaderStockList();
        } finally {
            loadBtns.forEach((btn) => {
                btn.disabled = false;
                btn.textContent = btn.id === 'ssaLeaderLoadStocksBtn' ? '加载龙头 →' : '加载龙头';
            });
        }
    },

    _filteredLeaderStocks() {
        const q = String(document.getElementById('ssaLeaderStockSearch')?.value || '')
            .trim()
            .toLowerCase();
        const items = this.leaderStockOptions || [];
        if (!q) return items.slice();
        return items.filter((item) => {
            const text = `${item.code || ''} ${item.name || ''} ${item.board_name || ''}`.toLowerCase();
            return text.includes(q);
        });
    },

    updateLeaderStockCount() {
        const countEl = document.getElementById('ssaLeaderStockCount');
        if (!countEl) return;
        const total = (this.leaderStockOptions || []).length;
        const filtered = this._filteredLeaderStocks().length;
        const selected = (this._leaderStockDraft || new Set()).size;
        const q = String(document.getElementById('ssaLeaderStockSearch')?.value || '').trim();
        countEl.textContent = q
            ? `匹配 ${filtered} / 共 ${total} · 已勾选 ${selected}`
            : `共 ${total} 个可选 · 已勾选 ${selected}`;
    },

    renderLeaderStockList() {
        const listEl = document.getElementById('ssaLeaderStockList');
        if (!listEl) return;
        const items = this._filteredLeaderStocks();
        this.updateLeaderStockCount();
        if (!(this.leaderStockOptions || []).length) {
            listEl.innerHTML = '<div class="lm-board-picker-empty">暂无龙头股，请返回重新选板加载</div>';
            return;
        }
        if (!items.length) {
            listEl.innerHTML = '<div class="lm-board-picker-empty">无匹配股票</div>';
            return;
        }
        const draft = this._leaderStockDraft || new Set();
        listEl.innerHTML = items.map((item) => {
            const code = item.code || '';
            const name = item.name || '';
            const role = item.role === 'mid' ? 'mid' : 'leader';
            const roleLabel = role === 'mid' ? '中军' : '龙头';
            const checked = draft.has(code) ? ' checked' : '';
            const boardMeta = item.board_name
                ? `<span class="ssa-leader-board-meta">${this.esc(item.board_name)}</span>`
                : '';
            const title = name ? `${code} ${name}` : code;
            return `<label class="lm-board-picker-item" title="${this.escAttr(title)}">
                <input type="checkbox" data-code="${this.escAttr(code)}" data-name="${this.escAttr(name)}"${checked}>
                <span class="lm-board-picker-item-text">
                    <span class="lm-board-picker-name">
                        ${this.esc(name || code)}
                        <span class="ssa-leader-role-tag${role === 'mid' ? ' is-mid' : ''}">${roleLabel}</span>
                    </span>
                    <span class="lm-board-picker-code">${this.esc(code)}</span>
                    ${boardMeta}
                </span>
            </label>`;
        }).join('');
    },

    leaderStockSelectAllVisible() {
        this._filteredLeaderStocks().forEach((item) => {
            if (item.code) this._leaderStockDraft.add(item.code);
        });
        this.renderLeaderStockList();
    },

    leaderStockClearVisible() {
        this._filteredLeaderStocks().forEach((item) => {
            if (item.code) this._leaderStockDraft.delete(item.code);
        });
        this.renderLeaderStockList();
    },

    confirmLeaderPicker() {
        const selected = new Set(this._leaderStockDraft || []);
        const boards = Array.from(this._leaderBoardDraft || []);
        if (this._leaderBoardKind === 'concept') {
            this._conceptLeaderSelectedCodes = selected;
            this.conceptLeaderStockOptions = (this.leaderStockOptions || []).slice();
            this._conceptLeaderSelectedBoardCodes = boards;
        } else {
            this._industryLeaderSelectedCodes = selected;
            this.industryLeaderStockOptions = (this.leaderStockOptions || []).slice();
            this._industryLeaderSelectedBoardCodes = boards;
        }
        this.updateLeaderSummary(this._leaderBoardKind);
        this.hideLeaderPicker();
    },

    updateLeaderSummary(kind) {
        const k = this._normalizeLeaderKind(kind || this._leaderBoardKind || 'industry');
        const elId = k === 'concept' ? 'ssaConceptLeaderSummary' : 'ssaLeaderSummary';
        const el = document.getElementById(elId);
        if (!el) return;
        const label = this._leaderKindLabel(k);
        const selected = this.getSelectedLeaderStocks(k);
        const n = selected.length;
        const boards = k === 'concept'
            ? (this._conceptLeaderSelectedBoardCodes || []).length
            : (this._industryLeaderSelectedBoardCodes || []).length;
        if (!n) {
            el.textContent = boards
                ? `未勾选龙头股（已备选板块 ${boards} 个），点击「选择${label}龙头」`
                : `未选择${label}龙头，点击「选择${label}龙头」`;
            return;
        }
        if (n <= 3) {
            el.textContent = `已选 ${n} 只：${selected.map((s) => (s.name ? `${s.code} ${s.name}` : s.code)).join('、')}`;
            return;
        }
        const preview = selected.slice(0, 2).map((s) => (s.name ? `${s.code} ${s.name}` : s.code)).join('、');
        el.textContent = `已选 ${n} 只：${preview} 等`;
    },

    getSelectedLeaderStocks(kind) {
        const k = kind ? this._normalizeLeaderKind(kind) : null;
        const packs = [];
        if (!k || k === 'industry') {
            packs.push({
                codes: this._industryLeaderSelectedCodes || new Set(),
                options: this.industryLeaderStockOptions || [],
            });
        }
        if (!k || k === 'concept') {
            packs.push({
                codes: this._conceptLeaderSelectedCodes || new Set(),
                options: this.conceptLeaderStockOptions || [],
            });
        }
        const map = new Map();
        packs.forEach(({ codes, options }) => {
            if (!codes || !codes.size) return;
            const byCode = new Map(options.map((s) => [s.code, s]));
            codes.forEach((code) => {
                if (!code || map.has(code)) return;
                const hit = byCode.get(code);
                map.set(code, { code, name: (hit && hit.name) || '' });
            });
        });
        return Array.from(map.values());
    },

    /** 自选 + 行业龙头 + 概念龙头 去重合并，供批量分析 */
    getSelectedBatchStocks() {
        const map = new Map();
        this.getSelectedWatchlistStocks().forEach((s) => {
            if (s.code) map.set(s.code, s);
        });
        this.getSelectedLeaderStocks().forEach((s) => {
            if (!s.code) return;
            if (!map.has(s.code)) map.set(s.code, s);
            else if (s.name && !map.get(s.code).name) map.set(s.code, s);
        });
        return Array.from(map.values());
    },

    _sessionKey(code) {
        let c = String(code || '').trim();
        if (/^(sh|sz|bj|hk)/i.test(c)) c = c.slice(2);
        return c || '';
    },

    _ensureStockTab(key, code, name) {
        if (!key || this.embeddedMode) return;
        if (!this.stockSessions) this.stockSessions = {};
        if (!this.stockSessions[key]) {
            this.stockSessions[key] = {
                key,
                code: code || key,
                name: name || '',
                status: 'pending',
                state: null,
                dom: null,
                errorMessage: '',
            };
        } else {
            if (code) this.stockSessions[key].code = code;
            if (name) this.stockSessions[key].name = name;
        }
        const tabsEl = document.getElementById('ssaStockTabs');
        if (tabsEl) tabsEl.hidden = false;
    },

    _renderStockTabs() {
        const host = document.getElementById('ssaStockTabs');
        if (!host || this.embeddedMode) return;
        if (!this.stockSessions) this.stockSessions = {};
        const keys = Object.keys(this.stockSessions);
        if (!keys.length) {
            host.hidden = true;
            host.innerHTML = '';
            return;
        }
        host.hidden = false;
        const canClose = !this._batchAnalyzing;
        host.innerHTML = keys.map((key) => {
            const s = this.stockSessions[key];
            const label = s.name ? `${s.code} ${s.name}` : s.code;
            const cls = [
                'ssa-stock-tab',
                key === this.activeSessionKey ? 'active' : '',
                s.status === 'loading' || s.status === 'fetched' ? 'is-loading' : '',
                s.status === 'error' ? 'is-error' : '',
            ].filter(Boolean).join(' ');
            const closeBtn = canClose
                ? `<span class="ssa-stock-tab-close" data-close-key="${this.escAttr(key)}" title="关闭" role="button" tabindex="0" aria-label="关闭 ${this.escAttr(label)}">×</span>`
                : '';
            return `<button type="button" class="${cls}" data-session-key="${this.escAttr(key)}" role="tab" aria-selected="${key === this.activeSessionKey ? 'true' : 'false'}"><span class="ssa-stock-tab-label">${this.esc(label)}</span>${closeBtn}</button>`;
        }).join('');
        if (!host.dataset.bound) {
            host.dataset.bound = '1';
            host.addEventListener('click', (e) => {
                const closeEl = e.target.closest('.ssa-stock-tab-close[data-close-key]');
                if (closeEl) {
                    e.preventDefault();
                    e.stopPropagation();
                    this._closeStockTab(closeEl.getAttribute('data-close-key'));
                    return;
                }
                const btn = e.target.closest('.ssa-stock-tab[data-session-key]');
                if (!btn) return;
                this._switchStockTab(btn.getAttribute('data-session-key'), { persistPrevious: true });
            });
        }
    },

    _closeStockTab(key) {
        if (!key || this.embeddedMode || this._batchAnalyzing) return;
        if (!this.stockSessions || !this.stockSessions[key]) return;

        const keys = Object.keys(this.stockSessions);
        const closingActive = this.activeSessionKey === key;
        const idx = keys.indexOf(key);

        delete this.stockSessions[key];

        // 同步取消自选 / 行业龙头 / 概念龙头勾选状态（若仍在已选集合中）
        if (this._watchlistSelectedCodes && this._watchlistSelectedCodes.has(key)) {
            this._watchlistSelectedCodes.delete(key);
            this.updateWatchlistSummary();
        }
        let leaderChanged = false;
        if (this._industryLeaderSelectedCodes && this._industryLeaderSelectedCodes.has(key)) {
            this._industryLeaderSelectedCodes.delete(key);
            leaderChanged = true;
            this.updateLeaderSummary('industry');
        }
        if (this._conceptLeaderSelectedCodes && this._conceptLeaderSelectedCodes.has(key)) {
            this._conceptLeaderSelectedCodes.delete(key);
            leaderChanged = true;
            this.updateLeaderSummary('concept');
        }
        if (leaderChanged) {
            // summaries already refreshed above
        }

        const remain = Object.keys(this.stockSessions);
        if (!remain.length) {
            this.activeSessionKey = null;
            this._renderStockTabs();
            this.hideResultBlocks();
            const empty = document.getElementById('ssaEmpty');
            if (empty) {
                empty.hidden = false;
                empty.textContent = '已关闭全部标签。可重新选择自选股 / 行业龙头 / 概念龙头或输入代码后分析。';
            }
            this.updateExportBtn();
            return;
        }

        if (closingActive) {
            const nextKey = remain[Math.min(idx, remain.length - 1)] || remain[0];
            this._switchStockTab(nextKey, { persistPrevious: false });
        } else {
            this._renderStockTabs();
        }
    },

    _switchStockTab(key, opts) {
        if (!key || this.embeddedMode) return;
        const options = opts || {};
        const session = this.stockSessions && this.stockSessions[key];
        if (!session) return;

        // 批量分析进行中：禁止手动切 Tab，避免打断并行生成与结果缓存
        if (this._batchAnalyzing && options.persistPrevious !== false) {
            return;
        }

        if (options.persistPrevious && this.activeSessionKey && this.activeSessionKey !== key) {
            this._persistActiveSession();
        }
        this.activeSessionKey = key;
        this._renderStockTabs();
        const empty = document.getElementById('ssaEmpty');
        const codeInput = document.getElementById('ssaStockCode');
        if (codeInput && session.code) {
            codeInput.value = session.name ? `${session.code} ${session.name}` : session.code;
        }
        if (session.status === 'loading' || session.status === 'fetched') {
            this.hideCandidates();
            this.hideResultBlocks();
            if (empty) {
                empty.hidden = false;
                empty.textContent = this._batchAnalyzing ? '批量分析进行中，请稍候…' : '正在分析…';
            }
            return;
        }
        if (session.state && session.dom) {
            this._restoreSession(session);
            if (empty) empty.hidden = true;
            return;
        }
        this.hideResultBlocks();
        if (empty) {
            if (session.status === 'error') {
                empty.hidden = false;
                empty.textContent = session.errorMessage || '分析失败';
            } else {
                empty.hidden = false;
                empty.textContent = '暂无分析结果';
            }
        }
    },

    _captureState() {
        return {
            lastStrategy: this.lastStrategy,
            lastStrategyError: this.lastStrategyError,
            lastStock: this.lastStock,
            lastTradeDate: this.lastTradeDate,
            lastLevels: this.lastLevels,
            lastRs: this.lastRs,
            lastPattern: this.lastPattern,
            lastSwing: this.lastSwing,
            lastGann: this.lastGann,
            lastTradePlan: this.lastTradePlan,
        };
    },

    _applyState(state) {
        if (!state) return;
        this.lastStrategy = state.lastStrategy;
        this.lastStrategyError = state.lastStrategyError;
        this.lastStock = state.lastStock;
        this.lastTradeDate = state.lastTradeDate;
        this.lastLevels = state.lastLevels;
        this.lastRs = state.lastRs;
        this.lastPattern = state.lastPattern;
        this.lastSwing = state.lastSwing;
        this.lastGann = state.lastGann;
        this.lastTradePlan = state.lastTradePlan;
    },

    _captureDom() {
        const pick = (id) => {
            const el = document.getElementById(id);
            if (!el) return { html: '', hidden: true, className: '', text: '' };
            return {
                html: el.innerHTML,
                hidden: !!el.hidden,
                className: el.className || '',
                text: el.textContent || '',
            };
        };
        return {
            meta: pick('ssaMeta'),
            strategy: pick('ssaResults'),
            strategyBlock: pick('ssaStrategyBlock'),
            rsHost: pick('ssaRsHost'),
            rsBlock: pick('ssaRsBlock'),
            rsStatus: pick('ssaRsStatus'),
            levelsHost: pick('ssaLevelsHost'),
            levelsBlock: pick('ssaLevelsBlock'),
            levelsStatus: pick('ssaLevelsStatus'),
            patternHost: pick('ssaPatternHost'),
            patternBlock: pick('ssaPatternBlock'),
            patternStatus: pick('ssaPatternStatus'),
            swingHost: pick('ssaSwingHost'),
            swingBlock: pick('ssaSwingBlock'),
            swingStatus: pick('ssaSwingStatus'),
            gannHost: pick('ssaGannHost'),
            gannBlock: pick('ssaGannBlock'),
            gannStatus: pick('ssaGannStatus'),
            planHost: pick('ssaTradePlanHost'),
            planBlock: pick('ssaTradePlanBlock'),
            planStatus: pick('ssaTradePlanStatus'),
        };
    },

    _restoreDom(dom) {
        if (!dom) return;
        const apply = (id, snap) => {
            const el = document.getElementById(id);
            if (!el || !snap) return;
            el.innerHTML = snap.html || '';
            el.hidden = !!snap.hidden;
            if (snap.className) el.className = snap.className;
        };
        apply('ssaMeta', dom.meta);
        apply('ssaResults', dom.strategy);
        apply('ssaStrategyBlock', dom.strategyBlock);
        apply('ssaRsHost', dom.rsHost);
        apply('ssaRsBlock', dom.rsBlock);
        apply('ssaRsStatus', dom.rsStatus);
        apply('ssaLevelsHost', dom.levelsHost);
        apply('ssaLevelsBlock', dom.levelsBlock);
        apply('ssaLevelsStatus', dom.levelsStatus);
        apply('ssaPatternHost', dom.patternHost);
        apply('ssaPatternBlock', dom.patternBlock);
        apply('ssaPatternStatus', dom.patternStatus);
        apply('ssaSwingHost', dom.swingHost);
        apply('ssaSwingBlock', dom.swingBlock);
        apply('ssaSwingStatus', dom.swingStatus);
        apply('ssaGannHost', dom.gannHost);
        apply('ssaGannBlock', dom.gannBlock);
        apply('ssaGannStatus', dom.gannStatus);
        apply('ssaTradePlanHost', dom.planHost);
        apply('ssaTradePlanBlock', dom.planBlock);
        apply('ssaTradePlanStatus', dom.planStatus);
    },

    _persistActiveSession() {
        if (!this.activeSessionKey || this.embeddedMode) return;
        if (!this.stockSessions) this.stockSessions = {};
        const session = this.stockSessions[this.activeSessionKey];
        if (!session) return;
        session.state = this._captureState();
        session.dom = this._captureDom();
        if (this.lastStock && this.lastStock.code) session.code = this.lastStock.code;
        if (this.lastStock && this.lastStock.name) session.name = this.lastStock.name;
    },

    _restoreSession(session) {
        this.hideCandidates();
        this._applyState(session.state);
        this._restoreDom(session.dom);
        // innerHTML 恢复会丢掉 KDE/VP「应用」监听，需按当前标的重新绑定
        this._rebindLevelsControls();
        this.updateExportBtn();
        this.updateTradeObserveBtn();
        this.updateGannTradeObserveBtn();
    },

    _levelsStockCode() {
        if (this.lastStock && this.lastStock.code) return String(this.lastStock.code).trim();
        const d = this.lastLevels && this.lastLevels.data;
        if (d && (d.stock_code || d.code)) return String(d.stock_code || d.code).trim();
        const input = document.getElementById('ssaStockCode');
        if (input && input.value) {
            const token = String(input.value).trim().split(/\s+/)[0] || '';
            const body = /^(sh|sz|bj|hk)/i.test(token) ? token.slice(2) : token;
            if (/^\d{4,6}$/.test(body)) return token;
        }
        return '';
    },

    _rebindLevelsControls() {
        const host = document.getElementById('ssaLevelsHost');
        if (!host || typeof KdeLevelsTool === 'undefined') return;
        if (typeof KdeLevelsTool.rebindEmbeddedControls !== 'function') return;
        if (!host.querySelector('.ssa-kde-lookback-apply') && !host.querySelector('.ssa-vp-lookback-apply')) {
            return;
        }
        const code = this._levelsStockCode();
        KdeLevelsTool.rebindEmbeddedControls(host, {
            code,
            adjust: 'qfq',
            factor_source: 'auto',
            max_levels: 8,
            onUpdated: (result) => {
                this.lastLevels = {
                    ok: !!result.ok,
                    data: result.data || {},
                    error: result.ok ? null : (result.message || '阻力支撑计算失败'),
                };
                this.updateExportBtn();
                this._persistActiveSession();
            },
        });
    },

    hideCandidates() {
        const box = document.getElementById('ssaCandidates');
        const list = document.getElementById('ssaCandidateList');
        if (box) box.hidden = true;
        if (list) list.innerHTML = '';
    },

    clearExportState() {
        this.lastStrategy = null;
        this.lastStrategyError = null;
        this.lastStock = null;
        this.lastTradeDate = null;
        this.lastLevels = null;
        this.lastRs = null;
        this.lastPattern = null;
        this.lastSwing = null;
        this.lastGann = null;
        this.lastTradePlan = null;
        const planHost = document.getElementById('ssaTradePlanHost');
        if (planHost) planHost.innerHTML = '';
        const observeBtn = document.getElementById('ssaTradeObserveBtn');
        if (observeBtn) {
            observeBtn.classList.remove('is-added');
            delete observeBtn.dataset.observeCode;
            observeBtn.textContent = '交易观察';
        }
        this.resetGannTradeObserveBtn();
        this.updateExportBtn();
        this.updateTradeObserveBtn();
    },

    hasExportableResult() {
        return !!(
            this.lastStrategy ||
            this.lastLevels ||
            this.lastRs ||
            this.lastPattern ||
            this.lastSwing ||
            this.lastGann ||
            this.lastTradePlan ||
            this.lastStrategyError
        );
    },

    updateExportBtn() {
        const ok = this.hasExportableResult();
        const pdfBtn = document.getElementById('ssaExportPdfBtn');
        const pngBtn = document.getElementById('ssaExportPngBtn');
        if (pdfBtn) {
            pdfBtn.disabled = !ok || this.exporting;
            if (!this.exporting) pdfBtn.textContent = '导出 PDF';
        }
        if (pngBtn) {
            pngBtn.disabled = !ok || this.exporting;
            if (!this.exporting) pngBtn.textContent = '导出 PNG';
        }
        this.updateTradeObserveBtn();
    },

    _normalizeObserveCode(raw) {
        let c = String(raw || '').trim();
        if (!c) return '';
        if (/^(sh|sz|bj|hk)/i.test(c)) c = c.slice(2);
        c = c.split(/[\s/|]/)[0].trim();
        if (/^\d+$/.test(c) && c.length === 5) return c.padStart(5, '0');
        if (/^\d+$/.test(c) && c.length <= 6) return c.padStart(6, '0');
        return '';
    },

    _inferObserveMarket(code) {
        const c = String(code || '').trim();
        if (c.length === 5 && /^\d+$/.test(c)) return 'HK';
        return 'CN';
    },

    _urtObserveKey(market, code) {
        const m = (market || 'CN').toUpperCase();
        const c = this._normalizeObserveCode(code);
        return c ? `${m}:${c}` : `${m}:`;
    },

    resolveObserveStock() {
        const fromLast = this.lastStock || {};
        let code = this._normalizeObserveCode(fromLast.code);
        let name = (fromLast.name || '').trim();
        if (!code) {
            const input = document.getElementById('ssaStockCode');
            const query = ((input && input.value) || '').trim();
            const firstToken = query.split(/\s+/)[0] || '';
            code = this._normalizeObserveCode(firstToken);
            if (code && query.length > firstToken.length) {
                name = query.slice(firstToken.length).trim() || name;
            }
        }
        if (!code) return null;
        return {
            code,
            name: name || code,
            market: this._inferObserveMarket(code),
        };
    },

    resolveObserveSignalDate() {
        const fromStrategy = this.lastStrategy && this.lastStrategy.trade_date
            ? String(this.lastStrategy.trade_date).slice(0, 10)
            : '';
        if (fromStrategy) return fromStrategy;
        if (this.lastTradeDate) return String(this.lastTradeDate).slice(0, 10);
        const dateEl = document.getElementById('ssaTradeDate');
        const asof = dateEl && dateEl.value ? String(dateEl.value).slice(0, 10) : '';
        if (asof) return asof;
        const swingAsof = this.lastSwing && this.lastSwing.asof
            ? String(this.lastSwing.asof).slice(0, 10)
            : '';
        if (swingAsof) return swingAsof;
        const gannAsof = this.lastGann && this.lastGann.asof
            ? String(this.lastGann.asof).slice(0, 10)
            : '';
        return gannAsof || '';
    },

    updateTradeObserveBtn() {
        const btn = document.getElementById('ssaTradeObserveBtn');
        if (!btn) return;
        if (this.observing) {
            btn.disabled = true;
            return;
        }
        const stock = this.resolveObserveStock();
        const ok = !!(stock && stock.code);
        const markedCode = btn.dataset.observeCode || '';
        if (btn.classList.contains('is-added')) {
            if (stock && stock.code && markedCode && markedCode !== stock.code) {
                btn.classList.remove('is-added');
                delete btn.dataset.observeCode;
                btn.textContent = '交易观察';
                btn.disabled = !ok;
                return;
            }
            btn.disabled = true;
            btn.textContent = '已观察';
            return;
        }
        btn.disabled = !ok;
        btn.textContent = '交易观察';
    },

    updateGannTradeObserveBtn() {
        const btn = document.getElementById('ssaGannTradeObserveBtn');
        if (!btn) return;
        if (this.gannObserving) {
            btn.disabled = true;
            return;
        }
        const stock = this.resolveObserveStock();
        const gannOk = !!(this.lastGann && this.lastGann.ok && !this.lastGann.error);
        const ok = !!(stock && stock.code && gannOk);
        const markedCode = btn.dataset.observeCode || '';
        if (btn.classList.contains('is-added')) {
            if (stock && stock.code && markedCode && markedCode !== stock.code) {
                btn.classList.remove('is-added');
                delete btn.dataset.observeCode;
                btn.textContent = '交易观察';
                btn.disabled = !ok;
                return;
            }
            btn.disabled = true;
            btn.textContent = '已观察';
            return;
        }
        btn.disabled = !ok;
        btn.textContent = '交易观察';
    },

    resetGannTradeObserveBtn() {
        const btn = document.getElementById('ssaGannTradeObserveBtn');
        if (!btn) return;
        btn.classList.remove('is-added');
        delete btn.dataset.observeCode;
        btn.textContent = '交易观察';
        btn.disabled = true;
    },

    async addGannTradeObserve() {
        if (this.gannObserving) return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        const stock = this.resolveObserveStock();
        if (!stock || !stock.code) {
            CommonUtils.showToast('请先输入有效的股票代码并完成分析', 'warning');
            return;
        }
        if (!this.lastGann || !this.lastGann.ok || this.lastGann.error) {
            CommonUtils.showToast('请先完成江恩趋势预测后再加入观察', 'warning');
            return;
        }
        const signalDate = this.resolveObserveSignalDate();
        if (!signalDate) {
            CommonUtils.showToast('请先指定基准日，或先点击「分析」以确定交易日', 'warning');
            const dateEl = document.getElementById('ssaTradeDate');
            if (dateEl) dateEl.focus();
            return;
        }

        const btn = document.getElementById('ssaGannTradeObserveBtn');
        const key = this._urtObserveKey(stock.market, stock.code);
        this.gannObserving = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = '加入中…';
            btn.classList.remove('is-added');
            delete btn.dataset.observeCode;
        }

        try {
            const [obsRes, formalRes] = await Promise.all([
                authFetch(`${this.API_BASE_URL}/api/stock/trade-observe/codes?source=gann_trend`),
                authFetch(`${this.API_BASE_URL}/api/stock/formal-trade/codes`),
            ]);
            const obsCodes = obsRes.ok ? await obsRes.json().catch(() => []) : [];
            const formalCodes = formalRes.ok ? await formalRes.json().catch(() => []) : [];
            const obsSet = new Set(Array.isArray(obsCodes) ? obsCodes : []);
            const formalSet = new Set(Array.isArray(formalCodes) ? formalCodes : []);
            if (formalSet.has(key)) {
                CommonUtils.showToast('该股票已在正式交易中', 'info');
                if (btn) {
                    btn.textContent = '已观察';
                    btn.classList.add('is-added');
                    btn.dataset.observeCode = stock.code;
                    btn.disabled = true;
                }
                return;
            }
            if (obsSet.has(key)) {
                CommonUtils.showToast('已在江恩趋势交易观察列表中', 'info');
                if (btn) {
                    btn.textContent = '已观察';
                    btn.classList.add('is-added');
                    btn.dataset.observeCode = stock.code;
                    btn.disabled = true;
                }
                return;
            }

            const g = (this.lastGann.data && this.lastGann.data.gann_trend) || {};
            const verdict = g.verdict || {};
            const res = await authFetch(`${this.API_BASE_URL}/api/stock/trade-observe/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: stock.code,
                    market: stock.market,
                    name: stock.name || stock.code,
                    signal_date: signalDate,
                    source: 'gann_trend',
                    snapshot: {
                        source: 'gann_trend',
                        code: stock.code,
                        name: stock.name || stock.code,
                        signal_date: signalDate,
                        trade_date: signalDate,
                        bias: verdict.bias || g.bias || null,
                        bias_label: verdict.bias_label || null,
                        summary: verdict.summary || null,
                        asof: this.lastGann.asof || signalDate,
                    },
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            CommonUtils.showToast(`已加入交易观察（江恩趋势）：${stock.name || stock.code}`, 'success');
            if (btn) {
                btn.textContent = '已观察';
                btn.classList.add('is-added');
                btn.dataset.observeCode = stock.code;
                btn.disabled = true;
            }
        } catch (e) {
            CommonUtils.showToast(e.message || '加入交易观察失败', 'error');
            if (btn) {
                btn.textContent = '交易观察';
                btn.classList.remove('is-added');
                delete btn.dataset.observeCode;
            }
        } finally {
            this.gannObserving = false;
            if (btn && !btn.classList.contains('is-added')) {
                this.updateGannTradeObserveBtn();
            }
        }
    },

    async addTradeObserve() {
        if (this.observing) return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        const stock = this.resolveObserveStock();
        if (!stock || !stock.code) {
            CommonUtils.showToast('请先输入有效的股票代码', 'warning');
            const codeInput = document.getElementById('ssaStockCode');
            if (codeInput) codeInput.focus();
            return;
        }
        const signalDate = this.resolveObserveSignalDate();
        if (!signalDate) {
            CommonUtils.showToast('请先指定基准日，或先点击「分析」以确定交易日', 'warning');
            const dateEl = document.getElementById('ssaTradeDate');
            if (dateEl) dateEl.focus();
            return;
        }

        const btn = document.getElementById('ssaTradeObserveBtn');
        const key = this._urtObserveKey(stock.market, stock.code);
        this.observing = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = '加入中…';
            btn.classList.remove('is-added');
            delete btn.dataset.observeCode;
        }

        try {
            const [obsRes, formalRes] = await Promise.all([
                authFetch(`${this.API_BASE_URL}/api/stock/trade-observe/codes`),
                authFetch(`${this.API_BASE_URL}/api/stock/formal-trade/codes`),
            ]);
            const obsCodes = obsRes.ok ? await obsRes.json().catch(() => []) : [];
            const formalCodes = formalRes.ok ? await formalRes.json().catch(() => []) : [];
            const obsSet = new Set(Array.isArray(obsCodes) ? obsCodes : []);
            const formalSet = new Set(Array.isArray(formalCodes) ? formalCodes : []);
            if (formalSet.has(key)) {
                CommonUtils.showToast('该股票已在正式交易中', 'info');
                if (btn) {
                    btn.textContent = '已观察';
                    btn.classList.add('is-added');
                    btn.dataset.observeCode = stock.code;
                    btn.disabled = true;
                }
                return;
            }
            if (obsSet.has(key)) {
                CommonUtils.showToast('已在交易观察列表中', 'info');
                if (btn) {
                    btn.textContent = '已观察';
                    btn.classList.add('is-added');
                    btn.dataset.observeCode = stock.code;
                    btn.disabled = true;
                }
                return;
            }

            const res = await authFetch(`${this.API_BASE_URL}/api/stock/trade-observe/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: stock.code,
                    market: stock.market,
                    name: stock.name || stock.code,
                    signal_date: signalDate,
                    source: 'stock_analysis',
                    snapshot: {
                        source: 'stock_ai',
                        code: stock.code,
                        name: stock.name || stock.code,
                        signal_date: signalDate,
                        trade_date: signalDate,
                    },
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            CommonUtils.showToast(`已加入交易观察：${stock.name || stock.code}`, 'success');
            if (btn) {
                btn.textContent = '已观察';
                btn.classList.add('is-added');
                btn.dataset.observeCode = stock.code;
                btn.disabled = true;
            }
        } catch (e) {
            CommonUtils.showToast(e.message || '加入交易观察失败', 'error');
            if (btn) {
                btn.textContent = '交易观察';
                btn.classList.remove('is-added');
                delete btn.dataset.observeCode;
            }
        } finally {
            this.observing = false;
            if (btn && !btn.classList.contains('is-added')) {
                this.updateTradeObserveBtn();
            }
        }
    },

    hideResultBlocks() {
        ['ssaTradePlanBlock', 'ssaStrategyBlock', 'ssaRsBlock', 'ssaLevelsBlock', 'ssaPatternBlock', 'ssaSwingBlock', 'ssaGannBlock'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.hidden = true;
        });
        const planHost = document.getElementById('ssaTradePlanHost');
        const rsHost = document.getElementById('ssaRsHost');
        const levelsHost = document.getElementById('ssaLevelsHost');
        const patternHost = document.getElementById('ssaPatternHost');
        const swingHost = document.getElementById('ssaSwingHost');
        const gannHost = document.getElementById('ssaGannHost');
        if (planHost) planHost.innerHTML = '';
        if (rsHost) rsHost.innerHTML = '';
        if (levelsHost) levelsHost.innerHTML = '';
        if (patternHost) patternHost.innerHTML = '';
        if (swingHost) swingHost.innerHTML = '';
        if (gannHost) gannHost.innerHTML = '';
        const rsStatus = document.getElementById('ssaRsStatus');
        const levelsStatus = document.getElementById('ssaLevelsStatus');
        const patternStatus = document.getElementById('ssaPatternStatus');
        const swingStatus = document.getElementById('ssaSwingStatus');
        const gannStatus = document.getElementById('ssaGannStatus');
        const planStatus = document.getElementById('ssaTradePlanStatus');
        [rsStatus, levelsStatus, patternStatus, swingStatus, gannStatus, planStatus].forEach((status) => {
            if (status) {
                status.textContent = '';
                status.hidden = false;
                status.className = 'ssa-block-status';
            }
        });
        this.clearExportState();
    },

    setBlockLoading(blockId, statusId, text) {
        const block = document.getElementById(blockId);
        const status = document.getElementById(statusId);
        if (block) block.hidden = false;
        if (status) {
            status.hidden = false;
            status.className = 'ssa-block-status is-loading';
            status.textContent = text || '加载中…';
        }
    },

    setBlockError(statusId, message) {
        const status = document.getElementById(statusId);
        if (status) {
            status.hidden = false;
            status.className = 'ssa-block-status is-error';
            status.textContent = message || '加载失败';
        }
    },

    setBlockOk(statusId, message) {
        const status = document.getElementById(statusId);
        if (status) {
            status.className = 'ssa-block-status is-ok';
            status.textContent = message || '';
            if (!message) status.hidden = true;
            else status.hidden = false;
        }
    },

    renderCandidates(candidates, message) {
        const box = document.getElementById('ssaCandidates');
        const list = document.getElementById('ssaCandidateList');
        const title = box && box.querySelector('.ssa-candidates-title');
        if (!box || !list) return;
        if (title) title.textContent = message || '匹配到多只股票，请选择：';
        list.innerHTML = (candidates || []).map((item) => {
            const code = String(item.code || '').trim();
            const name = String(item.name || '').trim();
            const label = name ? `${code} ${name}` : code;
            return `<li><button type="button" class="ssa-candidate-btn" data-code="${this.escAttr(code)}">${this.esc(label)}</button></li>`;
        }).join('');
        list.querySelectorAll('.ssa-candidate-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const code = btn.getAttribute('data-code') || '';
                const input = document.getElementById('ssaStockCode');
                if (input) input.value = code;
                this.hideCandidates();
                this.analyze();
            });
        });
        box.hidden = false;
        this.hideResultBlocks();
        const meta = document.getElementById('ssaMeta');
        const empty = document.getElementById('ssaEmpty');
        if (meta) meta.hidden = true;
        if (empty) empty.hidden = true;
    },

    _persistSessionKey(key) {
        if (!key || this.embeddedMode) return;
        if (!this.stockSessions) this.stockSessions = {};
        const session = this.stockSessions[key];
        if (!session) return;
        const prevActive = this.activeSessionKey;
        this.activeSessionKey = key;
        session.state = this._captureState();
        session.dom = this._captureDom();
        if (this.lastStock && this.lastStock.code) session.code = this.lastStock.code;
        if (this.lastStock && this.lastStock.name) session.name = this.lastStock.name;
        this.activeSessionKey = prevActive;
    },

    async _mapPool(items, concurrency, worker) {
        const list = Array.isArray(items) ? items : [];
        const limit = Math.max(1, concurrency || 1);
        let idx = 0;
        const runners = Array.from({ length: Math.min(limit, list.length) }, async () => {
            while (idx < list.length) {
                const cur = idx;
                idx += 1;
                await worker(list[cur], cur);
            }
        });
        await Promise.all(runners);
    },

    async _fetchAnalysisBundle(code, name, asof, opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        const query = name ? `${code} ${name}` : code;
        const q = new URLSearchParams({ code: query });
        if (asof && !useRealtime) q.set('date', asof);
        if (useRealtime) q.set('use_realtime', 'true');
        const resp = await authFetch(
            `${this.API_BASE_URL}/api/analysis/multi-strategy-check?${q}`
        );
        const payload = await resp.json().catch(() => ({}));
        const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
        if (candidates.length > 1 || (candidates.length > 0 && !payload.data)) {
            throw new Error(payload.message || '股票代码不唯一，请使用精确代码');
        }
        if (!resp.ok || !payload.success) {
            throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
        }
        const strategyData = payload.data || {};
        const stock = strategyData.stock || { code, name };
        const resolvedCode = stock.code || code;
        const tradeDate = useRealtime
            ? (strategyData.realtime_trade_date || (strategyData.realtime && strategyData.realtime.trade_date) || strategyData.trade_date || asof || '')
            : (strategyData.trade_date || asof || '');
        const rtOpts = useRealtime ? { use_realtime: true } : {};
        const levelsAdjust = useRealtime ? 'none' : 'qfq';

        const [rsFetched, levelsFetched, patternFetched, swingFetched, gannFetched] = await Promise.all([
            authFetch(
                `${this.API_BASE_URL}/api/analysis/rs-rating?${new URLSearchParams({
                    code: resolvedCode,
                    ...(tradeDate ? { date: tradeDate } : {}),
                })}`
            )
                .then(async (r) => {
                    const body = await r.json().catch(() => ({}));
                    if (!r.ok || !body.success) {
                        return { __error: body.message || `相对强度加载失败 ${r.status}` };
                    }
                    return body;
                })
                .catch((e) => ({ __error: e.message || '相对强度加载失败' })),
            (typeof KdeLevelsTool !== 'undefined' && KdeLevelsTool.fetchLevels)
                ? KdeLevelsTool.fetchLevels(resolvedCode, {
                    adjust: levelsAdjust,
                    factor_source: 'auto',
                    max_levels: 8,
                    ...rtOpts,
                }).catch((e) => ({ __error: e.message || '阻力支撑计算失败' }))
                : Promise.resolve({ __error: '阻力支撑模块未加载' }),
            (typeof PatternTool !== 'undefined' && PatternTool.fetchSingle)
                ? PatternTool.fetchSingle(resolvedCode, {
                    adjust: useRealtime ? 'none' : 'qfq',
                    asof: useRealtime ? undefined : (tradeDate || undefined),
                    ...rtOpts,
                }).catch((e) => ({ __error: e.message || '形态识别失败' }))
                : Promise.resolve({ __error: '形态识别模块未加载' }),
            (typeof MarketStructureTool !== 'undefined' && MarketStructureTool.fetchStructure)
                ? MarketStructureTool.fetchStructure(resolvedCode, {
                    adjust: useRealtime ? 'none' : 'qfq',
                    asof: useRealtime ? undefined : (tradeDate || undefined),
                    ...rtOpts,
                }).catch((e) => ({ __error: e.message || '波段趋势分析失败' }))
                : Promise.resolve({ __error: '波段趋势模块未加载' }),
            (typeof GannTrendTool !== 'undefined' && GannTrendTool.fetchGann)
                ? GannTrendTool.fetchGann(resolvedCode, {
                    adjust: useRealtime ? 'none' : 'qfq',
                    asof: useRealtime ? undefined : (tradeDate || undefined),
                    ...rtOpts,
                }).catch((e) => ({ __error: e.message || '江恩趋势分析失败' }))
                : Promise.resolve({ __error: '江恩趋势模块未加载' }),
        ]);

        let rs = null;
        if (rsFetched && !rsFetched.__error) {
            rs = {
                ok: true,
                data: rsFetched.data || {},
                reason: rsFetched.reason || null,
                error: null,
            };
        } else {
            rs = {
                ok: false,
                data: null,
                reason: null,
                error: (rsFetched && rsFetched.__error) || '相对强度加载失败',
            };
        }

        let levels = null;
        if (levelsFetched && !levelsFetched.__error) {
            levels = {
                ok: !!levelsFetched.ok,
                data: levelsFetched.data || {},
                error: levelsFetched.ok ? null : (levelsFetched.message || null),
                fetched: levelsFetched,
            };
        } else {
            levels = {
                ok: false,
                data: null,
                error: (levelsFetched && levelsFetched.__error) || '阻力支撑计算失败',
                fetched: null,
            };
        }

        let pattern = null;
        if (patternFetched && !patternFetched.__error) {
            pattern = {
                ok: true,
                items: patternFetched.items || [],
                invalidated_count: patternFetched.invalidated_count || 0,
                code: patternFetched.code || resolvedCode,
                name: patternFetched.name || '',
                asof: patternFetched.asof || tradeDate || '',
                price_adjust: patternFetched.price_adjust || 'qfq',
                tactical: patternFetched.tactical || null,
                error: null,
                fetched: patternFetched,
            };
        } else {
            pattern = {
                ok: false,
                items: [],
                code: resolvedCode,
                name: '',
                asof: tradeDate || '',
                price_adjust: 'qfq',
                error: (patternFetched && patternFetched.__error) || '形态识别失败',
                fetched: null,
            };
        }

        let swing = null;
        if (swingFetched && !swingFetched.__error) {
            swing = {
                ok: !!(swingFetched.market_structure && swingFetched.market_structure.ok !== false),
                data: swingFetched,
                code: swingFetched.code || resolvedCode,
                name: swingFetched.name || '',
                asof: swingFetched.asof || tradeDate || '',
                error: null,
                fetched: swingFetched,
            };
        } else {
            swing = {
                ok: false,
                data: null,
                code: resolvedCode,
                name: '',
                asof: tradeDate || '',
                error: (swingFetched && swingFetched.__error) || '波段趋势分析失败',
                fetched: null,
            };
        }

        let gann = null;
        if (gannFetched && !gannFetched.__error) {
            const g = gannFetched.gann_trend || {};
            gann = {
                ok: !!g.ok,
                data: gannFetched,
                code: gannFetched.code || resolvedCode,
                name: gannFetched.name || '',
                asof: gannFetched.asof || tradeDate || '',
                error: null,
                fetched: gannFetched,
            };
        } else {
            gann = {
                ok: false,
                data: null,
                code: resolvedCode,
                name: '',
                asof: tradeDate || '',
                error: (gannFetched && gannFetched.__error) || '江恩趋势分析失败',
                fetched: null,
            };
        }

        let tradePlan = null;
        try {
            const snapshots = {};
            if (levels && levels.data) snapshots.levels = { data: levels.data };
            if (pattern) {
                snapshots.pattern = {
                    tactical: pattern.tactical || null,
                    items: pattern.items || [],
                };
            }
            if (swing) snapshots.swing = { data: swing.data || null };
            if (gann) snapshots.gann = { data: gann.data || null };
            const body = { code: resolvedCode, snapshots };
            if (tradeDate) body.date = tradeDate;
            const planResp = await authFetch(
                `${this.API_BASE_URL}/api/analysis/stock-integrated-trade-plan`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                }
            );
            const planPayload = await planResp.json().catch(() => ({}));
            if (!planResp.ok || !planPayload.success) {
                throw new Error(planPayload.message || planPayload.detail || `合成失败 ${planResp.status}`);
            }
            const pdata = planPayload.data || {};
            tradePlan = {
                ok: true,
                plan: pdata.plan || {},
                code: (pdata.stock && pdata.stock.code) || resolvedCode,
                name: (pdata.stock && pdata.stock.name) || '',
                trade_date: pdata.trade_date || tradeDate || '',
                error: null,
            };
        } catch (e) {
            tradePlan = {
                ok: false,
                plan: null,
                code: resolvedCode,
                name: '',
                trade_date: tradeDate || '',
                error: e.message || '综合交易策略合成失败',
            };
        }

        return {
            strategyData,
            strategyError: null,
            stock,
            tradeDate,
            rs,
            levels,
            pattern,
            swing,
            gann,
            tradePlan,
            useRealtime,
            realtime: strategyData.realtime || null,
        };
    },

    _applyAnalysisBundle(bundle) {
        if (!bundle) return;
        this.hideCandidates();
        this.lastStrategyError = bundle.strategyError || null;
        this.lastStock = bundle.stock || null;
        this.lastTradeDate = bundle.tradeDate || null;
        this.lastUseRealtime = !!bundle.useRealtime;
        this.lastRealtime = bundle.realtime || (bundle.strategyData && bundle.strategyData.realtime) || null;
        this.lastRs = bundle.rs
            ? {
                ok: bundle.rs.ok,
                data: bundle.rs.data,
                reason: bundle.rs.reason || null,
                error: bundle.rs.error,
            }
            : null;
        this.lastLevels = bundle.levels
            ? {
                ok: bundle.levels.ok,
                data: bundle.levels.data,
                error: bundle.levels.error,
            }
            : null;
        this.lastPattern = bundle.pattern
            ? {
                ok: bundle.pattern.ok,
                items: bundle.pattern.items || [],
                invalidated_count: bundle.pattern.invalidated_count || 0,
                code: bundle.pattern.code,
                name: bundle.pattern.name || '',
                asof: bundle.pattern.asof || '',
                price_adjust: bundle.pattern.price_adjust || 'qfq',
                tactical: bundle.pattern.tactical || null,
                error: bundle.pattern.error,
            }
            : null;
        this.lastSwing = bundle.swing
            ? {
                ok: bundle.swing.ok,
                data: bundle.swing.data,
                code: bundle.swing.code,
                name: bundle.swing.name || '',
                asof: bundle.swing.asof || '',
                error: bundle.swing.error,
            }
            : null;
        this.lastGann = bundle.gann
            ? {
                ok: bundle.gann.ok,
                data: bundle.gann.data,
                code: bundle.gann.code,
                name: bundle.gann.name || '',
                asof: bundle.gann.asof || '',
                error: bundle.gann.error,
            }
            : null;
        this.lastTradePlan = bundle.tradePlan || null;

        if (bundle.strategyData) {
            this.renderStrategyResult(bundle.strategyData);
        } else if (bundle.strategyError) {
            const strategyBlock = document.getElementById('ssaStrategyBlock');
            const strategyHost = document.getElementById('ssaResults');
            this.lastStrategy = null;
            if (strategyBlock && strategyHost) {
                strategyBlock.hidden = false;
                strategyHost.innerHTML = `<div class="ssa-block-status is-error">${this.esc(bundle.strategyError)}</div>`;
            }
        }

        // 相对强度 RS
        const rsBlock = document.getElementById('ssaRsBlock');
        const rsHost = document.getElementById('ssaRsHost');
        if (rsBlock && rsHost) {
            if (bundle.rs && bundle.rs.ok && bundle.rs.data) {
                rsBlock.hidden = false;
                this.renderRsRating(rsHost, bundle.rs.data, bundle.rs.reason, null);
                this.setBlockOk('ssaRsStatus', '');
                const st = document.getElementById('ssaRsStatus');
                if (st) st.hidden = true;
            } else {
                rsBlock.hidden = false;
                rsHost.innerHTML = `<p class="ssa-rs-empty">${this.esc((bundle.rs && bundle.rs.error) || '相对强度暂不可用')}</p>`;
                this.setBlockError('ssaRsStatus', (bundle.rs && bundle.rs.error) || '相对强度暂不可用');
            }
        }

        // 阻力支撑
        const levelsBlock = document.getElementById('ssaLevelsBlock');
        const levelsHost = document.getElementById('ssaLevelsHost');
        if (levelsBlock && levelsHost) {
            levelsBlock.hidden = false;
            if (bundle.levels && bundle.levels.fetched && typeof KdeLevelsTool !== 'undefined') {
                const fetched = bundle.levels.fetched;
                KdeLevelsTool.renderEmbedded(levelsHost, fetched.data || {}, fetched.ok, fetched.message, {
                    code: this._levelsStockCode()
                        || (fetched.data && (fetched.data.stock_code || fetched.data.code))
                        || (bundle.stock && bundle.stock.code)
                        || '',
                    adjust: 'qfq',
                    factor_source: 'auto',
                    max_levels: 8,
                    onUpdated: (result) => {
                        this.lastLevels = {
                            ok: !!result.ok,
                            data: result.data || {},
                            error: result.ok ? null : (result.message || '阻力支撑计算失败'),
                        };
                        this.updateExportBtn();
                        this._persistActiveSession();
                    },
                });
                this.setBlockOk('ssaLevelsStatus', '');
                const st = document.getElementById('ssaLevelsStatus');
                if (st) st.hidden = true;
            } else {
                levelsHost.innerHTML = '';
                this.setBlockError('ssaLevelsStatus', (bundle.levels && bundle.levels.error) || '阻力支撑计算失败');
            }
        }

        // 形态
        const patternBlock = document.getElementById('ssaPatternBlock');
        const patternHost = document.getElementById('ssaPatternHost');
        if (patternBlock && patternHost) {
            patternBlock.hidden = false;
            if (bundle.pattern && bundle.pattern.fetched && typeof PatternTool !== 'undefined') {
                const fetched = bundle.pattern.fetched;
                const invN = fetched.invalidated_count || 0;
                const meta = `个股 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准日 ${this.esc(fetched.asof || '--')} · ${this.esc(PatternTool.adjustLabel(fetched.price_adjust))} · ${this.esc(PatternTool.formatHitMeta((fetched.items || []).length, invN))}`;
                const levelsData = (this.lastLevels && this.lastLevels.data) || {};
                const classic = levelsData.classic_levels || levelsData.classic || {};
                const confluence = classic.confluence_zones || levelsData.confluence_zones || null;
                PatternTool.renderEmbedded(patternHost, fetched.items || [], meta, fetched.price_adjust, {
                    asof: fetched.asof || '',
                    confluenceZones: confluence,
                    classicLevels: classic,
                    invalidatedCount: invN,
                    tactical: fetched.tactical || null,
                    kdeLevels: {
                        nearest_resistance: levelsData.nearest_resistance,
                        nearest_support: levelsData.nearest_support,
                        resistance_levels: levelsData.resistance_levels,
                        support_levels: levelsData.support_levels,
                    },
                });
                this.setBlockOk('ssaPatternStatus', '');
                const st = document.getElementById('ssaPatternStatus');
                if (st) st.hidden = true;
            } else {
                patternHost.innerHTML = '';
                this.setBlockError('ssaPatternStatus', (bundle.pattern && bundle.pattern.error) || '形态识别失败');
            }
        }

        // 波段
        const swingBlock = document.getElementById('ssaSwingBlock');
        const swingHost = document.getElementById('ssaSwingHost');
        if (swingBlock && swingHost) {
            swingBlock.hidden = false;
            if (bundle.swing && bundle.swing.fetched && typeof MarketStructureTool !== 'undefined') {
                MarketStructureTool.renderEmbedded(swingHost, bundle.swing.fetched);
                this.setBlockOk('ssaSwingStatus', '');
                const st = document.getElementById('ssaSwingStatus');
                if (st) st.hidden = true;
            } else {
                swingHost.innerHTML = '';
                this.setBlockError('ssaSwingStatus', (bundle.swing && bundle.swing.error) || '波段趋势分析失败');
            }
        }

        // 江恩
        const gannBlock = document.getElementById('ssaGannBlock');
        const gannHost = document.getElementById('ssaGannHost');
        if (gannBlock && gannHost) {
            gannBlock.hidden = false;
            if (bundle.gann && bundle.gann.fetched && typeof GannTrendTool !== 'undefined') {
                GannTrendTool.renderEmbedded(gannHost, bundle.gann.fetched);
                this.setBlockOk('ssaGannStatus', '');
                const st = document.getElementById('ssaGannStatus');
                if (st) st.hidden = true;
            } else {
                gannHost.innerHTML = '';
                this.setBlockError('ssaGannStatus', (bundle.gann && bundle.gann.error) || '江恩趋势分析失败');
            }
        }

        // 综合策略
        const planBlock = document.getElementById('ssaTradePlanBlock');
        const planHost = document.getElementById('ssaTradePlanHost');
        if (planBlock && planHost) {
            planBlock.hidden = false;
            if (bundle.tradePlan && bundle.tradePlan.ok) {
                if (typeof StockTradePlan !== 'undefined' && typeof StockTradePlan.render === 'function') {
                    StockTradePlan.render(planHost, bundle.tradePlan);
                } else {
                    const summary = (bundle.tradePlan.plan && bundle.tradePlan.plan.short_term
                        && bundle.tradePlan.plan.short_term.summary) || '综合策略已生成';
                    planHost.innerHTML = `<p class="ssa-muted">${this.esc(summary)}</p>`;
                }
                this.setBlockOk('ssaTradePlanStatus', '');
                const st = document.getElementById('ssaTradePlanStatus');
                if (st) st.hidden = true;
            } else {
                planHost.innerHTML = '';
                this.setBlockError(
                    'ssaTradePlanStatus',
                    (bundle.tradePlan && bundle.tradePlan.error) || '综合交易策略合成失败'
                );
            }
        }

        const empty = document.getElementById('ssaEmpty');
        if (empty) empty.hidden = true;
        this.updateExportBtn();
        this.updateTradeObserveBtn();
        this.updateGannTradeObserveBtn();
    },

    async analyzeWatchlistBatch(stocks, options) {
        const opts = options || {};
        let list = (stocks || []).slice();
        if (!list.length) {
            CommonUtils.showToast('请勾选至少一只自选股', 'warning');
            return;
        }

        const allowAllEl = document.getElementById('ssaAnalyzeAllSelected');
        const allowAll = !allowAllEl || !!allowAllEl.checked;
        const softLimit = this.WATCHLIST_BATCH_SOFT_LIMIT || 0;

        if (!allowAll && softLimit > 0 && list.length > softLimit) {
            CommonUtils.showToast(
                `未勾选「一次分析全部勾选」，本次仅分析前 ${softLimit} 只（已选 ${list.length} 只）`,
                'warning'
            );
            list = list.slice(0, softLimit);
        } else if (allowAll && list.length >= 40 && !opts.skipLargeConfirm) {
            const ok = window.confirm(
                `将一次分析全部 ${list.length} 只自选股，耗时可能较长，是否继续？`
            );
            if (!ok) return;
        }

        this.running = true;
        this._batchAnalyzing = true;
        this.hideCandidates();
        const btn = document.getElementById('ssaAnalyzeBtn');
        const rtBtn = document.getElementById('ssaRealtimeAnalyzeBtn');
        const empty = document.getElementById('ssaEmpty');
        const useRealtime = !!(options && options.useRealtime);
        if (btn) {
            btn.disabled = true;
            btn.textContent = '分析中…';
        }
        if (rtBtn) {
            rtBtn.disabled = true;
            rtBtn.textContent = '实时分析中…';
        }

        // 仅保留本次勾选的会话，避免旧 Tab 干扰
        const nextSessions = {};
        list.forEach(({ code, name }) => {
            const key = this._sessionKey(code);
            nextSessions[key] = {
                key,
                code,
                name: name || '',
                status: 'loading',
                state: null,
                dom: null,
                bundle: null,
                errorMessage: '',
            };
        });
        this.stockSessions = nextSessions;
        this.activeSessionKey = null;
        this._renderStockTabs();
        this.hideResultBlocks();
        if (empty) {
            empty.hidden = false;
            empty.textContent = useRealtime
                ? `正在并行实时分析 0/${list.length}…`
                : `正在并行分析 0/${list.length}…`;
        }

        const dateEl = document.getElementById('ssaTradeDate');
        const asof = (!useRealtime && dateEl && dateEl.value) ? dateEl.value : '';
        let doneCount = 0;
        let okCount = 0;
        const concurrency = Math.min(3, list.length);

        await this._mapPool(list, concurrency, async ({ code, name }) => {
            const key = this._sessionKey(code);
            const session = this.stockSessions[key];
            try {
                const bundle = await this._fetchAnalysisBundle(code, name, asof, {
                    useRealtime,
                });
                if (session) {
                    session.bundle = bundle;
                    session.status = 'fetched';
                    session.code = (bundle.stock && bundle.stock.code) || code;
                    session.name = (bundle.stock && bundle.stock.name) || name || '';
                    session.errorMessage = '';
                }
                okCount += 1;
            } catch (e) {
                if (session) {
                    session.status = 'error';
                    session.bundle = null;
                    session.errorMessage = e.message || '分析失败';
                }
            } finally {
                doneCount += 1;
                if (empty) {
                    empty.hidden = false;
                    empty.textContent = `正在并行分析 ${doneCount}/${list.length}…`;
                }
                if (btn) btn.textContent = `分析中 ${doneCount}/${list.length}`;
                this._renderStockTabs();
            }
        });

        // 全部请求完成后，依次渲染并缓存 DOM，保证切 Tab 即时展示
        const keys = list.map(({ code }) => this._sessionKey(code)).filter(Boolean);
        for (const key of keys) {
            const session = this.stockSessions[key];
            if (!session || session.status !== 'fetched' || !session.bundle) continue;
            this.activeSessionKey = key;
            this.hideResultBlocks();
            this._applyAnalysisBundle(session.bundle);
            this._persistSessionKey(key);
            session.status = 'ready';
            // bundle 已物化为 DOM 快照，释放原始 fetched 体积（可选保留 plan/state）
            session.bundle = null;
            this._renderStockTabs();
        }

        this._batchAnalyzing = false;
        this.running = false;
        if (btn) {
            btn.disabled = false;
            btn.textContent = '分析';
        }
        if (rtBtn) {
            rtBtn.disabled = false;
            rtBtn.textContent = '实时分析';
        }

        const firstReady = keys.find((k) => this.stockSessions[k] && this.stockSessions[k].status === 'ready');
        if (firstReady) {
            this._switchStockTab(firstReady, { persistPrevious: false });
            if (empty) empty.hidden = true;
        } else if (empty) {
            empty.hidden = false;
            empty.textContent = '批量分析未成功，请重试';
        }

        CommonUtils.showToast(
            useRealtime
                ? `批量实时分析完成：${okCount}/${list.length}`
                : `批量分析完成：${okCount}/${list.length}`,
            okCount === list.length ? 'success' : 'warning'
        );
        this.updateExportBtn();
    },

    async _runAnalyzeCore(resolved, opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        let { query, firstToken } = resolved;
        const codeInput = document.getElementById('ssaStockCode');
        const empty = document.getElementById('ssaEmpty');
        const meta = document.getElementById('ssaMeta');

        try {
            const q = new URLSearchParams({ code: query });
            const dateEl = document.getElementById('ssaTradeDate');
            const asof = (!useRealtime && dateEl && dateEl.value) ? dateEl.value : '';
            if (asof) q.set('date', asof);
            if (useRealtime) q.set('use_realtime', 'true');
            const resp = await authFetch(
                `${this.API_BASE_URL}/api/analysis/multi-strategy-check?${q}`
            );
            const payload = await resp.json().catch(() => ({}));
            const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
            if (candidates.length > 1 || (candidates.length > 0 && !payload.data)) {
                this.renderCandidates(candidates, payload.message);
                CommonUtils.showToast(payload.message || '请从候选中选择股票', 'warning');
                throw new Error(payload.message || '请从候选中选择股票');
            }
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
            }
            const data = payload.data || {};
            const stock = data.stock || {};
            if (stock.code && codeInput) {
                codeInput.value = stock.name ? `${stock.code} ${stock.name}` : stock.code;
            }
            this.lastUseRealtime = useRealtime;
            this.lastRealtime = data.realtime || null;
            this.lastTradeDate = useRealtime
                ? (data.realtime_trade_date || (data.realtime && data.realtime.trade_date) || data.trade_date || asof || null)
                : (data.trade_date || asof || null);
            this.renderStrategyResult(data);
            if (empty) empty.hidden = true;

            const resolvedCode = stock.code || query;
            const tradeDate = this.lastTradeDate || '';
            await Promise.all([
                this.loadRsRatingSection(resolvedCode, tradeDate),
                this.loadLevelsSection(resolvedCode, { useRealtime }),
                this.loadPatternSection(resolvedCode, useRealtime ? '' : tradeDate, { useRealtime }),
                this.loadSwingSection(resolvedCode, useRealtime ? '' : tradeDate, { useRealtime }),
                this.loadGannSection(resolvedCode, useRealtime ? '' : tradeDate, { useRealtime }),
            ]);
            await this.loadTradePlanSection(resolvedCode, tradeDate);
            this.updateExportBtn();

            if (!options.quietToast) {
                const rt = data.realtime;
                const px = rt && rt.current_price != null ? Number(rt.current_price).toFixed(2) : '';
                if (useRealtime && px) {
                    CommonUtils.showToast(
                        data.any_hit
                            ? `实时分析完成 · 现价 ${px} · 命中 ${data.hit_count || 0} 个策略`
                            : `实时分析完成 · 现价 ${px} · 四策略均未命中`,
                        data.any_hit ? 'success' : 'info'
                    );
                } else {
                    CommonUtils.showToast(
                        data.any_hit ? `命中 ${data.hit_count || 0} 个策略` : '四策略均未命中',
                        data.any_hit ? 'success' : 'info'
                    );
                }
            }
        } catch (e) {
            console.error(e);
            const dateEl = document.getElementById('ssaTradeDate');
            const asofFallback = dateEl && dateEl.value ? dateEl.value : '';
            const looksLikeCode = /^\d{4,6}$/.test(
                (/^(sh|sz|bj|hk)/i.test(firstToken) ? firstToken.slice(2) : firstToken)
            ) || /^(sh|sz|bj|hk)\d{4,6}$/i.test(firstToken);
            if (looksLikeCode) {
                if (empty) empty.hidden = true;
                const strategyBlock = document.getElementById('ssaStrategyBlock');
                const strategyHost = document.getElementById('ssaResults');
                this.lastStrategy = null;
                this.lastStrategyError = e.message || '策略分析失败';
                this.lastStock = { code: firstToken };
                this.lastTradeDate = asofFallback || null;
                const observeBtn = document.getElementById('ssaTradeObserveBtn');
                if (observeBtn) {
                    observeBtn.classList.remove('is-added');
                    delete observeBtn.dataset.observeCode;
                    observeBtn.textContent = '交易观察';
                }
                this.resetGannTradeObserveBtn();
                if (strategyBlock && strategyHost) {
                    strategyBlock.hidden = false;
                    strategyHost.innerHTML = `<div class="ssa-block-status is-error">${this.esc(e.message || '策略分析失败')}</div>`;
                }
                await Promise.all([
                    this.loadRsRatingSection(firstToken, asofFallback),
                    this.loadLevelsSection(firstToken),
                    this.loadPatternSection(firstToken, asofFallback),
                    this.loadSwingSection(firstToken, asofFallback),
                    this.loadGannSection(firstToken, asofFallback),
                ]);
                await this.loadTradePlanSection(firstToken, asofFallback);
                this.updateExportBtn();
                if (!options.quietToast) {
                    CommonUtils.showToast('策略分析失败，已尝试计算阻力支撑、形态、波段与江恩', 'warning');
                }
            } else {
                if (empty) {
                    empty.hidden = false;
                    empty.textContent = e.message || '分析失败';
                }
                if (!options.quietToast) {
                    CommonUtils.showToast(e.message || '分析失败', 'error');
                }
                throw e;
            }
        } finally {
            if (meta && this.lastStrategy) meta.hidden = false;
        }
    },

    async analyze(opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        if (this.running) return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;

        if (!this.embeddedMode) {
            const selected = this.getSelectedBatchStocks();
            if (selected.length > 0) {
                return this.analyzeWatchlistBatch(selected, { useRealtime });
            }
        }

        const resolved = this._resolveAnalyzeQuery();
        if (!resolved) {
            if (this.embeddedMode) return;
            CommonUtils.showToast('请输入股票代码或名称，或勾选自选股 / 行业龙头 / 概念龙头', 'warning');
            const codeInput = document.getElementById('ssaStockCode');
            if (codeInput && codeInput.focus) codeInput.focus();
            return;
        }
        let { query, firstToken } = resolved;
        const codeInput = document.getElementById('ssaStockCode');
        const btn = document.getElementById('ssaAnalyzeBtn');
        const rtBtn = document.getElementById('ssaRealtimeAnalyzeBtn');
        const empty = document.getElementById('ssaEmpty');

        if (!this.embeddedMode) {
            const key = this._sessionKey(firstToken);
            this._ensureStockTab(key, firstToken, '');
            this._switchStockTab(key, { persistPrevious: true });
            const session = this.stockSessions[key];
            if (session) session.status = 'loading';
            this._renderStockTabs();
        }

        this.running = true;
        this.hideCandidates();
        this.hideResultBlocks();
        if (btn) {
            btn.disabled = true;
            btn.textContent = this.embeddedMode ? '刷新中…' : '分析中…';
        }
        if (rtBtn) {
            rtBtn.disabled = true;
            rtBtn.textContent = '实时分析中…';
        }
        if (empty) {
            empty.hidden = false;
            empty.textContent = useRealtime
                ? '正在拉取实时价并评估策略、阻力支撑与形态，请稍候…'
                : '正在评估策略、阻力支撑与形态，请稍候…';
        }
        const meta = document.getElementById('ssaMeta');
        if (meta) meta.hidden = true;

        try {
            await this._runAnalyzeCore(resolved, { useRealtime });
            if (!this.embeddedMode && this.activeSessionKey) {
                this._persistActiveSession();
                const session = this.stockSessions[this.activeSessionKey];
                if (session) {
                    session.status = 'ready';
                    session.errorMessage = '';
                }
                this._renderStockTabs();
            }
        } catch (e) {
            if (!this.embeddedMode && this.activeSessionKey) {
                const session = this.stockSessions[this.activeSessionKey];
                if (session) {
                    session.status = 'error';
                    session.errorMessage = e.message || '分析失败';
                }
                this._persistActiveSession();
                this._renderStockTabs();
            }
        } finally {
            this.running = false;
            if (btn) {
                btn.disabled = false;
                btn.textContent = this.embeddedMode ? '刷新' : '分析';
            }
            if (rtBtn) {
                rtBtn.disabled = false;
                rtBtn.textContent = '实时分析';
            }
            this.updateExportBtn();
        }
    },

    async loadRsRatingSection(code, asof) {
        const block = document.getElementById('ssaRsBlock');
        const host = document.getElementById('ssaRsHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaRsBlock', 'ssaRsStatus', '正在加载相对强度…');
        try {
            const q = new URLSearchParams({ code: code || '' });
            if (asof) q.set('date', asof);
            const resp = await authFetch(
                `${this.API_BASE_URL}/api/analysis/rs-rating?${q}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (payload.candidates && payload.candidates.length > 1) {
                throw new Error(payload.message || '股票代码不唯一，请使用精确代码');
            }
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || `相对强度加载失败 ${resp.status}`);
            }
            const data = payload.data || {};
            this.renderRsRating(host, data, payload.reason, payload.message);
            this._syncRsTraceLink(data.code || code, data.name || '');
            this.lastRs = { ok: true, data, reason: payload.reason || null, error: null };
            this.setBlockOk('ssaRsStatus', '');
            const st = document.getElementById('ssaRsStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·相对强度失败', e);
            host.innerHTML = `<p class="ssa-rs-empty">${this.esc(e.message || '相对强度暂不可用')}</p>`;
            this._syncRsTraceLink(code, '');
            this.lastRs = { ok: false, data: null, error: e.message || '相对强度加载失败' };
            this.setBlockError('ssaRsStatus', e.message || '相对强度暂不可用（需日终预计算）');
        }
        this.updateExportBtn();
    },

    renderRsRating(host, data, reason, message) {
        if (!host) return;
        const rating = data.rs_rating;
        const label = data.strength_label || '';
        const tone =
            rating == null
                ? 'neutral'
                : rating >= 70
                  ? 'strong'
                  : rating >= 50
                    ? 'mid'
                    : 'weak';
        const fmtPct = (v) => {
            if (v == null || Number.isNaN(Number(v))) return '--';
            return `${(Number(v) * 100).toFixed(2)}%`;
        };
        const ratingHtml =
            rating == null
                ? `<span class="ssa-rs-score ssa-rs-score--na">--</span>`
                : `<span class="ssa-rs-score ssa-rs-score--${tone}">${this.esc(String(rating))}</span>`;
        const note =
            reason === 'rating_unpublished'
                ? message || '当日覆盖率不足，未发布 1–99 评级'
                : '';
        const code = data.code || '';
        const name = data.name || '';
        const traceHref = `stock_rs_trace.html?code=${encodeURIComponent(code)}`;
        host.innerHTML = `
            <div class="ssa-rs-card">
              <div class="ssa-rs-main">
                ${ratingHtml}
                <div class="ssa-rs-meta">
                  <div class="ssa-rs-label">${this.esc(label || (rating == null ? '无评级' : ''))}</div>
                  <div class="ssa-rs-date">基准日 ${this.esc(data.trade_date || '--')} · 宇宙 ${this.esc(String(data.universe_size ?? '--'))}</div>
                  ${note ? `<div class="ssa-rs-note">${this.esc(note)}</div>` : ''}
                  <div class="ssa-rs-actions">
                    <a class="ssa-rs-trace-link" href="${this.esc(traceHref)}" target="_blank" rel="noopener noreferrer">历史追溯</a>
                    <button type="button" class="ssa-rs-trace-toggle" id="ssaRsHistoryToggle">展开近期历史</button>
                  </div>
                </div>
              </div>
              <div class="ssa-rs-rocs">
                <div class="ssa-rs-roc"><span>近63日</span><strong>${fmtPct(data.roc_63)}</strong><em>权重40%</em></div>
                <div class="ssa-rs-roc"><span>近126日</span><strong>${fmtPct(data.roc_126)}</strong><em>权重20%</em></div>
                <div class="ssa-rs-roc"><span>近189日</span><strong>${fmtPct(data.roc_189)}</strong><em>权重20%</em></div>
                <div class="ssa-rs-roc"><span>近252日</span><strong>${fmtPct(data.roc_252)}</strong><em>权重20%</em></div>
              </div>
              <div class="ssa-rs-history" id="ssaRsHistoryPanel" hidden>
                <div class="ssa-rs-history-status" id="ssaRsHistoryStatus"></div>
                <div class="table-scroll">
                  <table class="ssa-rs-history-table" id="ssaRsHistoryTable">
                    <thead>
                      <tr><th>日期</th><th>RS</th><th>强弱</th><th>RS_Raw</th><th>近63日</th><th>近126日</th></tr>
                    </thead>
                    <tbody></tbody>
                  </table>
                </div>
              </div>
              <p class="ssa-rs-hint">IBD 风格截面百分位（前复权收盘）：RS 90 表示过去一年（偏近季）表现超过约 90% 的 A 股。非 RSI、非板块比价 Z。</p>
            </div>
        `;
        this._syncRsTraceLink(code, name);
        const toggle = host.querySelector('#ssaRsHistoryToggle');
        if (toggle && code) {
            toggle.addEventListener('click', () => this.toggleRsHistoryInline(code, toggle));
        }
    },

    _syncRsTraceLink(code, name) {
        const link = document.getElementById('ssaRsTraceLink');
        if (!link) return;
        const c = String(code || '').trim();
        if (!c) {
            link.hidden = true;
            return;
        }
        link.hidden = false;
        link.href = `stock_rs_trace.html?code=${encodeURIComponent(c)}`;
        link.title = name ? `${c} ${name} 历史追溯` : `${c} 历史追溯`;
    },

    async toggleRsHistoryInline(code, toggleBtn) {
        const panel = document.getElementById('ssaRsHistoryPanel');
        const status = document.getElementById('ssaRsHistoryStatus');
        const table = document.getElementById('ssaRsHistoryTable');
        if (!panel || !table) return;
        if (!panel.hidden) {
            panel.hidden = true;
            if (toggleBtn) toggleBtn.textContent = '展开近期历史';
            return;
        }
        panel.hidden = false;
        if (toggleBtn) toggleBtn.textContent = '收起近期历史';
        if (status) status.textContent = '加载中…';
        try {
            const q = new URLSearchParams({ code: code || '', limit: '30' });
            const resp = await authFetch(
                `${this.API_BASE_URL}/api/analysis/rs-rating/history?${q}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || `历史加载失败 ${resp.status}`);
            }
            const rows = Array.isArray(payload.data) ? payload.data : [];
            const tbody = table.querySelector('tbody');
            if (!tbody) return;
            if (!rows.length) {
                tbody.innerHTML = '';
                if (status) status.textContent = '暂无历史记录';
                return;
            }
            if (status) status.textContent = `近 ${rows.length} 条（新→旧）`;
            const fmtPct = (v) => {
                if (v == null || Number.isNaN(Number(v))) return '--';
                return `${(Number(v) * 100).toFixed(2)}%`;
            };
            tbody.innerHTML = rows
                .map((r) => {
                    const rating = r.rs_rating;
                    return `<tr>
                      <td>${this.esc(r.date || '--')}</td>
                      <td>${rating == null ? '--' : this.esc(String(rating))}</td>
                      <td>${this.esc(r.strength_label || '--')}</td>
                      <td>${r.rs_raw == null ? '--' : Number(r.rs_raw).toFixed(4)}</td>
                      <td>${fmtPct(r.roc_63)}</td>
                      <td>${fmtPct(r.roc_126)}</td>
                    </tr>`;
                })
                .join('');
        } catch (e) {
            if (status) status.textContent = e.message || '历史加载失败';
        }
    },

    async loadLevelsSection(code, opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        const block = document.getElementById('ssaLevelsBlock');
        const host = document.getElementById('ssaLevelsHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaLevelsBlock', 'ssaLevelsStatus', useRealtime ? '正在按实时价计算阻力支撑位…' : '正在计算阻力支撑位…');
        try {
            if (typeof KdeLevelsTool === 'undefined' || typeof KdeLevelsTool.fetchLevels !== 'function') {
                throw new Error('阻力支撑模块未加载');
            }
            const adjust = useRealtime ? 'none' : 'qfq';
            const fetched = await KdeLevelsTool.fetchLevels(code, {
                adjust,
                factor_source: 'auto',
                max_levels: 8,
                use_realtime: useRealtime,
            });
            if (fetched.candidates && fetched.candidates.length > 1 && !fetched.data) {
                throw new Error(fetched.message || '股票代码不唯一，请使用精确代码');
            }
            if (!fetched.httpOk && !fetched.data) {
                throw new Error(fetched.message || '阻力支撑计算失败');
            }
            KdeLevelsTool.renderEmbedded(host, fetched.data || {}, fetched.ok, fetched.message, {
                code: code
                    || this._levelsStockCode()
                    || (fetched.data && (fetched.data.stock_code || fetched.data.code))
                    || '',
                adjust,
                factor_source: 'auto',
                max_levels: 8,
                onUpdated: (result) => {
                    this.lastLevels = {
                        ok: !!result.ok,
                        data: result.data || {},
                        error: result.ok ? null : (result.message || '阻力支撑计算失败'),
                    };
                    this.updateExportBtn();
                    this._persistActiveSession();
                },
            });
            this.lastLevels = {
                ok: !!fetched.ok,
                data: fetched.data || {},
                error: fetched.ok ? null : (fetched.message || null),
            };
            this.setBlockOk('ssaLevelsStatus', '');
            const st = document.getElementById('ssaLevelsStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·阻力支撑失败', e);
            host.innerHTML = '';
            this.lastLevels = { ok: false, data: null, error: e.message || '阻力支撑计算失败' };
            this.setBlockError('ssaLevelsStatus', e.message || '阻力支撑计算失败，可稍后在「技术工具」重试');
        }
        this.updateExportBtn();
    },

    async loadPatternSection(code, asof, opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        const block = document.getElementById('ssaPatternBlock');
        const host = document.getElementById('ssaPatternHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaPatternBlock', 'ssaPatternStatus', useRealtime ? '正在按实时价识别形态…' : '正在识别形态…');
        try {
            if (typeof PatternTool === 'undefined' || typeof PatternTool.fetchSingle !== 'function') {
                throw new Error('形态识别模块未加载');
            }
            const fetched = await PatternTool.fetchSingle(code, {
                adjust: useRealtime ? 'none' : 'qfq',
                asof: useRealtime ? undefined : (asof || undefined),
                use_realtime: useRealtime,
            });
            const invN = fetched.invalidated_count || 0;
            const rtTag = useRealtime ? ' · 实时' : '';
            const meta = `个股 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准日 ${this.esc(fetched.asof || '--')} · ${this.esc(PatternTool.adjustLabel(fetched.price_adjust))} · ${this.esc(PatternTool.formatHitMeta(fetched.items.length, invN))}${rtTag}`;
            const levelsData = (this.lastLevels && this.lastLevels.data) || {};
            const classic = levelsData.classic_levels || levelsData.classic || {};
            const confluence =
                classic.confluence_zones || levelsData.confluence_zones || null;
            PatternTool.renderEmbedded(host, fetched.items, meta, fetched.price_adjust, {
                asof: fetched.asof || asof || '',
                confluenceZones: confluence,
                classicLevels: classic,
                invalidatedCount: invN,
                tactical: fetched.tactical || null,
                kdeLevels: {
                    nearest_resistance: levelsData.nearest_resistance,
                    nearest_support: levelsData.nearest_support,
                    resistance_levels: levelsData.resistance_levels,
                    support_levels: levelsData.support_levels,
                },
            });
            this.lastPattern = {
                ok: true,
                items: fetched.items || [],
                invalidated_count: invN,
                code: fetched.code,
                name: fetched.name || '',
                asof: fetched.asof || '',
                price_adjust: fetched.price_adjust,
                tactical: fetched.tactical || null,
                error: null,
            };
            this.setBlockOk('ssaPatternStatus', '');
            const st = document.getElementById('ssaPatternStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·形态识别失败', e);
            host.innerHTML = '';
            this.lastPattern = {
                ok: false,
                items: [],
                code,
                name: '',
                asof: asof || '',
                price_adjust: 'qfq',
                error: e.message || '形态识别失败',
            };
            this.setBlockError('ssaPatternStatus', e.message || '形态识别失败，可稍后在「技术工具」重试');
        }
        this.updateExportBtn();
        // 形态就绪后补一次波段对照（若波段已出）
        if (this.lastSwing && this.lastSwing.ok && this.lastSwing.data) {
            this._refreshSwingContrast();
        }
    },

    _patternShortBias() {
        const t = this.lastPattern && this.lastPattern.tactical;
        if (!t) return null;
        return t.short_bias || t.bias || null;
    },

    _refreshSwingContrast() {
        const host = document.getElementById('ssaSwingHost');
        if (!host || !this.lastSwing || !this.lastSwing.data) return;
        if (typeof MarketStructureTool === 'undefined') return;
        const bias = this._patternShortBias();
        const ms = this.lastSwing.data.market_structure || this.lastSwing.data;
        if (!ms) return;
        // 后端未带对照时，用已加载形态 bias 再请求一次（轻量）会慢；此处仅前端提示占位已由 API pattern_contrast
        if (bias && !ms.pattern_contrast && this.lastSwing.code) {
            // 异步静默补对照
            void MarketStructureTool.fetchStructure(this.lastSwing.code, {
                adjust: 'qfq',
                asof: this.lastSwing.asof || undefined,
                pattern_short_bias: bias,
            })
                .then((data) => {
                    this.lastSwing = {
                        ok: true,
                        data,
                        code: data.code,
                        name: data.name || '',
                        asof: data.asof || '',
                        error: null,
                    };
                    MarketStructureTool.renderEmbedded(host, data);
                })
                .catch(() => {});
        }
    },

    async loadSwingSection(code, asof, opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        const block = document.getElementById('ssaSwingBlock');
        const host = document.getElementById('ssaSwingHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaSwingBlock', 'ssaSwingStatus', useRealtime ? '正在按实时价分析波段与趋势…' : '正在分析波段与趋势…');
        try {
            if (typeof MarketStructureTool === 'undefined' || typeof MarketStructureTool.fetchStructure !== 'function') {
                throw new Error('波段趋势模块未加载');
            }
            // 稍候形态可能未完成；先拉结构，有 bias 再带上
            const bias = this._patternShortBias();
            const fetched = await MarketStructureTool.fetchStructure(code, {
                adjust: useRealtime ? 'none' : 'qfq',
                asof: useRealtime ? undefined : (asof || undefined),
                pattern_short_bias: bias || undefined,
                use_realtime: useRealtime,
            });
            MarketStructureTool.renderEmbedded(host, fetched);
            this.lastSwing = {
                ok: !!(fetched.market_structure && fetched.market_structure.ok !== false),
                data: fetched,
                code: fetched.code || code,
                name: fetched.name || '',
                asof: fetched.asof || asof || '',
                error: null,
            };
            this.setBlockOk('ssaSwingStatus', '');
            const st = document.getElementById('ssaSwingStatus');
            if (st) st.hidden = true;
            // 若并行时形态尚无 bias，形态回调会 _refreshSwingContrast
        } catch (e) {
            console.warn('个股分析·波段趋势失败', e);
            host.innerHTML = '';
            this.lastSwing = {
                ok: false,
                data: null,
                code,
                name: '',
                asof: asof || '',
                error: e.message || '波段趋势分析失败',
            };
            this.setBlockError('ssaSwingStatus', e.message || '波段趋势分析失败，可稍后重试');
        }
        this.updateExportBtn();
    },

    async loadGannSection(code, asof, opts) {
        const options = opts || {};
        const useRealtime = !!options.useRealtime;
        const block = document.getElementById('ssaGannBlock');
        const host = document.getElementById('ssaGannHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaGannBlock', 'ssaGannStatus', useRealtime ? '正在按实时价计算江恩趋势…' : '正在计算江恩趋势…');
        try {
            if (typeof GannTrendTool === 'undefined' || typeof GannTrendTool.fetchGann !== 'function') {
                throw new Error('江恩趋势模块未加载');
            }
            const fetched = await GannTrendTool.fetchGann(code, {
                adjust: useRealtime ? 'none' : 'qfq',
                asof: useRealtime ? undefined : (asof || undefined),
                use_realtime: useRealtime,
            });
            GannTrendTool.renderEmbedded(host, fetched);
            const g = fetched.gann_trend || {};
            this.lastGann = {
                ok: !!g.ok,
                data: fetched,
                code: fetched.code || code,
                name: fetched.name || '',
                asof: fetched.asof || asof || '',
                error: null,
            };
            this.setBlockOk('ssaGannStatus', '');
            const st = document.getElementById('ssaGannStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·江恩趋势失败', e);
            host.innerHTML = '';
            this.lastGann = {
                ok: false,
                data: null,
                code,
                name: '',
                asof: asof || '',
                error: e.message || '江恩趋势分析失败',
            };
            this.setBlockError('ssaGannStatus', e.message || '江恩趋势分析失败，可稍后重试');
        }
        this.updateExportBtn();
        this.updateGannTradeObserveBtn();
    },

    async loadTradePlanSection(code, asof) {
        const block = document.getElementById('ssaTradePlanBlock');
        const host = document.getElementById('ssaTradePlanHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaTradePlanBlock', 'ssaTradePlanStatus', '正在合成综合交易策略…');
        try {
            const snapshots = {};
            if (this.lastLevels && this.lastLevels.data) {
                snapshots.levels = { data: this.lastLevels.data };
            }
            if (this.lastPattern) {
                snapshots.pattern = {
                    tactical: this.lastPattern.tactical || null,
                    items: this.lastPattern.items || [],
                };
            }
            if (this.lastSwing) {
                snapshots.swing = { data: this.lastSwing.data || null };
            }
            if (this.lastGann) {
                snapshots.gann = { data: this.lastGann.data || null };
            }
            const body = { code, snapshots };
            if (asof) body.date = asof;
            const resp = await authFetch(`${this.API_BASE_URL}/api/analysis/stock-integrated-trade-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `合成失败 ${resp.status}`);
            }
            const data = payload.data || {};
            const plan = data.plan || {};
            this.lastTradePlan = {
                ok: true,
                plan,
                code: (data.stock && data.stock.code) || code,
                name: (data.stock && data.stock.name) || '',
                trade_date: data.trade_date || asof || '',
                error: null,
            };
            if (typeof StockTradePlan !== 'undefined' && typeof StockTradePlan.render === 'function') {
                StockTradePlan.render(host, this.lastTradePlan);
            } else {
                const summary = (plan.short_term && plan.short_term.summary) || '综合策略已生成';
                host.innerHTML = `<p class="ssa-muted">${this.esc(summary)}</p>`;
            }
            block.hidden = false;
            this.setBlockOk('ssaTradePlanStatus', '');
            const st = document.getElementById('ssaTradePlanStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·综合交易策略失败', e);
            host.innerHTML = '';
            this.lastTradePlan = {
                ok: false,
                plan: null,
                code,
                name: '',
                trade_date: asof || '',
                error: e.message || '综合交易策略合成失败',
            };
            block.hidden = false;
            this.setBlockError('ssaTradePlanStatus', e.message || '综合交易策略合成失败，可稍后重试');
        }
        this.updateExportBtn();
    },

    renderStrategyResult(data) {
        const empty = document.getElementById('ssaEmpty');
        const meta = document.getElementById('ssaMeta');
        const host = document.getElementById('ssaResults');
        const block = document.getElementById('ssaStrategyBlock');
        if (empty) empty.hidden = true;
        const stock = data.stock || {};
        this.lastStrategy = data;
        this.lastStrategyError = null;
        this.lastStock = stock;
        this.lastTradeDate = data.trade_date || null;
        const observeBtn = document.getElementById('ssaTradeObserveBtn');
        if (observeBtn) {
            observeBtn.classList.remove('is-added');
            delete observeBtn.dataset.observeCode;
            observeBtn.textContent = '交易观察';
        }
        this.resetGannTradeObserveBtn();
        if (meta) {
            meta.hidden = false;
            const rt = data.realtime || this.lastRealtime;
            const useRt = !!(data.use_realtime || this.lastUseRealtime);
            const px = rt && rt.current_price != null ? Number(rt.current_price) : null;
            const chg = rt && rt.change_percent != null ? Number(rt.change_percent) : null;
            const pxTxt = px != null && Number.isFinite(px) ? px.toFixed(2) : '';
            const chgTxt = chg != null && Number.isFinite(chg)
                ? `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`
                : '';
            const modeTag = useRt
                ? `<span class="ssa-meta-tag ssa-meta-tag--live">实时分析</span>`
                : '';
            const priceTag = pxTxt
                ? `<span>现价 ${this.esc(pxTxt)}${chgTxt ? `（${this.esc(chgTxt)}）` : ''}</span>`
                : '';
            const dateLabel = useRt ? '实时日' : '基准日';
            const dateVal = useRt
                ? (data.realtime_trade_date || (rt && rt.trade_date) || data.trade_date || '--')
                : (data.trade_date || '--');
            meta.innerHTML = `
                <div class="ssa-meta-card">
                    <strong>${this.esc(stock.code || '')}</strong>
                    <span>${this.esc(stock.name || '')}</span>
                    ${modeTag}
                    ${priceTag}
                    <span>${dateLabel} ${this.esc(dateVal)}</span>
                    <span>命中 ${data.hit_count != null ? data.hit_count : 0}/4</span>
                    <span class="ssa-muted">${this.esc((rt && rt.update_time) || data.asof || '')}</span>
                </div>`;
        }
        if (!host) return;
        const order = ['rpe', 'sbbr', 'gms', 'urt'];
        const byKey = {};
        (data.results || []).forEach((r) => {
            if (r && r.strategy) byKey[r.strategy] = r;
        });
        host.innerHTML = order.map((key) => {
            const r = byKey[key] || {
                strategy: key,
                name: key.toUpperCase(),
                hit: false,
                label: '--',
                score_display: '--',
                reason: '无结果',
            };
            const hitCls = r.hit ? 'ssa-card--hit' : 'ssa-card--miss';
            const badge = r.hit
                ? `<span class="ssa-badge ssa-badge--yes">${this.esc(r.label || '命中')}</span>`
                : '<span class="ssa-badge ssa-badge--no">未命中</span>';
            const err = r.error
                ? `<div class="ssa-error">${this.esc(r.error)}</div>`
                : '';
            const links = [];
            if (r.trace_url) {
                links.push(
                    `<a class="ssa-link" href="${this.escAttr(r.trace_url)}" target="_blank" rel="noopener">信号追溯</a>`
                );
            }
            if (r.screening_url) {
                links.push(
                    `<a class="ssa-link" href="${this.escAttr(r.screening_url)}" target="_blank" rel="noopener">选股页</a>`
                );
            }
            return `<article class="ssa-card ${hitCls}" data-strategy="${this.escAttr(key)}">
                <div class="ssa-card-head">
                    <h4>${this.esc(r.name || key.toUpperCase())}</h4>
                    ${badge}
                </div>
                <div class="ssa-card-score">${this.esc(r.score_display || '--')}</div>
                <p class="ssa-card-reason">${this.esc(r.reason || '')}</p>
                ${err}
                <div class="ssa-card-links">${links.join(' · ')}</div>
            </article>`;
        }).join('');
        if (block) block.hidden = false;
        this.updateExportBtn();
    },

    exportBasename() {
        const d = new Date();
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const stock =
            (this.lastStrategy && this.lastStrategy.stock) ||
            this.lastStock ||
            (this.lastLevels && this.lastLevels.data) ||
            {};
        const code = String(
            stock.code || stock.stock_code || (this.lastPattern && this.lastPattern.code) || ''
        ).replace(/[^\w.-]/g, '');
        const codePart = code || 'unknown';
        const rawName = String(
            stock.name ||
                stock.stock_name ||
                (this.lastPattern && this.lastPattern.name) ||
                ''
        ).trim();
        // 去掉 Windows / 通用文件名非法字符，空白压成下划线
        const namePart = rawName
            .replace(/[\\/:*?"<>|]/g, '')
            .replace(/\s+/g, '_')
            .slice(0, 40);
        const mid = namePart ? `${codePart}_${namePart}` : codePart;
        return `个股分析_${mid}_${y}${m}${day}`;
    },

    pdfFilename() {
        return `${this.exportBasename()}.pdf`;
    },

    pngFilename() {
        return `${this.exportBasename()}.png`;
    },

    buildPdfHtml() {
        const filename = this.pdfFilename().replace(/\.pdf$/i, '');
        const stock =
            (this.lastStrategy && this.lastStrategy.stock) ||
            this.lastStock ||
            {};
        const meta = document.getElementById('ssaMeta');
        const strategyHost = document.getElementById('ssaResults');
        const levelsHost = document.getElementById('ssaLevelsHost');
        const levelsStatus = document.getElementById('ssaLevelsStatus');
        const patternHost = document.getElementById('ssaPatternHost');
        const patternStatus = document.getElementById('ssaPatternStatus');
        const swingHost = document.getElementById('ssaSwingHost');
        const swingStatus = document.getElementById('ssaSwingStatus');
        const gannHost = document.getElementById('ssaGannHost');
        const gannStatus = document.getElementById('ssaGannStatus');

        const cloneClean = (el) => {
            if (!el) return '';
            const clone = el.cloneNode(true);
            clone.querySelectorAll('.ssa-block-status.is-loading, a').forEach((node) => {
                if (node.tagName === 'A') {
                    const span = document.createElement('span');
                    span.textContent = node.textContent || '';
                    node.replaceWith(span);
                } else {
                    node.remove();
                }
            });
            return clone.innerHTML;
        };

        let strategyHtml = '';
        if (this.lastStrategyError && !this.lastStrategy) {
            strategyHtml = `<p class="ssa-pdf-err">${this.esc(this.lastStrategyError)}</p>`;
        } else if (strategyHost && strategyHost.innerHTML.trim()) {
            strategyHtml = cloneClean(strategyHost);
        } else {
            strategyHtml = '<p class="ssa-pdf-empty">暂无策略结果</p>';
        }

        let levelsHtml = '';
        if (this.lastLevels && this.lastLevels.error && !this.lastLevels.data) {
            levelsHtml = `<p class="ssa-pdf-err">${this.esc(this.lastLevels.error)}</p>`;
        } else if (levelsHost && levelsHost.innerHTML.trim()) {
            levelsHtml = cloneClean(levelsHost);
            if (levelsStatus && levelsStatus.classList.contains('is-error') && levelsStatus.textContent) {
                levelsHtml += `<p class="ssa-pdf-err">${this.esc(levelsStatus.textContent)}</p>`;
            }
        } else if (this.lastLevels && this.lastLevels.error) {
            levelsHtml = `<p class="ssa-pdf-err">${this.esc(this.lastLevels.error)}</p>`;
        } else {
            levelsHtml = '<p class="ssa-pdf-empty">暂无阻力支撑结果</p>';
        }

        let patternHtml = '';
        if (this.lastPattern && this.lastPattern.error && !(this.lastPattern.items || []).length) {
            patternHtml = `<p class="ssa-pdf-err">${this.esc(this.lastPattern.error)}</p>`;
        } else if (patternHost && patternHost.innerHTML.trim()) {
            patternHtml = cloneClean(patternHost);
            if (patternStatus && patternStatus.classList.contains('is-error') && patternStatus.textContent) {
                patternHtml += `<p class="ssa-pdf-err">${this.esc(patternStatus.textContent)}</p>`;
            }
        } else if (this.lastPattern && this.lastPattern.error) {
            patternHtml = `<p class="ssa-pdf-err">${this.esc(this.lastPattern.error)}</p>`;
        } else {
            patternHtml = '<p class="ssa-pdf-empty">暂无形态识别结果</p>';
        }

        let swingHtml = '';
        if (this.lastSwing && this.lastSwing.error && !this.lastSwing.data) {
            swingHtml = `<p class="ssa-pdf-err">${this.esc(this.lastSwing.error)}</p>`;
        } else if (swingHost && swingHost.innerHTML.trim()) {
            swingHtml = cloneClean(swingHost);
            if (swingStatus && swingStatus.classList.contains('is-error') && swingStatus.textContent) {
                swingHtml += `<p class="ssa-pdf-err">${this.esc(swingStatus.textContent)}</p>`;
            }
        } else if (this.lastSwing && this.lastSwing.error) {
            swingHtml = `<p class="ssa-pdf-err">${this.esc(this.lastSwing.error)}</p>`;
        } else {
            swingHtml = '<p class="ssa-pdf-empty">暂无波段趋势结果</p>';
        }

        let gannHtml = '';
        if (this.lastGann && this.lastGann.error && !this.lastGann.data) {
            gannHtml = `<p class="ssa-pdf-err">${this.esc(this.lastGann.error)}</p>`;
        } else if (gannHost && gannHost.innerHTML.trim()) {
            gannHtml = cloneClean(gannHost);
            if (gannStatus && gannStatus.classList.contains('is-error') && gannStatus.textContent) {
                gannHtml += `<p class="ssa-pdf-err">${this.esc(gannStatus.textContent)}</p>`;
            }
        } else if (this.lastGann && this.lastGann.error) {
            gannHtml = `<p class="ssa-pdf-err">${this.esc(this.lastGann.error)}</p>`;
        } else {
            gannHtml = '<p class="ssa-pdf-empty">暂无江恩趋势结果</p>';
        }

        const metaHtml = meta && !meta.hidden && meta.innerHTML.trim()
            ? meta.innerHTML
            : `<div>${this.esc(stock.code || '')} ${this.esc(stock.name || '')}</div>`;

        return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"/>
<title>${this.esc(filename)}</title>
<style>
  @page { size: A4 portrait; margin: 12mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    color: #0f172a; font-size: 12px; line-height: 1.45; padding: 12px 16px; background: #fff;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  h1 { font-size: 18px; margin: 0 0 8px; }
  h2 { font-size: 14px; margin: 16px 0 8px; color: #1e40af; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px; }
  .meta { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; }
  .ssa-pdf-empty { color: #94a3b8; }
  .ssa-pdf-err { color: #b91c1c; }
  .print-hint {
    margin: 0 0 10px; padding: 8px 10px; background: #eff6ff; border: 1px solid #bfdbfe;
    border-radius: 6px; color: #1e3a8a; font-size: 12px;
  }
  .ssa-results { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .ssa-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; page-break-inside: avoid; }
  .ssa-card--hit { border-color: #86efac; background: #f0fdf4; }
  .ssa-card--miss { background: #f8fafc; }
  .ssa-card-head { display: flex; justify-content: space-between; align-items: center; }
  .ssa-card-head h4 { margin: 0; font-size: 13px; }
  .ssa-badge { font-size: 11px; padding: 1px 6px; border-radius: 3px; }
  .ssa-badge--yes { background: #dcfce7; color: #166534; }
  .ssa-badge--no { background: #e2e8f0; color: #475569; }
  .ssa-card-score { font-weight: 600; margin: 4px 0; }
  .ssa-card-reason { margin: 0; color: #334155; }
  .ssa-card-links { display: none; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; margin: 6px 0; }
  th, td { border: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; }
  th { background: #f1f5f9; }
  .kde-levels-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
  .kde-levels-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; page-break-inside: avoid; }
  .kde-levels-subtitle { margin: 12px 0 6px; font-size: 13px; color: #334155; }
  .pattern-expert-analysis { margin-top: 8px; padding: 8px; background: #f8fafc; border-radius: 6px; }
  .ms-zigzag-svg, .gann-fan-svg { max-width: 100%; }
  @media print {
    body { padding: 0; }
    .print-hint { display: none !important; }
  }
</style></head><body>
  <p class="print-hint">请在打印对话框中选择「另存为 PDF / Microsoft Print to PDF」。关闭本页不影响分析结果。</p>
  <h1>个股分析结果</h1>
  <div class="meta">${metaHtml}</div>
  <h2>策略分析</h2>
  ${strategyHtml}
  <h2>阻力支撑位</h2>
  ${levelsHtml}
  <h2>形态识别</h2>
  ${patternHtml}
  <h2>波段与趋势</h2>
  ${swingHtml}
  <h2>江恩趋势预测</h2>
  ${gannHtml}
</body></html>`;
    },

    exportViaPrint(html, filename) {
        const w = window.open('', '_blank');
        if (!w) {
            if (window.CommonUtils) {
                CommonUtils.showToast('浏览器拦截了弹窗，请允许后重试，再点「导出 PDF」', 'warning');
            }
            return false;
        }
        w.document.open();
        w.document.write(html);
        w.document.close();
        w.document.title = filename.replace(/\.pdf$/i, '');
        const triggerPrint = () => {
            try {
                w.focus();
                w.print();
            } catch (e) {
                console.warn(e);
            }
        };
        if (w.document.fonts && w.document.fonts.ready) {
            w.document.fonts.ready.then(() => setTimeout(triggerPrint, 80)).catch(() => setTimeout(triggerPrint, 350));
        } else {
            setTimeout(triggerPrint, 350);
        }
        return true;
    },

    _beginExport(btn, busyText) {
        this.exporting = true;
        this.updateExportBtn();
        if (btn) {
            btn.disabled = true;
            btn.classList.add('ssa-exporting');
            btn.textContent = busyText || '导出中…';
        }
    },

    _endExport(btn, idleText) {
        this.exporting = false;
        if (btn) {
            btn.classList.remove('ssa-exporting');
            btn.textContent = idleText;
        }
        this.updateExportBtn();
    },

    async exportPdf() {
        if (!this.hasExportableResult()) {
            if (window.CommonUtils) CommonUtils.showToast('请先完成个股分析再导出', 'warning');
            return;
        }
        if (this.exporting) return;
        const btn = document.getElementById('ssaExportPdfBtn');
        const filename = this.pdfFilename();
        this._beginExport(btn, '导出中…');
        try {
            if (!window.StockAnalysisPdf || typeof StockAnalysisPdf.exportFromHost !== 'function') {
                throw new Error('PDF 导出模块未加载');
            }
            const saved = await StockAnalysisPdf.exportFromHost(this);
            if (window.CommonUtils) CommonUtils.showToast(`已导出 ${saved || filename}`, 'success');
        } catch (e) {
            console.warn('结构化 PDF 导出失败，回退打印', e);
            const html = this.buildPdfHtml();
            const ok = this.exportViaPrint(html, filename);
            const reason = (e && e.message) || String(e || '未知错误');
            if (window.CommonUtils) {
                if (ok) {
                    CommonUtils.showToast(`结构化导出失败（${reason}），已打开打印预览作兜底`, 'warning');
                } else {
                    CommonUtils.showToast(`导出失败：${reason}`, 'error');
                }
            }
        } finally {
            this._endExport(btn, '导出 PDF');
        }
    },

    async exportPng() {
        if (!this.hasExportableResult()) {
            if (window.CommonUtils) CommonUtils.showToast('请先完成个股分析再导出', 'warning');
            return;
        }
        if (this.exporting) return;
        const btn = document.getElementById('ssaExportPngBtn');
        const filename = this.pngFilename();
        this._beginExport(btn, '导出中…');
        try {
            if (!window.StockAnalysisPng || typeof StockAnalysisPng.exportFromHost !== 'function') {
                throw new Error('PNG 导出模块未加载');
            }
            const saved = await StockAnalysisPng.exportFromHost(this);
            if (window.CommonUtils) CommonUtils.showToast(`已导出 ${saved || filename}`, 'success');
        } catch (e) {
            console.warn('PNG 导出失败', e);
            const reason = (e && e.message) || String(e || '未知错误');
            if (window.CommonUtils) CommonUtils.showToast(`导出 PNG 失败：${reason}`, 'error');
        } finally {
            this._endExport(btn, '导出 PNG');
        }
    },

    esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    escAttr(s) {
        return this.esc(s).replace(/'/g, '&#39;');
    },
};

window.StockMultiStrategy = StockMultiStrategy;
