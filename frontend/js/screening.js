// 选股页面功能模块
const ScreeningPage = {
    API_BASE_URL: Config ? Config.getApiBaseUrl() : '',
    currentStrategy: 'cyb-midline', // 当前选中的策略
    lastResults: {}, // 存储最近一次筛选结果，用于导出
    /** GMS 列表分页（选股页） */
    gmsPage: 1,
    GMS_PAGE_SIZE: 100,
    gmsLocateActive: false,
    _vsbOpenFromHash: false,
    vsbSubPanel: 'pick',
    /** 观察股池内子页：vsb=选股命中表；daily=日终爆量表 */
    vsbObserveSource: 'vsb',
    /** GMS 子页：signals=策略信号；trade-observe=交易观察；formal-trade=正式交易 */
    gmsSubPanel: 'signals',
    /** URT 子页：signals / trade-observe / formal-trade */
    urtSubPanel: 'signals',
    /** 已加入 URT 交易观察的 CN:code */
    urtTradeObserveCodeSet: new Set(),
    /** 已在 URT 正式交易中的 CN:code */
    urtFormalTradeCodeSet: new Set(),
    urtTradeObserveItems: [],
    _urtFormalTransferObserveId: null,
    lastUrtSearchDate: null,
    /** 已加入交易观察的 CN:code / HK:code */
    gmsTradeObserveCodeSet: new Set(),
    /** 已在正式交易中的 CN:code / HK:code（策略信号页也显示「已观察」） */
    gmsFormalTradeCodeSet: new Set(),
    /** 最近一次加载的交易观察列表（供转正式交易弹窗读取 price_plan） */
    gmsTradeObserveItems: [],
    /** 转正式交易弹窗：当前观察记录 id */
    _gmsFormalTransferObserveId: null,
    /** 编辑正式交易弹窗：当前交易 id */
    _gmsFormalEditTradeId: null,
    /** 编辑弹窗打开时是否为已平仓记录 */
    _gmsFormalEditWasClosed: false,
    /** 已加入 3倍量交易观察的 CN:code / HK:code */
    tvoTradeObserveCodeSet: new Set(),
    /** 日终爆量列表量比排序：null=默认观察日；asc/desc=按 volume_ratio_actual */
    dailyTvoVolumeRatioSort: null,
    /** 最近一次日终爆量列表数据 */
    lastDailyTvoItems: [],
    /** 最近一次 GMS 筛选基准交易日（与接口 search_date 一致） */
    lastGmsSearchDate: null,
    /** 当前选中的 GMS 策略参数版本 ID（服务端） */
    gmsConfigId: null,
    /** 当前 GMS 策略参数版本摘要（得分明细展示） */
    gmsConfigMeta: null,
    /** 行业板块下拉是否已加载 */
    _gmsIndustryBoardsLoaded: false,
    /** 概念板块下拉是否已加载 */
    _gmsConceptBoardsLoaded: false,
    /** 行业/概念板块选项缓存 */
    gmsIndustryBoardCatalog: [],
    gmsConceptBoardCatalog: [],
    /** 已选板块代码 */
    gmsSelectedIndustryBoardCodes: [],
    gmsSelectedConceptBoardCodes: [],
    /** URT 已选行业/概念板块 */
    urtSelectedIndustryBoardCodes: [],
    urtSelectedConceptBoardCodes: [],
    /** RPE 已选行业/概念板块 */
    rpeSelectedIndustryBoardCodes: [],
    rpeSelectedConceptBoardCodes: [],
    /** 板块选择弹窗：industry | concept */
    _gmsBoardPickerKind: null,
    _gmsBoardPickerDraft: new Set(),
    /** 板块选择弹窗代码来源筛选：all | eastmoney | tonghuashun */
    _gmsBoardPickerSourceFilter: 'all',
    /** 板块选择弹窗归属：gms | urt | rpe */
    _gmsBoardPickerOwner: 'gms',
    /** 板块选择弹窗正在刷新选项 */
    _gmsBoardPickerRefreshing: false,

    // 初始化
    async init() {
        await this.loadHeader();
        this.bindEvents();
        this.initStrategyTabs();
        this.initStrategyInfoCollapse();
        this.initVsbIntegratedTabs();
        this.initGmsIntegratedTabs();
        this.initUrtIntegratedTabs();
        // 权限引擎需在 Tab 事件绑定后再应用，以便正确切换到首个有权限的策略
        if (typeof loadPermissionEngine === 'function') {
            await loadPermissionEngine();
        }
        this.ensureActiveStrategyVisible();
        this.applyVsbHashOnLoad();
        void this.initUrtStrategyConfig();
    },

    /** 窄屏下策略说明默认折叠，避免占满首屏导致列表/按钮不可见 */
    initStrategyInfoCollapse() {
        document.querySelectorAll('.strategy-info-card').forEach((card) => {
            if (card.querySelector('.strategy-info-toggle')) return;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'strategy-info-toggle';
            btn.textContent = '展开策略说明';
            btn.addEventListener('click', () => {
                const open = card.classList.toggle('is-expanded');
                btn.textContent = open ? '收起策略说明' : '展开策略说明';
            });
            card.appendChild(btn);
        });
    },

    /** 默认策略 Tab 被权限隐藏时，切换到第一个可见且有权限的策略 */
    ensureActiveStrategyVisible() {
        const activeContent = document.querySelector('.strategy-content.active');
        const contentHidden = !activeContent
            || activeContent.getAttribute('aria-hidden') === 'true'
            || getComputedStyle(activeContent).display === 'none';
        if (!contentHidden) return;

        const legacyHidden = new Set(['parking-apron', 'backtrace-ma250', 'high-tight-flag']);
        const tabs = Array.from(document.querySelectorAll('.strategy-tab[data-strategy]'));
        const pick = tabs.find((t) => {
            if (legacyHidden.has(t.dataset.strategy)) return false;
            if (getComputedStyle(t).display === 'none') return false;
            const perm = t.getAttribute('data-perm');
            if (perm && window.PermissionEngine && !PermissionEngine.has(perm)) return false;
            return true;
        });
        if (pick) {
            this.switchStrategy(pick.dataset.strategy);
        }
    },

    // 初始化策略标签页
    initStrategyTabs() {
        const tabs = document.querySelectorAll('.strategy-tab');
        tabs.forEach(tab => {
            // 跳过隐藏的标签页（停机坪、回踩年线、高而窄的旗形）
            const hiddenStrategies = ['parking-apron', 'backtrace-ma250', 'high-tight-flag'];
            if (hiddenStrategies.includes(tab.dataset.strategy)) {
                return; // 跳过隐藏的策略
            }

            tab.addEventListener('click', () => {
                const strategy = tab.dataset.strategy;
                this.switchStrategy(strategy);
            });
        });
    },

    // 切换策略标签页
    switchStrategy(strategy) {
        // 检查是否为隐藏的策略
        const hiddenStrategies = ['parking-apron', 'backtrace-ma250', 'high-tight-flag'];
        if (hiddenStrategies.includes(strategy)) {
            console.warn(`策略 ${strategy} 已被隐藏，无法切换`);
            return;
        }

        // 权限校验：无对应 Tab 权限则不允许切换
        const tabPerm = (window.PERMISSION_TAB_MAP && window.PERMISSION_TAB_MAP[strategy]) || null;
        if (tabPerm && window.PermissionEngine && !PermissionEngine.has(tabPerm)) {
            if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                CommonUtils.showToast('您没有该选股策略的访问权限', 'warning');
            }
            return;
        }

        this.currentStrategy = strategy;

        // 更新标签页状态
        document.querySelectorAll('.strategy-tab').forEach(t => {
            t.classList.remove('active');
        });
        const targetTab = document.querySelector(`[data-strategy="${strategy}"]`);
        if (targetTab) {
            targetTab.classList.add('active');
        }

        // 更新内容区域显示
        document.querySelectorAll('.strategy-content').forEach(c => {
            c.classList.remove('active');
        });
        const targetContent = document.getElementById(`${strategy}-content`);
        if (targetContent) {
            targetContent.classList.add('active');
        }

        // 切换到 PVFARS 时加载策略参数
        if (strategy === 'pvfrs') {
            this.loadPvfrsParams();
        }
        // 切换到 GMS 时加载策略参数
        if (strategy === 'gms') {
            void this.initGmsStrategyConfig();
            this.syncGmsWatchlistMarketWrap();
            this.syncGmsCnBoardWrap();
            this.syncGmsIndustryBoardWrap();
            this.syncGmsSingleStockWrap();
            void this.loadGmsIndustryBoardOptions();
            void this.loadGmsObservedCodeSets();
        }
        if (strategy === 'urt') {
            void this.initUrtStrategyConfig();
            void this.loadUrtObservedCodeSets();
        }
        if (strategy === 'volume-shrink-breakout' && !this._vsbOpenFromHash) {
            this.switchVsbSubPanel('pick');
        }
        if (strategy === 'volume-shrink-breakout') {
            void this.loadTvoTradeObserveCodes();
        }
    },

    initGmsIntegratedTabs() {
        document.querySelectorAll('.gms-integrated-head .gms-sub-tab').forEach((btn) => {
            btn.addEventListener('click', () => {
                const sub = btn.getAttribute('data-gms-sub');
                if (sub === 'signals' || sub === 'trade-observe' || sub === 'formal-trade') {
                    this.switchGmsSubPanel(sub);
                }
            });
        });
        const refreshBtn = document.getElementById('gmsTradeObserveRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshGmsTradeObserveList());
        }
        const formalRefreshBtn = document.getElementById('gmsFormalTradeRefreshBtn');
        if (formalRefreshBtn) {
            formalRefreshBtn.addEventListener('click', () => this.refreshGmsFormalTradeList());
        }
        const formalStatusFilter = document.getElementById('gmsFormalTradeStatusFilter');
        if (formalStatusFilter) {
            formalStatusFilter.addEventListener('change', () => this.refreshGmsFormalTradeList());
        }
        const observeBody = document.getElementById('gmsTradeObserveTableBody');
        if (observeBody) {
            observeBody.addEventListener('click', (e) => {
                const transfer = e.target.closest('.gms-trade-observe-transfer');
                if (transfer) {
                    e.preventDefault();
                    const id = transfer.getAttribute('data-id');
                    const code = transfer.getAttribute('data-code') || '';
                    const name = transfer.getAttribute('data-name') || '';
                    if (id) this.openGmsFormalTransferModal(parseInt(id, 10), code, name);
                    return;
                }
                const rm = e.target.closest('.gms-trade-observe-remove');
                if (rm) {
                    e.preventDefault();
                    const id = rm.getAttribute('data-id');
                    if (id) void this.removeGmsTradeObserve(parseInt(id, 10), rm);
                    return;
                }
                const focusBtn = e.target.closest('.gms-key-focus-btn');
                if (focusBtn) {
                    e.preventDefault();
                    const id = focusBtn.getAttribute('data-id');
                    if (id) void this.toggleGmsTradeObserveKeyFocus(parseInt(id, 10), focusBtn);
                    return;
                }
                const latestBtn = e.target.closest('.gms-latest-price-btn');
                if (latestBtn) {
                    e.preventDefault();
                    const id = latestBtn.getAttribute('data-id');
                    if (id) void this.fetchGmsTradeObserveLatestPrice(parseInt(id, 10), latestBtn);
                }
            });
        }
        const formalBody = document.getElementById('gmsFormalTradeTableBody');
        if (formalBody) {
            formalBody.addEventListener('click', (e) => {
                const editBtn = e.target.closest('.gms-formal-trade-edit');
                if (editBtn) {
                    e.preventDefault();
                    const id = editBtn.getAttribute('data-id');
                    if (id) this.openGmsFormalEditModal(parseInt(id, 10), editBtn);
                    return;
                }
                const delBtn = e.target.closest('.gms-formal-trade-delete');
                if (delBtn) {
                    e.preventDefault();
                    const id = delBtn.getAttribute('data-id');
                    if (id && window.confirm('确定删除该正式交易记录？')) {
                        void this.deleteGmsFormalTrade(parseInt(id, 10), delBtn);
                    }
                }
            });
        }
        this._bindGmsFormalModalEvents();
        this._bindUrtFormalModalEvents();
        this._bindGmsBoardPickerEvents();
    },

    initUrtIntegratedTabs() {
        document.querySelectorAll('#urt-content .gms-integrated-head .gms-sub-tab').forEach((btn) => {
            btn.addEventListener('click', () => {
                const sub = btn.getAttribute('data-urt-sub');
                if (sub === 'signals' || sub === 'trade-observe' || sub === 'formal-trade') {
                    this.switchUrtSubPanel(sub);
                }
            });
        });
        const refreshBtn = document.getElementById('urtTradeObserveRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshUrtTradeObserveList());
        }
        const urtQfqBtn = document.getElementById('urtQfqLevelsBtn');
        if (urtQfqBtn) {
            urtQfqBtn.addEventListener('click', () => void this.recomputeUrtQfqLevels());
        }
        const formalRefreshBtn = document.getElementById('urtFormalTradeRefreshBtn');
        if (formalRefreshBtn) {
            formalRefreshBtn.addEventListener('click', () => this.refreshUrtFormalTradeList());
        }
        const formalStatusFilter = document.getElementById('urtFormalTradeStatusFilter');
        if (formalStatusFilter) {
            formalStatusFilter.addEventListener('change', () => this.refreshUrtFormalTradeList());
        }
        const observeBody = document.getElementById('urtTradeObserveTableBody');
        if (observeBody) {
            observeBody.addEventListener('click', (e) => {
                const detailBtn = e.target.closest('.urt-observe-detail-toggle');
                if (detailBtn) {
                    e.preventDefault();
                    const row = detailBtn.getAttribute('data-row');
                    const detailTr = observeBody.querySelector(`tr.urt-observe-detail-row[data-detail-for="${row}"]`);
                    if (detailTr) {
                        const hide = detailTr.style.display === 'none' || !detailTr.style.display;
                        detailTr.style.display = hide ? '' : 'none';
                    }
                    return;
                }
                const transfer = e.target.closest('.urt-trade-observe-transfer');
                if (transfer) {
                    e.preventDefault();
                    const id = transfer.getAttribute('data-id');
                    const code = transfer.getAttribute('data-code') || '';
                    const name = transfer.getAttribute('data-name') || '';
                    if (id) this.openUrtFormalTransferModal(parseInt(id, 10), code, name);
                    return;
                }
                const rm = e.target.closest('.urt-trade-observe-remove');
                if (rm) {
                    e.preventDefault();
                    const id = rm.getAttribute('data-id');
                    if (id) void this.removeUrtTradeObserve(parseInt(id, 10), rm);
                }
            });
        }
        const formalBody = document.getElementById('urtFormalTradeTableBody');
        if (formalBody) {
            formalBody.addEventListener('click', (e) => {
                const delBtn = e.target.closest('.urt-formal-trade-delete');
                if (delBtn) {
                    e.preventDefault();
                    const id = delBtn.getAttribute('data-id');
                    if (id && window.confirm('确定删除该正式交易记录？')) {
                        void this.deleteUrtFormalTrade(parseInt(id, 10), delBtn);
                    }
                }
            });
        }
    },

    _bindUrtFormalModalEvents() {
        const overlay = document.getElementById('urtFormalTransferModal');
        if (!overlay) return;
        ['urtFormalTransferClose', 'urtFormalTransferCancel'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', () => this._hideGmsModal(overlay));
        });
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this._hideGmsModal(overlay);
        });
        const card = overlay.querySelector('.gms-modal-card');
        if (card) card.addEventListener('click', (e) => e.stopPropagation());
        const confirmBtn = document.getElementById('urtFormalTransferConfirm');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => void this.submitUrtFormalTransfer());
        }
    },

    switchUrtSubPanel(sub) {
        this.urtSubPanel = sub;
        document.querySelectorAll('#urt-content .gms-integrated-head .gms-sub-tab').forEach((t) => {
            t.classList.toggle('active', t.getAttribute('data-urt-sub') === sub);
        });
        document.querySelectorAll('#urt-content .gms-sub-panel').forEach((p) => {
            const show =
                (sub === 'signals' && p.id === 'urt-sub-signals-wrap') ||
                (sub === 'trade-observe' && p.id === 'urt-sub-trade-observe-wrap') ||
                (sub === 'formal-trade' && p.id === 'urt-sub-formal-trade-wrap');
            p.classList.toggle('active', show);
        });
        if (sub === 'trade-observe') {
            void this.refreshUrtTradeObserveList();
        } else if (sub === 'formal-trade') {
            void this.refreshUrtFormalTradeList();
        }
    },

    _urtTradeObserveKey(market, code) {
        const m = (market || 'CN').toUpperCase();
        const c = this._gmsNormalizeCode(m, code);
        return c ? `${m}:${c}` : `${m}:`;
    },

    _isUrtInTradeObserve(stock, market, code) {
        const m = market || 'CN';
        const c = code || String(stock?.code || '').trim();
        const key = this._urtTradeObserveKey(m, c);
        return this.urtTradeObserveCodeSet.has(key) || this.urtFormalTradeCodeSet.has(key);
    },

    async loadUrtObservedCodeSets() {
        await Promise.all([
            this.loadUrtTradeObserveCodes(),
            this.loadUrtFormalTradeCodes(),
        ]);
    },

    async loadUrtTradeObserveCodes() {
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-trade-observe/codes`);
            if (!res.ok) return;
            const data = await res.json();
            this.urtTradeObserveCodeSet = new Set(Array.isArray(data) ? data : []);
        } catch (_) { /* ignore */ }
    },

    async loadUrtFormalTradeCodes() {
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-formal-trade/codes`);
            if (!res.ok) return;
            const data = await res.json();
            this.urtFormalTradeCodeSet = new Set(Array.isArray(data) ? data : []);
        } catch (_) { /* ignore */ }
    },

    _buildUrtTradeObserveSnapshot(stock) {
        if (!stock || typeof stock !== 'object') return {};
        const sd = stock.score_detail && typeof stock.score_detail === 'object'
            ? stock.score_detail
            : null;
        const st = sd && sd.structure && typeof sd.structure === 'object' ? sd.structure : {};
        const supportLevels = Array.isArray(stock.support_levels) && stock.support_levels.length
            ? stock.support_levels
            : (Array.isArray(st.support_levels) ? st.support_levels : []);
        const resistLevels = Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
            ? stock.resistance_levels
            : (Array.isArray(st.resistance_levels) ? st.resistance_levels : []);
        const nearestSupport = stock.nearest_support != null
            ? stock.nearest_support
            : (st.nearest_support != null
                ? st.nearest_support
                : (supportLevels.length ? supportLevels[0] : null));
        const nearestResist = stock.nearest_resistance != null
            ? stock.nearest_resistance
            : (st.nearest_resistance != null
                ? st.nearest_resistance
                : (resistLevels.length ? resistLevels[0] : null));
        return {
            code: stock.code,
            name: stock.name,
            signal_date: stock.signal_date,
            close: stock.close,
            open: stock.open,
            ma20: stock.ma20,
            ma5: stock.ma5,
            ma10: stock.ma10,
            ma20_stack: stock.ma20_stack,
            above_ma20: stock.above_ma20,
            ma_bull_ok: stock.ma_bull_ok,
            ma_bull_periods: stock.ma_bull_periods,
            yang_count_4: stock.yang_count_4,
            yang_count_5: stock.yang_count_5,
            yang_count_10: stock.yang_count_10,
            yang_count_15: stock.yang_count_15,
            yang_count_20: stock.yang_count_20,
            yang_medium_ok: stock.yang_medium_ok,
            yang_medium_detail: stock.yang_medium_detail,
            rule_a_ok: stock.rule_a_ok,
            rule_b_ok: stock.rule_b_ok,
            volume_multiple: stock.volume_multiple,
            volume_ratio: stock.volume_ratio,
            turnover_rate: stock.turnover_rate,
            score: stock.score,
            buy_signal: stock.buy_signal,
            filter_ok: stock.filter_ok,
            filter_reason: stock.filter_reason,
            score_ok: stock.score_ok,
            buy_logic: stock.buy_logic || null,
            score_detail: sd,
            support_levels: supportLevels,
            resistance_levels: resistLevels,
            nearest_support: nearestSupport,
            nearest_resistance: nearestResist,
            kde_ok: stock.kde_ok != null ? stock.kde_ok : st.kde_ok,
            kde_reason: stock.kde_reason || st.kde_reason || null,
            kde_lookback_used: stock.kde_lookback_used != null
                ? stock.kde_lookback_used
                : st.kde_lookback_used,
            price_adjust: stock.price_adjust || null,
        };
    },

    _resolveUrtSignalDate(stock) {
        if (!stock || typeof stock !== 'object') return this.lastUrtSearchDate || null;
        if (stock.signal_date) return String(stock.signal_date).slice(0, 10);
        return this.lastUrtSearchDate || null;
    },

    async refreshUrtTradeObserveList() {
        const errEl = document.getElementById('urtTradeObserveError');
        const loadingEl = document.getElementById('urtTradeObserveLoading');
        const tbody = document.getElementById('urtTradeObserveTableBody');
        const countEl = document.getElementById('urtTradeObserveCount');
        const user = (window.CommonUtils && CommonUtils.auth)
            ? await CommonUtils.auth.ensureLogin({
                redirect: true,
                message: '请先登录后查看交易观察列表',
            })
            : null;
        if (!user) return;
        if (errEl) errEl.style.display = 'none';
        if (loadingEl) loadingEl.style.display = '';
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-trade-observe/list?page=1&page_size=500`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加载失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            const items = data.items || [];
            this.urtTradeObserveCodeSet = new Set(
                items.map((it) => this._urtTradeObserveKey(it.market, it.code))
            );
            this.renderUrtTradeObserveTable(items);
            if (countEl) {
                const total = data.total != null ? data.total : items.length;
                countEl.textContent = `共 ${total} 只观察股`;
            }
        } catch (e) {
            if (errEl) {
                errEl.style.display = '';
                errEl.textContent = e.message || '加载交易观察列表失败';
            }
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="12" class="empty-state">加载失败</td></tr>';
            }
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    },

    renderUrtTradeObserveTable(items) {
        const tbody = document.getElementById('urtTradeObserveTableBody');
        if (!tbody) return;
        this.urtTradeObserveItems = Array.isArray(items) ? items : [];
        if (!this.urtTradeObserveItems.length) {
            tbody.innerHTML = '<tr><td colspan="12" class="empty-state">暂无交易观察股票，请在「策略信号」中点击「观察」加入</td></tr>';
            return;
        }
        const esc = (s) => String(s ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
        const fmtPrice = (v) => (v != null && Number.isFinite(Number(v))) ? Number(v).toFixed(2) : '--';
        const fmtDt = (iso) => {
            if (!iso) return '--';
            const s = String(iso);
            return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10);
        };
        const levelTitle = (levels, nearest, qfqTag) => {
            const arr = Array.isArray(levels) ? levels : [];
            if (arr.length) {
                return `${qfqTag}${arr.map((x) => Number(x).toFixed(2)).join('、')}`;
            }
            return qfqTag.trim() || (nearest != null ? String(nearest) : '');
        };
        tbody.innerHTML = this.urtTradeObserveItems.map((it, index) => {
            const snap = it.snapshot || {};
            const href = `stock.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            const traceHref = `stock_urt_trace.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            const qfqTag = snap.price_adjust === 'qfq' ? '前复权 ' : '';
            const nearSup = snap.nearest_support;
            const nearRes = snap.nearest_resistance;
            const supportTitle = levelTitle(snap.support_levels, nearSup, qfqTag);
            const resistTitle = levelTitle(snap.resistance_levels, nearRes, qfqTag);
            const buyLabel = snap.buy_signal === true ? '是' : (snap.buy_signal === false ? '否' : '--');
            const buyClass = snap.buy_signal === true ? 'strength-high' : (snap.buy_signal === false ? 'strength-low' : '');
            let detailHtml = '<div class="gms-score-detail-inner">信号快照明细未加载</div>';
            if (window.UrtScoreDetail && typeof window.UrtScoreDetail.buildHtml === 'function') {
                detailHtml = window.UrtScoreDetail.buildHtml(snap);
            }
            return `
                <tr class="urt-trade-observe-row" data-observe-id="${it.id}">
                    <td class="gms-col-code"><a class="stock-code" href="${href}" target="_blank" rel="noopener noreferrer">${esc(it.code)}</a></td>
                    <td class="gms-col-name"><span class="stock-name" title="${esc(it.name)}">${esc(it.name || '--')}</span></td>
                    <td class="gms-col-narrow">${esc(it.signal_date || snap.signal_date || '--')}</td>
                    <td class="gms-col-price">${fmtPrice(snap.close)}</td>
                    <td class="gms-col-price">${fmtPrice(snap.ma20)}</td>
                    <td class="gms-col-narrow">${snap.yang_count_4 != null ? snap.yang_count_4 : '--'}/${snap.yang_count_5 != null ? snap.yang_count_5 : '--'}</td>
                    <td class="gms-col-price support" title="${esc(supportTitle)}">${fmtPrice(nearSup)}</td>
                    <td class="gms-col-price resistance" title="${esc(resistTitle)}">${fmtPrice(nearRes)}</td>
                    <td class="gms-col-narrow"><span class="${buyClass}">${buyLabel}</span></td>
                    <td class="gms-col-narrow">${snap.score != null ? Number(snap.score).toFixed(1) : '--'}</td>
                    <td class="gms-col-narrow">${fmtDt(it.updated_at || it.created_at)}</td>
                    <td class="gms-col-actions gms-col-actions--wide">
                        <div class="action-links">
                            <a href="${traceHref}" class="gms-op-btn" target="_blank" rel="noopener noreferrer">历史</a>
                            <button type="button" class="gms-op-btn urt-observe-detail-toggle" data-row="${index}" title="展开/收起信号快照明细">明细</button>
                            <button type="button" class="gms-op-btn gms-op-btn--primary urt-trade-observe-transfer" data-id="${it.id}" data-code="${esc(it.code)}" data-name="${esc(it.name || '')}" title="转入正式交易">转正式交易</button>
                            <button type="button" class="gms-op-btn urt-trade-observe-remove" data-id="${it.id}" title="移出交易观察">移除</button>
                        </div>
                    </td>
                </tr>
                <tr class="gms-score-detail-row urt-observe-detail-row" data-detail-for="${index}" style="display:none;">
                    <td colspan="12" class="gms-score-detail-cell">${detailHtml}</td>
                </tr>
            `;
        }).join('');
    },

    async addUrtTradeObserveFromRow(rowIndex, btnEl) {
        const stocks = this.lastResults.urt;
        const stock = Array.isArray(stocks) ? stocks[rowIndex] : null;
        if (!stock) {
            if (window.CommonUtils) CommonUtils.showToast('未找到该行信号数据，请刷新筛选后重试', 'warning');
            return;
        }
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            if (window.CommonUtils) CommonUtils.showToast('请先登录后再加入交易观察', 'warning');
            window.location.href = 'login.html';
            return;
        }
        const code = String(stock.code || '').trim();
        const market = 'CN';
        const key = this._urtTradeObserveKey(market, code);
        if (this._isUrtInTradeObserve(stock, market, code)) {
            if (window.CommonUtils) {
                const inFormal = this.urtFormalTradeCodeSet.has(key);
                CommonUtils.showToast(inFormal ? '该股票已在正式交易中' : '已在交易观察列表中', 'info');
            }
            if (btnEl) {
                btnEl.textContent = '已观察';
                btnEl.classList.add('is-added');
                btnEl.disabled = true;
            }
            this.urtTradeObserveCodeSet.add(key);
            return;
        }
        const signalDate = this._resolveUrtSignalDate(stock);
        if (!signalDate) {
            if (window.CommonUtils) CommonUtils.showToast('无法确定信号交易日，请先刷新 URT 筛选', 'warning');
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) {
                btnEl.disabled = true;
                btnEl.textContent = '加入中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-trade-observe/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code,
                    market,
                    name: stock.name || code,
                    signal_date: signalDate,
                    snapshot: this._buildUrtTradeObserveSnapshot(stock),
                    config_id: this.urtConfigId || null,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this.urtTradeObserveCodeSet.add(key);
            if (window.CommonUtils) CommonUtils.showToast(`已加入交易观察：${stock.name || code}`, 'success');
            if (btnEl) {
                btnEl.textContent = '已观察';
                btnEl.classList.add('is-added');
                btnEl.disabled = true;
            }
            if (this.urtSubPanel === 'trade-observe') {
                void this.refreshUrtTradeObserveList();
            }
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '加入交易观察失败', 'error');
            await this.loadUrtObservedCodeSets();
            const stillIn = this._isUrtInTradeObserve(stock, market, code);
            if (btnEl) {
                if (stillIn) {
                    btnEl.textContent = '已观察';
                    btnEl.classList.add('is-added');
                    btnEl.disabled = true;
                } else {
                    btnEl.textContent = '观察';
                    btnEl.classList.remove('is-added');
                    btnEl.disabled = false;
                }
            }
        }
    },

    async removeUrtTradeObserve(itemId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) btnEl.disabled = true;
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-trade-observe/${itemId}`, {
                method: 'DELETE',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `移除失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (window.CommonUtils) CommonUtils.showToast('已移出交易观察', 'success');
            await this.loadUrtObservedCodeSets();
            void this.refreshUrtTradeObserveList();
            this._refreshUrtTradeObserveButtonsInSignalTable();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '移除失败', 'error');
            if (btnEl) btnEl.disabled = false;
        }
    },

    _refreshUrtTradeObserveButtonsInSignalTable() {
        const tbody = document.getElementById('resultsTableBody-urt');
        if (!tbody) return;
        tbody.querySelectorAll('.urt-trade-observe-add').forEach((btn) => {
            const rowIndex = parseInt(btn.getAttribute('data-row'), 10);
            const stocks = this.lastResults.urt;
            const stock = Array.isArray(stocks) ? stocks[rowIndex] : null;
            if (!stock) return;
            const code = String(stock.code || '').trim();
            const key = this._urtTradeObserveKey('CN', code);
            const added = this._isUrtInTradeObserve(stock, 'CN', code);
            btn.textContent = added ? '已观察' : '观察';
            btn.classList.toggle('is-added', added);
            btn.disabled = added;
            if (added) this.urtTradeObserveCodeSet.add(key);
        });
    },

    /**
     * URT 策略信号列表：按前复权批量重算 KDE 支撑/阻力（不改得分与买卖点）。
     */
    async recomputeUrtQfqLevels() {
        if (typeof CommonUtils !== 'undefined' && typeof CommonUtils.checkLoginAndHandleExpiry === 'function') {
            if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        }
        const stocks = this.lastResults.urt;
        if (!Array.isArray(stocks) || !stocks.length) {
            if (window.CommonUtils) {
                CommonUtils.showToast('请先「刷新筛选」得到股票列表，再按前复权计算支撑/阻力', 'warning');
            }
            return;
        }

        const isAShare = (code) => {
            const c = String(code || '').trim().replace(/^(SH|SZ)/i, '');
            return /^\d{6}$/.test(c);
        };
        const codes = [];
        const seen = new Set();
        stocks.forEach((s) => {
            const c = String(s.code || '').trim().replace(/^(SH|SZ)/i, '');
            if (!isAShare(c) || seen.has(c)) return;
            seen.add(c);
            codes.push(c);
        });
        if (!codes.length) {
            if (window.CommonUtils) {
                CommonUtils.showToast('当前列表无 A 股代码（前复权暂不支持港股）', 'warning');
            }
            return;
        }

        const btn = document.getElementById('urtQfqLevelsBtn');
        const loading = document.getElementById('loadingIndicator-urt');
        const prevBtnText = btn ? btn.textContent : '';
        const CHUNK = 8;
        if (btn) {
            btn.disabled = true;
            btn.textContent = '前复权重算中…';
        }
        if (loading) {
            loading.style.display = 'flex';
            const span = loading.querySelector('span');
            if (span) span.textContent = '前复权支撑/阻力重算中…';
        }

        const byCode = new Map();
        let okCount = 0;
        let failCount = 0;
        try {
            const fetchFn = this.getAuthFetchFn();
            for (let i = 0; i < codes.length; i += CHUNK) {
                const chunk = codes.slice(i, i + CHUNK);
                if (loading) {
                    const span = loading.querySelector('span');
                    if (span) {
                        span.textContent = `前复权支撑/阻力 ${Math.min(i + chunk.length, codes.length)}/${codes.length}…`;
                    }
                }
                if (btn) {
                    btn.textContent = `前复权 ${Math.min(i + chunk.length, codes.length)}/${codes.length}`;
                }
                const res = await fetchFn(`${this.API_BASE_URL}/api/analysis/levels/batch`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        codes: chunk,
                        adjust: 'qfq',
                        max_levels: 8,
                        refresh_factor: false,
                        factor_source: 'auto',
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    throw new Error(data.message || data.detail || `批量计算失败 HTTP ${res.status}`);
                }
                (data.items || []).forEach((it) => {
                    const c = String(it.code || '').trim();
                    if (!c) return;
                    byCode.set(c, it);
                    if (it.success) okCount += 1;
                    else failCount += 1;
                });
            }

            stocks.forEach((stock) => {
                const c = String(stock.code || '').trim().replace(/^(SH|SZ)/i, '');
                const it = byCode.get(c);
                if (!it || !it.success) return;
                stock.nearest_support = it.nearest_support;
                stock.nearest_resistance = it.nearest_resistance;
                stock.support_levels = Array.isArray(it.support_levels) ? it.support_levels : [];
                stock.resistance_levels = Array.isArray(it.resistance_levels) ? it.resistance_levels : [];
                stock.price_adjust = it.price_adjust || 'qfq';
                if (stock.score_detail && typeof stock.score_detail === 'object') {
                    const st = stock.score_detail.structure && typeof stock.score_detail.structure === 'object'
                        ? stock.score_detail.structure
                        : (stock.score_detail.structure = {});
                    st.nearest_support = stock.nearest_support;
                    st.nearest_resistance = stock.nearest_resistance;
                    st.support_levels = stock.support_levels;
                    st.resistance_levels = stock.resistance_levels;
                }
            });

            this.renderResults(stocks, this.lastUrtSearchDate || null, 'urt');
            this._refreshUrtTradeObserveButtonsInSignalTable();

            const searchDate = document.getElementById('searchDate-urt');
            if (searchDate) {
                const base = this.lastUrtSearchDate
                    ? `筛选时间: ${this.lastUrtSearchDate}`
                    : (searchDate.textContent || '').replace(/\s*·\s*支撑阻力前复权.*$/, '');
                searchDate.textContent = `${base} · 支撑阻力前复权（成功 ${okCount}${failCount ? `，失败 ${failCount}` : ''}）`;
            }
            if (window.CommonUtils) {
                CommonUtils.showToast(
                    `前复权支撑/阻力已更新：成功 ${okCount}${failCount ? `，失败 ${failCount}` : ''}（未改得分）`,
                    failCount ? 'warning' : 'success'
                );
            }
        } catch (e) {
            if (window.CommonUtils) {
                CommonUtils.showToast(e.message || '前复权支撑/阻力计算失败', 'error');
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = prevBtnText || '按前复权计算';
            }
            if (loading) {
                loading.style.display = 'none';
                const span = loading.querySelector('span');
                if (span) span.textContent = '正在筛选股票，请稍候...';
            }
        }
    },

    openUrtFormalTransferModal(observeId, code, name) {
        this._urtFormalTransferObserveId = observeId;
        const label = document.getElementById('urtFormalTransferStockLabel');
        if (label) label.textContent = `${code} ${name || ''}`.trim();
        const item = (this.urtTradeObserveItems || []).find((it) => it.id === observeId);
        const snap = item && item.snapshot ? item.snapshot : {};
        const priceEl = document.getElementById('urtFormalTransferEntryPrice');
        if (priceEl && snap.close != null) priceEl.value = Number(snap.close).toFixed(2);
        else if (priceEl) priceEl.value = '';
        const lotsEl = document.getElementById('urtFormalTransferLots');
        if (lotsEl && !lotsEl.value) lotsEl.value = '1';
        this._showGmsModal(document.getElementById('urtFormalTransferModal'));
    },

    async submitUrtFormalTransfer() {
        const observeId = this._urtFormalTransferObserveId;
        if (!observeId) return;
        const priceEl = document.getElementById('urtFormalTransferEntryPrice');
        const lotsEl = document.getElementById('urtFormalTransferLots');
        const entryPrice = priceEl ? parseFloat(priceEl.value) : NaN;
        const lots = lotsEl ? parseInt(lotsEl.value, 10) : NaN;
        if (!entryPrice || entryPrice <= 0 || !lots || lots < 1) {
            if (window.CommonUtils) CommonUtils.showToast('请填写有效的入场价与仓位', 'warning');
            return;
        }
        const confirmBtn = document.getElementById('urtFormalTransferConfirm');
        const fetchFn = this.getAuthFetchFn();
        try {
            if (confirmBtn) {
                confirmBtn.disabled = true;
                confirmBtn.textContent = '提交中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-formal-trade/from-observe/${observeId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ entry_price: entryPrice, position_lots: lots }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `转入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this._hideGmsModal(document.getElementById('urtFormalTransferModal'));
            this._urtFormalTransferObserveId = null;
            if (window.CommonUtils) CommonUtils.showToast('已转入正式交易', 'success');
            await this.loadUrtObservedCodeSets();
            void this.refreshUrtTradeObserveList();
            this._refreshUrtTradeObserveButtonsInSignalTable();
            if (this.urtSubPanel === 'formal-trade') {
                void this.refreshUrtFormalTradeList();
            }
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '转入正式交易失败', 'error');
        } finally {
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = '确认转入';
            }
        }
    },

    async refreshUrtFormalTradeList() {
        const errEl = document.getElementById('urtFormalTradeError');
        const loadingEl = document.getElementById('urtFormalTradeLoading');
        const tbody = document.getElementById('urtFormalTradeTableBody');
        const countEl = document.getElementById('urtFormalTradeCount');
        const statusEl = document.getElementById('urtFormalTradeStatusFilter');
        const user = (window.CommonUtils && CommonUtils.auth)
            ? await CommonUtils.auth.ensureLogin({
                redirect: true,
                message: '请先登录后查看正式交易列表',
            })
            : null;
        if (!user) return;
        if (errEl) errEl.style.display = 'none';
        if (loadingEl) loadingEl.style.display = '';
        const fetchFn = this.getAuthFetchFn();
        const status = statusEl ? statusEl.value : '';
        const qs = status ? `?page=1&page_size=500&status=${encodeURIComponent(status)}` : '?page=1&page_size=500';
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-formal-trade/list${qs}`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加载失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            const items = data.items || [];
            this.renderUrtFormalTradeTable(items);
            if (countEl) {
                const total = data.total != null ? data.total : items.length;
                countEl.textContent = `共 ${total} 条正式交易`;
            }
        } catch (e) {
            if (errEl) {
                errEl.style.display = '';
                errEl.textContent = e.message || '加载正式交易列表失败';
            }
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="11" class="empty-state">加载失败</td></tr>';
            }
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    },

    renderUrtFormalTradeTable(items) {
        const tbody = document.getElementById('urtFormalTradeTableBody');
        if (!tbody) return;
        if (!items || !items.length) {
            tbody.innerHTML = '<tr><td colspan="11" class="empty-state">暂无正式交易记录</td></tr>';
            return;
        }
        const esc = (s) => String(s ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
        const fmtPrice = (v) => (v != null && !isNaN(v)) ? Number(v).toFixed(2) : '--';
        const fmtDt = (iso) => {
            if (!iso) return '--';
            const s = String(iso);
            return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10);
        };
        tbody.innerHTML = items.map((it) => {
            const statusLabel = it.status === 'closed' ? '已平仓' : '持仓中';
            const href = `stock.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            return `
                <tr data-trade-id="${it.id}">
                    <td class="gms-col-code"><a class="stock-code" href="${href}" target="_blank" rel="noopener noreferrer">${esc(it.code)}</a></td>
                    <td class="gms-col-name"><span class="stock-name">${esc(it.name || '--')}</span></td>
                    <td class="gms-col-price">${fmtPrice(it.entry_price)}</td>
                    <td class="gms-col-narrow">${it.position_lots != null ? it.position_lots : '--'}</td>
                    <td class="gms-col-price">${fmtPrice(it.exit_price)}</td>
                    <td class="gms-col-narrow">${it.pnl_amount != null ? fmtPrice(it.pnl_amount) : '--'}</td>
                    <td class="gms-col-narrow">${it.pnl_percent != null ? Number(it.pnl_percent).toFixed(2) + '%' : '--'}</td>
                    <td class="gms-col-narrow">${statusLabel}</td>
                    <td class="gms-col-narrow">${esc(it.signal_date || '--')}</td>
                    <td class="gms-col-narrow">${fmtDt(it.entry_at)}</td>
                    <td class="gms-col-actions">
                        <button type="button" class="gms-op-btn urt-formal-trade-delete" data-id="${it.id}" title="删除">删除</button>
                    </td>
                </tr>
            `;
        }).join('');
    },

    async deleteUrtFormalTrade(tradeId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) btnEl.disabled = true;
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/urt-formal-trade/${tradeId}`, {
                method: 'DELETE',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `删除失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (window.CommonUtils) CommonUtils.showToast('已删除正式交易记录', 'success');
            await this.loadUrtObservedCodeSets();
            void this.refreshUrtFormalTradeList();
            this._refreshUrtTradeObserveButtonsInSignalTable();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '删除失败', 'error');
            if (btnEl) btnEl.disabled = false;
        }
    },

    _bindGmsBoardPickerEvents() {
        const overlay = document.getElementById('gmsBoardPickerModal');
        if (!overlay) return;
        const closeIds = ['gmsBoardPickerClose', 'gmsBoardPickerCancel'];
        closeIds.forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', () => this._hideGmsModal(overlay));
        });
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this._hideGmsModal(overlay);
        });
        const card = overlay.querySelector('.gms-modal-card');
        if (card) card.addEventListener('click', (e) => e.stopPropagation());

        const industryBtn = document.getElementById('gmsIndustryBoardPickBtn');
        if (industryBtn) {
            industryBtn.addEventListener('click', () => void this.openGmsBoardPickerModal('industry', 'gms'));
        }
        const conceptBtn = document.getElementById('gmsConceptBoardPickBtn');
        if (conceptBtn) {
            conceptBtn.addEventListener('click', () => void this.openGmsBoardPickerModal('concept', 'gms'));
        }
        const urtIndustryBtn = document.getElementById('urtIndustryBoardPickBtn');
        if (urtIndustryBtn) {
            urtIndustryBtn.addEventListener('click', () => void this.openGmsBoardPickerModal('industry', 'urt'));
        }
        const urtConceptBtn = document.getElementById('urtConceptBoardPickBtn');
        if (urtConceptBtn) {
            urtConceptBtn.addEventListener('click', () => void this.openGmsBoardPickerModal('concept', 'urt'));
        }
        const rpeIndustryBtn = document.getElementById('rpeIndustryBoardPickBtn');
        if (rpeIndustryBtn) {
            rpeIndustryBtn.addEventListener('click', () => void this.openGmsBoardPickerModal('industry', 'rpe'));
        }
        const rpeConceptBtn = document.getElementById('rpeConceptBoardPickBtn');
        if (rpeConceptBtn) {
            rpeConceptBtn.addEventListener('click', () => void this.openGmsBoardPickerModal('concept', 'rpe'));
        }

        const confirmBtn = document.getElementById('gmsBoardPickerConfirm');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmGmsBoardPicker());
        }
        const selectAllBtn = document.getElementById('gmsBoardPickerSelectAll');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => this._gmsBoardPickerSelectAllVisible());
        }
        const clearBtn = document.getElementById('gmsBoardPickerClear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this._gmsBoardPickerClearVisible());
        }
        const refreshBtn = document.getElementById('gmsBoardPickerRefresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => void this.refreshGmsBoardPickerOptions());
        }
        const searchEl = document.getElementById('gmsBoardPickerSearch');
        if (searchEl) {
            searchEl.addEventListener('input', () => this._renderGmsBoardPickerList());
        }
        const sourceFilterWrap = document.querySelector('#gmsBoardPickerModal .gms-board-picker-source-filters');
        if (sourceFilterWrap) {
            sourceFilterWrap.addEventListener('click', (e) => {
                const btn = e.target.closest('.gms-board-source-btn');
                if (!btn) return;
                const source = String(btn.getAttribute('data-board-source') || 'all').trim() || 'all';
                this._gmsBoardPickerSourceFilter = source;
                sourceFilterWrap.querySelectorAll('.gms-board-source-btn').forEach((el) => {
                    el.classList.toggle('active', el === btn);
                });
                this._renderGmsBoardPickerList();
            });
        }
        const listEl = document.getElementById('gmsBoardPickerList');
        if (listEl) {
            listEl.addEventListener('change', (e) => {
                const cb = e.target.closest('input[type="checkbox"]');
                if (!cb) return;
                const code = String(cb.value || '').trim();
                if (!code) return;
                if (cb.checked) this._gmsBoardPickerDraft.add(code);
                else this._gmsBoardPickerDraft.delete(code);
            });
        }
    },

    _bindGmsFormalModalEvents() {
        const bindClose = (overlayId, closeIds) => {
            const overlay = document.getElementById(overlayId);
            if (!overlay) return;
            closeIds.forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.addEventListener('click', () => this._hideGmsModal(overlay));
            });
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this._hideGmsModal(overlay);
            });
        };
        bindClose('gmsFormalTransferModal', ['gmsFormalTransferClose', 'gmsFormalTransferCancel']);
        bindClose('gmsFormalEditModal', ['gmsFormalEditClose', 'gmsFormalEditCancel']);
        const transferConfirm = document.getElementById('gmsFormalTransferConfirm');
        if (transferConfirm) {
            transferConfirm.addEventListener('click', () => void this.submitGmsFormalTransfer());
        }
        const editSave = document.getElementById('gmsFormalEditSave');
        if (editSave) {
            editSave.addEventListener('click', () => void this.submitGmsFormalEdit());
        }
        document.querySelectorAll('#gmsFormalTransferModal .gms-modal-card, #gmsFormalEditModal .gms-modal-card').forEach((card) => {
            card.addEventListener('click', (e) => e.stopPropagation());
        });
        const reopenCb = document.getElementById('gmsFormalEditReopen');
        const exitEl = document.getElementById('gmsFormalEditExitPrice');
        if (reopenCb && exitEl) {
            reopenCb.addEventListener('change', () => {
                exitEl.disabled = reopenCb.checked;
                if (reopenCb.checked) exitEl.value = '';
            });
        }
    },

    _parseAttrNum(raw) {
        const s = String(raw ?? '').trim();
        if (!s) return null;
        const n = Number(s);
        return Number.isFinite(n) ? n : null;
    },

    _showGmsModal(overlay) {
        if (!overlay) return;
        overlay.style.display = 'flex';
        overlay.setAttribute('aria-hidden', 'false');
    },

    _hideGmsModal(overlay) {
        if (!overlay) return;
        overlay.style.display = 'none';
        overlay.setAttribute('aria-hidden', 'true');
    },

    _fmtGmsPricePlanSource(source) {
        const map = {
            t_plus_1_open: 'T+1开盘价',
            signal_close: '信号日收盘',
            unavailable: '暂无',
        };
        return map[source] || source || '';
    },

    _renderGmsPricePlanHint(plan) {
        const el = document.getElementById('gmsFormalTransferPricePlanHint');
        if (!el) return;
        if (!plan || typeof plan !== 'object') {
            el.style.display = 'none';
            el.innerHTML = '';
            return;
        }
        const fmt = (v) => (v != null && !isNaN(v)) ? Number(v).toFixed(2) : '--';
        const params = plan.params || {};
        const tgt = params.target_pct != null ? (Number(params.target_pct) * 100).toFixed(0) : '5';
        const stop = params.stop_loss_pct != null ? (Number(params.stop_loss_pct) * 100).toFixed(0) : '5';
        const ob = params.overbought_ratio != null ? (Number(params.overbought_ratio) * 100).toFixed(0) : '15';
        const src = this._fmtGmsPricePlanSource(plan.buy_price_source);
        el.innerHTML = `
            <div class="gms-price-plan-hint__title">系统价格参考（${src}）</div>
            <div class="gms-price-plan-hint__grid">
                <span>建议止损：<b>${fmt(plan.stop_loss_price)}</b></span>
                <span>建议止盈：<b>${fmt(plan.take_profit_price)}</b></span>
                <span>参考卖点：<b>${fmt(plan.reference_sell_price)}</b></span>
            </div>
            <div class="gms-price-plan-hint__meta">参数：止盈 +${tgt}% / 止损 -${stop}% / 乖离卖点 +${ob}%</div>
        `;
        el.style.display = '';
    },

    openGmsFormalTransferModal(observeId, code, name) {
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            if (window.CommonUtils) CommonUtils.showToast('请先登录', 'warning');
            return;
        }
        this._gmsFormalTransferObserveId = observeId;
        const label = document.getElementById('gmsFormalTransferStockLabel');
        if (label) label.textContent = `${code} ${name || ''}`.trim();
        const item = (this.gmsTradeObserveItems || []).find((it) => it.id === observeId);
        const plan = item?.price_plan || item?.snapshot?.price_plan || null;
        const snap = item?.snapshot || {};
        const defaultPrice = plan?.buy_price_suggested ?? snap.current_price;
        const priceEl = document.getElementById('gmsFormalTransferEntryPrice');
        if (priceEl) {
            const p = parseFloat(defaultPrice);
            priceEl.value = (!isNaN(p) && p > 0) ? p.toFixed(2) : '';
        }
        this._renderGmsPricePlanHint(plan);
        const lotsEl = document.getElementById('gmsFormalTransferLots');
        if (lotsEl) lotsEl.value = '1';
        const notesEl = document.getElementById('gmsFormalTransferNotes');
        if (notesEl) notesEl.value = '';
        this._showGmsModal(document.getElementById('gmsFormalTransferModal'));
    },

    async submitGmsFormalTransfer() {
        const observeId = this._gmsFormalTransferObserveId;
        if (!observeId) return;
        const priceEl = document.getElementById('gmsFormalTransferEntryPrice');
        const lotsEl = document.getElementById('gmsFormalTransferLots');
        const notesEl = document.getElementById('gmsFormalTransferNotes');
        const entryPrice = parseFloat(priceEl?.value);
        const positionLots = parseInt(lotsEl?.value, 10);
        if (!entryPrice || entryPrice <= 0) {
            if (window.CommonUtils) CommonUtils.showToast('请输入有效的入场价格', 'warning');
            return;
        }
        if (!positionLots || positionLots < 1) {
            if (window.CommonUtils) CommonUtils.showToast('仓位至少为 1 手', 'warning');
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        const confirmBtn = document.getElementById('gmsFormalTransferConfirm');
        try {
            if (confirmBtn) {
                confirmBtn.disabled = true;
                confirmBtn.textContent = '提交中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-formal-trade/from-observe/${observeId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    entry_price: entryPrice,
                    position_lots: positionLots,
                    notes: notesEl?.value?.trim() || null,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `转入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this._hideGmsModal(document.getElementById('gmsFormalTransferModal'));
            this._gmsFormalTransferObserveId = null;
            if (window.CommonUtils) CommonUtils.showToast('已转入正式交易', 'success');
            await this.loadGmsObservedCodeSets();
            void this.refreshGmsTradeObserveList();
            this._refreshGmsTradeObserveButtonsInSignalTable();
            if (this.gmsSubPanel === 'formal-trade') {
                void this.refreshGmsFormalTradeList();
            } else {
                this.switchGmsSubPanel('formal-trade');
            }
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '转入正式交易失败', 'error');
        } finally {
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = '确认转入';
            }
        }
    },

    async refreshGmsFormalTradeList() {
        const errEl = document.getElementById('gmsFormalTradeError');
        const loadingEl = document.getElementById('gmsFormalTradeLoading');
        const tbody = document.getElementById('gmsFormalTradeTableBody');
        const countEl = document.getElementById('gmsFormalTradeCount');
        const user = (window.CommonUtils && CommonUtils.auth)
            ? await CommonUtils.auth.ensureLogin({
                redirect: true,
                message: '请先登录后查看正式交易列表',
            })
            : null;
        if (!user) return;
        if (errEl) errEl.style.display = 'none';
        if (loadingEl) loadingEl.style.display = '';
        const statusFilter = document.getElementById('gmsFormalTradeStatusFilter');
        const status = statusFilter ? statusFilter.value : '';
        const qs = status ? `&status=${encodeURIComponent(status)}` : '';
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-formal-trade/list?page=1&page_size=500${qs}`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加载失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            const items = data.items || [];
            this.renderGmsFormalTradeTable(items);
            if (countEl) countEl.textContent = `共 ${data.total != null ? data.total : items.length} 笔正式交易`;
        } catch (e) {
            if (errEl) {
                errEl.style.display = '';
                errEl.textContent = e.message || '加载正式交易列表失败';
            }
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="11" class="empty-state">加载失败</td></tr>';
            }
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    },

    renderGmsFormalTradeTable(items) {
        const tbody = document.getElementById('gmsFormalTradeTableBody');
        if (!tbody) return;
        if (!items || items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="12" class="empty-state">暂无正式交易记录，请在「交易观察」中点击「转正式交易」</td></tr>';
            return;
        }
        const esc = (s) => String(s ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
        const fmtPrice = (v) => (v != null && !isNaN(v)) ? Number(v).toFixed(2) : '--';
        const fmtDt = (iso) => {
            if (!iso) return '--';
            const s = String(iso);
            return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10);
        };
        const fmtPnl = (v, suffix = '%') => {
            if (v == null || isNaN(v)) return '--';
            const n = Number(v);
            const cls = n > 0 ? 'gms-pnl-up' : (n < 0 ? 'gms-pnl-down' : '');
            const sign = n > 0 ? '+' : '';
            return `<span class="${cls}">${sign}${n.toFixed(2)}${suffix}</span>`;
        };
        const fmtStatus = (st) => (st === 'closed' ? '已平仓' : '持仓中');
        tbody.innerHTML = items.map((it) => {
            const href = `stock.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            const notesAttr = esc(it.notes || '');
            return `
                <tr data-trade-id="${it.id}">
                    <td class="gms-col-code"><a class="stock-code" href="${href}" target="_blank" rel="noopener noreferrer">${esc(it.code)}</a></td>
                    <td class="gms-col-name"><span class="stock-name" title="${esc(it.name)}">${esc(it.name || '--')}</span></td>
                    <td class="gms-col-price">${fmtPrice(it.entry_price)}</td>
                    <td class="gms-col-narrow">${esc(it.position_lots)}</td>
                    <td class="gms-col-price">${fmtPrice(it.exit_price)}</td>
                    <td class="gms-col-narrow">${fmtPnl(it.pnl_amount, '')}</td>
                    <td class="gms-col-narrow">${fmtPnl(it.pnl_percent)}</td>
                    <td class="gms-col-narrow">${fmtStatus(it.status)}</td>
                    <td class="gms-col-narrow">${esc(it.signal_date || '--')}</td>
                    <td class="gms-col-narrow">${fmtDt(it.entry_at)}</td>
                    <td class="gms-col-narrow">${fmtDt(it.exit_at)}</td>
                    <td class="gms-col-actions gms-col-actions--wide">
                        <div class="action-links">
                            <button type="button" class="gms-op-btn gms-op-btn--primary gms-formal-trade-edit"
                                data-id="${it.id}"
                                data-code="${esc(it.code)}"
                                data-name="${esc(it.name || '')}"
                                data-entry-price="${it.entry_price != null ? esc(it.entry_price) : ''}"
                                data-position-lots="${esc(it.position_lots)}"
                                data-exit-price="${it.exit_price != null ? esc(it.exit_price) : ''}"
                                data-status="${esc(it.status)}"
                                data-notes="${notesAttr}"
                                title="编辑或平仓">编辑</button>
                            <button type="button" class="gms-op-btn gms-formal-trade-delete" data-id="${it.id}" title="删除记录">删除</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    },

    openGmsFormalEditModal(tradeId, btnEl) {
        if (!btnEl) return;
        const status = btnEl.getAttribute('data-status') || 'open';
        const item = {
            id: tradeId,
            code: btnEl.getAttribute('data-code') || '',
            name: btnEl.getAttribute('data-name') || '',
            entry_price: this._parseAttrNum(btnEl.getAttribute('data-entry-price')),
            position_lots: this._parseAttrNum(btnEl.getAttribute('data-position-lots')),
            exit_price: this._parseAttrNum(btnEl.getAttribute('data-exit-price')),
            status,
            notes: btnEl.getAttribute('data-notes') || '',
        };
        this._gmsFormalEditTradeId = tradeId;
        this._gmsFormalEditWasClosed = status === 'closed';
        const label = document.getElementById('gmsFormalEditStockLabel');
        if (label) label.textContent = `${item.code} ${item.name || ''}`.trim();
        const title = document.getElementById('gmsFormalEditTitle');
        if (title) title.textContent = '编辑正式交易';
        const entryEl = document.getElementById('gmsFormalEditEntryPrice');
        if (entryEl) entryEl.value = item.entry_price != null ? item.entry_price.toFixed(2) : '';
        const lotsEl = document.getElementById('gmsFormalEditLots');
        if (lotsEl) lotsEl.value = String(item.position_lots != null ? item.position_lots : 1);
        const exitEl = document.getElementById('gmsFormalEditExitPrice');
        const reopenCb = document.getElementById('gmsFormalEditReopen');
        const reopenWrap = document.getElementById('gmsFormalEditReopenWrap');
        if (exitEl) {
            exitEl.value = item.exit_price != null ? item.exit_price.toFixed(2) : '';
            exitEl.disabled = false;
        }
        if (reopenCb) reopenCb.checked = false;
        if (reopenWrap) reopenWrap.style.display = this._gmsFormalEditWasClosed ? '' : 'none';
        const notesEl = document.getElementById('gmsFormalEditNotes');
        if (notesEl) notesEl.value = item.notes || '';
        this._showGmsModal(document.getElementById('gmsFormalEditModal'));
        if (entryEl) entryEl.focus();
    },

    async submitGmsFormalEdit() {
        const tradeId = this._gmsFormalEditTradeId;
        if (!tradeId) return;
        const entryEl = document.getElementById('gmsFormalEditEntryPrice');
        const lotsEl = document.getElementById('gmsFormalEditLots');
        const exitEl = document.getElementById('gmsFormalEditExitPrice');
        const notesEl = document.getElementById('gmsFormalEditNotes');
        const entryPrice = parseFloat(entryEl?.value);
        const positionLots = parseInt(lotsEl?.value, 10);
        const exitRaw = (exitEl?.value || '').trim();
        const exitPrice = exitRaw ? parseFloat(exitRaw) : null;
        const reopenCb = document.getElementById('gmsFormalEditReopen');
        const reopen = !!(reopenCb && reopenCb.checked);
        if (!entryPrice || entryPrice <= 0) {
            if (window.CommonUtils) CommonUtils.showToast('请输入有效的入场价格', 'warning');
            return;
        }
        if (!positionLots || positionLots < 1) {
            if (window.CommonUtils) CommonUtils.showToast('仓位至少为 1 手', 'warning');
            return;
        }
        if (!reopen && exitPrice != null && (isNaN(exitPrice) || exitPrice <= 0)) {
            if (window.CommonUtils) CommonUtils.showToast('出场价格无效', 'warning');
            return;
        }
        const body = {
            entry_price: entryPrice,
            position_lots: positionLots,
            notes: notesEl?.value?.trim() || null,
        };
        if (reopen) {
            body.reopen = true;
        } else if (exitPrice != null) {
            body.exit_price = exitPrice;
        } else if (this._gmsFormalEditWasClosed) {
            if (window.CommonUtils) CommonUtils.showToast('已平仓记录请填写出场价，或勾选恢复为持仓中', 'warning');
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        const saveBtn = document.getElementById('gmsFormalEditSave');
        try {
            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-formal-trade/${tradeId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `保存失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this._hideGmsModal(document.getElementById('gmsFormalEditModal'));
            this._gmsFormalEditTradeId = null;
            this._gmsFormalEditWasClosed = false;
            if (window.CommonUtils) {
                const msg = reopen ? '已恢复为持仓中' : (exitPrice != null ? '已保存并记为平仓' : '已保存');
                CommonUtils.showToast(msg, 'success');
            }
            void this.refreshGmsFormalTradeList();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '保存失败', 'error');
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = '保存';
            }
        }
    },

    async deleteGmsFormalTrade(tradeId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) btnEl.disabled = true;
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-formal-trade/${tradeId}`, {
                method: 'DELETE',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `删除失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (window.CommonUtils) CommonUtils.showToast('已删除正式交易记录', 'success');
            await this.loadGmsObservedCodeSets();
            void this.refreshGmsFormalTradeList();
            this._refreshGmsTradeObserveButtonsInSignalTable();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '删除失败', 'error');
            if (btnEl) btnEl.disabled = false;
        }
    },

    switchGmsSubPanel(sub) {
        this.gmsSubPanel = sub;
        document.querySelectorAll('.gms-integrated-head .gms-sub-tab').forEach((t) => {
            t.classList.toggle('active', t.getAttribute('data-gms-sub') === sub);
        });
        document.querySelectorAll('.gms-sub-panel').forEach((p) => {
            const show =
                (sub === 'signals' && p.id === 'gms-sub-signals-wrap') ||
                (sub === 'trade-observe' && p.id === 'gms-sub-trade-observe-wrap') ||
                (sub === 'formal-trade' && p.id === 'gms-sub-formal-trade-wrap');
            p.classList.toggle('active', show);
        });
        if (sub === 'trade-observe') {
            this.refreshGmsTradeObserveList();
        } else if (sub === 'formal-trade') {
            this.refreshGmsFormalTradeList();
        }
    },

    _gmsMarketFromStock(stock) {
        const m = (stock && stock.market ? String(stock.market) : '').trim().toUpperCase();
        if (m === 'HK' || m === 'CN') return m;
        const code = String(stock?.symbol || stock?.code || '').trim();
        if (code.length === 5 && /^\d+$/.test(code)) return 'HK';
        return 'CN';
    },

    _gmsNormalizeCode(market, code) {
        const m = (market || 'CN').toUpperCase();
        let c = String(code || '').trim().toUpperCase().replace(/^SZ|^SH/, '');
        if (!c) return '';
        if (m === 'HK' && /^\d+$/.test(c)) return c.padStart(5, '0');
        if (/^\d+$/.test(c) && c.length <= 6) return c.padStart(6, '0');
        return c;
    },

    _gmsTradeObserveKey(market, code) {
        const m = (market || 'CN').toUpperCase();
        const c = this._gmsNormalizeCode(m, code);
        return c ? `${m}:${c}` : `${m}:`;
    },

    _isGmsInTradeObserve(stock, market, code) {
        if (stock && stock.in_trade_observe === true) return true;
        const m = market || this._gmsMarketFromStock(stock);
        const c = code || String(stock?.symbol || stock?.code || '').trim();
        const key = this._gmsTradeObserveKey(m, c);
        return this.gmsTradeObserveCodeSet.has(key) || this.gmsFormalTradeCodeSet.has(key);
    },

    async loadGmsObservedCodeSets() {
        await Promise.all([
            this.loadGmsTradeObserveCodes(),
            this.loadGmsFormalTradeCodes(),
        ]);
    },

    _resolveGmsSignalDate(stock) {
        if (!stock || typeof stock !== 'object') return this.lastGmsSearchDate || null;
        const direct = stock.signal_date || stock.indicator_date || stock.search_date;
        if (direct) return String(direct).slice(0, 10);
        const sd = stock.score_detail || stock.indicators?.score_detail || {};
        if (sd.d20_date) return String(sd.d20_date).slice(0, 10);
        if (sd.date) return String(sd.date).slice(0, 10);
        return this.lastGmsSearchDate || null;
    },

    _gmsDisplayIndustry(raw) {
        if (raw == null || raw === '') return '--';
        const s = String(raw).trim();
        if (!s) return '--';
        const low = s.toLowerCase();
        if (low === 'nan' || low === 'none' || low === 'null' || low === '<na>' || low === 'nat') return '--';
        const parts = s.split(',').map((p) => p.trim()).filter(Boolean);
        const names = parts.filter((p) => !/^BK\d+$/i.test(p));
        if (!names.length) return '--';
        return names.join(',');
    },

    _gmsWatchThresholdFromForm() {
        const el = document.getElementById('gms-watch_threshold');
        if (!el || el.value === '') return 60;
        const n = Number(el.value);
        return Number.isFinite(n) ? n : 60;
    },

    _sortGmsTradeObserveItems(items) {
        const list = Array.isArray(items) ? items.slice() : [];
        list.sort((a, b) => {
            const fa = a.key_focus_flag ? 1 : 0;
            const fb = b.key_focus_flag ? 1 : 0;
            if (fb !== fa) return fb - fa;
            const ta = String(a.updated_at || a.created_at || '');
            const tb = String(b.updated_at || b.created_at || '');
            return tb.localeCompare(ta);
        });
        return list;
    },

    _gmsKeyFocusIconHtml(it, esc) {
        const on = !!it.key_focus_flag;
        const cls = on ? 'gms-key-focus-btn is-on' : 'gms-key-focus-btn';
        const title = on ? '取消重点关注' : '标记为重点关注';
        return `<button type="button" class="${cls}" data-id="${it.id}" title="${esc(title)}" aria-label="${esc(title)}"><span class="gms-key-focus-icon" aria-hidden="true">★</span></button>`;
    },

    _gmsLatestPriceCellHtml(it, esc, fmtPrice) {
        const hasPrice = it.latest_close_price != null && !isNaN(it.latest_close_price);
        if (hasPrice) {
            const title = it.latest_close_date ? `title="行情日 ${esc(it.latest_close_date)}"` : '';
            return `<td class="gms-col-price gms-latest-price-cell" ${title}>
                <div class="gms-latest-price-value">${fmtPrice(it.latest_close_price)}</div>
                <button type="button" class="gms-op-btn gms-latest-price-btn" data-id="${it.id}" title="重新查询最新价格">刷新</button>
            </td>`;
        }
        return `<td class="gms-col-price gms-latest-price-cell">
            <button type="button" class="gms-op-btn gms-latest-price-btn" data-id="${it.id}" title="查询最新价格">查看最新价格</button>
        </td>`;
    },

    async fetchGmsTradeObserveLatestPrice(itemId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        const cell = btnEl ? btnEl.closest('.gms-latest-price-cell') : null;
        try {
            if (btnEl) {
                btnEl.disabled = true;
                btnEl.textContent = '查询中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-trade-observe/${itemId}/latest-price`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `查询失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (data.latest_close_price == null || isNaN(data.latest_close_price)) {
                throw new Error('暂无最新价格数据');
            }
            const idx = (this.gmsTradeObserveItems || []).findIndex((it) => it.id === itemId);
            if (idx >= 0) {
                this.gmsTradeObserveItems[idx] = {
                    ...this.gmsTradeObserveItems[idx],
                    latest_close_price: data.latest_close_price,
                    latest_close_date: data.latest_close_date || null,
                };
            }
            this.renderGmsTradeObserveTable(this.gmsTradeObserveItems);
        } catch (e) {
            if (cell && btnEl) {
                btnEl.disabled = false;
                const row = (this.gmsTradeObserveItems || []).find((it) => it.id === itemId);
                const hasPrice = row && row.latest_close_price != null && !isNaN(row.latest_close_price);
                btnEl.textContent = hasPrice ? '刷新' : '查看最新价格';
            }
            if (window.CommonUtils) CommonUtils.showToast(e.message || '查询最新价格失败', 'error');
        }
    },

    async toggleGmsTradeObserveKeyFocus(itemId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        const row = (this.gmsTradeObserveItems || []).find((it) => it.id === itemId);
        const nextFlag = row ? !row.key_focus_flag : true;
        try {
            if (btnEl) btnEl.disabled = true;
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-trade-observe/${itemId}/key-focus`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key_focus_flag: nextFlag }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `操作失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            const idx = (this.gmsTradeObserveItems || []).findIndex((it) => it.id === itemId);
            if (idx >= 0) {
                this.gmsTradeObserveItems[idx] = data;
            }
            this.renderGmsTradeObserveTable(this.gmsTradeObserveItems);
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '更新重点关注失败', 'error');
        } finally {
            if (btnEl) btnEl.disabled = false;
        }
    },

    _buildGmsTradeObserveSnapshot(stock) {
        if (!stock || typeof stock !== 'object') return {};
        const sd = stock.score_detail || stock.indicators?.score_detail || {};
        const signalDate = this._resolveGmsSignalDate(stock);
        return {
            signal_date: signalDate,
            industry: this._gmsDisplayIndustry(stock.industry) === '--' ? null : this._gmsDisplayIndustry(stock.industry),
            signal_strength: stock.signal_strength,
            score_total: stock.score_total,
            watch_threshold: this._gmsWatchThresholdFromForm(),
            buy_type: stock.buy_type,
            left_buy_signal: stock.left_buy_signal,
            right_buy_signal: stock.right_buy_signal,
            sell_signal: stock.sell_signal,
            current_price: stock.current_price,
            change_percent: stock.change_percent,
            delta: stock.delta,
            d_ma20: stock.d_ma20,
            ratio_d20: stock.ratio_d20,
            ratio_d1: stock.ratio_d1,
            fz_ratio: stock.fz_ratio,
            rising_days: stock.rising_days,
            falling_days: stock.falling_days,
            score_detail: sd,
        };
    },

    async loadGmsFormalTradeCodes() {
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            this.gmsFormalTradeCodeSet = new Set();
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-formal-trade/codes`);
            if (!res.ok) {
                this.gmsFormalTradeCodeSet = new Set();
                return;
            }
            const codes = await res.json();
            const normalized = (Array.isArray(codes) ? codes : []).map((raw) => {
                const s = String(raw || '');
                const idx = s.indexOf(':');
                if (idx <= 0) return s;
                const m = s.slice(0, idx).toUpperCase();
                const c = s.slice(idx + 1);
                return this._gmsTradeObserveKey(m, c);
            });
            this.gmsFormalTradeCodeSet = new Set(normalized);
        } catch (_) {
            this.gmsFormalTradeCodeSet = new Set();
        }
    },

    async loadGmsTradeObserveCodes() {
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            this.gmsTradeObserveCodeSet = new Set();
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-trade-observe/codes`);
            if (!res.ok) {
                this.gmsTradeObserveCodeSet = new Set();
                return;
            }
            const codes = await res.json();
            const normalized = (Array.isArray(codes) ? codes : []).map((raw) => {
                const s = String(raw || '');
                const idx = s.indexOf(':');
                if (idx <= 0) return s;
                const m = s.slice(0, idx).toUpperCase();
                const c = s.slice(idx + 1);
                return this._gmsTradeObserveKey(m, c);
            });
            this.gmsTradeObserveCodeSet = new Set(normalized);
        } catch (_) {
            this.gmsTradeObserveCodeSet = new Set();
        }
    },

    async refreshGmsTradeObserveList() {
        const errEl = document.getElementById('gmsTradeObserveError');
        const loadingEl = document.getElementById('gmsTradeObserveLoading');
        const tbody = document.getElementById('gmsTradeObserveTableBody');
        const countEl = document.getElementById('gmsTradeObserveCount');
        const user = (window.CommonUtils && CommonUtils.auth)
            ? await CommonUtils.auth.ensureLogin({
                redirect: true,
                message: '请先登录后查看交易观察列表',
            })
            : null;
        if (!user) return;
        if (errEl) errEl.style.display = 'none';
        if (loadingEl) loadingEl.style.display = '';
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-trade-observe/list?page=1&page_size=500`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加载失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            const items = this._sortGmsTradeObserveItems(data.items || []);
            this.gmsTradeObserveCodeSet = new Set(
                items.map((it) => this._gmsTradeObserveKey(it.market, it.code))
            );
            this.renderGmsTradeObserveTable(items);
            const focusCount = items.filter((it) => it.key_focus_flag).length;
            if (countEl) {
                const total = data.total != null ? data.total : items.length;
                countEl.textContent = focusCount > 0
                    ? `共 ${total} 只观察股，重点关注 ${focusCount} 只`
                    : `共 ${total} 只观察股`;
            }
        } catch (e) {
            if (errEl) {
                errEl.style.display = '';
                errEl.textContent = e.message || '加载交易观察列表失败';
            }
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="14" class="empty-state">加载失败</td></tr>';
            }
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    },

    renderGmsTradeObserveTable(items) {
        const tbody = document.getElementById('gmsTradeObserveTableBody');
        if (!tbody) return;
        const sorted = this._sortGmsTradeObserveItems(items);
        this.gmsTradeObserveItems = sorted;
        if (!sorted || sorted.length === 0) {
            tbody.innerHTML = '<tr><td colspan="14" class="empty-state">暂无交易观察股票，请在「策略信号」中点击「交易观察」加入</td></tr>';
            return;
        }
        const esc = (s) => String(s ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
        const fmtStrength = (snap) => {
            if (!snap) return '--';
            let v = snap.signal_strength;
            if ((v == null || v === 0) && snap.score_total > 0) v = snap.score_total / 100;
            if (v == null) return '--';
            return (Number(v) * 100).toFixed(1) + '%';
        };
        const fmtPrice = (v) => (v != null && !isNaN(v)) ? Number(v).toFixed(2) : '--';
        const fmtDt = (iso) => {
            if (!iso) return '--';
            const s = String(iso);
            return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10);
        };
        tbody.innerHTML = sorted.map((it) => {
            const snap = it.snapshot || {};
            const plan = it.price_plan || snap.price_plan || {};
            const buyType = snap.buy_type || '—';
            const buyClass = snap.left_buy_signal ? 'gms-left' : (snap.right_buy_signal ? 'gms-right' : '');
            const buySrc = this._fmtGmsPricePlanSource(plan.buy_price_source);
            const buyTitle = buySrc ? `title="${esc(buySrc)}"` : '';
            const href = `stock.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            const traceHref = `stock_gms_trace.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            const rowFocusCls = it.key_focus_flag ? ' gms-trade-observe-row--focus' : '';
            const latestPriceCell = this._gmsLatestPriceCellHtml(it, esc, fmtPrice);
            return `
                <tr class="gms-trade-observe-row${rowFocusCls}" data-observe-id="${it.id}">
                    <td class="gms-col-code">
                        <div class="gms-code-with-focus">
                            ${this._gmsKeyFocusIconHtml(it, esc)}
                            <a class="stock-code" href="${href}" target="_blank" rel="noopener noreferrer">${esc(it.code)}</a>
                        </div>
                    </td>
                    <td class="gms-col-name"><span class="stock-name" title="${esc(it.name)}">${esc(it.name || '--')}</span></td>
                    <td class="gms-col-industry"><span class="stock-industry" title="${esc(this._gmsDisplayIndustry(it.industry || snap.industry))}">${esc(this._gmsDisplayIndustry(it.industry || snap.industry))}</span></td>
                    <td class="gms-col-narrow">${fmtStrength(snap)}</td>
                    <td class="gms-col-narrow"><span class="${buyClass}">${esc(buyType)}</span></td>
                    <td class="gms-col-price">${fmtPrice(snap.current_price)}</td>
                    ${latestPriceCell}
                    <td class="gms-col-price" ${buyTitle}>${fmtPrice(plan.buy_price_suggested)}</td>
                    <td class="gms-col-price">${fmtPrice(plan.stop_loss_price)}</td>
                    <td class="gms-col-price">${fmtPrice(plan.take_profit_price)}</td>
                    <td class="gms-col-price">${fmtPrice(plan.reference_sell_price)}</td>
                    <td class="gms-col-narrow">${esc(it.signal_date || '--')}</td>
                    <td class="gms-col-narrow">${fmtDt(it.updated_at || it.created_at)}</td>
                    <td class="gms-col-actions gms-col-actions--wide">
                        <div class="action-links">
                            <a href="${traceHref}" class="gms-op-btn" target="_blank" rel="noopener noreferrer">历史</a>
                            <button type="button" class="gms-op-btn gms-op-btn--primary gms-trade-observe-transfer" data-id="${it.id}" data-code="${esc(it.code)}" data-name="${esc(it.name || '')}" title="转入正式交易">转正式交易</button>
                            <button type="button" class="gms-op-btn gms-trade-observe-remove" data-id="${it.id}" title="移出交易观察">移除</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    },

    async addGmsTradeObserveFromRow(rowIndex, btnEl) {
        const stocks = this.lastResults.gms;
        const stock = Array.isArray(stocks) ? stocks[rowIndex] : null;
        if (!stock) {
            if (window.CommonUtils) CommonUtils.showToast('未找到该行信号数据，请刷新筛选后重试', 'warning');
            return;
        }
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            if (window.CommonUtils) CommonUtils.showToast('请先登录后再加入交易观察', 'warning');
            window.location.href = 'login.html';
            return;
        }
        const code = String(stock.symbol || stock.code || '').trim();
        const market = this._gmsMarketFromStock(stock);
        const key = this._gmsTradeObserveKey(market, code);
        if (this._isGmsInTradeObserve(stock, market, code)) {
            if (window.CommonUtils) {
                const inFormal = this.gmsFormalTradeCodeSet.has(key);
                CommonUtils.showToast(
                    inFormal ? '该股票已在正式交易中' : '已在交易观察列表中',
                    'info'
                );
            }
            if (btnEl) {
                btnEl.textContent = '已观察';
                btnEl.classList.add('is-added');
                btnEl.disabled = true;
            }
            this.gmsTradeObserveCodeSet.add(key);
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        const snapshot = this._buildGmsTradeObserveSnapshot(stock);
        const signalDate = this._resolveGmsSignalDate(stock);
        if (!signalDate) {
            if (window.CommonUtils) CommonUtils.showToast('无法确定信号交易日，请先刷新 GMS 筛选', 'warning');
            return;
        }
        try {
            if (btnEl) {
                btnEl.disabled = true;
                btnEl.textContent = '加入中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-trade-observe/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code,
                    market,
                    name: stock.name || code,
                    signal_date: signalDate,
                    snapshot,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this.gmsTradeObserveCodeSet.add(key);
            if (window.CommonUtils) CommonUtils.showToast(`已加入交易观察：${stock.name || code}`, 'success');
            if (btnEl) {
                btnEl.textContent = '已观察';
                btnEl.classList.add('is-added');
                btnEl.disabled = true;
            }
            if (this.gmsSubPanel === 'trade-observe') {
                void this.refreshGmsTradeObserveList();
            }
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '加入交易观察失败', 'error');
            await this.loadGmsObservedCodeSets();
            const stillIn = this._isGmsInTradeObserve(stock, market, code);
            if (btnEl) {
                if (stillIn) {
                    btnEl.textContent = '已观察';
                    btnEl.classList.add('is-added');
                    btnEl.disabled = true;
                } else {
                    btnEl.textContent = '观察';
                    btnEl.disabled = false;
                }
            }
        }
    },

    async removeGmsTradeObserve(itemId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) btnEl.disabled = true;
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/gms-trade-observe/${itemId}`, {
                method: 'DELETE',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `移除失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (window.CommonUtils) CommonUtils.showToast('已移出交易观察列表', 'success');
            await this.loadGmsObservedCodeSets();
            void this.refreshGmsTradeObserveList();
            this._refreshGmsTradeObserveButtonsInSignalTable();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '移除失败', 'error');
            if (btnEl) btnEl.disabled = false;
        }
    },

    _refreshGmsTradeObserveButtonsInSignalTable() {
        const tbody = document.getElementById('resultsTableBody-gms');
        if (!tbody) return;
        tbody.querySelectorAll('.gms-trade-observe-add').forEach((btn) => {
            const code = btn.getAttribute('data-code') || '';
            const market = (btn.getAttribute('data-market') || 'CN').toUpperCase();
            const key = this._gmsTradeObserveKey(market, code);
            const rowIdx = parseInt(btn.getAttribute('data-row'), 10);
            const stock = Array.isArray(this.lastResults.gms) ? this.lastResults.gms[rowIdx] : null;
            const observed = this._isGmsInTradeObserve(stock, market, code);
            if (observed) {
                btn.textContent = '已观察';
                btn.classList.add('is-added');
                btn.disabled = true;
            } else {
                btn.textContent = '观察';
                btn.classList.remove('is-added');
                btn.disabled = false;
            }
        });
    },

    _tvoTradeObserveKey(market, code) {
        const m = String(market || 'CN').trim().toUpperCase();
        const c = String(code || '').trim();
        return `${m}:${c}`;
    },

    async loadTvoTradeObserveCodes() {
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            this.tvoTradeObserveCodeSet = new Set();
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/triple-volume-trade-observe/codes`);
            if (!res.ok) {
                this.tvoTradeObserveCodeSet = new Set();
                return;
            }
            const codes = await res.json();
            this.tvoTradeObserveCodeSet = new Set(Array.isArray(codes) ? codes : []);
        } catch (_) {
            this.tvoTradeObserveCodeSet = new Set();
        }
    },

    _buildTvoTradeObserveSnapshot(row) {
        if (!row || typeof row !== 'object') return {};
        return {
            observe_trade_date: row.observe_trade_date,
            prev_trade_date: row.prev_trade_date,
            prev_volume: row.prev_volume,
            curr_volume: row.curr_volume,
            volume_ratio_actual: row.volume_ratio_actual,
            status: row.status,
            vsb_evaluated_at: row.vsb_evaluated_at,
        };
    },

    async addTvoTradeObserveFromDailyRow(rowIndex, btnEl) {
        const row = Array.isArray(this.lastDailyTvoItems) ? this.lastDailyTvoItems[rowIndex] : null;
        if (!row) {
            if (window.CommonUtils) CommonUtils.showToast('未找到该行数据，请刷新列表后重试', 'warning');
            return;
        }
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            if (window.CommonUtils) CommonUtils.showToast('请先登录后再加入交易观察', 'warning');
            window.location.href = 'login.html';
            return;
        }
        const code = String(row.code || '').trim();
        const market = String(row.market || 'CN').trim().toUpperCase();
        const key = this._tvoTradeObserveKey(market, code);
        if (this.tvoTradeObserveCodeSet.has(key)) {
            if (window.CommonUtils) CommonUtils.showToast('已在3倍量交易观察列表中', 'info');
            return;
        }
        const observeDate = row.observe_trade_date ? String(row.observe_trade_date).trim().slice(0, 10) : '';
        if (!observeDate) {
            if (window.CommonUtils) CommonUtils.showToast('缺少观察日，无法加入交易观察', 'warning');
            return;
        }
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) {
                btnEl.disabled = true;
                btnEl.textContent = '加入中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/triple-volume-trade-observe/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code,
                    market,
                    name: row.name || code,
                    observe_trade_date: observeDate,
                    snapshot: this._buildTvoTradeObserveSnapshot(row),
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加入失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this.tvoTradeObserveCodeSet.add(key);
            if (window.CommonUtils) CommonUtils.showToast(`已加入3倍量交易观察：${row.name || code}`, 'success');
            if (btnEl) {
                btnEl.textContent = '已观察';
                btnEl.classList.add('is-added');
                btnEl.disabled = true;
            }
            if (this.vsbSubPanel === 'trade-observe') {
                void this.refreshTvoTradeObserveList();
            }
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '加入交易观察失败', 'error');
            if (btnEl) {
                btnEl.textContent = '观察';
                btnEl.disabled = false;
            }
        }
    },

    async refreshTvoTradeObserveList() {
        const errEl = document.getElementById('tvoTradeObserveError');
        const loadingEl = document.getElementById('tvoTradeObserveLoading');
        const tbody = document.getElementById('tvoTradeObserveTableBody');
        const countEl = document.getElementById('tvoTradeObserveCount');
        const user = (window.CommonUtils && CommonUtils.auth)
            ? await CommonUtils.auth.ensureLogin({
                redirect: true,
                message: '请先登录后查看交易观察列表',
            })
            : null;
        if (!user) return;
        if (errEl) {
            errEl.style.display = 'none';
            errEl.textContent = '';
        }
        if (loadingEl) loadingEl.style.display = 'flex';
        const fetchFn = this.getAuthFetchFn();
        try {
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/triple-volume-trade-observe/list?page=1&page_size=500`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `加载失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            const items = data.items || [];
            this.tvoTradeObserveCodeSet = new Set(
                items.map((it) => this._tvoTradeObserveKey(it.market, it.code))
            );
            this.renderTvoTradeObserveTable(items);
            if (countEl) countEl.textContent = `共 ${data.total || items.length} 只`;
            this._refreshTvoTradeObserveButtonsInDailyTable();
        } catch (e) {
            if (errEl) {
                errEl.textContent = e.message || '加载交易观察列表失败';
                errEl.style.display = 'block';
            }
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    },

    renderTvoTradeObserveTable(items) {
        const tbody = document.getElementById('tvoTradeObserveTableBody');
        if (!tbody) return;
        if (!items || items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">暂无交易观察股票，请在「观察股池 → 日终爆量」中点击「观察」加入</td></tr>';
            return;
        }
        const esc = this._tvoEscapeHtml.bind(this);
        const fmtNum = this._tvoFmtNum.bind(this);
        const fmtDt = (iso) => {
            if (!iso) return '--';
            const s = String(iso);
            return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10);
        };
        tbody.innerHTML = items.map((it) => {
            const snap = it.snapshot || {};
            const ratio =
                snap.volume_ratio_actual != null && snap.volume_ratio_actual !== ''
                    ? Number(snap.volume_ratio_actual).toFixed(2)
                    : '--';
            const status = snap.status || '--';
            const href = `stock.html?code=${encodeURIComponent(it.code)}&name=${encodeURIComponent(it.name || '')}`;
            return `
                <tr data-observe-id="${it.id}">
                    <td>${esc(it.market)}</td>
                    <td><a class="stock-code" href="${href}" target="_blank" rel="noopener noreferrer">${esc(it.code)}</a></td>
                    <td><span class="stock-name" title="${esc(it.name)}">${esc(it.name || '--')}</span></td>
                    <td>${esc(it.observe_trade_date || '--')}</td>
                    <td>${esc(ratio)}</td>
                    <td>${esc(status)}</td>
                    <td>${esc(fmtDt(it.updated_at || it.created_at))}</td>
                    <td>
                        <div class="action-links">
                            <a href="${href}" class="gms-op-btn" target="_blank" rel="noopener noreferrer">行情</a>
                            <button type="button" class="gms-op-btn tvo-trade-observe-remove" data-id="${it.id}" title="移出交易观察">移除</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    },

    async removeTvoTradeObserve(itemId, btnEl) {
        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) btnEl.disabled = true;
            const res = await fetchFn(`${this.API_BASE_URL}/api/stock/triple-volume-trade-observe/${itemId}`, {
                method: 'DELETE',
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = data.detail || data.message || `移除失败(${res.status})`;
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (window.CommonUtils) CommonUtils.showToast('已移出3倍量交易观察列表', 'success');
            await this.loadTvoTradeObserveCodes();
            void this.refreshTvoTradeObserveList();
            this._refreshTvoTradeObserveButtonsInDailyTable();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '移除失败', 'error');
            if (btnEl) btnEl.disabled = false;
        }
    },

    _refreshTvoTradeObserveButtonsInDailyTable() {
        const tbody = document.getElementById('dailyTvoObserveTableBody');
        if (!tbody) return;
        tbody.querySelectorAll('.tvo-trade-observe-add').forEach((btn) => {
            const rowIdx = parseInt(btn.getAttribute('data-row') || '-1', 10);
            const row = Array.isArray(this.lastDailyTvoItems) ? this.lastDailyTvoItems[rowIdx] : null;
            if (!row) return;
            const market = String(row.market || 'CN').trim().toUpperCase();
            const code = String(row.code || '').trim();
            const key = this._tvoTradeObserveKey(market, code);
            if (this.tvoTradeObserveCodeSet.has(key)) {
                btn.textContent = '已观察';
                btn.classList.add('is-added');
                btn.disabled = true;
            } else {
                btn.textContent = '观察';
                btn.classList.remove('is-added');
                btn.disabled = false;
            }
        });
    },

    initVsbIntegratedTabs() {
        const pick = document.getElementById('vsbSubTabPick');
        const obs = document.getElementById('vsbSubTabObserve');
        const tradeObs = document.getElementById('vsbSubTabTradeObserve');
        [pick, obs, tradeObs].forEach((btn) => {
            if (!btn) return;
            btn.addEventListener('click', () => {
                const sub = btn.getAttribute('data-vsb-sub');
                if (sub === 'pick' || sub === 'observe' || sub === 'trade-observe') {
                    this.switchVsbSubPanel(sub);
                }
            });
        });
        document.querySelectorAll('#vsb-sub-observe-wrap .observe-source-tab').forEach((btn) => {
            btn.addEventListener('click', () => {
                const src = btn.getAttribute('data-observe-source');
                if (src === 'vsb' || src === 'daily') {
                    this.switchObserveSource(src);
                }
            });
        });
        const br = document.getElementById('btnObservePoolRefresh');
        const bx = document.getElementById('btnObservePoolExport');
        if (br) {
            br.addEventListener('click', () => this.refreshObserveActiveList());
        }
        if (bx) {
            bx.addEventListener('click', () => this.exportObserveActiveXlsx());
        }
        const dailyTvoBody = document.getElementById('dailyTvoObserveTableBody');
        if (dailyTvoBody) {
            dailyTvoBody.addEventListener('click', (e) => {
                const btn = e.target.closest('.tvo-trade-observe-add');
                if (!btn || btn.disabled) return;
                const idx = btn.getAttribute('data-row');
                if (idx == null) return;
                void this.addTvoTradeObserveFromDailyRow(parseInt(idx, 10), btn);
            });
        }
        const tvoTradeObsRefresh = document.getElementById('tvoTradeObserveRefreshBtn');
        if (tvoTradeObsRefresh) {
            tvoTradeObsRefresh.addEventListener('click', () => this.refreshTvoTradeObserveList());
        }
        const tvoTradeObsBody = document.getElementById('tvoTradeObserveTableBody');
        if (tvoTradeObsBody) {
            tvoTradeObsBody.addEventListener('click', (e) => {
                const rm = e.target.closest('.tvo-trade-observe-remove');
                if (!rm) return;
                e.preventDefault();
                const id = rm.getAttribute('data-id');
                if (id) void this.removeTvoTradeObserve(parseInt(id, 10), rm);
            });
        }
        const dailyTvoSortRatio = document.getElementById('dailyTvoSortRatio');
        if (dailyTvoSortRatio) {
            dailyTvoSortRatio.addEventListener('click', () => this.toggleDailyTvoVolumeRatioSort());
        }
    },

    applyVsbHashOnLoad() {
        const h = (window.location.hash || '').replace(/^#/, '').split('&')[0];
        if (h === 'vsb-observe' || h === 'vsb-observe-daily' || h === 'triple-volume-observe') {
            this._vsbOpenFromHash = true;
            this.switchStrategy('volume-shrink-breakout');
            this._vsbOpenFromHash = false;
            if (h === 'vsb-observe-daily' || h === 'triple-volume-observe') {
                this.vsbObserveSource = 'daily';
            } else {
                this.vsbObserveSource = 'vsb';
            }
            this.switchVsbSubPanel('observe');
            return;
        }
        if (h === 'vsb-trade-observe') {
            this._vsbOpenFromHash = true;
            this.switchStrategy('volume-shrink-breakout');
            this._vsbOpenFromHash = false;
            this.switchVsbSubPanel('trade-observe');
            return;
        }
        if (h === 'vsb-pick') {
            this._vsbOpenFromHash = true;
            this.switchStrategy('volume-shrink-breakout');
            this._vsbOpenFromHash = false;
            this.switchVsbSubPanel('pick');
        }
    },

    switchVsbSubPanel(sub) {
        this.vsbSubPanel = sub;
        document.querySelectorAll('.vsb-integrated-head .vsb-sub-tab').forEach((t) => {
            t.classList.toggle('active', t.getAttribute('data-vsb-sub') === sub);
        });
        document.querySelectorAll('.vsb-sub-panel').forEach((p) => {
            const show =
                (sub === 'pick' && p.id === 'vsb-sub-pick-wrap') ||
                (sub === 'observe' && p.id === 'vsb-sub-observe-wrap') ||
                (sub === 'trade-observe' && p.id === 'vsb-sub-trade-observe-wrap');
            p.classList.toggle('active', show);
        });
        if (sub === 'observe') {
            this._syncObserveInnerTabsFromState();
            this.refreshObserveActiveList();
        }
        if (sub === 'trade-observe') {
            this.refreshTvoTradeObserveList();
        }
        this._replaceVsbScreeningHash();
    },

    _syncObserveInnerTabsFromState() {
        const src = this.vsbObserveSource === 'daily' ? 'daily' : 'vsb';
        document.querySelectorAll('#vsb-sub-observe-wrap .observe-source-tab').forEach((t) => {
            t.classList.toggle('active', t.getAttribute('data-observe-source') === src);
        });
        const wV = document.getElementById('observe-source-vsb-wrap');
        const wD = document.getElementById('observe-source-daily-wrap');
        if (wV) wV.classList.toggle('active', src === 'vsb');
        if (wD) wD.classList.toggle('active', src === 'daily');
        const statusWrap = document.getElementById('dailyTvoFilterStatusWrap');
        if (statusWrap) {
            statusWrap.style.display = src === 'daily' ? '' : 'none';
        }
    },

    switchObserveSource(src) {
        this.vsbObserveSource = src === 'daily' ? 'daily' : 'vsb';
        this._syncObserveInnerTabsFromState();
        this.refreshObserveActiveList();
        this._replaceVsbScreeningHash();
    },

    _replaceVsbScreeningHash() {
        try {
            if (!window.history || !window.history.replaceState) return;
            let suffix = '#vsb-pick';
            if (this.vsbSubPanel === 'observe') {
                suffix = this.vsbObserveSource === 'daily' ? '#vsb-observe-daily' : '#vsb-observe';
            } else if (this.vsbSubPanel === 'trade-observe') {
                suffix = '#vsb-trade-observe';
            }
            window.history.replaceState(null, '', 'screening.html' + suffix);
        } catch (_) {}
    },

    refreshObserveActiveList() {
        if (this.vsbObserveSource === 'daily') {
            this.loadDailyTripleVolumeObserveList();
        } else {
            this.loadVsbObserveStocksList();
        }
    },

    exportObserveActiveXlsx() {
        if (this.vsbObserveSource === 'daily') {
            this.exportDailyTripleVolumeObserveXlsx();
        } else {
            this.exportVsbObserveStocksXlsx();
        }
    },

    _tvoEscapeHtml(s) {
        if (s == null || s === '') return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    /** 观察股池「市场/板块」下拉：值为 HK | CN | CN|CYB 等 */
    _parseObserveMarketSelect(raw) {
        const v = (raw || '').trim();
        if (!v) return { market: '', board: '' };
        const i = v.indexOf('|');
        if (i === -1) return { market: v, board: '' };
        return { market: v.slice(0, i).trim(), board: v.slice(i + 1).trim() };
    },

    _applyObserveMarketBoardToQs(qs, rawSelectValue) {
        const { market, board } = this._parseObserveMarketSelect(rawSelectValue);
        if (market) qs.set('market', market);
        if (board) qs.set('board', board);
    },

    async loadVsbObserveStocksList() {
        const apiBase = this.API_BASE_URL || '';
        const marketEl = document.getElementById('tvoFilterMarket');
        const err = document.getElementById('tvoObserveError');
        if (err) {
            err.style.display = 'none';
            err.textContent = '';
        }
        const mv = marketEl ? marketEl.value : '';
        const qs = new URLSearchParams({ page: '1', page_size: '200' });
        this._applyObserveMarketBoardToQs(qs, mv);
        const url = `${apiBase}/api/stock/vsb-observe-stocks/list?${qs.toString()}`;
        const fetchFn = typeof smartFetch === 'function' ? smartFetch : fetch;
        let res;
        try {
            res = await fetchFn(url);
        } catch (e) {
            if (err) {
                err.textContent = String(e.message || e);
                err.style.display = 'block';
            }
            return;
        }
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            if (err) {
                err.textContent = '响应解析失败';
                err.style.display = 'block';
            }
            return;
        }
        if (!res.ok) {
            if (err) {
                err.textContent = data.detail || data.message || '加载失败';
                err.style.display = 'block';
            }
            return;
        }
        const tbody = document.getElementById('tvoObserveTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        const items = data.items || [];
        if (items.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="10" class="empty-state">暂无数据</td>';
            tbody.appendChild(tr);
        } else {
            const esc = this._tvoEscapeHtml.bind(this);
            items.forEach((row) => {
                const tr = document.createElement('tr');
                const up = row.updated_at
                    ? String(row.updated_at).replace('T', ' ').slice(0, 19)
                    : '';
                const strength =
                    row.signal_strength != null || row.signal_strength_level
                        ? (row.signal_strength != null ? String(row.signal_strength) : '') +
                          (row.signal_strength_level ? ' ' + esc(row.signal_strength_level) : '')
                        : '';
                tr.innerHTML =
                    '<td>' + esc(row.market) + '</td>' +
                    '<td>' + esc(row.code) + '</td>' +
                    '<td>' + esc(row.name) + '</td>' +
                    '<td>' + esc(row.display_status || '') + '</td>' +
                    '<td>' + esc(row.signal_date) + '</td>' +
                    '<td>' + esc(row.boom_date) + '</td>' +
                    '<td>' + esc(row.run_search_date) + '</td>' +
                    '<td>' + strength.trim() + '</td>' +
                    '<td>' + esc(row.buy_signal_text) + '</td>' +
                    '<td>' + esc(up) + '</td>';
                tbody.appendChild(tr);
            });
        }
        const pager = document.getElementById('tvoObservePager');
        if (pager) {
            pager.textContent = '共 ' + (data.total || 0) + ' 条，本页 ' + items.length + ' 条';
        }
    },

    _tvoFmtNum(v) {
        if (v == null || v === '') return '';
        const n = Number(v);
        if (Number.isNaN(n)) return String(v);
        if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿';
        if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万';
        return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    },

    toggleDailyTvoVolumeRatioSort() {
        if (this.dailyTvoVolumeRatioSort === null) {
            this.dailyTvoVolumeRatioSort = 'desc';
        } else if (this.dailyTvoVolumeRatioSort === 'desc') {
            this.dailyTvoVolumeRatioSort = 'asc';
        } else {
            this.dailyTvoVolumeRatioSort = null;
        }
        this._updateDailyTvoSortHeader();
        if (this.vsbObserveSource === 'daily') {
            void this.loadDailyTripleVolumeObserveList();
        }
    },

    _updateDailyTvoSortHeader() {
        const th = document.getElementById('dailyTvoSortRatio');
        if (!th) return;
        const ind = th.querySelector('.sort-indicator');
        const order = this.dailyTvoVolumeRatioSort;
        th.classList.toggle('is-sorted', order === 'asc' || order === 'desc');
        th.classList.toggle('sort-desc', order === 'desc');
        th.classList.toggle('sort-asc', order === 'asc');
        if (ind) {
            ind.textContent = order === 'desc' ? ' ▼' : order === 'asc' ? ' ▲' : '';
        }
    },

    async loadDailyTripleVolumeObserveList() {
        const apiBase = this.API_BASE_URL || '';
        const marketEl = document.getElementById('tvoFilterMarket');
        const statusEl = document.getElementById('dailyTvoFilterStatus');
        const err = document.getElementById('tvoObserveError');
        if (err) {
            err.style.display = 'none';
            err.textContent = '';
        }
        await this.loadTvoTradeObserveCodes();
        const mv = marketEl ? marketEl.value : '';
        const status = statusEl ? statusEl.value : '';
        const qs = new URLSearchParams({ page: '1', page_size: '200' });
        this._applyObserveMarketBoardToQs(qs, mv);
        if (status) qs.set('status', status);
        if (this.dailyTvoVolumeRatioSort === 'asc' || this.dailyTvoVolumeRatioSort === 'desc') {
            qs.set('sort_by', 'volume_ratio');
            qs.set('sort_order', this.dailyTvoVolumeRatioSort);
        }
        const url = `${apiBase}/api/stock/triple-volume-observe/list?${qs.toString()}`;
        const fetchFn = typeof smartFetch === 'function' ? smartFetch : fetch;
        let res;
        try {
            res = await fetchFn(url);
        } catch (e) {
            if (err) {
                err.textContent = String(e.message || e);
                err.style.display = 'block';
            }
            return;
        }
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            if (err) {
                err.textContent = '响应解析失败';
                err.style.display = 'block';
            }
            return;
        }
        if (!res.ok) {
            if (err) {
                err.textContent = data.detail || data.message || '加载失败';
                err.style.display = 'block';
            }
            return;
        }
        const tbody = document.getElementById('dailyTvoObserveTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        const items = data.items || [];
        this.lastDailyTvoItems = items;
        if (items.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="12" class="empty-state">暂无数据</td>';
            tbody.appendChild(tr);
        } else {
            const esc = this._tvoEscapeHtml.bind(this);
            const fmtNum = this._tvoFmtNum.bind(this);
            items.forEach((row, index) => {
                const tr = document.createElement('tr');
                const up = row.updated_at
                    ? String(row.updated_at).replace('T', ' ').slice(0, 19)
                    : '';
                const ev = row.vsb_evaluated_at
                    ? String(row.vsb_evaluated_at).replace('T', ' ').slice(0, 19)
                    : '';
                const ratio =
                    row.volume_ratio_actual != null && row.volume_ratio_actual !== ''
                        ? Number(row.volume_ratio_actual).toFixed(2)
                        : '';
                const market = String(row.market || 'CN').trim().toUpperCase();
                const code = String(row.code || '').trim();
                const observeKey = this._tvoTradeObserveKey(market, code);
                const already = this.tvoTradeObserveCodeSet.has(observeKey);
                const btnLabel = already ? '已观察' : '观察';
                const btnClass = already ? ' is-added' : '';
                const btnDisabled = already ? ' disabled' : '';
                tr.innerHTML =
                    '<td>' + esc(row.market) + '</td>' +
                    '<td>' + esc(row.code) + '</td>' +
                    '<td>' + esc(row.name) + '</td>' +
                    '<td>' + esc(row.observe_trade_date) + '</td>' +
                    '<td>' + esc(row.prev_trade_date || '') + '</td>' +
                    '<td>' + esc(fmtNum(row.prev_volume)) + '</td>' +
                    '<td>' + esc(fmtNum(row.curr_volume)) + '</td>' +
                    '<td>' + esc(ratio) + '</td>' +
                    '<td>' + esc(row.status) + '</td>' +
                    '<td>' + esc(ev) + '</td>' +
                    '<td>' + esc(up) + '</td>' +
                    '<td><button type="button" class="gms-op-btn gms-op-btn--primary tvo-trade-observe-add' +
                    btnClass + '" data-row="' + index + '" title="加入3倍量交易观察"' +
                    btnDisabled + '>' + btnLabel + '</button></td>';
                tbody.appendChild(tr);
            });
        }
        const pager = document.getElementById('dailyTvoObservePager');
        if (pager) {
            pager.textContent = '共 ' + (data.total || 0) + ' 条，本页 ' + items.length + ' 条';
        }
        this._updateDailyTvoSortHeader();
    },

    async exportVsbObserveStocksXlsx() {
        const apiBase = this.API_BASE_URL || '';
        const marketEl = document.getElementById('tvoFilterMarket');
        const err = document.getElementById('tvoObserveError');
        const mv = marketEl ? marketEl.value : '';
        const qs = new URLSearchParams();
        this._applyObserveMarketBoardToQs(qs, mv);
        const url = `${apiBase}/api/stock/vsb-observe-stocks/export?${qs.toString()}`;
        const fetchFn = typeof smartFetch === 'function' ? smartFetch : fetch;
        let res;
        try {
            res = await fetchFn(url);
        } catch (e) {
            if (err) {
                err.textContent = String(e.message || e);
                err.style.display = 'block';
            }
            return;
        }
        if (!res.ok) {
            if (err) {
                err.textContent = '导出失败';
                err.style.display = 'block';
            }
            return;
        }
        if (err) {
            err.style.display = 'none';
        }
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'vsb_observe_stocks.xlsx';
        a.click();
        URL.revokeObjectURL(a.href);
    },

    async exportDailyTripleVolumeObserveXlsx() {
        const apiBase = this.API_BASE_URL || '';
        const marketEl = document.getElementById('tvoFilterMarket');
        const statusEl = document.getElementById('dailyTvoFilterStatus');
        const err = document.getElementById('tvoObserveError');
        const mv = marketEl ? marketEl.value : '';
        const status = statusEl ? statusEl.value : '';
        const qs = new URLSearchParams();
        this._applyObserveMarketBoardToQs(qs, mv);
        if (status) qs.set('status', status);
        const url = `${apiBase}/api/stock/triple-volume-observe/export?${qs.toString()}`;
        const fetchFn = typeof smartFetch === 'function' ? smartFetch : fetch;
        let res;
        try {
            res = await fetchFn(url);
        } catch (e) {
            if (err) {
                err.textContent = String(e.message || e);
                err.style.display = 'block';
            }
            return;
        }
        if (!res.ok) {
            if (err) {
                err.textContent = '导出失败';
                err.style.display = 'block';
            }
            return;
        }
        if (err) {
            err.style.display = 'none';
        }
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'triple_volume_observe_stocks.xlsx';
        a.click();
        URL.revokeObjectURL(a.href);
    },

    /** 显示/隐藏「GMS观察股」下的市场筛选行 */
    syncGmsWatchlistMarketWrap() {
        const wrap = document.getElementById('gmsWatchlistMarketWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="gmsScope"]:checked');
        const show = checked && checked.value === 'gms_watchlist';
        wrap.style.display = show ? 'flex' : 'none';
        this.syncGmsWatchlistBoardWrap();
    },

    /** 显示/隐藏「GMS观察股」下的 A 股板块筛选（仅港股时隐藏） */
    syncGmsWatchlistBoardWrap() {
        const wrap = document.getElementById('gmsWatchlistBoardWrap');
        if (!wrap) return;
        const scopeEl = document.querySelector('input[name="gmsScope"]:checked');
        const marketEl = document.querySelector('input[name="gmsWatchlistMarket"]:checked');
        const show = scopeEl && scopeEl.value === 'gms_watchlist'
            && marketEl && marketEl.value !== 'hk';
        wrap.style.display = show ? 'flex' : 'none';
    },

    /** 显示/隐藏 A 股板块筛选行（全部A股 / 行业板块 / 概念板块） */
    syncGmsCnBoardWrap() {
        const wrap = document.getElementById('gmsCnBoardWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="gmsScope"]:checked');
        const show = checked && ['cn', 'industry_board', 'concept_board'].includes(checked.value);
        wrap.style.display = show ? 'flex' : 'none';
    },

    /** 已选行业板块代码 */
    getGmsSelectedIndustryBoardCodes() {
        return Array.isArray(this.gmsSelectedIndustryBoardCodes)
            ? this.gmsSelectedIndustryBoardCodes.filter(Boolean)
            : [];
    },

    /** 已选概念板块代码 */
    getGmsSelectedConceptBoardCodes() {
        return Array.isArray(this.gmsSelectedConceptBoardCodes)
            ? this.gmsSelectedConceptBoardCodes.filter(Boolean)
            : [];
    },

    _gmsBoardCatalogByKind(kind) {
        return kind === 'industry' ? this.gmsIndustryBoardCatalog : this.gmsConceptBoardCatalog;
    },

    _gmsBoardSourceValue(board) {
        const raw = String(board?.board_code_source || '').trim().toLowerCase();
        if (raw) return raw;
        return 'eastmoney';
    },

    _gmsBoardSourceLabel(board) {
        const label = String(board?.board_code_source_label || '').trim();
        if (label) return label;
        const map = {
            eastmoney: '东方财富',
            tonghuashun: '同花顺',
            huatai: '华泰',
            manual: '手动维护',
            other: '其他',
        };
        return map[this._gmsBoardSourceValue(board)] || '东方财富';
    },

    _gmsBoardLabel(board) {
        const code = String(board?.board_code || '').trim();
        const name = String(board?.board_name || '').trim();
        const base = name || code;
        const src = this._gmsBoardSourceLabel(board);
        return src ? `${base}（${src}）` : base;
    },

    /** 板块目录中已标记交易观察的板块代码 */
    _gmsBoardTradeObserveCodes(kind) {
        return this._gmsBoardCatalogByKind(kind)
            .filter((b) => b.trade_observe_flag === true)
            .map((b) => String(b.board_code || '').trim())
            .filter(Boolean);
    },

    /** 将交易观察板块并入已选集合 */
    _mergeGmsTradeObserveBoardSelection(kind, selected) {
        const set = selected instanceof Set
            ? new Set(selected)
            : new Set(Array.isArray(selected) ? selected : []);
        this._gmsBoardTradeObserveCodes(kind).forEach((code) => set.add(code));
        return set;
    },

    /** 将交易观察板块写入 GMS 数据来源已选列表 */
    _applyGmsTradeObserveBoardDefaults(kind) {
        if (kind === 'industry') {
            const merged = this._mergeGmsTradeObserveBoardSelection(
                kind,
                this.getGmsSelectedIndustryBoardCodes(),
            );
            this.gmsSelectedIndustryBoardCodes = Array.from(merged);
            this.updateGmsIndustryBoardSummary();
            return;
        }
        if (kind === 'concept') {
            const merged = this._mergeGmsTradeObserveBoardSelection(
                kind,
                this.getGmsSelectedConceptBoardCodes(),
            );
            this.gmsSelectedConceptBoardCodes = Array.from(merged);
            this.updateGmsConceptBoardSummary();
        }
    },

    /** 行业板块同名同来源去重（优先 BK；不同代码来源可并存） */
    _dedupeGmsIndustryBoardCatalog(boards) {
        const list = Array.isArray(boards) ? boards : [];
        const buckets = new Map();
        list.forEach((b) => {
            const code = String(b?.board_code || '').trim();
            if (!code) return;
            const name = String(b?.board_name || '').trim() || code;
            const source = this._gmsBoardSourceValue(b);
            const key = `${name}||${source}`;
            const prev = buckets.get(key);
            const isBk = /^BK\d+$/i.test(code);
            const observeFlag = !!(b?.trade_observe_flag || prev?.trade_observe_flag);
            const normalized = {
                ...b,
                board_code_source: source,
                board_code_source_label: b?.board_code_source_label || this._gmsBoardSourceLabel({ board_code_source: source }),
                trade_observe_flag: !!b?.trade_observe_flag,
            };
            if (!prev) {
                buckets.set(key, normalized);
                return;
            }
            const prevBk = /^BK\d+$/i.test(String(prev.board_code || ''));
            if (!prevBk && isBk) {
                buckets.set(key, { ...normalized, trade_observe_flag: observeFlag });
            } else {
                buckets.set(key, { ...prev, trade_observe_flag: observeFlag });
            }
        });
        return Array.from(buckets.values()).sort((a, b) => String(a.board_name || a.board_code).localeCompare(
            String(b.board_name || b.board_code),
            'zh-CN',
        ));
    },

    /** 概念板块同名同来源去重：优先保留成分股更多的编码（避免同花顺空壳板盖住有成分板） */
    _dedupeGmsConceptBoardCatalog(boards) {
        const list = Array.isArray(boards) ? boards : [];
        const buckets = new Map();
        list.forEach((b) => {
            const code = String(b?.board_code || '').trim();
            if (!code) return;
            const name = String(b?.board_name || '').trim() || code;
            const source = this._gmsBoardSourceValue(b);
            const key = `${name}||${source}`;
            const count = Number(b?.stock_count);
            const stockCount = Number.isFinite(count) ? count : 0;
            const observeFlag = !!(b?.trade_observe_flag);
            const normalized = {
                ...b,
                board_code_source: source,
                board_code_source_label: b?.board_code_source_label || this._gmsBoardSourceLabel({ board_code_source: source }),
                trade_observe_flag: observeFlag,
                stock_count: stockCount,
            };
            const prev = buckets.get(key);
            if (!prev) {
                buckets.set(key, normalized);
                return;
            }
            const prevCount = Number(prev.stock_count) || 0;
            if (stockCount > prevCount) {
                buckets.set(key, {
                    ...normalized,
                    trade_observe_flag: observeFlag || !!prev.trade_observe_flag,
                });
            } else {
                buckets.set(key, {
                    ...prev,
                    trade_observe_flag: observeFlag || !!prev.trade_observe_flag,
                });
            }
        });
        return Array.from(buckets.values()).sort((a, b) => String(a.board_name || a.board_code).localeCompare(
            String(b.board_name || b.board_code),
            'zh-CN',
        ));
    },

    _syncGmsBoardPickerSourceFilterUi() {
        const wrap = document.querySelector('#gmsBoardPickerModal .gms-board-picker-source-filters');
        if (!wrap) return;
        const current = this._gmsBoardPickerSourceFilter || 'all';
        wrap.querySelectorAll('.gms-board-source-btn').forEach((el) => {
            const src = String(el.getAttribute('data-board-source') || 'all');
            el.classList.toggle('active', src === current);
        });
    },

    updateGmsIndustryBoardSummary() {
        const el = document.getElementById('gmsIndustryBoardSummary');
        if (!el) return;
        const codes = this.getGmsSelectedIndustryBoardCodes();
        if (!codes.length) {
            el.textContent = '未选择板块，点击「选择板块」';
            return;
        }
        const names = codes.map((code) => {
            const b = this.gmsIndustryBoardCatalog.find((x) => String(x.board_code) === code);
            return b?.board_name || code;
        });
        el.textContent = names.length <= 3
            ? `已选 ${codes.length} 个：${names.join('、')}`
            : `已选 ${codes.length} 个：${names.slice(0, 3).join('、')} 等`;
    },

    updateGmsConceptBoardSummary() {
        const el = document.getElementById('gmsConceptBoardSummary');
        if (!el) return;
        const codes = this.getGmsSelectedConceptBoardCodes();
        if (!codes.length) {
            el.textContent = '未选择板块，点击「选择板块」';
            return;
        }
        const names = codes.map((code) => {
            const b = this.gmsConceptBoardCatalog.find((x) => String(x.board_code) === code);
            return b?.board_name || code;
        });
        el.textContent = names.length <= 3
            ? `已选 ${codes.length} 个：${names.join('、')}`
            : `已选 ${codes.length} 个：${names.slice(0, 3).join('、')} 等`;
    },

    async openGmsBoardPickerModal(kind, owner = 'gms') {
        // 强制重拉，避免后端升级后仍用缺来源字段的旧缓存（会导致「同花顺」筛空）
        if (kind === 'industry') await this.loadGmsIndustryBoardOptions(true);
        else await this.loadGmsConceptBoardOptions(true);

        this._gmsBoardPickerKind = kind;
        if (owner === 'urt') this._gmsBoardPickerOwner = 'urt';
        else if (owner === 'rpe') this._gmsBoardPickerOwner = 'rpe';
        else this._gmsBoardPickerOwner = 'gms';

        let selected;
        if (this._gmsBoardPickerOwner === 'urt') {
            selected = kind === 'industry'
                ? this.getUrtSelectedIndustryBoardCodes()
                : this.getUrtSelectedConceptBoardCodes();
            this._gmsBoardPickerDraft = new Set(selected);
        } else if (this._gmsBoardPickerOwner === 'rpe') {
            selected = kind === 'industry'
                ? this.getRpeSelectedIndustryBoardCodes()
                : this.getRpeSelectedConceptBoardCodes();
            this._gmsBoardPickerDraft = new Set(selected);
        } else {
            selected = kind === 'industry'
                ? this.getGmsSelectedIndustryBoardCodes()
                : this.getGmsSelectedConceptBoardCodes();
            this._gmsBoardPickerDraft = this._mergeGmsTradeObserveBoardSelection(kind, selected);
        }

        const titleEl = document.getElementById('gmsBoardPickerTitle');
        if (titleEl) {
            titleEl.textContent = kind === 'industry' ? '选择行业板块' : '选择概念板块';
        }
        const searchEl = document.getElementById('gmsBoardPickerSearch');
        if (searchEl) searchEl.value = '';
        this._gmsBoardPickerSourceFilter = 'all';
        this._syncGmsBoardPickerSourceFilterUi();
        this._renderGmsBoardPickerList();
        this._showGmsModal(document.getElementById('gmsBoardPickerModal'));
    },

    _renderGmsBoardPickerList() {
        const listEl = document.getElementById('gmsBoardPickerList');
        if (!listEl) return;
        const kind = this._gmsBoardPickerKind;
        const catalog = this._gmsBoardCatalogByKind(kind);
        const draft = this._gmsBoardPickerDraft;
        const filter = String(document.getElementById('gmsBoardPickerSearch')?.value || '').trim().toLowerCase();
        const sourceFilter = this._gmsBoardPickerSourceFilter || 'all';
        const esc = (s) => String(s ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');

        const filtered = catalog.filter((b) => {
            if (sourceFilter !== 'all' && this._gmsBoardSourceValue(b) !== sourceFilter) {
                return false;
            }
            if (!filter) return true;
            const name = String(b.board_name || '').toLowerCase();
            const code = String(b.board_code || '').toLowerCase();
            const src = this._gmsBoardSourceLabel(b).toLowerCase();
            return name.includes(filter) || code.includes(filter) || src.includes(filter);
        });

        if (!filtered.length) {
            listEl.innerHTML = '<div class="gms-board-picker-empty">无匹配板块</div>';
            return;
        }

        listEl.innerHTML = filtered.map((b) => {
            const code = String(b.board_code || '').trim();
            const name = String(b.board_name || '').trim() || code;
            const srcLabel = this._gmsBoardSourceLabel(b);
            const count = Number(b.stock_count);
            const countTxt = Number.isFinite(count) ? `${count}只` : '';
            const title = `${this._gmsBoardLabel(b)}${countTxt ? ` · ${countTxt}` : ''} · ${code}`;
            const checked = draft.has(code) ? ' checked' : '';
            const sourceLine = countTxt ? `${srcLabel} · ${countTxt}` : srcLabel;
            return `<label class="gms-board-picker-item" title="${esc(title)}"><input type="checkbox" value="${esc(code)}"${checked}><span class="gms-board-picker-item-text"><span class="gms-board-picker-name">${esc(name)}</span><span class="gms-board-picker-source">${esc(sourceLine)}</span></span></label>`;
        }).join('');
    },

    _gmsBoardPickerSelectAllVisible() {
        const listEl = document.getElementById('gmsBoardPickerList');
        if (!listEl) return;
        listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
            cb.checked = true;
            const code = String(cb.value || '').trim();
            if (code) this._gmsBoardPickerDraft.add(code);
        });
    },

    _gmsBoardPickerClearVisible() {
        const listEl = document.getElementById('gmsBoardPickerList');
        if (!listEl) return;
        listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
            cb.checked = false;
            const code = String(cb.value || '').trim();
            if (code) this._gmsBoardPickerDraft.delete(code);
        });
    },

    /**
     * 弹窗内刷新板块选项：清缓存后强制重拉，按板块代码保留当前勾选。
     * GMS / URT / RPE 共用同一弹窗，均可使用。
     */
    async refreshGmsBoardPickerOptions() {
        const kind = this._gmsBoardPickerKind;
        if (!kind || this._gmsBoardPickerRefreshing) return;

        const btn = document.getElementById('gmsBoardPickerRefresh');
        const listEl = document.getElementById('gmsBoardPickerList');
        const kindLabel = kind === 'industry' ? '行业' : '概念';
        const preserved = new Set(
            Array.from(this._gmsBoardPickerDraft || []).map((c) => String(c || '').trim()).filter(Boolean),
        );

        this._gmsBoardPickerRefreshing = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = '刷新中…';
        }
        if (listEl) {
            listEl.classList.add('gms-board-picker-list--loading');
            listEl.setAttribute('aria-busy', 'true');
        }

        try {
            const ok = kind === 'industry'
                ? await this.loadGmsIndustryBoardOptions(true)
                : await this.loadGmsConceptBoardOptions(true);
            if (!ok) {
                throw new Error(`刷新${kindLabel}板块选项失败`);
            }

            const catalog = this._gmsBoardCatalogByKind(kind);
            const validCodes = new Set(
                catalog.map((b) => String(b.board_code || '').trim()).filter(Boolean),
            );
            let nextDraft = new Set([...preserved].filter((code) => validCodes.has(code)));
            if ((this._gmsBoardPickerOwner || 'gms') === 'gms') {
                nextDraft = this._mergeGmsTradeObserveBoardSelection(kind, nextDraft);
            }
            this._gmsBoardPickerDraft = nextDraft;
            this._renderGmsBoardPickerList();

            if (window.CommonUtils) {
                CommonUtils.showToast(
                    `已刷新${kindLabel}板块选项（共 ${catalog.length} 个）`,
                    'success',
                );
            }
        } catch (e) {
            console.warn('[板块选择] 刷新选项失败', e);
            if (window.CommonUtils) {
                CommonUtils.showToast(e.message || `刷新${kindLabel}板块选项失败`, 'error');
            }
        } finally {
            this._gmsBoardPickerRefreshing = false;
            if (btn) {
                btn.disabled = false;
                btn.textContent = '刷新';
            }
            if (listEl) {
                listEl.classList.remove('gms-board-picker-list--loading');
                listEl.removeAttribute('aria-busy');
            }
        }
    },

    confirmGmsBoardPicker() {
        const kind = this._gmsBoardPickerKind;
        const codes = Array.from(this._gmsBoardPickerDraft);
        const owner = this._gmsBoardPickerOwner || 'gms';
        if (owner === 'urt') {
            if (kind === 'industry') {
                this.urtSelectedIndustryBoardCodes = codes;
                this.updateUrtIndustryBoardSummary();
            } else if (kind === 'concept') {
                this.urtSelectedConceptBoardCodes = codes;
                this.updateUrtConceptBoardSummary();
            }
        } else if (owner === 'rpe') {
            if (kind === 'industry') {
                this.rpeSelectedIndustryBoardCodes = codes;
                this.updateRpeIndustryBoardSummary();
            } else if (kind === 'concept') {
                this.rpeSelectedConceptBoardCodes = codes;
                this.updateRpeConceptBoardSummary();
            }
        } else if (kind === 'industry') {
            this.gmsSelectedIndustryBoardCodes = codes;
            this.updateGmsIndustryBoardSummary();
        } else if (kind === 'concept') {
            this.gmsSelectedConceptBoardCodes = codes;
            this.updateGmsConceptBoardSummary();
        }
        this._hideGmsModal(document.getElementById('gmsBoardPickerModal'));
    },

    getRpeSelectedIndustryBoardCodes() {
        return Array.isArray(this.rpeSelectedIndustryBoardCodes)
            ? this.rpeSelectedIndustryBoardCodes.filter(Boolean)
            : [];
    },

    getRpeSelectedConceptBoardCodes() {
        return Array.isArray(this.rpeSelectedConceptBoardCodes)
            ? this.rpeSelectedConceptBoardCodes.filter(Boolean)
            : [];
    },

    updateRpeIndustryBoardSummary() {
        const el = document.getElementById('rpeIndustryBoardSummary');
        if (!el) return;
        const codes = this.getRpeSelectedIndustryBoardCodes();
        if (!codes.length) {
            el.textContent = '未选择板块，点击「选择板块」';
            return;
        }
        const names = codes.map((code) => {
            const b = this.gmsIndustryBoardCatalog.find((x) => String(x.board_code) === code);
            return b ? this._gmsBoardLabel(b) : code;
        });
        el.textContent = names.length <= 3
            ? `已选 ${codes.length} 个：${names.join('、')}`
            : `已选 ${codes.length} 个：${names.slice(0, 3).join('、')} 等`;
    },

    updateRpeConceptBoardSummary() {
        const el = document.getElementById('rpeConceptBoardSummary');
        if (!el) return;
        const codes = this.getRpeSelectedConceptBoardCodes();
        if (!codes.length) {
            el.textContent = '未选择板块，点击「选择板块」';
            return;
        }
        const names = codes.map((code) => {
            const b = this.gmsConceptBoardCatalog.find((x) => String(x.board_code) === code);
            return b ? this._gmsBoardLabel(b) : code;
        });
        el.textContent = names.length <= 3
            ? `已选 ${codes.length} 个：${names.join('、')}`
            : `已选 ${codes.length} 个：${names.slice(0, 3).join('、')} 等`;
    },

    getUrtSelectedIndustryBoardCodes() {
        return Array.isArray(this.urtSelectedIndustryBoardCodes)
            ? this.urtSelectedIndustryBoardCodes.filter(Boolean)
            : [];
    },

    getUrtSelectedConceptBoardCodes() {
        return Array.isArray(this.urtSelectedConceptBoardCodes)
            ? this.urtSelectedConceptBoardCodes.filter(Boolean)
            : [];
    },

    updateUrtIndustryBoardSummary() {
        const el = document.getElementById('urtIndustryBoardSummary');
        if (!el) return;
        const codes = this.getUrtSelectedIndustryBoardCodes();
        if (!codes.length) {
            el.textContent = '未选择板块，点击「选择板块」';
            return;
        }
        const names = codes.map((code) => {
            const b = this.gmsIndustryBoardCatalog.find((x) => String(x.board_code) === code);
            return b?.board_name || code;
        });
        el.textContent = names.length <= 3
            ? `已选 ${codes.length} 个：${names.join('、')}`
            : `已选 ${codes.length} 个：${names.slice(0, 3).join('、')} 等`;
    },

    updateUrtConceptBoardSummary() {
        const el = document.getElementById('urtConceptBoardSummary');
        if (!el) return;
        const codes = this.getUrtSelectedConceptBoardCodes();
        if (!codes.length) {
            el.textContent = '未选择板块，点击「选择板块」';
            return;
        }
        const names = codes.map((code) => {
            const b = this.gmsConceptBoardCatalog.find((x) => String(x.board_code) === code);
            return b?.board_name || code;
        });
        el.textContent = names.length <= 3
            ? `已选 ${codes.length} 个：${names.join('、')}`
            : `已选 ${codes.length} 个：${names.slice(0, 3).join('、')} 等`;
    },

    syncUrtCnBoardWrap() {
        const wrap = document.getElementById('urtCnBoardWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="urtScope"]:checked');
        const show = checked && ['cn', 'industry_board', 'concept_board'].includes(checked.value);
        wrap.style.display = show ? 'flex' : 'none';
    },

    syncUrtIndustryBoardWrap() {
        const wrap = document.getElementById('urtIndustryBoardWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="urtScope"]:checked');
        const show = checked && checked.value === 'industry_board';
        wrap.style.display = show ? 'flex' : 'none';
    },

    syncUrtConceptBoardWrap() {
        const wrap = document.getElementById('urtConceptBoardWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="urtScope"]:checked');
        const show = checked && checked.value === 'concept_board';
        wrap.style.display = show ? 'flex' : 'none';
    },

    syncUrtSingleStockWrap() {
        const wrap = document.getElementById('urtSingleStockWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="urtScope"]:checked');
        const show = checked && checked.value === 'single';
        wrap.style.display = show ? 'flex' : 'none';
        this.syncUrtFilterParamsForScope();
    },

    /** 单只股票：禁用量能/最低得分等筛选控件（后端亦不应用筛选） */
    syncUrtFilterParamsForScope() {
        const checked = document.querySelector('input[name="urtScope"]:checked');
        const isSingle = checked && checked.value === 'single';
        ['urtVolumeMultiple', 'urtMinScore'].forEach((id) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.disabled = !!isSingle;
            el.title = isSingle ? '单只股票模式不应用筛选条件，仅直接计算策略信号' : '';
        });
        const hint = document.getElementById('urtSingleSkipFilterHint');
        if (hint) hint.style.display = isSingle ? 'block' : 'none';
    },

    /** 显示/隐藏「行业板块」选择行 */
    syncGmsIndustryBoardWrap() {
        const wrap = document.getElementById('gmsIndustryBoardWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="gmsScope"]:checked');
        const show = checked && checked.value === 'industry_board';
        wrap.style.display = show ? 'flex' : 'none';
    },

    /** 显示/隐藏「概念板块」选择行 */
    syncGmsConceptBoardWrap() {
        const wrap = document.getElementById('gmsConceptBoardWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="gmsScope"]:checked');
        const show = checked && checked.value === 'concept_board';
        wrap.style.display = show ? 'flex' : 'none';
    },

    /**
     * 加载行业板块选项
     * @param {boolean} [force] 强制重新拉取
     * @returns {Promise<boolean>} 是否加载成功
     */
    async loadGmsIndustryBoardOptions(force = false) {
        if (!force && this._gmsIndustryBoardsLoaded && this.gmsIndustryBoardCatalog.length) return true;
        try {
            const res = await fetch(`${this.API_BASE_URL}/api/market/industry_board/catalog`);
            const data = await res.json();
            if (!res.ok || data.success === false) {
                throw new Error(data.message || `HTTP ${res.status}`);
            }
            const boards = Array.isArray(data.data) ? data.data : [];
            this.gmsIndustryBoardCatalog = this._dedupeGmsIndustryBoardCatalog(boards);
            this._gmsIndustryBoardsLoaded = true;
            this._applyGmsTradeObserveBoardDefaults('industry');
            return true;
        } catch (e) {
            console.warn('[GMS] 加载行业板块列表失败', e);
            this.gmsIndustryBoardCatalog = [];
            this._gmsIndustryBoardsLoaded = false;
            const summary = document.getElementById('gmsIndustryBoardSummary');
            if (summary) summary.textContent = '加载失败，请刷新页面';
            return false;
        }
    },

    /**
     * 加载概念板块选项
     * @param {boolean} [force] 强制重新拉取
     * @returns {Promise<boolean>} 是否加载成功
     */
    async loadGmsConceptBoardOptions(force = false) {
        if (!force && this._gmsConceptBoardsLoaded && this.gmsConceptBoardCatalog.length) return true;
        try {
            const res = await fetch(`${this.API_BASE_URL}/api/market/concept_board`);
            const data = await res.json();
            if (!res.ok || data.success === false) {
                throw new Error(data.message || `HTTP ${res.status}`);
            }
            const boards = Array.isArray(data.data) ? data.data : [];
            const mapped = boards.map((b) => {
                const source = this._gmsBoardSourceValue(b);
                const count = Number(b?.stock_count);
                return {
                    ...b,
                    board_code_source: source,
                    board_code_source_label: b.board_code_source_label || this._gmsBoardSourceLabel({ board_code_source: source }),
                    stock_count: Number.isFinite(count) ? count : 0,
                };
            });
            this.gmsConceptBoardCatalog = this._dedupeGmsConceptBoardCatalog(mapped);
            this._gmsConceptBoardsLoaded = true;
            this._applyGmsTradeObserveBoardDefaults('concept');
            return true;
        } catch (e) {
            console.warn('[GMS] 加载概念板块列表失败', e);
            this.gmsConceptBoardCatalog = [];
            this._gmsConceptBoardsLoaded = false;
            const summary = document.getElementById('gmsConceptBoardSummary');
            if (summary) summary.textContent = '加载失败，请刷新页面';
            return false;
        }
    },

    /** 显示/隐藏「单只股票」输入行 */
    syncGmsSingleStockWrap() {
        const wrap = document.getElementById('gmsSingleStockWrap');
        if (!wrap) return;
        const checked = document.querySelector('input[name="gmsScope"]:checked');
        const show = checked && checked.value === 'single';
        wrap.style.display = show ? 'flex' : 'none';
    },

    /**
     * 将用户输入的股票代码或名称解析为代码（本地缓存优先，否则 /api/stock/list）
     * @returns {Promise<string|null>}
     */
    async resolveGmsSingleStockKeyword(keywordRaw) {
        const keyword = String(keywordRaw || '').trim();
        if (!keyword) return null;

        let code = keyword.replace(/\s/g, '');
        if (/^(sh|sz)/i.test(code)) code = code.slice(2);
        if (/^\d{4,6}$/.test(code)) {
            if (code.length <= 5) return code.padStart(5, '0');
            return code.padStart(6, '0');
        }

        const lower = keyword.toLowerCase();
        try {
            const cached = localStorage.getItem('stockBasicInfo');
            if (cached) {
                const stocks = JSON.parse(cached);
                if (Array.isArray(stocks)) {
                    const exactCode = stocks.find((s) => String(s.code || '').trim().toLowerCase() === lower);
                    if (exactCode) return String(exactCode.code).trim();
                    const exactName = stocks.find((s) => String(s.name || '').trim() === keyword);
                    if (exactName) return String(exactName.code).trim();
                    const fuzzy = stocks.find((s) => {
                        const c = String(s.code || '').toLowerCase();
                        const n = String(s.name || '').toLowerCase();
                        return c.includes(lower) || n.includes(lower);
                    });
                    if (fuzzy) return String(fuzzy.code).trim();
                }
            }
        } catch (e) {
            console.warn('[GMS] 本地股票缓存解析失败', e);
        }

        const fetchFn = this.getAuthFetchFn();
        const url = `${this.API_BASE_URL}/api/stock/list?query=${encodeURIComponent(keyword)}&limit=10`;
        const res = await fetchFn(url);
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.success || !Array.isArray(data.data) || data.data.length === 0) {
            return null;
        }
        const exactCode = data.data.find((s) => String(s.code || '').trim().toLowerCase() === lower);
        if (exactCode) return String(exactCode.code).trim();
        const exactName = data.data.find((s) => String(s.name || '').trim() === keyword);
        if (exactName) return String(exactName.code).trim();
        return String(data.data[0].code || '').trim() || null;
    },

    // 加载头部导航
    async loadHeader() {
        try {
            const headerContainer = document.getElementById('header-container');
            if (headerContainer) {
                // 动态加载头部组件HTML
                const response = await fetch('components/header.html');
                if (response.ok) {
                    const headerHtml = await response.text();
                    headerContainer.innerHTML = headerHtml;

                    // 等待DOM更新后初始化头部功能
                    setTimeout(() => {
                        // 高亮当前频道
                        const nav = document.getElementById('nav-screening');
                        if (nav) {
                            nav.classList.add('active');
                        }

                        // 初始化用户菜单
                        if (typeof initUserMenu === 'function') {
                            initUserMenu();
                        }

                        // 初始化股票搜索功能
                        if (typeof initStockSearch === 'function') {
                            initStockSearch();
                        } else {
                            console.warn('initStockSearch函数未找到，等待header.js加载');
                            // 等待header.js加载完成
                            const checkInterval = setInterval(() => {
                                if (typeof initStockSearch === 'function') {
                                    initStockSearch();
                                    clearInterval(checkInterval);
                                }
                            }, 100);

                            // 5秒后停止检查
                            setTimeout(() => clearInterval(checkInterval), 5000);
                        }

                        // 更新用户显示
                        if (window.CommonUtils && window.CommonUtils.auth) {
                            CommonUtils.auth.updateUserDisplay(CommonUtils.auth.getUserInfo());
                        }
                    }, 100);
                }
            }
        } catch (error) {
            console.error('加载头部导航失败:', error);
        }
    },

    // 绑定事件
    bindEvents() {
        // 绑定所有刷新按钮（仅带 data-strategy 的真正「刷新筛选」）
        // rpe / sbbr 由独立脚本（rpe_screening.js / sbbr_screening.js）自行处理，勿走通用 loadScreeningResults
        const externalRefreshStrategies = new Set(['rpe', 'sbbr']);
        document.querySelectorAll('.refresh-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const strategy = btn.dataset.strategy;
                if (!strategy || externalRefreshStrategies.has(strategy)) return;
                this.loadScreeningResults(strategy);
            });
        });

        // 绑定各策略「导出 CSV」：仅 id 为 exportBtn-<策略名> 的按钮（与 GMS 导出 Excel、观察股池导出 Excel、定位清除等区分）
        document.querySelectorAll('.export-btn').forEach(btn => {
            if (btn.id === 'exportExcelBtn-gms') return; // GMS Excel 单独绑定
            if (!btn.id || !btn.id.startsWith('exportBtn-')) return;
            btn.addEventListener('click', () => {
                const strategy = btn.id.replace('exportBtn-', '');
                if (strategy === 'gms') {
                    void this.exportGmsCsvFull();
                } else {
                    this.exportToCSV(strategy);
                }
            });
        });
        const exportExcelBtnGms = document.getElementById('exportExcelBtn-gms');
        if (exportExcelBtnGms) {
            exportExcelBtnGms.addEventListener('click', () => void this.exportToExcelGms());
        }
        const gmsLocateBtn = document.getElementById('gmsLocateBtn');
        const gmsLocateClearBtn = document.getElementById('gmsLocateClearBtn');
        const gmsLocateInput = document.getElementById('gmsLocateInput');
        if (gmsLocateBtn) {
            gmsLocateBtn.addEventListener('click', () => void this.locateGmsStock());
        }
        if (gmsLocateClearBtn) {
            gmsLocateClearBtn.addEventListener('click', () => {
                this.gmsLocateActive = false;
                if (gmsLocateInput) gmsLocateInput.value = '';
                const hint = document.getElementById('gmsLocateHint');
                if (hint) {
                    hint.textContent = '';
                    hint.style.display = 'none';
                }
                gmsLocateClearBtn.style.display = 'none';
                void this.loadScreeningResults('gms', { resetGmsPage: false });
            });
        }
        if (gmsLocateInput) {
            gmsLocateInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    void this.locateGmsStock();
                }
            });
        }

        const gmsPrev = document.getElementById('gmsPaginationPrev');
        const gmsNext = document.getElementById('gmsPaginationNext');
        if (gmsPrev) {
            gmsPrev.addEventListener('click', () => {
                if (this.gmsPage <= 1) return;
                this.gmsPage -= 1;
                void this.loadScreeningResults('gms', { resetGmsPage: false });
            });
        }
        if (gmsNext) {
            gmsNext.addEventListener('click', () => {
                const bar = document.getElementById('gmsPaginationBar');
                const maxP = bar ? parseInt(bar.getAttribute('data-total-pages') || '0', 10) : 0;
                if (maxP <= 0 || this.gmsPage >= maxP) return;
                this.gmsPage += 1;
                void this.loadScreeningResults('gms', { resetGmsPage: false });
            });
        }

        // 绑定PVFARS策略范围切换事件
        document.querySelectorAll('input[name="pvfrsScope"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.loadScreeningResults('pvfrs');
            });
        });

        // 绑定 GMS 策略范围切换事件（仅更新 UI，不自动触发选股计算）
        document.querySelectorAll('input[name="gmsScope"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.syncGmsWatchlistMarketWrap();
                this.syncGmsCnBoardWrap();
                this.syncGmsIndustryBoardWrap();
                this.syncGmsConceptBoardWrap();
                this.syncGmsSingleStockWrap();
                const scopeEl = document.querySelector('input[name="gmsScope"]:checked');
                if (scopeEl && scopeEl.value === 'industry_board') {
                    void this.loadGmsIndustryBoardOptions().then(() => {
                        this._applyGmsTradeObserveBoardDefaults('industry');
                    });
                }
                if (scopeEl && scopeEl.value === 'concept_board') {
                    void this.loadGmsConceptBoardOptions().then(() => {
                        this._applyGmsTradeObserveBoardDefaults('concept');
                    });
                }
            });
        });
        document.querySelectorAll('input[name="gmsWatchlistMarket"]').forEach((radio) => {
            radio.addEventListener('change', () => this.syncGmsWatchlistBoardWrap());
        });
        this.syncGmsWatchlistMarketWrap();
        this.syncGmsCnBoardWrap();
        this.syncGmsIndustryBoardWrap();
        this.syncGmsConceptBoardWrap();
        this.syncGmsSingleStockWrap();
        const gmsSingleInput = document.getElementById('gmsSingleStockInput');
        if (gmsSingleInput) {
            gmsSingleInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const scopeEl = document.querySelector('input[name="gmsScope"]:checked');
                    if (scopeEl && scopeEl.value === 'single') {
                        e.preventDefault();
                        void this.loadScreeningResults('gms');
                    }
                }
            });
        }

        // URT 数据来源切换（仅更新 UI，不自动触发选股）
        document.querySelectorAll('input[name="urtScope"]').forEach((radio) => {
            radio.addEventListener('change', () => {
                this.syncUrtCnBoardWrap();
                this.syncUrtIndustryBoardWrap();
                this.syncUrtConceptBoardWrap();
                this.syncUrtSingleStockWrap();
                this.syncUrtFilterParamsForScope();
                const scopeEl = document.querySelector('input[name="urtScope"]:checked');
                if (scopeEl && scopeEl.value === 'industry_board') {
                    void this.loadGmsIndustryBoardOptions();
                }
                if (scopeEl && scopeEl.value === 'concept_board') {
                    void this.loadGmsConceptBoardOptions();
                }
            });
        });
        this.syncUrtCnBoardWrap();
        this.syncUrtIndustryBoardWrap();
        this.syncUrtConceptBoardWrap();
        this.syncUrtSingleStockWrap();
        this.syncUrtFilterParamsForScope();
        const urtSingleInput = document.getElementById('urtSingleStockInput');
        if (urtSingleInput) {
            urtSingleInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const scopeEl = document.querySelector('input[name="urtScope"]:checked');
                    if (scopeEl && scopeEl.value === 'single') {
                        e.preventDefault();
                        void this.loadScreeningResults('urt');
                    }
                }
            });
        }

        // GMS 策略参数：保存 / 同步
        const gmsParamsSaveBtn = document.getElementById('gmsParamsSaveBtn');
        if (gmsParamsSaveBtn) {
            gmsParamsSaveBtn.addEventListener('click', () => this.saveGmsParams());
        }
        const gmsParamsSyncBtn = document.getElementById('gmsParamsSyncBtn');
        if (gmsParamsSyncBtn) {
            gmsParamsSyncBtn.addEventListener('click', () => this.syncGmsParamsFromServer());
        }
        const gmsConfigSelect = document.getElementById('gms-config_id');
        if (gmsConfigSelect) {
            gmsConfigSelect.addEventListener('change', () => {
                const v = gmsConfigSelect.value;
                this.gmsConfigId = v ? parseInt(v, 10) : null;
                void this.syncGmsParamsFromServer(this.gmsConfigId);
            });
        }
        this.initGmsParamOverrideCollapse();

        // GMS 得分明细：点击「得分明细」展开/收起（事件委托）
        const gmsContainer = document.getElementById('resultsContainer-gms');
        if (gmsContainer) {
            gmsContainer.addEventListener('click', (e) => {
                const observeBtn = e.target.closest('.gms-trade-observe-add');
                if (observeBtn) {
                    e.preventDefault();
                    const rowIndex = observeBtn.getAttribute('data-row');
                    if (rowIndex != null && rowIndex !== '') {
                        void this.addGmsTradeObserveFromRow(parseInt(rowIndex, 10), observeBtn);
                    }
                    return;
                }
                const addBtn = e.target.closest('.gms-watchlist-add');
                if (addBtn) {
                    e.preventDefault();
                    const code = addBtn.getAttribute('data-code') || '';
                    const name = addBtn.getAttribute('data-name') || '';
                    void this.addGmsRowToWatchlist(code, name, addBtn);
                    return;
                }
                const btn = e.target.closest('.gms-score-detail-toggle');
                if (!btn) return;
                e.preventDefault();
                const rowIndex = btn.getAttribute('data-row');
                const tbody = document.getElementById('resultsTableBody-gms');
                if (!tbody) return;
                const detailRow = tbody.querySelector(`tr.gms-score-detail-row[data-detail-for="${rowIndex}"]`);
                if (detailRow) {
                    detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
                }
            });
        }

        // URT 得分明细：展开/收起（风格对齐 GMS）
        const urtContainer = document.getElementById('resultsContainer-urt');
        if (urtContainer) {
            urtContainer.addEventListener('click', (e) => {
                const observeBtn = e.target.closest('.urt-trade-observe-add');
                if (observeBtn) {
                    e.preventDefault();
                    const rowIndex = observeBtn.getAttribute('data-row');
                    if (rowIndex != null && rowIndex !== '') {
                        void this.addUrtTradeObserveFromRow(parseInt(rowIndex, 10), observeBtn);
                    }
                    return;
                }
                const btn = e.target.closest('.urt-score-detail-toggle');
                if (!btn) return;
                e.preventDefault();
                const rowIndex = btn.getAttribute('data-row');
                const tbody = document.getElementById('resultsTableBody-urt');
                if (!tbody) return;
                const detailRow = tbody.querySelector(`tr.urt-score-detail-row[data-detail-for="${rowIndex}"]`);
                if (detailRow) {
                    detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
                }
            });
        }

        // PVFARS 策略参数：保存按钮
        const pvfrsParamsSaveBtn = document.getElementById('pvfrsParamsSaveBtn');
        if (pvfrsParamsSaveBtn) {
            pvfrsParamsSaveBtn.addEventListener('click', () => this.savePvfrsParams());
        }

        // PVFARS 得分明细：点击「得分明细」展开/收起（事件委托，绑定在结果容器上）
        const pvfrsContainer = document.getElementById('resultsContainer-pvfrs');
        if (pvfrsContainer) {
            pvfrsContainer.addEventListener('click', (e) => {
                const btn = e.target.closest('.pvfrs-score-detail-toggle');
                if (!btn) return;
                e.preventDefault();
                const rowIndex = btn.getAttribute('data-row');
                const tbody = document.getElementById('resultsTableBody-pvfrs');
                if (!tbody) return;
                const detailRow = tbody.querySelector(`tr.pvfrs-score-detail-row[data-detail-for="${rowIndex}"]`);
                if (detailRow) {
                    detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
                }
            });
        }
    },

    getAuthFetchFn() {
        return (typeof authFetch === 'function')
            ? authFetch
            : async (url, options) => {
                const token = localStorage.getItem('access_token');
                const headers = options?.headers || {};
                if (token) {
                    headers['Authorization'] = 'Bearer ' + token;
                }
                return fetch(url, { ...options, headers });
            };
    },

    async handleHttpAndParseScreening(strategy, response) {
        const contentType = response.headers.get('Content-Type') || '';
        const text = await response.text();
        const gateway502Msg =
            strategy === 'gms'
                ? '网关502/503：全A股 GMS 耗时常达数分钟。请确认 Nginx 已用 location ^~ /api/screening/gms-strategy 且 proxy_read_timeout≥600s，并已 nginx -t 与 reload；若经 Cloudflare 等 CDN，免费版约 100s 也会断连。也可改用「港股」或「自选股」。'
                : '服务暂时不可用，请稍后重试';
        if (!response.ok) {
            if (response.status === 504) {
                throw new Error(
                    strategy === 'gms'
                        ? '请求超时(504)，全A股 GMS 计算耗时较长，请稍后重试或缩小股票范围'
                        : '请求超时(504)，选股计算耗时较长，请稍后重试'
                );
            }
            if (response.status === 502 || response.status === 503) {
                throw new Error(gateway502Msg);
            }
            let errMsg = `请求失败(${response.status})`;
            if (contentType.includes('application/json') && text && text.trim().startsWith('{')) {
                try {
                    const errBody = JSON.parse(text);
                    errMsg = errBody.detail || errBody.message || errMsg;
                    if (typeof errMsg !== 'string') {
                        errMsg = JSON.stringify(errMsg);
                    }
                } catch (_) {
                    if (text.length < 200) errMsg = text;
                }
            } else if (text && text.length < 200) {
                errMsg = text;
            }
            throw new Error(errMsg);
        }
        let parsed;
        try {
            if (!contentType.includes('application/json') || !text || !text.trim().startsWith('{')) {
                throw new Error('服务器返回了非 JSON 数据，请稍后重试');
            }
            parsed = JSON.parse(text);
        } catch (parseError) {
            if (parseError instanceof SyntaxError) {
                throw new Error('服务返回异常，请稍后重试');
            }
            throw parseError;
        }
        return parsed;
    },

    /**
     * 构建 GMS 接口查询串（不含 trace_only）
     * @param {{ page?: number, includePagination?: boolean, resolvedSingleCode?: string }} options
     */
    getGmsQuerySearchParams(options = {}) {
        const includePagination = options.includePagination !== false;
        const page = options.page != null ? options.page : this.gmsPage;
        const scopeElement = document.querySelector('input[name="gmsScope"]:checked');
        const scope = scopeElement ? scopeElement.value : 'all';
        const gmsParams = this.getGmsParams();
        const q = new URLSearchParams();
        if (scope === 'single') {
            const code = options.resolvedSingleCode || '';
            if (code) q.set('code', code);
            q.set('scope', 'cn');
        } else {
            q.set('scope', scope);
        }
        if (scope === 'gms_watchlist') {
            const mEl = document.querySelector('input[name="gmsWatchlistMarket"]:checked');
            q.set('gms_watchlist_market', mEl ? mEl.value : 'all');
            const segEl = document.querySelector('input[name="gmsWatchlistBoardSegment"]:checked');
            const seg = segEl ? segEl.value : 'ALL';
            if (seg && seg !== 'ALL' && (!mEl || mEl.value !== 'hk')) {
                q.set('cn_board_segment', seg);
            }
        }
        if (scope === 'cn' || scope === 'industry_board' || scope === 'concept_board') {
            const segEl = document.querySelector('input[name="gmsCnBoardSegment"]:checked');
            const seg = segEl ? segEl.value : 'ALL';
            if (seg && seg !== 'ALL') {
                q.set('cn_board_segment', seg);
            }
        }
        if (scope === 'industry_board') {
            this.getGmsSelectedIndustryBoardCodes().forEach((code) => q.append('industry_board_code', code));
        }
        if (scope === 'concept_board') {
            this.getGmsSelectedConceptBoardCodes().forEach((code) => q.append('concept_board_code', code));
        }
        const configEl = document.getElementById('gms-config_id');
        const configId = configEl && configEl.value ? parseInt(configEl.value, 10) : this.gmsConfigId;
        if (configId) {
            q.set('config_id', String(configId));
        }
        const overrideEl = document.getElementById('gms-param-override');
        const useOverride = overrideEl && overrideEl.checked;
        if (useOverride) {
            if (gmsParams.start_date) q.set('date', gmsParams.start_date);
            if (gmsParams.accumulation_fz_min != null) q.set('accumulation_fz_min', gmsParams.accumulation_fz_min);
            if (gmsParams.balance_ratio_max != null) q.set('balance_ratio_max', gmsParams.balance_ratio_max);
            if (gmsParams.volume_ratio_min != null) q.set('volume_ratio_min', gmsParams.volume_ratio_min);
            if (gmsParams.ratio_d20_max != null) q.set('ratio_d20_max', gmsParams.ratio_d20_max);
            if (gmsParams.volume_ratio_max != null) q.set('volume_ratio_max', gmsParams.volume_ratio_max);
            if (gmsParams.left_buy_min_accumulation != null) q.set('left_buy_min_accumulation', gmsParams.left_buy_min_accumulation);
            if (gmsParams.watch_threshold != null) q.set('watch_threshold', gmsParams.watch_threshold);
            if (gmsParams.alert_threshold != null) q.set('alert_threshold', gmsParams.alert_threshold);
            if (gmsParams.overbought_ratio != null) q.set('overbought_ratio', gmsParams.overbought_ratio);
            if (gmsParams.accumulation_s_threshold != null) q.set('accumulation_s_threshold', gmsParams.accumulation_s_threshold);
            if (gmsParams.accumulation_a_threshold != null) q.set('accumulation_a_threshold', gmsParams.accumulation_a_threshold);
            if (gmsParams.momentum_full_threshold != null) q.set('momentum_full_threshold', gmsParams.momentum_full_threshold);
            if (gmsParams.momentum_batch_threshold != null) q.set('momentum_batch_threshold', gmsParams.momentum_batch_threshold);
            if (gmsParams.instant_deviation_stable_days != null) q.set('instant_deviation_stable_days', gmsParams.instant_deviation_stable_days);
            if (gmsParams.weight_acc_fz != null) q.set('weight_acc_fz', gmsParams.weight_acc_fz);
            if (gmsParams.weight_acc_balance != null) q.set('weight_acc_balance', gmsParams.weight_acc_balance);
            if (gmsParams.weight_acc_volume != null) q.set('weight_acc_volume', gmsParams.weight_acc_volume);
            if (gmsParams.weight_mom_ratio_d1 != null) q.set('weight_mom_ratio_d1', gmsParams.weight_mom_ratio_d1);
            if (gmsParams.weight_mom_deviation != null) q.set('weight_mom_deviation', gmsParams.weight_mom_deviation);
            if (gmsParams.weight_mom_volume != null) q.set('weight_mom_volume', gmsParams.weight_mom_volume);
        } else if (gmsParams.start_date) {
            q.set('date', gmsParams.start_date);
        }
        const excludeStEl = document.getElementById('gmsExcludeSt');
        if (excludeStEl && excludeStEl.checked) {
            q.set('exclude_st', 'true');
        }
        if (scope === 'single') {
            q.set('use_pagination', 'false');
        } else if (includePagination) {
            q.set('use_pagination', 'true');
            q.set('page', String(page));
            q.set('page_size', String(this.GMS_PAGE_SIZE));
        } else {
            q.set('use_pagination', 'false');
        }
        return q;
    },

    /** 构建 GMS 查询串（含单只股票代码解析） */
    async buildGmsQuerySearchParams(options = {}) {
        const scopeElement = document.querySelector('input[name="gmsScope"]:checked');
        const scope = scopeElement ? scopeElement.value : 'all';
        if (scope === 'industry_board') {
            if (this.getGmsSelectedIndustryBoardCodes().length === 0) {
                throw new Error('请选择至少一个行业板块');
            }
        }
        if (scope === 'concept_board') {
            if (this.getGmsSelectedConceptBoardCodes().length === 0) {
                throw new Error('请选择至少一个概念板块');
            }
        }
        if (scope === 'single') {
            const inputEl = document.getElementById('gmsSingleStockInput');
            const raw = inputEl ? String(inputEl.value || '').trim() : '';
            if (!raw) {
                throw new Error('请输入股票代码或名称');
            }
            const resolved = await this.resolveGmsSingleStockKeyword(raw);
            if (!resolved) {
                throw new Error(`未找到与「${raw}」匹配的股票`);
            }
            return this.getGmsQuerySearchParams({
                ...options,
                resolvedSingleCode: resolved,
                includePagination: false,
            });
        }
        return this.getGmsQuerySearchParams(options);
    },

    /** 构建 URT 选股查询参数（数据来源对齐 GMS） */
    async buildUrtQuerySearchParams() {
        const scopeElement = document.querySelector('input[name="urtScope"]:checked');
        const scope = scopeElement ? scopeElement.value : 'cn';
        if (scope === 'industry_board') {
            if (this.getUrtSelectedIndustryBoardCodes().length === 0) {
                throw new Error('请选择至少一个行业板块');
            }
        }
        if (scope === 'concept_board') {
            if (this.getUrtSelectedConceptBoardCodes().length === 0) {
                throw new Error('请选择至少一个概念板块');
            }
        }
        if (scope === 'single') {
            const inputEl = document.getElementById('urtSingleStockInput');
            const raw = inputEl ? String(inputEl.value || '').trim() : '';
            if (!raw) {
                throw new Error('请输入股票代码或名称');
            }
        }

        const params = new URLSearchParams();
        params.set('scope', scope);

        if (scope === 'cn' || scope === 'industry_board' || scope === 'concept_board') {
            document.querySelectorAll('input[name="urtCnBoardSegment"]:checked').forEach((cb) => {
                const v = cb && cb.value ? String(cb.value).trim().toUpperCase() : '';
                if (v && v !== 'ALL') params.append('cn_board_segment', v);
            });
        }
        if (scope === 'industry_board') {
            this.getUrtSelectedIndustryBoardCodes().forEach((code) => {
                params.append('industry_board_code', code);
            });
        }
        if (scope === 'concept_board') {
            this.getUrtSelectedConceptBoardCodes().forEach((code) => {
                params.append('concept_board_code', code);
            });
        }
        if (scope === 'single') {
            const inputEl = document.getElementById('urtSingleStockInput');
            params.set('stock_code', String(inputEl?.value || '').trim());
        }

        const urtDateEl = document.getElementById('urtScreeningDate');
        if (urtDateEl && urtDateEl.value) {
            params.set('date', urtDateEl.value);
        }
        if (scope === 'cn' || scope === 'hk') {
            const limEl = document.getElementById('urtLimit');
            const limRaw = limEl && limEl.value != null ? String(limEl.value).trim() : '';
            if (limRaw !== '') {
                const lim = parseInt(limRaw, 10);
                if (!isNaN(lim) && lim > 0) params.set('limit', String(lim));
            }
        }
        const configEl = document.getElementById('urt-config_id');
        const cid = configEl && configEl.value ? parseInt(configEl.value, 10) : NaN;
        if (!isNaN(cid) && cid > 0) params.set('config_id', String(cid));

        // 单只股票：不传筛选参数，后端跳过硬筛/最低得分，直接计算信号
        if (scope !== 'single') {
            const vm = parseFloat(document.getElementById('urtVolumeMultiple')?.value);
            if (!isNaN(vm) && vm > 0) params.set('volume_multiple', String(vm));
            const ms = parseFloat(document.getElementById('urtMinScore')?.value);
            if (!isNaN(ms) && ms >= 0) params.set('min_score', String(ms));
        }
        return params;
    },

    /** 加载 URT 策略参数版本列表（切换后不自动刷新，须点「刷新筛选」） */
    async initUrtStrategyConfig() {
        const selectEl = document.getElementById('urt-config_id');
        if (!selectEl) return;
        selectEl.innerHTML = '<option value="">加载中…</option>';
        try {
            const res = await fetch(`${this.API_BASE_URL}/api/frontend/urt/strategy-configs`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            if (!json.success) throw new Error(json.detail || json.message || '接口返回失败');
            const list = json.data || [];
            if (!list.length) {
                selectEl.innerHTML = '<option value="">暂无可用参数版本</option>';
                return;
            }
            const defaultId = json.default_config_id;
            let preferId = null;
            try {
                const saved = sessionStorage.getItem('urtScreeningConfigId');
                if (saved) preferId = parseInt(saved, 10);
            } catch (_) { /* ignore */ }
            selectEl.innerHTML = '';
            list.forEach((item) => {
                const opt = document.createElement('option');
                opt.value = String(item.id);
                const label = item.version_label
                    ? `${item.name}（${item.version_label}）`
                    : item.name;
                opt.textContent = item.is_default ? `${label}（默认）` : label;
                selectEl.appendChild(opt);
            });
            const ids = new Set(list.map((x) => x.id));
            let selected = preferId && ids.has(preferId) ? preferId : defaultId;
            if (selected == null || !ids.has(selected)) selected = list[0].id;
            selectEl.value = String(selected);
            this.urtConfigId = selected;
            if (!selectEl._urtConfigBound) {
                selectEl.addEventListener('change', () => {
                    const v = parseInt(selectEl.value, 10);
                    this.urtConfigId = !isNaN(v) ? v : null;
                    try {
                        if (this.urtConfigId != null) {
                            sessionStorage.setItem('urtScreeningConfigId', String(this.urtConfigId));
                        }
                    } catch (_) { /* ignore */ }
                });
                selectEl._urtConfigBound = true;
            }
        } catch (e) {
            console.error('initUrtStrategyConfig:', e);
            selectEl.innerHTML = '<option value="">参数版本加载失败</option>';
        }
    },

    /** GMS：按代码/名称精准定位（全量拉取后匹配） */
    async locateGmsStock() {
        const inputEl = document.getElementById('gmsLocateInput');
        const clearBtn = document.getElementById('gmsLocateClearBtn');
        const hintEl = document.getElementById('gmsLocateHint');
        const keywordRaw = inputEl ? String(inputEl.value || '').trim() : '';
        if (!keywordRaw) {
            if (window.CommonUtils) CommonUtils.showToast('请输入股票代码或名称', 'warning');
            return;
        }
        const keyword = keywordRaw.toLowerCase();
        try {
            const q = this.getGmsQuerySearchParams({ includePagination: false });
            const result = await this.fetchGmsStrategyResult(q.toString());
            if (!result.success || !Array.isArray(result.data)) {
                throw new Error(result.message || '定位查询失败');
            }
            const fullData = result.data;
            const exactCode = fullData.find((r) => {
                const code = String(r.symbol || r.code || '').trim().toLowerCase();
                return code === keyword;
            });
            const exactName = exactCode ? null : fullData.find((r) => {
                const name = String(r.name || '').trim().toLowerCase();
                return name === keyword;
            });
            const fuzzy = (!exactCode && !exactName) ? fullData.find((r) => {
                const code = String(r.symbol || r.code || '').trim().toLowerCase();
                const name = String(r.name || '').trim().toLowerCase();
                return code.includes(keyword) || name.includes(keyword);
            }) : null;
            const hit = exactCode || exactName || fuzzy;
            if (!hit) {
                if (window.CommonUtils) CommonUtils.showToast(`未找到“${keywordRaw}”对应的股票`, 'warning');
                if (hintEl) {
                    hintEl.textContent = `未找到“${keywordRaw}”`;
                    hintEl.style.display = 'inline-block';
                }
                return;
            }
            this.gmsLocateActive = true;
            this.lastResults.gms = [hit];
            if (result.search_date) {
                this.lastGmsSearchDate = String(result.search_date).slice(0, 10);
            }
            await this.loadGmsObservedCodeSets();
            this.renderResults([hit], result.search_date, 'gms', null, { enabled: false });
            this._refreshGmsTradeObserveButtonsInSignalTable();
            this.updateGmsPaginationUi({ enabled: false });
            if (clearBtn) clearBtn.style.display = 'inline-block';
            if (hintEl) {
                const hitCode = String(hit.symbol || hit.code || '');
                const hitName = String(hit.name || '--');
                hintEl.textContent = `定位结果：${hitCode} ${hitName}`;
                hintEl.style.display = 'inline-block';
            }
            const searchDate = document.getElementById('searchDate-gms');
            if (searchDate && result.search_date) searchDate.textContent = `筛选时间: ${result.search_date}`;
        } catch (e) {
            const msg = e && e.message ? e.message : String(e);
            if (window.CommonUtils) CommonUtils.showToast(`定位失败: ${msg}`, 'warning');
        }
    },

    /** GMS：先 trace_only 再按需全量，queryString 已含分页或全量参数 */
    async fetchGmsStrategyResult(queryString) {
        const apiBaseUrl = this.API_BASE_URL;
        const fetchFn = this.getAuthFetchFn();
        const traceUrl = `${apiBaseUrl}/api/screening/gms-strategy?${queryString}&trace_only=true`;
        let result = await this.handleHttpAndParseScreening('gms', await fetchFn(traceUrl));
        const meta = result.gms_trace_meta || {};
        // 二次全量计算仅在几乎无缓存时触发，避免「有预计算仍再算一遍全市场」
        const fromTrace = Number(meta.from_trace_count || 0);
        const hitRate = Number(meta.trace_hit_rate || 0);
        const layer = String(meta.cache_layer || '');
        const needFullCompute =
            meta.trace_complete !== true &&
            layer !== 'snapshot' &&
            (fromTrace === 0 || hitRate < 0.5);
        if (needFullCompute) {
            const fullUrl = `${apiBaseUrl}/api/screening/gms-strategy?${queryString}`;
            result = await this.handleHttpAndParseScreening('gms', await fetchFn(fullUrl));
        }
        return result;
    },

    updateGmsPaginationUi(paging) {
        const bar = document.getElementById('gmsPaginationBar');
        const label = document.getElementById('gmsPaginationLabel');
        const prev = document.getElementById('gmsPaginationPrev');
        const next = document.getElementById('gmsPaginationNext');
        if (!bar || !label) return;
        if (!paging || !paging.enabled) {
            bar.style.display = 'none';
            return;
        }
        const total = paging.total != null ? paging.total : 0;
        const totalPages = paging.total_pages != null ? paging.total_pages : 0;
        const page = paging.page != null ? paging.page : this.gmsPage;
        this.gmsPage = page;
        bar.style.display = 'flex';
        bar.setAttribute('data-total-pages', String(Math.max(0, totalPages)));
        label.textContent = totalPages > 0 ? `第 ${page} / ${totalPages} 页` : '';
        if (prev) prev.disabled = page <= 1 || total <= 0;
        if (next) next.disabled = totalPages <= 0 || page >= totalPages;
    },

    /** GMS 列表行：加入自选股 */
    async addGmsRowToWatchlist(stockCode, stockName, btnEl) {
        const code = String(stockCode || '').trim();
        const name = String(stockName || '').trim() || code;
        if (!code) {
            if (window.CommonUtils) CommonUtils.showToast('股票代码无效，无法加入自选', 'warning');
            return;
        }
        const user = (window.CommonUtils && CommonUtils.auth) ? CommonUtils.auth.getUserInfo() : null;
        if (!user || !user.id) {
            if (window.CommonUtils) CommonUtils.showToast('请先登录后再操作自选股', 'warning');
            window.location.href = 'login.html';
            return;
        }

        const fetchFn = this.getAuthFetchFn();
        try {
            if (btnEl) {
                btnEl.disabled = true;
                btnEl.textContent = '处理中...';
            }
            const res = await fetchFn(`${this.API_BASE_URL}/api/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: user.id,
                    stock_code: code,
                    stock_name: name,
                    group_name: 'default',
                }),
            });
            const result = await res.json().catch(() => ({}));
            if (res.ok && result.success) {
                if (window.CommonUtils) CommonUtils.showToast(`已添加 ${name} 到自选股`, 'success');
                if (btnEl) {
                    btnEl.textContent = '已自选';
                    btnEl.classList.add('is-added');
                    btnEl.disabled = true;
                }
                return;
            }
            const msg = result.message || `添加失败(${res.status})`;
            if (window.CommonUtils) CommonUtils.showToast(msg, 'warning');
            if (btnEl) {
                btnEl.textContent = '+自选';
                btnEl.disabled = false;
            }
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast('网络错误，添加自选失败', 'error');
            if (btnEl) {
                btnEl.textContent = '+自选';
                btnEl.disabled = false;
            }
        }
    },

    // 加载选股结果
    async loadScreeningResults(strategy = null, options = {}) {
        const resetGmsPage = options.resetGmsPage !== false;
        if (!strategy) {
            strategy = this.currentStrategy;
        }
        // 比价效应 / 做小做底由独立模块刷新，避免落入「未知的策略类型」
        if (strategy === 'rpe' || strategy === 'sbbr') {
            return;
        }
        if (strategy === 'gms' && resetGmsPage) {
            this.gmsPage = 1;
        }

        let suffix;
        if (strategy === 'cyb-midline') {
            suffix = 'cyb';
        } else if (strategy === 'parking-apron') {
            suffix = 'parking';
        } else if (strategy === 'backtrace-ma250') {
            suffix = 'backtrace';
        } else if (strategy === 'high-tight-flag') {
            suffix = 'high-tight';
        } else if (strategy === 'keep-increasing') {
            suffix = 'keep-increasing';
        } else if (strategy === 'long-lower-shadow') {
            suffix = 'long-lower-shadow';
        } else if (strategy === 'low-nine') {
            suffix = 'low-nine';
        } else if (strategy === 'one-yang-three-lines') {
            suffix = 'one-yang-three-lines';
        } else if (strategy === 'pvfrs') {
            suffix = 'pvfrs';
        } else if (strategy === 'gms') {
            suffix = 'gms';
        } else if (strategy === 'volume-shrink-breakout') {
            suffix = 'volume-shrink-breakout';
        } else if (strategy === 'urt') {
            suffix = 'urt';
        } else {
            suffix = 'cyb';
        }
        const loadingIndicator = document.getElementById(`loadingIndicator-${suffix}`);
        const errorMessage = document.getElementById(`errorMessage-${suffix}`);
        const resultsTableBody = document.getElementById(`resultsTableBody-${suffix}`);
        const resultsCount = document.getElementById(`resultsCount-${suffix}`);
        const refreshBtn = document.getElementById(`refreshBtn-${strategy}`);
        const exportBtn = document.getElementById(`exportBtn-${strategy}`);
        const searchDate = document.getElementById(`searchDate-${suffix}`);

        // 显示加载状态
        if (loadingIndicator) {
            loadingIndicator.style.display = 'flex';
        }
        if (errorMessage) {
            errorMessage.style.display = 'none';
            errorMessage.textContent = '';
        }
        if (refreshBtn) {
            refreshBtn.disabled = true;
        }
        if (exportBtn) {
            exportBtn.style.display = 'none';
        }
        if (strategy === 'gms') {
            const excelBtn = document.getElementById('exportExcelBtn-gms');
            if (excelBtn) excelBtn.style.display = 'none';
            this.gmsLocateActive = false;
            const hint = document.getElementById('gmsLocateHint');
            if (hint) {
                hint.textContent = '';
                hint.style.display = 'none';
            }
            const clearBtn = document.getElementById('gmsLocateClearBtn');
            if (clearBtn) clearBtn.style.display = 'none';
        }

        try {
            // 获取API基础URL
            const apiBaseUrl = this.API_BASE_URL;
            let url;
            let gmsQueryString = null;

            if (strategy === 'cyb-midline') {
                url = `${apiBaseUrl}/api/screening/cyb-midline-strategy?months=4`;
            } else if (strategy === 'parking-apron') {
                url = `${apiBaseUrl}/api/screening/parking-apron-strategy`;
            } else if (strategy === 'backtrace-ma250') {
                url = `${apiBaseUrl}/api/screening/backtrace-ma250-strategy`;
            } else if (strategy === 'high-tight-flag') {
                url = `${apiBaseUrl}/api/screening/high-tight-flag-strategy`;
            } else if (strategy === 'keep-increasing') {
                url = `${apiBaseUrl}/api/screening/keep-increasing-strategy`;
            } else if (strategy === 'long-lower-shadow') {
                // 读取参数并转换为数字
                let lowerShadowRatio = parseFloat(document.getElementById('lowerShadowRatio')?.value);
                if (isNaN(lowerShadowRatio)) lowerShadowRatio = 1.0;

                let upperShadowRatio = parseFloat(document.getElementById('upperShadowRatio')?.value);
                if (isNaN(upperShadowRatio)) upperShadowRatio = 0.3;

                let minAmplitude = parseFloat(document.getElementById('minAmplitude')?.value);
                if (isNaN(minAmplitude)) minAmplitude = 0.02;

                // 智能处理振幅参数：如果用户输入 > 0.5（可能是百分比），则自动除以100
                // 例如：输入 2 -> 0.02, 输入 5 -> 0.05
                if (minAmplitude > 0.5) {
                    console.log(`[长下影线] 检测到振幅参数 ${minAmplitude} > 0.5，自动转换为 ${minAmplitude / 100}`);
                    minAmplitude = minAmplitude / 100;
                }

                let recentDays = parseInt(document.getElementById('recentDays')?.value);
                if (isNaN(recentDays)) recentDays = 2;

                // 构造带参数的URL
                url = `${apiBaseUrl}/api/screening/long-lower-shadow-strategy?` +
                    `lower_shadow_ratio=${lowerShadowRatio}&` +
                    `upper_shadow_ratio=${upperShadowRatio}&` +
                    `min_amplitude=${minAmplitude}&` +
                    `recent_days=${recentDays}`;
            } else if (strategy === 'low-nine') {
                url = `${apiBaseUrl}/api/screening/low-nine-strategy`;
            } else if (strategy === 'one-yang-three-lines') {
                // 获取一阳穿三线策略参数
                const params = this.getOneYangThreeLinesParams();
                const queryString = new URLSearchParams(params).toString();
                url = `${apiBaseUrl}/api/screening/one-yang-three-lines?${queryString}`;
            } else if (strategy === 'pvfrs') {
                // 读取股票范围参数
                const scopeElement = document.querySelector('input[name="pvfrsScope"]:checked');
                let scope = scopeElement ? scopeElement.value : 'all';

                url = `${apiBaseUrl}/api/screening/pvfrs-strategy?scope=${scope}`;
            } else if (strategy === 'gms') {
                const gmsQ = await this.buildGmsQuerySearchParams({
                    page: this.gmsPage,
                    includePagination: true,
                });
                gmsQueryString = gmsQ.toString();
            } else if (strategy === 'volume-shrink-breakout') {
                const params = new URLSearchParams();
                params.set('scope', 'all');
                const vsbDateEl = document.getElementById('vsbScreeningDate');
                if (vsbDateEl && vsbDateEl.value) {
                    params.set('date', vsbDateEl.value);
                }
                const limEl = document.getElementById('vsbLimit');
                const limRaw = limEl && limEl.value != null ? String(limEl.value).trim() : '';
                if (limRaw !== '') {
                    const lim = parseInt(limRaw, 10);
                    if (!isNaN(lim) && lim > 0) params.set('limit', String(lim));
                }
                const vr = parseFloat(document.getElementById('vsbVolumeRatio')?.value);
                if (!isNaN(vr) && vr > 0) params.set('volume_ratio', String(vr));
                const bmin = parseInt(document.getElementById('vsbBoomMin')?.value, 10);
                if (!isNaN(bmin) && bmin > 0) params.set('boom_lookback_min', String(bmin));
                const bmax = parseInt(document.getElementById('vsbBoomMax')?.value, 10);
                if (!isNaN(bmax) && bmax > 0) params.set('boom_lookback_max', String(bmax));
                document.querySelectorAll('input[name="vsbBoard"]:checked').forEach((cb) => {
                    const v = cb && cb.value ? String(cb.value).trim() : '';
                    if (v) params.append('boards', v);
                });
                url = `${apiBaseUrl}/api/screening/volume-shrink-breakout-strategy?${params.toString()}`;
            } else if (strategy === 'urt') {
                const params = await this.buildUrtQuerySearchParams();
                url = `${apiBaseUrl}/api/screening/urt-strategy?${params.toString()}`;
            } else {
                throw new Error('未知的策略类型');
            }

            const fetchFn = this.getAuthFetchFn();

            let result;
            if (strategy === 'gms' && gmsQueryString != null) {
                result = await this.fetchGmsStrategyResult(gmsQueryString);
            } else {
                result = await this.handleHttpAndParseScreening(strategy, await fetchFn(url));
            }

            if (result.success && result.data) {
                this.lastResults[strategy] = result.data;
                if (strategy === 'gms' && result.search_date) {
                    this.lastGmsSearchDate = String(result.search_date).slice(0, 10);
                }
                if (strategy === 'urt' && result.search_date) {
                    this.lastUrtSearchDate = String(result.search_date).slice(0, 10);
                }
                if (strategy === 'gms') {
                    const traceMeta = result.gms_trace_meta || {};
                    const configSel = document.getElementById('gms-config_id');
                    const selLabel = configSel && configSel.selectedIndex >= 0
                        ? configSel.options[configSel.selectedIndex].textContent
                        : '';
                    this.gmsConfigMeta = {
                        strategy_config_id: traceMeta.config_id || traceMeta.strategy_config_id || this.gmsConfigId,
                        strategy_config_name: traceMeta.config_name || traceMeta.strategy_config_name || selLabel.split(' · ')[0] || '',
                        scoring_mechanism: traceMeta.scoring_mechanism || '',
                        scoring_mechanism_label: traceMeta.scoring_mechanism_label || (selLabel.includes('增强版') ? '增强版·阶梯+减分' : (selLabel.includes('标准版') ? '标准版·双模块阶梯' : '')),
                    };
                }
                const emptyMsg = (result.data.length === 0 && result.message) ? result.message : null;
                const gmsPaging = strategy === 'gms' ? result.paging : null;
                if (strategy === 'gms') {
                    await this.loadGmsObservedCodeSets();
                }
                if (strategy === 'urt') {
                    await this.loadUrtObservedCodeSets();
                }
                this.renderResults(result.data, result.search_date, strategy, emptyMsg, gmsPaging);
                if (strategy === 'gms') {
                    this._refreshGmsTradeObserveButtonsInSignalTable();
                }
                if (strategy === 'urt') {
                    this._refreshUrtTradeObserveButtonsInSignalTable();
                }
                if (strategy === 'gms') {
                    if (result.paging) {
                        this.updateGmsPaginationUi(result.paging);
                    } else {
                        this.updateGmsPaginationUi({ enabled: false });
                    }
                }
                if (searchDate) {
                    let dateText = `筛选时间: ${result.search_date}`;
                    if (result.data.length > 0 && result.message) dateText += `（${result.message}）`;
                    searchDate.textContent = dateText;
                }
                // 显示导出按钮（尊重 data-perm 权限）
                if (exportBtn && result.data.length > 0) {
                    const exportPerm = exportBtn.getAttribute('data-perm');
                    const allowed = !exportPerm
                        || !window.PermissionEngine
                        || PermissionEngine.has(exportPerm);
                    if (allowed) {
                        exportBtn.style.display = 'inline-block';
                        exportBtn.removeAttribute('aria-hidden');
                    } else {
                        exportBtn.style.display = 'none';
                        exportBtn.setAttribute('aria-hidden', 'true');
                    }
                }
                if (strategy === 'gms' && result.data.length > 0) {
                    const excelBtn = document.getElementById('exportExcelBtn-gms');
                    if (excelBtn) excelBtn.style.display = 'inline-block';
                }
            } else {
                this.lastResults[strategy] = [];
                throw new Error(result.message || '未找到符合条件的股票');
            }

        } catch (error) {
            console.error('加载选股结果失败:', error);
            if (errorMessage) {
                // 处理不同类型的错误对象
                let errorMsg = '未知错误';
                if (typeof error === 'string') {
                    errorMsg = error;
                } else if (error && error.message) {
                    errorMsg = error.message;
                } else if (error && error.detail) {
                    if (Array.isArray(error.detail)) {
                        errorMsg = error.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                    } else {
                        errorMsg = JSON.stringify(error.detail);
                    }
                } else {
                    try {
                        errorMsg = JSON.stringify(error);
                        if (errorMsg === '{}') errorMsg = error.toString();
                    } catch (e) {
                        errorMsg = error.toString();
                    }
                }

                errorMessage.textContent = `加载失败: ${errorMsg}`;
                errorMessage.style.display = 'block';
            }
            let colSpan;
            if (strategy === 'cyb-midline') {
                colSpan = 12;
            } else if (strategy === 'parking-apron') {
                colSpan = 7;
            } else if (strategy === 'backtrace-ma250') {
                colSpan = 9;
            } else if (strategy === 'high-tight-flag') {
                colSpan = 7;
            } else if (strategy === 'keep-increasing') {
                colSpan = 8;
            } else if (strategy === 'long-lower-shadow') {
                colSpan = 13;
            } else if (strategy === 'low-nine') {
                colSpan = 11;
            } else if (strategy === 'one-yang-three-lines') {
                colSpan = 13;
            } else if (strategy === 'pvfrs') {
                colSpan = 12;
            } else if (strategy === 'gms') {
                colSpan = 11;
            } else if (strategy === 'volume-shrink-breakout') {
                colSpan = 16;
            } else if (strategy === 'urt') {
                colSpan = 14;
            } else {
                colSpan = 12;
            }
            if (resultsTableBody) {
                resultsTableBody.innerHTML = `<tr><td colspan="${colSpan}" class="empty-state">加载失败，请稍后重试</td></tr>`;
            }
            if (resultsCount) {
                resultsCount.textContent = '共找到 0 只符合条件的股票';
            }
            if (strategy === 'gms') {
                this.updateGmsPaginationUi({ enabled: false });
            }
        } finally {
            // 隐藏加载状态
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    },

    // 加载 PVFARS 策略参数到表单
    async loadPvfrsParams() {
        const apiBaseUrl = this.API_BASE_URL;
        const statusEl = document.getElementById('pvfrsParamsSaveStatus');
        try {
            const res = await fetch(`${apiBaseUrl}/api/screening/pvfrs-params`);
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.success) {
                if (statusEl) statusEl.textContent = json.message || '加载参数失败';
                return;
            }
            const data = json.data || {};
            const set = (id, value) => {
                const el = document.getElementById(id);
                if (!el) return;
                if (el.type === 'checkbox') el.checked = !!value;
                else if (el.tagName === 'SELECT') el.value = String(value === true || value === 'true');
                else el.value = value != null ? value : '';
            };
            set('pvfrs-observation_period', data.observation_period);
            set('pvfrs-buy_ratio_d20_max', data.buy_ratio_d20_max);
            set('pvfrs-buy_exclude_sideways', data.buy_exclude_sideways);
            set('pvfrs-buy_macro_displacement_min', data.buy_macro_displacement_min);
            set('pvfrs-buy_instant_deviation_min', data.buy_instant_deviation_min);
            set('pvfrs-buy_bias_min', data.buy_bias_min);
            set('pvfrs-buy_relative_displacement_min', data.buy_relative_displacement_min);
            if (statusEl) statusEl.textContent = '';
        } catch (e) {
            console.error('loadPvfrsParams:', e);
            if (statusEl) statusEl.textContent = '加载失败';
        }
    },

    // 保存 PVFARS 策略参数
    async savePvfrsParams() {
        const apiBaseUrl = this.API_BASE_URL;
        const statusEl = document.getElementById('pvfrsParamsSaveStatus');
        const get = (id) => {
            const el = document.getElementById(id);
            if (!el) return undefined;
            if (el.type === 'number') return el.value === '' ? undefined : parseFloat(el.value);
            if (el.tagName === 'SELECT') return el.value === 'true';
            return el.value;
        };
        const body = {
            observation_period: get('pvfrs-observation_period'),
            buy_ratio_d20_max: get('pvfrs-buy_ratio_d20_max'),
            buy_exclude_sideways: get('pvfrs-buy_exclude_sideways'),
            buy_macro_displacement_min: get('pvfrs-buy_macro_displacement_min'),
            buy_instant_deviation_min: get('pvfrs-buy_instant_deviation_min'),
            buy_bias_min: get('pvfrs-buy_bias_min'),
            buy_relative_displacement_min: get('pvfrs-buy_relative_displacement_min')
        };
        try {
            if (statusEl) statusEl.textContent = '保存中…';
            const res = await fetch(`${apiBaseUrl}/api/screening/pvfrs-params`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const json = await res.json().catch(() => ({}));
            if (res.ok && json.success) {
                if (statusEl) statusEl.textContent = '已保存';
            } else {
                if (statusEl) statusEl.textContent = json.message || '保存失败';
            }
        } catch (e) {
            console.error('savePvfrsParams:', e);
            if (statusEl) statusEl.textContent = '保存失败';
        }
    },

    // 加载 GMS 策略参数版本列表并同步表单
    async initGmsStrategyConfig() {
        const statusEl = document.getElementById('gmsParamsSaveStatus');
        const selectEl = document.getElementById('gms-config_id');
        if (!selectEl) return;
        selectEl.innerHTML = '<option value="">加载中…</option>';
        try {
            const res = await fetch(`${this.API_BASE_URL}/api/frontend/gms/strategy-configs`);
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const json = await res.json();
            if (!json.success) {
                throw new Error(json.detail || json.message || '接口返回失败');
            }
            const list = json.data || [];
            if (!list.length) {
                selectEl.innerHTML = '<option value="">暂无可用参数版本</option>';
                if (statusEl) statusEl.textContent = '服务端无启用的 GMS 参数版本';
                return;
            }
            const defaultId = json.default_config_id;
            let savedConfigId = null;
            try {
                const token = localStorage.getItem('access_token');
                if (token) {
                    const prefRes = await fetch(`${this.API_BASE_URL}/api/user/preferences/gms-screening`, {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    if (prefRes.ok) {
                        const prefJson = await prefRes.json();
                        const pref = prefJson.data || {};
                        if (pref.config_id != null) savedConfigId = parseInt(pref.config_id, 10);
                    }
                }
                if (savedConfigId == null) {
                    const saved = sessionStorage.getItem('gmsScreeningPrefs');
                    if (saved) {
                        const parsed = JSON.parse(saved);
                        if (parsed.config_id != null) savedConfigId = parseInt(parsed.config_id, 10);
                    }
                }
            } catch (_) { /* ignore */ }

            selectEl.innerHTML = '';
            list.forEach((item) => {
                const opt = document.createElement('option');
                opt.value = String(item.id);
                const nameLabels = { default: '标准版', gms_penalty: '减分版' };
                let label = nameLabels[item.name] || item.name || `v${item.id}`;
                if (item.scoring_mechanism_label) label += ` · ${item.scoring_mechanism_label}`;
                else if (item.version_label) label += ` (${item.version_label})`;
                if (item.is_default) label += ' [默认]';
                opt.textContent = label;
                selectEl.appendChild(opt);
            });
            const pickId = savedConfigId || defaultId || (list[0] && list[0].id);
            if (pickId) {
                selectEl.value = String(pickId);
                this.gmsConfigId = pickId;
            }
            await this.syncGmsParamsFromServer(this.gmsConfigId, false);
            if (statusEl) statusEl.textContent = '已与服务端默认版本对齐';
        } catch (e) {
            console.error('initGmsStrategyConfig:', e);
            selectEl.innerHTML = '<option value="">加载失败（请确认后端 API 已启动）</option>';
            if (statusEl) statusEl.textContent = '参数版本加载失败，请刷新页面或检查后端';
            this.loadGmsParams();
        }
    },

    applyGmsFlatParamsToForm(data) {
        const set = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.value = value != null && value !== '' ? value : '';
        };
        set('gms-start_date', data.start_date || '');
        set('gms-observation_period', data.observation_period);
        set('gms-ratio_d20_max', data.ratio_d20_max);
        set('gms-volume_ratio_max', data.volume_ratio_max);
        set('gms-left_buy_min_accumulation', data.left_buy_min_accumulation);
        set('gms-volume_ratio_min', data.volume_ratio_min);
        set('gms-accumulation_fz_min', data.accumulation_fz_min);
        set('gms-balance_ratio_max', data.balance_ratio_max);
        set('gms-watch_threshold', data.watch_threshold);
        set('gms-alert_threshold', data.alert_threshold);
        set('gms-overbought_ratio', data.overbought_ratio);
        set('gms-accumulation_s_threshold', data.accumulation_s_threshold);
        set('gms-accumulation_a_threshold', data.accumulation_a_threshold);
        set('gms-momentum_full_threshold', data.momentum_full_threshold);
        set('gms-momentum_batch_threshold', data.momentum_batch_threshold);
        set('gms-instant_deviation_stable_days', data.instant_deviation_stable_days);
        set('gms-weight_acc_fz', data.weight_acc_fz);
        set('gms-weight_acc_balance', data.weight_acc_balance);
        set('gms-weight_acc_volume', data.weight_acc_volume);
        set('gms-weight_mom_ratio_d1', data.weight_mom_ratio_d1);
        set('gms-weight_mom_deviation', data.weight_mom_deviation);
        set('gms-weight_mom_volume', data.weight_mom_volume);
    },

    setGmsParamOverridePanelExpanded(expanded) {
        const panel = document.getElementById('gms-param-override-panel');
        const toggle = document.getElementById('gms-param-override-toggle');
        if (!panel) return;
        panel.classList.toggle('is-collapsed', !expanded);
        panel.setAttribute('aria-hidden', expanded ? 'false' : 'true');
        if (toggle) {
            toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            const label = toggle.querySelector('.gms-param-collapse-label');
            const icon = toggle.querySelector('.gms-param-collapse-icon');
            if (label) label.textContent = expanded ? '收起参数表单' : '展开参数表单';
            if (icon) icon.textContent = expanded ? '▲' : '▼';
        }
    },

    initGmsParamOverrideCollapse() {
        const panel = document.getElementById('gms-param-override-panel');
        const toggle = document.getElementById('gms-param-override-toggle');
        const overrideEl = document.getElementById('gms-param-override');
        if (!panel) return;
        this.setGmsParamOverridePanelExpanded(false);
        if (toggle) {
            toggle.addEventListener('click', () => {
                const willExpand = panel.classList.contains('is-collapsed');
                this.setGmsParamOverridePanelExpanded(willExpand);
            });
        }
        if (overrideEl) {
            overrideEl.addEventListener('change', () => {
                if (overrideEl.checked) {
                    this.setGmsParamOverridePanelExpanded(true);
                }
            });
        }
    },

    async syncGmsParamsFromServer(configId, showToast = true) {
        const statusEl = document.getElementById('gmsParamsSaveStatus');
        const cid = configId || this.gmsConfigId;
        if (!cid) return;
        try {
            const res = await fetch(`${this.API_BASE_URL}/api/frontend/gms/strategy-configs/${cid}/form-params`);
            const json = await res.json();
            if (!json.success || !json.data) throw new Error(json.detail || '加载失败');
            this.applyGmsFlatParamsToForm(json.data.form_params || {});
            this.gmsConfigId = cid;
            const selectEl = document.getElementById('gms-config_id');
            if (selectEl) selectEl.value = String(cid);
            if (statusEl) statusEl.textContent = `已同步：${json.data.name || cid}`;
            if (showToast && window.CommonUtils) CommonUtils.showToast('已从服务端同步参数', 'success');
        } catch (e) {
            console.error('syncGmsParamsFromServer:', e);
            if (statusEl) statusEl.textContent = '同步失败';
        }
    },

    // 加载 GMS 策略参数到表单（仅默认占位；策略参数以服务端为准）
    loadGmsParams() {
        const statusEl = document.getElementById('gmsParamsSaveStatus');
        try {
            const defaults = {
                start_date: '',
                observation_period: 20,
                ratio_d20_max: 0.015,
                volume_ratio_max: 0.8,
                left_buy_min_accumulation: 0,
                volume_ratio_min: 1.5,
                accumulation_fz_min: 1.5,
                balance_ratio_max: 0.01,
                watch_threshold: 60,
                alert_threshold: 90,
                overbought_ratio: 0.15,
                accumulation_s_threshold: 85,
                accumulation_a_threshold: 70,
                momentum_full_threshold: 90,
                momentum_batch_threshold: 80,
                instant_deviation_stable_days: 3,
                weight_acc_fz: 30,
                weight_acc_balance: 40,
                weight_acc_volume: 30,
                weight_mom_ratio_d1: 40,
                weight_mom_deviation: 30,
                weight_mom_volume: 30
            };
            const saved = sessionStorage.getItem('gmsScreeningPrefs');
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed.config_id != null) {
                    this.gmsConfigId = parseInt(parsed.config_id, 10);
                    const selectEl = document.getElementById('gms-config_id');
                    if (selectEl) selectEl.value = String(this.gmsConfigId);
                }
            }
            this.applyGmsFlatParamsToForm(defaults);
            if (statusEl) statusEl.textContent = '';
        } catch (e) {
            console.error('loadGmsParams:', e);
            if (statusEl) statusEl.textContent = '加载失败';
        }
    },

    // 获取当前 GMS 策略参数（从表单读取，用于 API 请求和保存）
    getGmsParams() {
        const get = (id) => {
            const el = document.getElementById(id);
            if (!el) return undefined;
            const v = el.value;
            return v === '' ? undefined : (el.type === 'number' ? parseFloat(v) : v);
        };
        const getStr = (id) => {
            const el = document.getElementById(id);
            return el ? (el.value || '').trim() : '';
        };
        return {
            start_date: getStr('gms-start_date'),
            observation_period: get('gms-observation_period'),
            ratio_d20_max: get('gms-ratio_d20_max'),
            volume_ratio_max: get('gms-volume_ratio_max'),
            left_buy_min_accumulation: get('gms-left_buy_min_accumulation'),
            volume_ratio_min: get('gms-volume_ratio_min'),
            accumulation_fz_min: get('gms-accumulation_fz_min'),
            balance_ratio_max: get('gms-balance_ratio_max'),
            watch_threshold: get('gms-watch_threshold'),
            alert_threshold: get('gms-alert_threshold'),
            overbought_ratio: get('gms-overbought_ratio'),
            accumulation_s_threshold: get('gms-accumulation_s_threshold'),
            accumulation_a_threshold: get('gms-accumulation_a_threshold'),
            momentum_full_threshold: get('gms-momentum_full_threshold'),
            momentum_batch_threshold: get('gms-momentum_batch_threshold'),
            instant_deviation_stable_days: get('gms-instant_deviation_stable_days'),
            weight_acc_fz: get('gms-weight_acc_fz'),
            weight_acc_balance: get('gms-weight_acc_balance'),
            weight_acc_volume: get('gms-weight_acc_volume'),
            weight_mom_ratio_d1: get('gms-weight_mom_ratio_d1'),
            weight_mom_deviation: get('gms-weight_mom_deviation'),
            weight_mom_volume: get('gms-weight_mom_volume')
        };
    },

    // 保存 GMS 筛选偏好（config_id / scope 等，策略参数以服务端为准）
    async saveGmsParams() {
        const statusEl = document.getElementById('gmsParamsSaveStatus');
        const prefs = {
            config_id: this.gmsConfigId || undefined,
            scope: document.getElementById('gms-scope')?.value,
            cn_board_segment: document.getElementById('gms-cn_board_segment')?.value,
            page_size: parseInt(document.getElementById('gms-page_size')?.value || '100', 10) || 100,
            use_pagination: document.getElementById('gms-use_pagination')?.checked || false,
            exclude_st: document.getElementById('gms-exclude_st')?.checked || false,
        };
        try {
            const token = localStorage.getItem('access_token');
            if (token) {
                const res = await fetch(`${this.API_BASE_URL}/api/user/preferences/gms-screening`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                    body: JSON.stringify(prefs),
                });
                const json = await res.json().catch(() => ({}));
                if (res.ok && json.success) {
                    if (statusEl) statusEl.textContent = '筛选偏好已保存到账号';
                    if (window.CommonUtils) CommonUtils.showToast('GMS 筛选偏好已保存', 'success');
                    return;
                }
            }
            sessionStorage.setItem('gmsScreeningPrefs', JSON.stringify(prefs));
            if (statusEl) statusEl.textContent = '筛选偏好已保存到本会话';
            if (window.CommonUtils) CommonUtils.showToast('GMS 筛选偏好已保存（本会话）', 'success');
        } catch (e) {
            console.error('saveGmsParams:', e);
            if (statusEl) statusEl.textContent = '保存失败';
        }
    },

    // 渲染结果
    renderResults(data, searchDate, strategy = 'cyb-midline', emptyMessage = null, gmsPaging = null) {
        let suffix;
        if (strategy === 'cyb-midline') {
            suffix = 'cyb';
        } else if (strategy === 'parking-apron') {
            suffix = 'parking';
        } else if (strategy === 'backtrace-ma250') {
            suffix = 'backtrace';
        } else if (strategy === 'high-tight-flag') {
            suffix = 'high-tight';
        } else if (strategy === 'keep-increasing') {
            suffix = 'keep-increasing';
        } else if (strategy === 'long-lower-shadow') {
            suffix = 'long-lower-shadow';
        } else if (strategy === 'low-nine') {
            suffix = 'low-nine';
        } else if (strategy === 'one-yang-three-lines') {
            suffix = 'one-yang-three-lines';
        } else if (strategy === 'pvfrs') {
            suffix = 'pvfrs';
        } else if (strategy === 'gms') {
            suffix = 'gms';
        } else if (strategy === 'volume-shrink-breakout') {
            suffix = 'volume-shrink-breakout';
        } else if (strategy === 'urt') {
            suffix = 'urt';
        } else {
            suffix = 'cyb';
        }
        const resultsTableBody = document.getElementById(`resultsTableBody-${suffix}`);
        const resultsCount = document.getElementById(`resultsCount-${suffix}`);

        if (!resultsTableBody) {
            return;
        }

        if (!data || data.length === 0) {
            let colSpan;
            if (strategy === 'cyb-midline') {
                colSpan = 12;
            } else if (strategy === 'parking-apron') {
                colSpan = 7;
            } else if (strategy === 'backtrace-ma250') {
                colSpan = 9;
            } else if (strategy === 'high-tight-flag') {
                colSpan = 7;
            } else if (strategy === 'keep-increasing') {
                colSpan = 8;
            } else if (strategy === 'long-lower-shadow') {
                colSpan = 13;
            } else if (strategy === 'low-nine') {
                colSpan = 11;
            } else if (strategy === 'one-yang-three-lines') {
                colSpan = 13;
            } else if (strategy === 'pvfrs') {
                colSpan = 12;
            } else if (strategy === 'gms') {
                colSpan = 17;
            } else if (strategy === 'volume-shrink-breakout') {
                colSpan = 16;
            } else if (strategy === 'urt') {
                colSpan = 14;
            } else {
                colSpan = 12;
            }
            const emptyText = emptyMessage ? `未找到符合条件的股票。${emptyMessage}` : '未找到符合条件的股票';
            resultsTableBody.innerHTML = `<tr><td colspan="${colSpan}" class="empty-state">${emptyText}</td></tr>`;
            if (resultsCount) {
                resultsCount.textContent = '共找到 0 只符合条件的股票';
            }
            if (strategy === 'gms') {
                const bar = document.getElementById('gmsPaginationBar');
                if (bar) bar.style.display = 'none';
            }
            return;
        }

        // 更新计数
        if (resultsCount) {
            if (strategy === 'gms' && gmsPaging && gmsPaging.enabled && gmsPaging.total != null) {
                const pageSize = gmsPaging.page_size || this.GMS_PAGE_SIZE;
                resultsCount.textContent = `共 ${gmsPaging.total} 条 · 本页 ${data.length} 条（每页 ${pageSize} 条）`;
            } else if (strategy === 'gms') {
                resultsCount.textContent = `共 ${data.length} 条信号`;
            } else {
                resultsCount.textContent = `共找到 ${data.length} 只符合条件的股票`;
            }
        }

        // 渲染表格
        let html = '';
        data.forEach((stock, index) => {
            const changePercent = stock.current_change_percent || 0;
            const changeClass = changePercent > 0 ? 'price-positive' : (changePercent < 0 ? 'price-negative' : 'price-neutral');
            const changeSymbol = changePercent > 0 ? '+' : '';

            if (strategy === 'cyb-midline') {
                // 创业板中线选股策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.limit_up_date}</td>
                        <td>${stock.limit_up_price.toFixed(2)}</td>
                        <td>${stock.breakthrough_date}</td>
                        <td>${stock.breakthrough_price.toFixed(2)}</td>
                        <td>${stock.current_price.toFixed(2)}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.ma5.toFixed(2)}</td>
                        <td>${stock.ma10.toFixed(2)}</td>
                        <td>${stock.ma20.toFixed(2)}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'parking-apron') {
                // 停机坪策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.limit_up_date || '--'}</td>
                        <td>${stock.limit_up_price ? stock.limit_up_price.toFixed(2) : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'backtrace-ma250') {
                // 回踩年线策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.highest_date || '--'}</td>
                        <td>${stock.highest_price ? stock.highest_price.toFixed(2) : '--'}</td>
                        <td>${stock.lowest_date || '--'}</td>
                        <td>${stock.lowest_price ? stock.lowest_price.toFixed(2) : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'high-tight-flag') {
                // 高而窄的旗形策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.period_low ? stock.period_low.toFixed(2) : '--'}</td>
                        <td>${stock.price_ratio ? stock.price_ratio.toFixed(2) : '--'}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'keep-increasing') {
                // 持续上涨（MA30向上）策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.current_ma30 ? stock.current_ma30.toFixed(2) : '--'}</td>
                        <td>${stock.ma30_before_30 ? stock.ma30_before_30.toFixed(2) : '--'}</td>
                        <td>${stock.ma30_increase_ratio ? (stock.ma30_increase_ratio * 100).toFixed(2) + '%' : '--'}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'long-lower-shadow') {
                // 长下影阳线策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.pattern_date || '--'}</td>
                        <td>${stock.pattern_close ? stock.pattern_close.toFixed(2) : '--'}</td>
                        <td>${stock.lower_shadow ? stock.lower_shadow.toFixed(2) : '--'}</td>
                        <td>${stock.body_length ? stock.body_length.toFixed(2) : '--'}</td>
                        <td>${stock.shadow_body_ratio ? stock.shadow_body_ratio.toFixed(2) : '--'}</td>
                        <td>${stock.amplitude ? (stock.amplitude * 100).toFixed(2) + '%' : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.ma20 ? stock.ma20.toFixed(2) : '--'}</td>
                        <td class="${stock.deviation_from_ma20 < 0 ? 'negative' : (stock.deviation_from_ma20 > 0 ? 'positive' : '')}">${stock.deviation_from_ma20 ? (stock.deviation_from_ma20 * 100).toFixed(2) + '%' : '--'}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'low-nine') {
                // 低九策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.pattern_start_date || '--'}</td>
                        <td>${stock.pattern_end_date || '--'}</td>
                        <td>${stock.pattern_start_price ? stock.pattern_start_price.toFixed(2) : '--'}</td>
                        <td class="price-negative">${stock.nine_day_decline ? stock.nine_day_decline.toFixed(2) + '%' : '--'}</td>
                        <td>${stock.nine_day_high ? stock.nine_day_high.toFixed(2) : '--'}</td>
                        <td>${stock.nine_day_low ? stock.nine_day_low.toFixed(2) : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'volume-shrink-breakout') {
                const maStr = [
                    stock.ma5_at_boom != null ? Number(stock.ma5_at_boom).toFixed(2) : '--',
                    stock.ma10_at_boom != null ? Number(stock.ma10_at_boom).toFixed(2) : '--',
                    stock.ma20_at_boom != null ? Number(stock.ma20_at_boom).toFixed(2) : '--',
                ].join(' / ');
                const buyTxt = (stock.buy_signal || '--').replace(/</g, '＜').replace(/>/g, '＞');
                const lvl = stock.signal_strength_level || '--';
                const sc = stock.signal_strength != null && !isNaN(Number(stock.signal_strength)) ? Number(stock.signal_strength) : null;
                const strengthCell = sc != null ? `${sc}（${lvl}）` : `--（${lvl}）`;
                const remindArr = Array.isArray(stock.signal_reminders) ? stock.signal_reminders : [];
                const remindTxt = remindArr.length ? remindArr.join('；').replace(/</g, '＜').replace(/>/g, '＞') : '—';
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.strategy_phase || '--'}</td>
                        <td>${stock.boom_date || '--'}</td>
                        <td>${stock.boom_close != null ? Number(stock.boom_close).toFixed(2) : '--'}</td>
                        <td>${stock.boom_volume != null ? stock.boom_volume : '--'}</td>
                        <td>${stock.boom_volume_ratio_vs_prev != null ? Number(stock.boom_volume_ratio_vs_prev).toFixed(2) : '--'}</td>
                        <td>${maStr}</td>
                        <td>${stock.breakout_date || '--'}</td>
                        <td>${stock.breakout_close != null ? Number(stock.breakout_close).toFixed(2) : '--'}</td>
                        <td>${stock.breakout_volume != null ? stock.breakout_volume : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td title="${buyTxt}">${buyTxt.length > 28 ? buyTxt.slice(0, 28) + '…' : buyTxt}</td>
                        <td>${strengthCell}</td>
                        <td style="max-width:220px;font-size:12px;" title="${remindTxt}">${remindTxt.length > 40 ? remindTxt.slice(0, 40) + '…' : remindTxt}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_vsb_trace.html?code=${stock.code}&name=${encodeURIComponent(stock.name || '')}" class="action-link" target="_blank">信号历史</a>
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'urt') {
                const urtName = stock.name || '--';
                const urtTitleAttr = String(urtName)
                    .replace(/&/g, '&amp;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;')
                    .replace(/</g, '&lt;');
                const urtCode = String(stock.code || '');
                const urtMarket = 'CN';
                const urtAlreadyObserve = this._isUrtInTradeObserve(stock, urtMarket, urtCode);
                const urtDetailHref = `stock.html?code=${encodeURIComponent(urtCode)}&name=${encodeURIComponent(stock.name || '')}`;
                const urtTraceHref = `stock_urt_trace.html?code=${encodeURIComponent(urtCode)}&name=${encodeURIComponent(stock.name || '')}`;
                let urtScoreDetailHtml = '<div class="gms-score-detail-inner">得分明细组件未加载</div>';
                if (window.UrtScoreDetail && typeof window.UrtScoreDetail.buildHtml === 'function') {
                    urtScoreDetailHtml = window.UrtScoreDetail.buildHtml(stock);
                }
                const scoreVal = stock.score != null ? Number(stock.score) : null;
                let scoreClass = '';
                if (scoreVal != null) {
                    if (scoreVal >= 85) scoreClass = 'strength-high';
                    else if (scoreVal >= 70) scoreClass = 'strength-mid';
                }
                const urtSd = stock.score_detail && typeof stock.score_detail === 'object' ? stock.score_detail : {};
                const urtSt = urtSd.structure && typeof urtSd.structure === 'object' ? urtSd.structure : {};
                const urtSupport = stock.nearest_support != null
                    ? stock.nearest_support
                    : (Array.isArray(stock.support_levels) && stock.support_levels.length
                        ? stock.support_levels[0]
                        : urtSt.nearest_support);
                const urtResist = stock.nearest_resistance != null
                    ? stock.nearest_resistance
                    : (Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                        ? stock.resistance_levels[0]
                        : urtSt.nearest_resistance);
                const urtQfqTag = stock.price_adjust === 'qfq' ? '前复权 ' : '';
                const urtSupportTitle = Array.isArray(stock.support_levels) && stock.support_levels.length
                    ? `${urtQfqTag}${stock.support_levels.map((x) => Number(x).toFixed(2)).join('、')}`
                    : (Array.isArray(urtSt.support_levels) && urtSt.support_levels.length
                        ? `${urtQfqTag}${urtSt.support_levels.map((x) => Number(x).toFixed(2)).join('、')}`
                        : urtQfqTag.trim());
                const urtResistTitle = Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                    ? `${urtQfqTag}${stock.resistance_levels.map((x) => Number(x).toFixed(2)).join('、')}`
                    : (Array.isArray(urtSt.resistance_levels) && urtSt.resistance_levels.length
                        ? `${urtQfqTag}${urtSt.resistance_levels.map((x) => Number(x).toFixed(2)).join('、')}`
                        : urtQfqTag.trim());
                html += `
                    <tr data-urt-row="${index}">
                        <td class="gms-col-code"><a class="stock-code gms-stock-code-link" href="${urtDetailHref}" target="_blank" rel="noopener noreferrer" title="打开股票详情">${urtCode}</a></td>
                        <td class="gms-col-name"><span class="stock-name" title="${urtTitleAttr}">${urtName}</span></td>
                        <td class="gms-col-narrow">${stock.signal_date || '--'}</td>
                        <td class="gms-col-price">${stock.close != null ? Number(stock.close).toFixed(2) : '--'}</td>
                        <td class="gms-col-price">${stock.ma20 != null ? Number(stock.ma20).toFixed(2) : '--'}</td>
                        <td class="gms-col-narrow">${stock.yang_count_4 != null ? stock.yang_count_4 : '--'}</td>
                        <td class="gms-col-narrow">${stock.yang_count_5 != null ? stock.yang_count_5 : '--'}</td>
                        <td class="gms-col-narrow">${stock.yang_count_10 != null ? stock.yang_count_10 : '--'}</td>
                        <td class="gms-col-narrow">${stock.yang_count_15 != null ? stock.yang_count_15 : '--'}</td>
                        <td class="gms-col-narrow">${stock.yang_count_20 != null ? stock.yang_count_20 : '--'}</td>
                        <td class="gms-col-narrow">${stock.ma_bull_ok === true ? '是' : (stock.ma_bull_ok === false ? '否' : '--')}</td>
                        <td class="gms-col-narrow">${stock.volume_multiple != null ? Number(stock.volume_multiple).toFixed(2) : '--'}</td>
                        <td class="gms-col-narrow">${stock.volume_ratio != null ? Number(stock.volume_ratio).toFixed(2) : '--'}</td>
                        <td class="gms-col-narrow">${stock.turnover_rate != null ? Number(stock.turnover_rate).toFixed(2) : '--'}</td>
                        <td class="gms-col-price support" title="${urtSupportTitle || ''}">${urtSupport != null && Number.isFinite(Number(urtSupport)) ? Number(urtSupport).toFixed(2) : '--'}</td>
                        <td class="gms-col-price resistance" title="${urtResistTitle || ''}">${urtResist != null && Number.isFinite(Number(urtResist)) ? Number(urtResist).toFixed(2) : '--'}</td>
                        <td class="gms-col-narrow"><span class="${scoreClass}">${scoreVal != null ? scoreVal.toFixed(1) : '--'}</span></td>
                        <td class="gms-col-actions">
                            <div class="action-links">
                                <a href="${urtTraceHref}" class="gms-op-btn" target="_blank" rel="noopener noreferrer">历史</a>
                                <button type="button" class="gms-op-btn gms-op-btn--primary urt-trade-observe-add${urtAlreadyObserve ? ' is-added' : ''}" data-row="${index}" data-code="${urtCode}" data-market="${urtMarket}" title="加入交易观察" ${urtAlreadyObserve ? 'disabled' : ''}>${urtAlreadyObserve ? '已观察' : '观察'}</button>
                                <button type="button" class="gms-op-btn urt-score-detail-toggle" data-row="${index}" title="展开/收起得分明细">明细</button>
                            </div>
                        </td>
                    </tr>
                    <tr class="gms-score-detail-row urt-score-detail-row" data-detail-for="${index}" style="display:none;">
                        <td colspan="18" class="gms-score-detail-cell">${urtScoreDetailHtml}</td>
                    </tr>
                `;
            } else if (strategy === 'one-yang-three-lines') {
                // 一阳穿三线策略表格
                // 位置类型颜色标识
                let positionClass = '';
                if (stock.position_type === '低位') {
                    positionClass = 'position-low';
                } else if (stock.position_type === '中位') {
                    positionClass = 'position-mid';
                } else if (stock.position_type === '高位') {
                    positionClass = 'position-high';
                }

                // 风险提示
                const riskWarnings = stock.risk_warnings && stock.risk_warnings.length > 0
                    ? stock.risk_warnings.join('；')
                    : '--';

                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.signal_date || '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td><span class="crossed-lines">${stock.crossed_lines || '--'}</span></td>
                        <td>${stock.volume_ratio ? stock.volume_ratio.toFixed(2) : '--'}</td>
                        <td>${stock.turnover_rate ? stock.turnover_rate.toFixed(2) + '%' : '--'}</td>
                        <td><span class="${positionClass}">${stock.position_type || '--'}</span></td>
                        <td>${stock.retracement ? stock.retracement.toFixed(2) + '%' : '--'}</td>
                        <td>${stock.bias30 ? stock.bias30.toFixed(2) + '%' : '--'}</td>
                        <td><span class="signal-score">${stock.signal_score || '--'}</span></td>
                        <td><span class="risk-warnings">${riskWarnings}</span></td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'pvfrs') {
                // PVFARS量价频幅度共振策略表格
                // 信号强度颜色标识
                let strengthClass = '';
                const signalStrength = stock.signal_strength || 0;
                if (signalStrength >= 0.8) {
                    strengthClass = 'strength-high';
                } else if (signalStrength >= 0.6) {
                    strengthClass = 'strength-mid';
                } else {
                    strengthClass = 'strength-low';
                }

                // 调试日志：检查股票名称
                if (index < 3) { // 只打印前3条数据
                    console.log(`[DEBUG] PVFARS股票 ${index}: code=${stock.symbol || stock.code}, name=${stock.name}, symbol=${stock.symbol}`);
                }

                // 共振状态显示
                const resonanceStatus = stock.resonance_status || '--';
                let resonanceClass = '';
                if (resonanceStatus === '三维共振') {
                    resonanceClass = 'resonance-active';
                } else if (resonanceStatus === '部分共振') {
                    resonanceClass = 'resonance-partial';
                } else {
                    resonanceClass = 'resonance-none';
                }

                // 投资建议颜色
                let adviceClass = '';
                const advice = stock.investment_advice || '--';
                if (advice === 'BUY' || advice === '买入') {
                    adviceClass = 'advice-buy';
                } else if (advice === 'HOLD' || advice === '持有') {
                    adviceClass = 'advice-hold';
                } else {
                    adviceClass = 'advice-wait';
                }

                // 得分明细：在【得分明细】展开区显示各项权重得分 + 信号强度计算过程
                const sd = stock.score_detail || stock.indicators?.score_detail || {};
                const cm = stock.conditions_met || {};
                const fmt = (v) => (v != null && typeof v === 'number') ? (v * 100).toFixed(1) + '%' : '--';
                const weightItems = [
                    { label: '共振强度', value: sd.resonance_strength, weight: '基础（满足条件权重和/总权重）' },
                    { label: '价格维度得分', value: sd.price_score, weight: '宏观位移、即时强度、价格高于均线等' },
                    { label: '频率维度得分', value: sd.frequency_score, weight: '频率优势、持续买盘、无虚假繁荣等' },
                    { label: '成交量维度得分', value: sd.volume_score, weight: '量价共振、成交量效率、资金支撑等' }
                ];
                const weightRows = weightItems.map(w => `<tr><td>${w.label}</td><td>${fmt(w.value)}</td><td>${w.weight}</td></tr>`).join('');

                // 信号强度计算过程（与后端 signal_generator._calculate_buy_signal_strength 一致）
                const baseStr = (sd.resonance_strength != null && typeof sd.resonance_strength === 'number') ? (sd.resonance_strength * 100).toFixed(1) : '--';
                const condAddends = [
                    { key: 'macro_displacement_positive', name: '宏观位移为正', add: 0.05 },
                    { key: 'instant_strength_positive', name: '即时强度为正', add: 0.05 },
                    { key: 'frequency_advantage', name: '频率优势', add: 0.05 },
                    { key: 'no_false_prosperity', name: '无虚假繁荣', add: 0.03 },
                    { key: 'volume_price_resonance', name: '量价共振', add: 0.07 },
                    { key: 'strong_fund_support', name: '资金支撑强', add: 0.05 }
                ];
                let addendRows = '';
                let totalAdd = 0;
                condAddends.forEach(c => {
                    const met = cm[c.key] === true || cm[c.key] === 'true';
                    if (met) totalAdd += c.add;
                    addendRows += `<tr><td>${c.name}</td><td>${met ? '+' + c.add : '—'}</td><td>${met ? '满足' : '—'}</td></tr>`;
                });
                const originalVal = cm.original_strength != null && typeof cm.original_strength === 'number'
                    ? (cm.original_strength * 100).toFixed(1) : (sd.resonance_strength != null && typeof sd.resonance_strength === 'number'
                        ? (Math.min(1, Math.max(0, sd.resonance_strength + totalAdd)) * 100).toFixed(1) : '--');
                const qualityLevel = cm.quality_level || '—';
                const biasScore = (cm.bias_score != null && typeof cm.bias_score === 'number') ? (cm.bias_score * 100).toFixed(1) + '%' : '—';
                const finalStr = (signalStrength * 100).toFixed(1);

                const signalProcessHtml = `
                    <div class="pvfrs-score-detail-section">
                        <strong>信号强度计算过程</strong>
                        <table class="pvfrs-weight-table pvfrs-signal-process-table">
                            <tbody>
                                <tr><td>① 基础（共振强度）</td><td colspan="2">= ${baseStr}%</td></tr>
                                <tr><td>② 条件加分</td><td>加分</td><td>是否满足</td></tr>
                                ${addendRows}
                                <tr><td>② 加分合计</td><td colspan="2">+ ${(totalAdd * 100).toFixed(0)}%</td></tr>
                                <tr><td>③ 原始强度（基础+加分，截断到0～1）</td><td colspan="2">= ${originalVal}%</td></tr>
                                <tr><td>④ 质量等级</td><td colspan="2">${qualityLevel}</td></tr>
                                <tr><td>⑤ 乖离率得分（参与质量调整）</td><td colspan="2">${biasScore}</td></tr>
                                <tr><td>⑥ 最终信号强度（经质量与乖离率调整）</td><td colspan="2"><strong>= ${finalStr}%</strong></td></tr>
                            </tbody>
                        </table>
                    </div>
                `;

                const scoreDetailHtml = `
                    <div class="pvfrs-score-detail-inner">
                        <div class="pvfrs-score-detail-section">
                            <strong>各项权重得分</strong>
                            <table class="pvfrs-weight-table">
                                <thead><tr><th>项目</th><th>得分</th><th>权重说明</th></tr></thead>
                                <tbody>${weightRows}</tbody>
                            </table>
                        </div>
                        ${signalProcessHtml}
                    </div>
                `;

                html += `
                    <tr data-pvfrs-row="${index}">
                        <td><span class="stock-code">${stock.symbol || stock.code}</span></td>
                        <td><span class="stock-name">${stock.name || '--'}</span></td>
                        <td><span class="${strengthClass}">${(signalStrength * 100).toFixed(1)}%</span></td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td>${stock.price_dimension_status || '--'}</td>
                        <td>${stock.frequency_dimension_status || '--'}</td>
                        <td>${stock.volume_dimension_status || '--'}</td>
                        <td><span class="${resonanceClass}">${resonanceStatus}</span></td>
                        <td>${stock.entry_timing_status || '--'}</td>
                        <td><span class="${adviceClass}">${advice}</span></td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.symbol || stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.symbol || stock.code}&name=${encodeURIComponent(stock.name || '')}" class="action-link" target="_blank">详情</a>
                                <button type="button" class="action-link pvfrs-score-detail-toggle" data-row="${index}" title="展开/收起得分明细">得分明细</button>
                            </div>
                        </td>
                    </tr>
                    <tr class="pvfrs-score-detail-row" data-detail-for="${index}" style="display:none;">
                        <td colspan="12" class="pvfrs-score-detail-cell">${scoreDetailHtml}</td>
                    </tr>
                `;
            } else if (strategy === 'gms') {
                // GMS 均值引力动量策略表格
                const sd = {
                    ratio_d: stock.ratio_d,
                    avg_volume_20d: stock.avg_volume_20d,
                    current_volume: stock.current_volume,
                    ratio_d20: stock.ratio_d20,
                    ratio_d1: stock.ratio_d1,
                    delta: stock.delta,
                    d: stock.d_ma20,
                    rising_days: stock.rising_days,
                    falling_days: stock.falling_days,
                    fz_ratio: stock.fz_ratio,
                    instant_deviation: stock.instant_deviation,
                    volume_ratio: stock.volume_ratio,
                    ...(stock.score_detail || stock.indicators?.score_detail || {}),
                    risk_tags: stock.risk_tags || [],
                    ...(this.gmsConfigMeta || {}),
                };
                const fmtPct = (v) => (v != null && typeof v === 'number') ? (v * 100).toFixed(1) + '%' : '--';
                const scoreDetailHtml = this.buildGmsScoreDetailHtml(sd);
                const buyType = stock.buy_type || '—';
                const buyTypeClass = stock.left_buy_signal ? 'gms-left' : (stock.right_buy_signal ? 'gms-right' : '');
                const riskTags = Array.isArray(stock.risk_tags) ? stock.risk_tags : [];
                const riskHtml = riskTags.length
                    ? riskTags.map((t) => `<span class="gms-risk-tag gms-risk-${t.level || 'info'}" title="${String(t.reason || '').replace(/"/g, '&quot;')}">${t.label || t.id}</span>`).join('')
                    : '—';
                // 信号强度：优先用后端值；若为 0 但 score_detail 有总分则用总分/100（避免 trace 中 score_total=0 导致显示 0）
                let signalStrength = stock.signal_strength != null ? stock.signal_strength : (stock.score_total != null ? stock.score_total / 100 : 0);
                if (signalStrength === 0 && sd && sd.score_total != null && sd.score_total > 0) {
                    signalStrength = sd.score_total / 100;
                }
                let strengthClass = 'strength-low';
                if (signalStrength >= 0.8) strengthClass = 'strength-high';
                else if (signalStrength >= 0.6) strengthClass = 'strength-mid';
                const gmsName = stock.name || '--';
                const gmsTitleAttr = String(gmsName)
                    .replace(/&/g, '&amp;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;')
                    .replace(/</g, '&lt;');
                const gmsCode = String(stock.symbol || stock.code || '');
                const gmsMarket = this._gmsMarketFromStock(stock);
                const gmsAlreadyObserve = this._isGmsInTradeObserve(stock, gmsMarket, gmsCode);
                const gmsScopeElement = document.querySelector('input[name="gmsScope"]:checked');
                const gmsScope = gmsScopeElement ? gmsScopeElement.value : 'all';
                const canShowWatchlistAction = gmsScope !== 'watchlist';
                const gmsIndustry = this._gmsDisplayIndustry(stock.industry);
                const gmsIndustryAttr = String(gmsIndustry)
                    .replace(/&/g, '&amp;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;')
                    .replace(/</g, '&lt;');
                const gmsDetailHref = `stock.html?code=${encodeURIComponent(gmsCode)}&name=${encodeURIComponent(stock.name || '')}`;
                const gmsSt = (sd.structure && typeof sd.structure === 'object') ? sd.structure : {};
                const gmsSupport = stock.nearest_support != null
                    ? stock.nearest_support
                    : (Array.isArray(stock.support_levels) && stock.support_levels.length
                        ? stock.support_levels[0]
                        : gmsSt.nearest_support);
                const gmsResist = stock.nearest_resistance != null
                    ? stock.nearest_resistance
                    : (Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                        ? stock.resistance_levels[0]
                        : gmsSt.nearest_resistance);
                const gmsSupportTitle = Array.isArray(stock.support_levels) && stock.support_levels.length
                    ? stock.support_levels.map((x) => Number(x).toFixed(2)).join('、')
                    : (Array.isArray(gmsSt.support_levels) && gmsSt.support_levels.length
                        ? gmsSt.support_levels.map((x) => Number(x).toFixed(2)).join('、')
                        : '');
                const gmsResistTitle = Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                    ? stock.resistance_levels.map((x) => Number(x).toFixed(2)).join('、')
                    : (Array.isArray(gmsSt.resistance_levels) && gmsSt.resistance_levels.length
                        ? gmsSt.resistance_levels.map((x) => Number(x).toFixed(2)).join('、')
                        : '');
                html += `
                    <tr data-gms-row="${index}">
                        <td class="gms-col-code"><a class="stock-code gms-stock-code-link" href="${gmsDetailHref}" target="_blank" rel="noopener noreferrer" title="打开股票详情">${gmsCode}</a></td>
                        <td class="gms-col-name"><span class="stock-name" title="${gmsTitleAttr}">${gmsName}</span></td>
                        <td class="gms-col-industry"><span class="stock-industry" title="${gmsIndustryAttr}">${gmsIndustry === '--' ? '--' : gmsIndustryAttr}</span></td>
                        <td style="display:none;"><span class="gms-score-total">${stock.score_total != null ? stock.score_total.toFixed(1) : '--'}</span></td>
                        <td class="gms-col-narrow"><span class="${strengthClass}">${(signalStrength * 100).toFixed(1)}%</span></td>
                        <td class="gms-col-narrow"><span class="${buyTypeClass}">${buyType}</span></td>
                        <td class="gms-col-narrow gms-col-risk"><span class="gms-risk-tags-inline">${riskHtml}</span></td>
                        <td class="gms-col-price">${stock.current_price != null ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="gms-col-price support" title="${gmsSupportTitle || ''}">${gmsSupport != null && Number.isFinite(Number(gmsSupport)) ? Number(gmsSupport).toFixed(2) : '--'}</td>
                        <td class="gms-col-price resistance" title="${gmsResistTitle || ''}">${gmsResist != null && Number.isFinite(Number(gmsResist)) ? Number(gmsResist).toFixed(2) : '--'}</td>
                        <td class="gms-col-num">${stock.delta != null ? stock.delta.toFixed(4) : '--'}</td>
                        <td class="gms-col-num">${stock.falling_days != null ? stock.falling_days : '--'}</td>
                        <td class="gms-col-num">${stock.rising_days != null ? stock.rising_days : '--'}</td>
                        <td class="gms-col-num">${stock.d_ma20 != null ? stock.d_ma20.toFixed(2) : '--'}</td>
                        <td class="gms-col-num">${stock.ratio_relative != null ? (stock.ratio_relative * 100).toFixed(2) + '%' : '--'}</td>
                        <td class="gms-col-pct">${stock.ratio_d20 != null ? fmtPct(stock.ratio_d20) : '--'}</td>
                        <td class="gms-col-pct">${stock.ratio_d1 != null ? fmtPct(stock.ratio_d1) : '--'}</td>
                        <td class="gms-col-narrow">${stock.fz_ratio != null ? stock.fz_ratio.toFixed(2) : '--'}</td>
                        <td class="gms-col-pct ${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td class="gms-col-actions">
                            <div class="action-links">
                                <a href="stock_gms_trace.html?code=${stock.symbol || stock.code}&name=${encodeURIComponent(stock.name || '')}" class="gms-op-btn" target="_blank" rel="noopener noreferrer">历史</a>
                                <button type="button" class="gms-op-btn gms-op-btn--primary gms-trade-observe-add${gmsAlreadyObserve ? ' is-added' : ''}" data-row="${index}" data-code="${gmsCode}" data-market="${gmsMarket}" title="加入交易观察" ${gmsAlreadyObserve ? 'disabled' : ''}>${gmsAlreadyObserve ? '已观察' : '观察'}</button>
                                ${canShowWatchlistAction ? `<button type="button" class="gms-op-btn gms-watchlist-add" data-code="${gmsCode}" data-name="${gmsTitleAttr}" title="加入自选股">自选</button>` : ''}
                                <button type="button" class="gms-op-btn gms-score-detail-toggle" data-row="${index}" title="展开/收起得分明细">明细</button>
                            </div>
                        </td>
                    </tr>
                    <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
                        <td colspan="19" class="gms-score-detail-cell">${scoreDetailHtml}</td>
                    </tr>
                `;
            }
        });

        resultsTableBody.innerHTML = html;
    },

    // 获取一阳穿三线策略参数
    getOneYangThreeLinesParams() {
        const minIncreasePercent = document.getElementById('minIncreasePercent').value;
        const minBodyRatio = document.getElementById('minBodyRatio').value;
        const minCrossLines = document.getElementById('minCrossLines').value;
        const minVolumeRatio = document.getElementById('minVolumeRatio').value;
        const minTurnoverRate = document.getElementById('minTurnoverRate').value;
        const maxTurnoverRate = document.getElementById('maxTurnoverRate').value;
        const recentDays = document.getElementById('recentDays-one-yang').value;

        // 获取选中的均线周期
        const maPeriodsCheckboxes = document.querySelectorAll('input[name="maPeriods"]:checked');
        const maPeriods = Array.from(maPeriodsCheckboxes).map(cb => cb.value);

        return {
            min_increase_percent: parseFloat(minIncreasePercent),
            min_body_ratio: parseFloat(minBodyRatio),
            min_cross_lines: parseInt(minCrossLines),
            min_volume_ratio: parseFloat(minVolumeRatio),
            min_turnover_rate: parseFloat(minTurnoverRate),
            max_turnover_rate: parseFloat(maxTurnoverRate),
            recent_days: parseInt(recentDays),
            ma_periods: maPeriods.join(',')
        };
    },

    // 重置一阳穿三线策略参数
    resetOneYangThreeLinesParams() {
        document.getElementById('minIncreasePercent').value = '3.0';
        document.getElementById('minBodyRatio').value = '0.7';
        document.getElementById('minCrossLines').value = '3';
        document.getElementById('minVolumeRatio').value = '2.0';
        document.getElementById('minTurnoverRate').value = '3.0';
        document.getElementById('maxTurnoverRate').value = '10.0';
        document.getElementById('recentDays-one-yang').value = '1';

        // 重置均线周期选择
        const maPeriodsCheckboxes = document.querySelectorAll('input[name="maPeriods"]');
        maPeriodsCheckboxes.forEach(cb => {
            cb.checked = true; // 默认全选
        });

        if (window.CommonUtils) {
            CommonUtils.showToast('参数已重置为默认值', 'success');
        }
    },

    // 保存一阳穿三线策略参数到本地存储
    saveOneYangThreeLinesParams() {
        const params = this.getOneYangThreeLinesParams();
        localStorage.setItem('oneYangThreeLinesParams', JSON.stringify(params));
        if (window.CommonUtils) {
            CommonUtils.showToast('参数已保存', 'success');
        }
    },

    // 从本地存储加载一阳穿三线策略参数
    loadOneYangThreeLinesParams() {
        const savedParams = localStorage.getItem('oneYangThreeLinesParams');
        if (savedParams) {
            try {
                const params = JSON.parse(savedParams);
                document.getElementById('minIncreasePercent').value = params.min_increase_percent || '3.0';
                document.getElementById('minBodyRatio').value = params.min_body_ratio || '0.7';
                document.getElementById('minCrossLines').value = params.min_cross_lines || '3';
                document.getElementById('minVolumeRatio').value = params.min_volume_ratio || '2.0';
                document.getElementById('minTurnoverRate').value = params.min_turnover_rate || '3.0';
                document.getElementById('maxTurnoverRate').value = params.max_turnover_rate || '10.0';
                document.getElementById('recentDays-one-yang').value = params.recent_days || '1';

                // 恢复均线周期选择
                if (params.ma_periods) {
                    const maPeriodsCheckboxes = document.querySelectorAll('input[name="maPeriods"]');
                    maPeriodsCheckboxes.forEach(cb => {
                        cb.checked = params.ma_periods.includes(cb.value);
                    });
                }
            } catch (e) {
                console.error('加载参数失败:', e);
            }
        }
    },

    /** GMS：导出 CSV 前拉取全量（不分页） */
    async exportGmsCsvFull() {
        try {
            const q = await this.buildGmsQuerySearchParams({ includePagination: false });
            const result = await this.fetchGmsStrategyResult(q.toString());
            if (!result.success || !result.data) {
                if (window.CommonUtils) CommonUtils.showToast(result.message || '没有可导出的数据', 'warning');
                else alert(result.message || '没有可导出的数据');
                return;
            }
            const prev = this.lastResults.gms;
            this.lastResults.gms = result.data;
            this.exportToCSV('gms');
            this.lastResults.gms = prev;
        } catch (e) {
            const msg = (e && e.message) ? e.message : String(e);
            if (window.CommonUtils) CommonUtils.showToast(`导出失败: ${msg}`, 'warning');
            else alert(`导出失败: ${msg}`);
        }
    },

    // 导出结果到CSV
    exportToCSV(strategy) {
        const data = this.lastResults[strategy];
        if (!data || data.length === 0) {
            if (window.CommonUtils) {
                CommonUtils.showToast('没有可导出的数据', 'warning');
            } else {
                alert('没有可导出的数据');
            }
            return;
        }

        let headers = [];
        let rows = [];
        let filename = `选股结果_${strategy}_${new Date().toISOString().split('T')[0]}.csv`;

        if (strategy === 'one-yang-three-lines') {
            headers = [
                '股票代码', '股票名称', '信号日期', '当前价格',
                '穿越均线', '成交量倍数', '换手率', '位置类型',
                '回撤幅度', 'BIAS30', '信号评分', '风险提示'
            ];
            rows = data.map(stock => [
                `\u2060${stock.code}`, // 零宽字符前缀使 Excel 整列统一按文本显示，左对齐且保留前导零
                stock.name,
                stock.signal_date || '',
                stock.current_price || '',
                stock.crossed_lines || '',
                stock.volume_ratio || '',
                stock.turnover_rate ? stock.turnover_rate + '%' : '',
                stock.position_type || '',
                stock.retracement ? stock.retracement + '%' : '',
                stock.bias30 ? stock.bias30 + '%' : '',
                stock.signal_score || '',
                (stock.risk_warnings || []).join(';')
            ]);
            filename = `一阳穿三线筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'cyb-midline') {
            headers = [
                '股票代码', '股票名称', '涨停日期', '涨停价格',
                '突破日期', '突破价格', '当前价格', '当前涨跌幅',
                'MA5', 'MA10', 'MA20'
            ];
            rows = data.map(stock => [
                `\u2060${stock.code}`,
                stock.name,
                stock.limit_up_date || '',
                stock.limit_up_price || '',
                stock.breakthrough_date || '',
                stock.breakthrough_price || '',
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%',
                stock.ma5 || '',
                stock.ma10 || '',
                stock.ma20 || ''
            ]);
            filename = `创业板中线筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'pvfrs') {
            headers = [
                '股票代码', '股票名称', '信号强度', '当前价格',
                '价格维度', '频率维度', '成交量维度', '共振状态',
                '入场时机', '投资建议', '当前涨跌幅'
            ];
            rows = data.map(stock => [
                `\u2060${stock.symbol || stock.code}`,
                stock.name || '',
                stock.signal_strength ? (stock.signal_strength * 100).toFixed(1) + '%' : '',
                stock.current_price || '',
                stock.price_dimension_status || '',
                stock.frequency_dimension_status || '',
                stock.volume_dimension_status || '',
                stock.resonance_status || '',
                stock.entry_timing_status || '',
                stock.investment_advice || '',
                stock.current_change_percent ? stock.current_change_percent.toFixed(2) + '%' : '0%'
            ]);
            filename = `PVFARS量价频幅度共振筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'gms') {
            headers = [
                '股票代码', '股票名称', '所属行业', '信号强度', '买点类型', '当前价格', '支撑', '阻力',
                'Δ (20日位移)', 'F (下跌天)', 'Z (上涨天)', 'd (20日均价)', 'Δ/d (位移/均价)',
                'Δ/d₂₀', 'Δ/d₁', 'F/Z', '当前涨跌幅', '得分明细'
            ];
            rows = data.map(stock => {
                let sig = stock.signal_strength != null ? stock.signal_strength : (stock.score_total != null ? stock.score_total / 100 : 0);
                const sd = {
                    ratio_d: stock.ratio_d,
                    avg_volume_20d: stock.avg_volume_20d,
                    current_volume: stock.current_volume,
                    ratio_d20: stock.ratio_d20,
                    ratio_d1: stock.ratio_d1,
                    delta: stock.delta,
                    d: stock.d_ma20,
                    rising_days: stock.rising_days,
                    falling_days: stock.falling_days,
                    fz_ratio: stock.fz_ratio,
                    instant_deviation: stock.instant_deviation,
                    volume_ratio: stock.volume_ratio,
                    ...(stock.score_detail || {})
                };
                const st = (sd.structure && typeof sd.structure === 'object') ? sd.structure : {};
                const support = stock.nearest_support != null
                    ? stock.nearest_support
                    : (Array.isArray(stock.support_levels) && stock.support_levels.length
                        ? stock.support_levels[0]
                        : st.nearest_support);
                const resist = stock.nearest_resistance != null
                    ? stock.nearest_resistance
                    : (Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                        ? stock.resistance_levels[0]
                        : st.nearest_resistance);
                if (sig === 0 && sd.score_total != null && sd.score_total > 0) sig = sd.score_total / 100;
                const fmt = (v) => (v != null && typeof v === 'number' && !isNaN(v)) ? v.toFixed(1) : '--';
                const accPart = sd.score_accumulation != null
                    ? `蓄势${fmt(sd.score_accumulation)}(引力${fmt(sd.score_acc_fz)}+平衡${fmt(sd.score_acc_balance)}+量缩${fmt(sd.score_acc_volume)})${sd.accumulation_grade || ''}`
                    : '蓄势--';
                const momPart = sd.score_momentum != null
                    ? `动量${fmt(sd.score_momentum)}(推力${fmt(sd.score_mom_ratio_d1)}+支撑${fmt(sd.score_mom_deviation)}+攻击${fmt(sd.score_mom_volume)})${sd.momentum_grade || ''}`
                    : '动量--';
                const scoreDetailStr = `总分${fmt(sd.score_total)} ${accPart} ${momPart}`;
                return [
                    `\u2060${stock.symbol || stock.code}`,
                    stock.name || '',
                    this._gmsDisplayIndustry(stock.industry) === '--' ? '' : this._gmsDisplayIndustry(stock.industry),
                    (sig * 100).toFixed(1) + '%',
                    stock.buy_type || '',
                    stock.current_price != null ? stock.current_price.toFixed(2) : '',
                    support != null && Number.isFinite(Number(support)) ? Number(support).toFixed(2) : '',
                    resist != null && Number.isFinite(Number(resist)) ? Number(resist).toFixed(2) : '',
                    stock.delta != null ? stock.delta.toFixed(4) : '',
                    stock.falling_days != null ? stock.falling_days : '',
                    stock.rising_days != null ? stock.rising_days : '',
                    stock.d_ma20 != null ? stock.d_ma20.toFixed(2) : '',
                    stock.ratio_relative != null ? (stock.ratio_relative * 100).toFixed(2) + '%' : '',
                    stock.ratio_d20 != null ? (stock.ratio_d20 * 100).toFixed(2) + '%' : '',
                    stock.ratio_d1 != null ? (stock.ratio_d1 * 100).toFixed(2) + '%' : '',
                    stock.fz_ratio != null ? stock.fz_ratio.toFixed(2) : '',
                    stock.current_change_percent != null ? stock.current_change_percent.toFixed(2) + '%' : '0%',
                    scoreDetailStr
                ];
            });
            filename = `GMS均值引力动量筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'long-lower-shadow') {
            headers = [
                '股票代码', '股票名称', '形态日期', '形态收盘价',
                '下影线长度', '实体长度', '影线/实体比', '当日振幅',
                '当前价格', '当前涨跌幅', 'MA20', '偏离MA20'
            ];
            rows = data.map(stock => [
                `\u2060${stock.code}`,
                stock.name,
                stock.pattern_date || '',
                stock.pattern_close || '',
                stock.lower_shadow || '',
                stock.body_length || '',
                stock.shadow_body_ratio || '',
                stock.amplitude ? (stock.amplitude * 100).toFixed(2) + '%' : '',
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%',
                stock.ma20 || '',
                stock.deviation_from_ma20 ? (stock.deviation_from_ma20 * 100).toFixed(2) + '%' : ''
            ]);
            filename = `长下影线筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'keep-increasing') {
            headers = [
                '股票代码', '股票名称', '当前价格', '当前涨跌幅',
                '当日MA30', '30日前MA30', 'MA30涨幅'
            ];
            rows = data.map(stock => [
                `\u2060${stock.code}`,
                stock.name,
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%',
                stock.current_ma30 || '',
                stock.ma30_before_30 || '',
                stock.ma30_increase_ratio ? (stock.ma30_increase_ratio * 100).toFixed(2) + '%' : ''
            ]);
            filename = `持续上涨(MA30向上)筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'low-nine') {
            headers = [
                '股票代码', '股票名称', '形态开始日期', '形态结束日期',
                '形态开始价格', '9天跌幅', '9天最高价', '9天最低价',
                '当前价格', '当前涨跌幅'
            ];
            rows = data.map(stock => [
                `\u2060${stock.code}`,
                stock.name,
                stock.pattern_start_date || '',
                stock.pattern_end_date || '',
                stock.pattern_start_price || '',
                stock.nine_day_decline ? stock.nine_day_decline.toFixed(2) + '%' : '',
                stock.nine_day_high || '',
                stock.nine_day_low || '',
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%'
            ]);
            filename = `低九策略筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'volume-shrink-breakout') {
            headers = [
                '股票代码', '股票名称', '模式', '爆量日', '爆量收盘', '爆量成交量', '量比(对前日)',
                'MA5', 'MA10', 'MA20', '突破日', '突破收盘', '突破量', '涨跌幅%',
                '参考买点', '信号强度', '强度分级', '强度提醒',
            ];
            rows = data.map((stock) => {
                const ma5 = stock.ma5_at_boom != null ? Number(stock.ma5_at_boom).toFixed(2) : '';
                const ma10 = stock.ma10_at_boom != null ? Number(stock.ma10_at_boom).toFixed(2) : '';
                const ma20 = stock.ma20_at_boom != null ? Number(stock.ma20_at_boom).toFixed(2) : '';
                const remindArr = Array.isArray(stock.signal_reminders) ? stock.signal_reminders : [];
                const remindStr = remindArr.join('；');
                return [
                    `\u2060${stock.code}`,
                    stock.name,
                    stock.strategy_phase || '',
                    stock.boom_date || '',
                    stock.boom_close != null ? Number(stock.boom_close).toFixed(2) : '',
                    stock.boom_volume != null ? stock.boom_volume : '',
                    stock.boom_volume_ratio_vs_prev != null ? Number(stock.boom_volume_ratio_vs_prev).toFixed(2) : '',
                    ma5, ma10, ma20,
                    stock.breakout_date || '',
                    stock.breakout_close != null ? Number(stock.breakout_close).toFixed(2) : '',
                    stock.breakout_volume != null ? stock.breakout_volume : '',
                    stock.current_change_percent != null ? `${stock.current_change_percent}%` : '',
                    stock.buy_signal || '',
                    stock.signal_strength != null ? String(stock.signal_strength) : '',
                    stock.signal_strength_level || '',
                    remindStr,
                ];
            });
            filename = `3倍量缩量突破筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'urt') {
            headers = [
                '股票代码', '股票名称', '信号日', '收盘', 'MA20', '4日阳', '5日阳',
                '10日阳', '15日阳', '20日阳', '多头',
                '量能倍数', '量比', '换手%', '支撑', '阻力', '得分',
            ];
            rows = data.map((stock) => {
                const sd = stock.score_detail && typeof stock.score_detail === 'object' ? stock.score_detail : {};
                const st = sd.structure && typeof sd.structure === 'object' ? sd.structure : {};
                const support = stock.nearest_support != null
                    ? stock.nearest_support
                    : (Array.isArray(stock.support_levels) && stock.support_levels.length
                        ? stock.support_levels[0]
                        : st.nearest_support);
                const resist = stock.nearest_resistance != null
                    ? stock.nearest_resistance
                    : (Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                        ? stock.resistance_levels[0]
                        : st.nearest_resistance);
                return [
                `\u2060${stock.code}`,
                stock.name,
                stock.signal_date || '',
                stock.close != null ? Number(stock.close).toFixed(2) : '',
                stock.ma20 != null ? Number(stock.ma20).toFixed(2) : '',
                stock.yang_count_4 != null ? stock.yang_count_4 : '',
                stock.yang_count_5 != null ? stock.yang_count_5 : '',
                stock.yang_count_10 != null ? stock.yang_count_10 : '',
                stock.yang_count_15 != null ? stock.yang_count_15 : '',
                stock.yang_count_20 != null ? stock.yang_count_20 : '',
                stock.ma_bull_ok === true ? '是' : (stock.ma_bull_ok === false ? '否' : ''),
                stock.volume_multiple != null ? Number(stock.volume_multiple).toFixed(2) : '',
                stock.volume_ratio != null ? Number(stock.volume_ratio).toFixed(2) : '',
                stock.turnover_rate != null ? Number(stock.turnover_rate).toFixed(2) : '',
                support != null && Number.isFinite(Number(support)) ? Number(support).toFixed(2) : '',
                resist != null && Number.isFinite(Number(resist)) ? Number(resist).toFixed(2) : '',
                stock.score != null ? Number(stock.score).toFixed(1) : '',
                ];
            });
            filename = `上升趋势策略筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else {
            // 通用导出（如果需要支持其他策略）
            if (data.length > 0) {
                headers = Object.keys(data[0]);
                rows = data.map(item => headers.map(header => item[header]));
            }
        }

        if (headers.length === 0) return;

        // 构建CSV内容
        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.map(cell => {
                // 处理包含逗号、换行符或引号的单元格
                const cellStr = String(cell);
                if (cellStr.includes(',') || cellStr.includes('\n') || cellStr.includes('"')) {
                    return `"${cellStr.replace(/"/g, '""')}"`;
                }
                return cellStr;
            }).join(','))
        ].join('\n');

        // 添加 BOM 以支持 Excel 中文显示
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');

        if (navigator.msSaveBlob) { // IE 10+
            navigator.msSaveBlob(blob, filename);
        } else {
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        if (window.CommonUtils) {
            CommonUtils.showToast('导出成功', 'success');
        }
    },

    /**
     * 构建 GMS 得分明细 HTML（策略版本 / 双模块得分 / 减分 / 指标细项）
     */
    buildGmsScoreDetailHtml(sd) {
        if (typeof GmsScoreDetail !== 'undefined' && GmsScoreDetail.buildHtml) {
            return GmsScoreDetail.buildHtml(sd, this.gmsConfigMeta || {}, this.gmsConfigId);
        }
        return '<div class="gms-score-detail-inner">得分明细组件未加载</div>';
    },

    /**
     * 生成 GMS 得分明细的纯文本（与前端页面展示结构一致），用于 Excel 批注
     */
    buildGmsScoreDetailCommentText(sd) {
        if (!sd || typeof sd !== 'object') return '—';
        const gmsFmt = (v, type) => {
            if (v == null || (typeof v === 'number' && isNaN(v))) return '--';
            if (type === 'pct') return (v * 100).toFixed(2) + '%';
            if (type === 'int') return String(Math.round(v));
            if (type === 'vol') return (v >= 10000 ? (v / 10000).toFixed(2) + '万手' : Number(v).toFixed(0) + '手');
            if (type === 'price') return typeof v === 'number' ? v.toFixed(2) : String(v);
            if (type === 'ratio') return typeof v === 'number' ? v.toFixed(2) : String(v);
            if (type === 'num') return typeof v === 'number' ? v.toFixed(4) : String(v);
            return String(v);
        };
        const accS = (sd.accumulation_s_threshold != null && !isNaN(sd.accumulation_s_threshold)) ? sd.accumulation_s_threshold : 85;
        const accA = (sd.accumulation_a_threshold != null && !isNaN(sd.accumulation_a_threshold)) ? sd.accumulation_a_threshold : 70;
        const momFull = (sd.momentum_full_threshold != null && !isNaN(sd.momentum_full_threshold)) ? sd.momentum_full_threshold : 90;
        const momBatch = (sd.momentum_batch_threshold != null && !isNaN(sd.momentum_batch_threshold)) ? sd.momentum_batch_threshold : 80;
        const fzTiers = sd.acc_fz_tiers || [2.5, 1.5];
        const balTiers = sd.balance_tiers || [0.01, 0.015];
        const volShrink = sd.vol_shrink_tiers || [0.6, 0.8];
        const ratioD1Tiers = sd.ratio_d1_tiers || [0.001, 0.03];
        const volAttack = sd.vol_attack_tiers || [2.0, 1.5];
        const wAccFz = (sd.weight_acc_fz != null && !isNaN(sd.weight_acc_fz)) ? sd.weight_acc_fz : 30;
        const wAccBal = (sd.weight_acc_balance != null && !isNaN(sd.weight_acc_balance)) ? sd.weight_acc_balance : 40;
        const wAccVol = (sd.weight_acc_volume != null && !isNaN(sd.weight_acc_volume)) ? sd.weight_acc_volume : 30;
        const wMomD1 = (sd.weight_mom_ratio_d1 != null && !isNaN(sd.weight_mom_ratio_d1)) ? sd.weight_mom_ratio_d1 : 40;
        const wMomDev = (sd.weight_mom_deviation != null && !isNaN(sd.weight_mom_deviation)) ? sd.weight_mom_deviation : 30;
        const wMomVol = (sd.weight_mom_volume != null && !isNaN(sd.weight_mom_volume)) ? sd.weight_mom_volume : 30;
        const lines = [];
        const n = (v) => (v != null && !isNaN(v)) ? v.toFixed(1) : '--';
        const meta = this.gmsConfigMeta || {};
        const cfgName = sd.strategy_config_name || meta.strategy_config_name || '';
        const mechLabel = sd.scoring_mechanism_label || meta.scoring_mechanism_label || '';
        if (cfgName || mechLabel) {
            lines.push('策略参数版本\t' + (cfgName || '—') + (mechLabel ? '\t' + mechLabel : ''));
            lines.push('');
        }
        lines.push('【均值收敛态】得分明细');
        lines.push('维度\t得分\t判定\t规则');
        lines.push(`时间耗散 F/Z\t${n(sd.score_acc_fz)}\t${sd.acc_fz_judge || '—'}\t权重${wAccFz}: ≥${fzTiers[0]}→满分; [${fzTiers[1]},${fzTiers[0]})→2/3`);
        lines.push(`引力粘合 |Δ/d|\t${n(sd.score_acc_balance)}\t${sd.acc_balance_judge || '—'}\t权重${wAccBal}: ≤${(balTiers[0] * 100).toFixed(1)}%→满分; ≤${(balTiers[1] * 100).toFixed(1)}%→1/2`);
        lines.push(`成交量缩 m₂₀/m\t${n(sd.score_acc_volume)}\t${sd.acc_volume_judge || '—'}\t权重${wAccVol}: ≤${volShrink[0]}→满分; (${volShrink[0]},${volShrink[1]}]→1/2`);
        lines.push(`均值收敛态小计\t${n(sd.score_accumulation)}\t判定: ${sd.accumulation_grade || '—'} (≥${accS} S; ≥${accA} A)`);
        lines.push('');
        lines.push('【动量溢出态】得分明细');
        lines.push('维度\t得分\t判定\t规则');
        lines.push(`盈亏反转 Δ/d₁\t${n(sd.score_mom_ratio_d1)}\t${sd.mom_ratio_d1_judge || '—'}\t权重${wMomD1}: (0,${(ratioD1Tiers[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2`);
        lines.push(`推力支撑 d₂₀-d\t${n(sd.score_mom_deviation)}\t${sd.mom_deviation_judge || '—'}\t权重${wMomDev}: 站稳3日→满分; 仅当日→1/2; <0→-10`);
        lines.push(`攻击强度 m₂₀/m\t${n(sd.score_mom_volume)}\t${sd.mom_volume_judge || '—'}\t权重${wMomVol}: ≥${volAttack[0]}→满分; [${volAttack[1]},${volAttack[0]})→2/3`);
        lines.push(`动量溢出态小计\t${n(sd.score_momentum)}\t判定: ${sd.momentum_grade || '—'} (≥${momFull}全速; ≥${momBatch}分批)`);
        lines.push('');
        lines.push('综合  总分=' + (sd.score_total != null ? sd.score_total.toFixed(1) : '--') + '；信号强度=总分/100');
        lines.push('说明  基础分=max(均值收敛态小计,动量溢出态小计)，非两模块相加');
        const penaltyDeduction = sd.score_penalty_deduction != null ? Number(sd.score_penalty_deduction) : 0;
        const penalties = Array.isArray(sd.penalties) ? sd.penalties : [];
        if (penaltyDeduction > 0 || penalties.length > 0 || (sd.scoring_mechanism || meta.scoring_mechanism) === 'tiered_dual_penalty') {
            lines.push('');
            lines.push('【减分项】');
            if (penalties.length) {
                penalties.forEach((p) => {
                    let line = (p.label || p.id || '减分') + '\t' + (p.applied !== false ? '命中 -' + (p.points || 0) : '未命中');
                    if (p.id === 'close_below_ma60' && p.ma60_flat) {
                        line += '\tMA60走平，扣分减半';
                        if (p.base_points != null && p.points != null && Number(p.points) !== Number(p.base_points)) {
                            line += `（${p.base_points}→${p.points}）`;
                        }
                    }
                    lines.push(line);
                });
            } else {
                lines.push('未触发减分规则');
            }
            lines.push('减分合计\t-' + penaltyDeduction.toFixed(1));
            if (sd.score_base_total != null) lines.push('基础分\t' + Number(sd.score_base_total).toFixed(1));
        }
        lines.push('');
        lines.push('计算指标细项');
        lines.push('d₁ (首日收盘价)\t' + gmsFmt(sd.d1, 'price') + '\t周期起点价格' + (sd.d1_date ? '，交易日期 ' + sd.d1_date : ''));
        lines.push('d₂₀ (末日收盘价)\t' + gmsFmt(sd.d20, 'price') + '\t周期末位/当日价格' + (sd.d20_date ? '，交易日期 ' + sd.d20_date : ''));
        const ma60FlatLookback = sd.ma60_flat_lookback_days != null ? sd.ma60_flat_lookback_days : 20;
        let ma60LineHint = '减分规则 close_below_ma60 参照';
        if (sd.ma60_flat === true) {
            const chg = sd.ma60_flat_change_pct != null ? (Number(sd.ma60_flat_change_pct) * 100).toFixed(2) + '%' : '--';
            ma60LineHint += '；MA60走平（' + ma60FlatLookback + '日变化 ' + chg + '）';
        } else if (sd.ma60_flat === false && sd.ma60_flat_change_pct != null) {
            ma60LineHint += '；MA60非走平（' + ma60FlatLookback + '日变化 ' + (Number(sd.ma60_flat_change_pct) * 100).toFixed(2) + '%）';
        }
        lines.push('MA60 (60日均价)\t' + gmsFmt(sd.ma60_d, 'price') + '\t' + ma60LineHint);
        lines.push('d (20日均价)\t' + gmsFmt(sd.d, 'price') + '\t周期均价');
        lines.push('Δ (d₂₀ - d₁)\t' + gmsFmt(sd.delta, 'num') + '\t宏观位移');
        lines.push('Δ/d\t' + (sd.delta != null && sd.d != null && sd.d !== 0 ? gmsFmt(sd.delta / sd.d, 'pct') : '--') + '\t宏观位移相对均价');
        lines.push('Δ/d₂₀（宏观位移/收盘价）\t' + gmsFmt(sd.ratio_d20, 'pct') + '\t左侧买点用|Δ/d₂₀|；≠ 均线乖离');
        lines.push('Δ/d₁（突变率）\t' + gmsFmt(sd.ratio_d1, 'pct') + '\t现价相对周期起点位移');
        lines.push('Δ₂₀/d（均线乖离）\t' + gmsFmt(sd.ratio_d, 'pct') + '\t(d₂₀−d)/d，非左侧判定用 Δ/d₂₀');
        lines.push('Z (上涨天数)\t' + gmsFmt(sd.rising_days, 'int') + '\t多头天数');
        lines.push('F (下跌天数)\t' + gmsFmt(sd.falling_days, 'int') + '\t空头天数');
        lines.push('m (20日平均成交量)\t' + gmsFmt(sd.avg_volume_20d, 'vol') + '\t平均量');
        lines.push('m₂₀ (当日成交量)\t' + gmsFmt(sd.current_volume, 'vol') + '\t当日成交量');
        lines.push('量比 (m₂₀/m)\t' + gmsFmt(sd.volume_ratio, 'ratio') + '\t放量/地量判断');
        lines.push('F/Z (数方比)\t' + gmsFmt(sd.fz_ratio, 'ratio') + '\t蓄势判断');
        lines.push('d₂₀ - d (价格vs均线)\t' + gmsFmt(sd.instant_deviation, 'num') + '\t价格相对均线偏离');
        return lines.join('\n');
    },

    /**
     * GMS 策略导出 Excel：每只股票占两行（数据行 + 得分明细行），明细行用 Excel 行分组默认折叠，点击行首 +/- 可展开/收起
     */
    async exportToExcelGms() {
        let data;
        try {
            const q = await this.buildGmsQuerySearchParams({ includePagination: false });
            const result = await this.fetchGmsStrategyResult(q.toString());
            if (!result.success || !result.data || result.data.length === 0) {
                if (window.CommonUtils) CommonUtils.showToast(result.message || '没有可导出的数据', 'warning');
                else alert(result.message || '没有可导出的数据');
                return;
            }
            data = result.data;
        } catch (e) {
            const msg = (e && e.message) ? e.message : String(e);
            if (window.CommonUtils) CommonUtils.showToast(`导出失败: ${msg}`, 'warning');
            else alert(`导出失败: ${msg}`);
            return;
        }
        try {
            if (typeof window.ensureSheetJsLoaded === 'function') {
                await window.ensureSheetJsLoaded();
            }
        } catch (e) {
            const msg = (e && e.message) ? e.message : String(e);
            if (window.CommonUtils) CommonUtils.showToast(`Excel 组件加载失败: ${msg}`, 'warning');
            else alert(`Excel 组件加载失败: ${msg}`);
            return;
        }
        if (typeof XLSX === 'undefined') {
            if (window.CommonUtils) CommonUtils.showToast('请刷新页面后重试（Excel 导出依赖未加载）', 'warning');
            else alert('请刷新页面后重试');
            return;
        }
        const headers = [
            '股票代码', '股票名称', '所属行业', '信号强度', '买点类型', '当前价格', '支撑', '阻力',
            'Δ (20日位移)', 'F (下跌天)', 'Z (上涨天)', 'd (20日均价)', 'Δ/d (位移/均价)',
            'Δ/d₂₀', 'Δ/d₁', 'F/Z', '当前涨跌幅', '得分明细'
        ];
        const aoa = [headers];
        data.forEach(stock => {
            let sig = stock.signal_strength != null ? stock.signal_strength : (stock.score_total != null ? stock.score_total / 100 : 0);
            const sd = {
                ratio_d: stock.ratio_d,
                avg_volume_20d: stock.avg_volume_20d,
                current_volume: stock.current_volume,
                ratio_d20: stock.ratio_d20,
                ratio_d1: stock.ratio_d1,
                delta: stock.delta,
                d: stock.d_ma20,
                rising_days: stock.rising_days,
                falling_days: stock.falling_days,
                fz_ratio: stock.fz_ratio,
                instant_deviation: stock.instant_deviation,
                volume_ratio: stock.volume_ratio,
                ...(stock.score_detail || {})
            };
            const st = (sd.structure && typeof sd.structure === 'object') ? sd.structure : {};
            const support = stock.nearest_support != null
                ? stock.nearest_support
                : (Array.isArray(stock.support_levels) && stock.support_levels.length
                    ? stock.support_levels[0]
                    : st.nearest_support);
            const resist = stock.nearest_resistance != null
                ? stock.nearest_resistance
                : (Array.isArray(stock.resistance_levels) && stock.resistance_levels.length
                    ? stock.resistance_levels[0]
                    : st.nearest_resistance);
            if (sig === 0 && sd.score_total != null && sd.score_total > 0) sig = sd.score_total / 100;
            aoa.push([
                '\u2060' + (stock.symbol || stock.code),
                stock.name || '',
                this._gmsDisplayIndustry(stock.industry) === '--' ? '' : this._gmsDisplayIndustry(stock.industry),
                (sig * 100).toFixed(1) + '%',
                stock.buy_type || '',
                stock.current_price != null ? stock.current_price.toFixed(2) : '',
                support != null && Number.isFinite(Number(support)) ? Number(support).toFixed(2) : '',
                resist != null && Number.isFinite(Number(resist)) ? Number(resist).toFixed(2) : '',
                stock.delta != null ? stock.delta.toFixed(4) : '',
                stock.falling_days != null ? stock.falling_days : '',
                stock.rising_days != null ? stock.rising_days : '',
                stock.d_ma20 != null ? stock.d_ma20.toFixed(2) : '',
                stock.ratio_relative != null ? (stock.ratio_relative * 100).toFixed(2) + '%' : '',
                stock.ratio_d20 != null ? (stock.ratio_d20 * 100).toFixed(2) + '%' : '',
                stock.ratio_d1 != null ? (stock.ratio_d1 * 100).toFixed(2) + '%' : '',
                stock.fz_ratio != null ? stock.fz_ratio.toFixed(2) : '',
                stock.current_change_percent != null ? stock.current_change_percent.toFixed(2) + '%' : '0%',
                '点击行首 + 展开'
            ]);
            const detailText = this.buildGmsScoreDetailCommentText(stock.score_detail);
            const detailRow = [detailText];
            for (let c = 1; c < headers.length; c++) detailRow.push('');
            aoa.push(detailRow);
        });
        const ws = XLSX.utils.aoa_to_sheet(aoa);
        if (!ws['!rows']) ws['!rows'] = [];
        const merges = ws['!merges'] || [];
        data.forEach((stock, i) => {
            const dataRowIdx = 1 + i * 2;
            const detailRowIdx = 2 + i * 2;
            ws['!rows'][dataRowIdx] = { level: 0 };
            ws['!rows'][detailRowIdx] = { level: 1, hidden: true };
            merges.push({ s: { r: detailRowIdx, c: 0 }, e: { r: detailRowIdx, c: headers.length - 1 } });
        });
        ws['!merges'] = merges;
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'GMS选股结果');
        const filename = `GMS均值引力动量筛选结果_${new Date().toISOString().split('T')[0]}.xlsx`;
        XLSX.writeFile(wb, filename, { cellStyles: true });
        if (window.CommonUtils) CommonUtils.showToast('Excel 导出成功，点击每行左侧 + 展开得分明细，- 收起', 'success');
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    ScreeningPage.init();

    // 绑定一阳穿三线策略参数按钮事件
    const resetParamsBtn = document.getElementById('resetParamsBtn');
    const saveParamsBtn = document.getElementById('saveParamsBtn');

    if (resetParamsBtn) {
        resetParamsBtn.addEventListener('click', () => {
            ScreeningPage.resetOneYangThreeLinesParams();
        });
    }

    if (saveParamsBtn) {
        saveParamsBtn.addEventListener('click', () => {
            ScreeningPage.saveOneYangThreeLinesParams();
        });
    }

    // 加载保存的参数
    ScreeningPage.loadOneYangThreeLinesParams();
});

