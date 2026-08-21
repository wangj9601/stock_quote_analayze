/**
 * 分析频道 · 个股综合分析（RPE / SBBR / GMS / URT + 阻力支撑 + 形态 + 波段趋势 + 江恩）
 */
const StockMultiStrategy = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
    running: false,
    exporting: false,
    observing: false,
    lastStrategy: null,
    lastStrategyError: null,
    lastStock: null,
    lastTradeDate: null,
    lastLevels: null,
    lastPattern: null,
    lastSwing: null,
    lastGann: null,

    init() {
        const btn = document.getElementById('ssaAnalyzeBtn');
        if (btn) {
            btn.addEventListener('click', () => this.analyze());
        }
        const exportBtn = document.getElementById('ssaExportPdfBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPdf());
        }
        const observeBtn = document.getElementById('ssaTradeObserveBtn');
        if (observeBtn) {
            observeBtn.addEventListener('click', () => this.addTradeObserve());
        }
        const codeInput = document.getElementById('ssaStockCode');
        if (codeInput) {
            codeInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.analyze();
                }
            });
            codeInput.addEventListener('input', () => this.updateTradeObserveBtn());
        }
        const watchSelect = document.getElementById('ssaWatchlist');
        if (watchSelect) {
            watchSelect.addEventListener('change', () => {
                const val = (watchSelect.value || '').trim();
                if (val && codeInput) codeInput.value = val;
                this.updateTradeObserveBtn();
            });
        }
        const dateEl = document.getElementById('ssaTradeDate');
        if (dateEl) {
            dateEl.addEventListener('change', () => this.updateTradeObserveBtn());
        }
        this.updateExportBtn();
        this.updateTradeObserveBtn();
        this.bindScrollFab();
    },

    /**
     * 从 URL ?code=&name= 填入个股分析输入框并自动分析（仅执行一次）。
     * 供 analysis.html?tab=stock-ai&code=xxx 深链（如龙头/中军标签跳转）使用。
     */
    bootstrapFromUrl() {
        if (this._urlBootstrapped) return;
        let code = '';
        let name = '';
        try {
            const params = new URLSearchParams(window.location.search || '');
            code = (params.get('code') || '').trim();
            name = (params.get('name') || '').trim();
        } catch (e) {
            return;
        }
        if (!code) return;
        this._urlBootstrapped = true;
        const input = document.getElementById('ssaStockCode');
        if (input) {
            input.value = name ? `${code} ${name}` : code;
        }
        void this.analyze();
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

    async loadWatchlistOptions() {
        const select = document.getElementById('ssaWatchlist');
        if (!select || select.dataset.loaded === '1') return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        try {
            const resp = await authFetch(`${this.API_BASE_URL}/api/watchlist`);
            if (!resp.ok) return;
            const payload = await resp.json();
            const list = Array.isArray(payload)
                ? payload
                : (payload.data || payload.items || payload.stocks || []);
            if (!Array.isArray(list)) return;
            const seen = new Set();
            const opts = ['<option value="">-- 可选自选股 --</option>'];
            list.forEach((item) => {
                const code = String(item.code || item.stock_code || '').trim();
                if (!code || seen.has(code)) return;
                seen.add(code);
                const name = item.name || item.stock_name || '';
                opts.push(`<option value="${code}">${name ? `${code} ${name}` : code}</option>`);
            });
            select.innerHTML = opts.join('');
            select.dataset.loaded = '1';
        } catch (e) {
            console.warn('加载自选股失败', e);
        }
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
        this.lastPattern = null;
        this.lastSwing = null;
        this.lastGann = null;
        const observeBtn = document.getElementById('ssaTradeObserveBtn');
        if (observeBtn) {
            observeBtn.classList.remove('is-added');
            delete observeBtn.dataset.observeCode;
            observeBtn.textContent = '交易观察';
        }
        this.updateExportBtn();
        this.updateTradeObserveBtn();
    },

    hasExportableResult() {
        return !!(
            this.lastStrategy ||
            this.lastLevels ||
            this.lastPattern ||
            this.lastSwing ||
            this.lastGann ||
            this.lastStrategyError
        );
    },

    updateExportBtn() {
        const btn = document.getElementById('ssaExportPdfBtn');
        const ok = this.hasExportableResult();
        if (btn) {
            btn.disabled = !ok || this.exporting;
            if (!this.exporting) btn.textContent = '导出 PDF';
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
        return swingAsof || '';
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
        ['ssaStrategyBlock', 'ssaLevelsBlock', 'ssaPatternBlock', 'ssaSwingBlock', 'ssaGannBlock'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.hidden = true;
        });
        const levelsHost = document.getElementById('ssaLevelsHost');
        const patternHost = document.getElementById('ssaPatternHost');
        const swingHost = document.getElementById('ssaSwingHost');
        const gannHost = document.getElementById('ssaGannHost');
        if (levelsHost) levelsHost.innerHTML = '';
        if (patternHost) patternHost.innerHTML = '';
        if (swingHost) swingHost.innerHTML = '';
        if (gannHost) gannHost.innerHTML = '';
        const levelsStatus = document.getElementById('ssaLevelsStatus');
        const patternStatus = document.getElementById('ssaPatternStatus');
        const swingStatus = document.getElementById('ssaSwingStatus');
        const gannStatus = document.getElementById('ssaGannStatus');
        [levelsStatus, patternStatus, swingStatus, gannStatus].forEach((status) => {
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

    async analyze() {
        if (this.running) return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        const codeInput = document.getElementById('ssaStockCode');
        const btn = document.getElementById('ssaAnalyzeBtn');
        const empty = document.getElementById('ssaEmpty');
        if (!codeInput) return;

        let query = (codeInput.value || '').trim();
        if (!query) {
            CommonUtils.showToast('请输入股票代码或名称', 'warning');
            codeInput.focus();
            return;
        }
        const firstToken = query.split(/\s+/)[0];
        const firstBody = /^(sh|sz|bj)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
        if (/^\d{4,6}$/.test(firstBody)) query = firstToken;

        this.running = true;
        this.hideCandidates();
        this.hideResultBlocks();
        if (btn) {
            btn.disabled = true;
            btn.textContent = '分析中…';
        }
        if (empty) {
            empty.hidden = false;
            empty.textContent = '正在评估策略、阻力支撑与形态，请稍候…';
        }
        const meta = document.getElementById('ssaMeta');
        if (meta) meta.hidden = true;

        try {
            const q = new URLSearchParams({ code: query });
            const dateEl = document.getElementById('ssaTradeDate');
            const asof = dateEl && dateEl.value ? dateEl.value : '';
            if (asof) q.set('date', asof);
            const resp = await authFetch(
                `${this.API_BASE_URL}/api/analysis/multi-strategy-check?${q}`
            );
            const payload = await resp.json().catch(() => ({}));
            const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
            if (candidates.length > 1 || (candidates.length > 0 && !payload.data)) {
                this.renderCandidates(candidates, payload.message);
                CommonUtils.showToast(payload.message || '请从候选中选择股票', 'warning');
                return;
            }
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
            }
            const data = payload.data || {};
            const stock = data.stock || {};
            if (stock.code && codeInput) {
                codeInput.value = stock.name ? `${stock.code} ${stock.name}` : stock.code;
            }
            this.lastTradeDate = data.trade_date || asof || null;
            this.renderStrategyResult(data);
            if (empty) empty.hidden = true;

            // 策略成功后并行拉取阻力支撑、形态、波段趋势、江恩（失败互不影响）
            const resolvedCode = stock.code || query;
            const tradeDate = data.trade_date || asof || '';
            await Promise.all([
                this.loadLevelsSection(resolvedCode),
                this.loadPatternSection(resolvedCode, tradeDate),
                this.loadSwingSection(resolvedCode, tradeDate),
                this.loadGannSection(resolvedCode, tradeDate),
            ]);
            this.updateExportBtn();

            CommonUtils.showToast(
                data.any_hit ? `命中 ${data.hit_count || 0} 个策略` : '四策略均未命中',
                data.any_hit ? 'success' : 'info'
            );
        } catch (e) {
            console.error(e);
            // 策略失败时：若输入已是明确代码，仍尝试阻力支撑与形态
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
                if (strategyBlock && strategyHost) {
                    strategyBlock.hidden = false;
                    strategyHost.innerHTML = `<div class="ssa-block-status is-error">${this.esc(e.message || '策略分析失败')}</div>`;
                }
                await Promise.all([
                    this.loadLevelsSection(firstToken),
                    this.loadPatternSection(firstToken, asofFallback),
                    this.loadSwingSection(firstToken, asofFallback),
                    this.loadGannSection(firstToken, asofFallback),
                ]);
                this.updateExportBtn();
                CommonUtils.showToast('策略分析失败，已尝试计算阻力支撑、形态、波段与江恩', 'warning');
            } else {
                if (empty) {
                    empty.hidden = false;
                    empty.textContent = e.message || '分析失败';
                }
                CommonUtils.showToast(e.message || '分析失败', 'error');
            }
        } finally {
            this.running = false;
            if (btn) {
                btn.disabled = false;
                btn.textContent = '分析';
            }
            this.updateExportBtn();
        }
    },

    async loadLevelsSection(code) {
        const block = document.getElementById('ssaLevelsBlock');
        const host = document.getElementById('ssaLevelsHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaLevelsBlock', 'ssaLevelsStatus', '正在计算阻力支撑位…');
        try {
            if (typeof KdeLevelsTool === 'undefined' || typeof KdeLevelsTool.fetchLevels !== 'function') {
                throw new Error('阻力支撑模块未加载');
            }
            const fetched = await KdeLevelsTool.fetchLevels(code, {
                adjust: 'qfq',
                factor_source: 'auto',
                max_levels: 8,
            });
            if (fetched.candidates && fetched.candidates.length > 1 && !fetched.data) {
                throw new Error(fetched.message || '股票代码不唯一，请使用精确代码');
            }
            if (!fetched.httpOk && !fetched.data) {
                throw new Error(fetched.message || '阻力支撑计算失败');
            }
            KdeLevelsTool.renderEmbedded(host, fetched.data || {}, fetched.ok, fetched.message, {
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

    async loadPatternSection(code, asof) {
        const block = document.getElementById('ssaPatternBlock');
        const host = document.getElementById('ssaPatternHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaPatternBlock', 'ssaPatternStatus', '正在识别形态…');
        try {
            if (typeof PatternTool === 'undefined' || typeof PatternTool.fetchSingle !== 'function') {
                throw new Error('形态识别模块未加载');
            }
            const fetched = await PatternTool.fetchSingle(code, {
                adjust: 'qfq',
                asof: asof || undefined,
            });
            const invN = fetched.invalidated_count || 0;
            const meta = `个股 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准日 ${this.esc(fetched.asof || '--')} · ${this.esc(PatternTool.adjustLabel(fetched.price_adjust))} · ${this.esc(PatternTool.formatHitMeta(fetched.items.length, invN))}`;
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

    async loadSwingSection(code, asof) {
        const block = document.getElementById('ssaSwingBlock');
        const host = document.getElementById('ssaSwingHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaSwingBlock', 'ssaSwingStatus', '正在分析波段与趋势…');
        try {
            if (typeof MarketStructureTool === 'undefined' || typeof MarketStructureTool.fetchStructure !== 'function') {
                throw new Error('波段趋势模块未加载');
            }
            // 稍候形态可能未完成；先拉结构，有 bias 再带上
            const bias = this._patternShortBias();
            const fetched = await MarketStructureTool.fetchStructure(code, {
                adjust: 'qfq',
                asof: asof || undefined,
                pattern_short_bias: bias || undefined,
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

    async loadGannSection(code, asof) {
        const block = document.getElementById('ssaGannBlock');
        const host = document.getElementById('ssaGannHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaGannBlock', 'ssaGannStatus', '正在计算江恩趋势…');
        try {
            if (typeof GannTrendTool === 'undefined' || typeof GannTrendTool.fetchGann !== 'function') {
                throw new Error('江恩趋势模块未加载');
            }
            const fetched = await GannTrendTool.fetchGann(code, {
                adjust: 'qfq',
                asof: asof || undefined,
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
        if (meta) {
            meta.hidden = false;
            meta.innerHTML = `
                <div class="ssa-meta-card">
                    <strong>${this.esc(stock.code || '')}</strong>
                    <span>${this.esc(stock.name || '')}</span>
                    <span>基准日 ${this.esc(data.trade_date || '--')}</span>
                    <span>命中 ${data.hit_count != null ? data.hit_count : 0}/4</span>
                    <span class="ssa-muted">${this.esc(data.asof || '')}</span>
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

    pdfFilename() {
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
        return `个股分析_${mid}_${y}${m}${day}.pdf`;
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

    async exportPdf() {
        if (!this.hasExportableResult()) {
            if (window.CommonUtils) CommonUtils.showToast('请先完成个股分析再导出', 'warning');
            return;
        }
        if (this.exporting) return;
        const btn = document.getElementById('ssaExportPdfBtn');
        const filename = this.pdfFilename();
        this.exporting = true;
        if (btn) {
            btn.disabled = true;
            btn.classList.add('ssa-exporting');
            btn.textContent = '导出中…';
        }
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
            this.exporting = false;
            if (btn) {
                btn.classList.remove('ssa-exporting');
                btn.textContent = '导出 PDF';
            }
            this.updateExportBtn();
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
