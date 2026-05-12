// 选股页面功能模块
const ScreeningPage = {
    API_BASE_URL: Config ? Config.getApiBaseUrl() : '',
    currentStrategy: 'cyb-midline', // 当前选中的策略
    lastResults: {}, // 存储最近一次筛选结果，用于导出
    /** GMS 列表分页（选股页） */
    gmsPage: 1,
    GMS_PAGE_SIZE: 50,
    gmsLocateActive: false,
    _vsbOpenFromHash: false,
    vsbSubPanel: 'pick',
    /** 观察股池内子页：vsb=选股命中表；daily=日终爆量表 */
    vsbObserveSource: 'vsb',

    // 初始化
    async init() {
        await this.loadHeader();
        this.bindEvents();
        this.initStrategyTabs();
        this.initVsbIntegratedTabs();
        this.applyVsbHashOnLoad();
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
            this.loadGmsParams();
            this.syncGmsWatchlistMarketWrap();
        }
        if (strategy === 'volume-shrink-breakout' && !this._vsbOpenFromHash) {
            this.switchVsbSubPanel('pick');
        }
    },

    initVsbIntegratedTabs() {
        const pick = document.getElementById('vsbSubTabPick');
        const obs = document.getElementById('vsbSubTabObserve');
        [pick, obs].forEach((btn) => {
            if (!btn) return;
            btn.addEventListener('click', () => {
                const sub = btn.getAttribute('data-vsb-sub');
                if (sub === 'pick' || sub === 'observe') {
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
                (sub === 'observe' && p.id === 'vsb-sub-observe-wrap');
            p.classList.toggle('active', show);
        });
        if (sub === 'observe') {
            this._syncObserveInnerTabsFromState();
            this.refreshObserveActiveList();
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

    async loadDailyTripleVolumeObserveList() {
        const apiBase = this.API_BASE_URL || '';
        const marketEl = document.getElementById('tvoFilterMarket');
        const statusEl = document.getElementById('dailyTvoFilterStatus');
        const err = document.getElementById('tvoObserveError');
        if (err) {
            err.style.display = 'none';
            err.textContent = '';
        }
        const mv = marketEl ? marketEl.value : '';
        const status = statusEl ? statusEl.value : '';
        const qs = new URLSearchParams({ page: '1', page_size: '200' });
        this._applyObserveMarketBoardToQs(qs, mv);
        if (status) qs.set('status', status);
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
        if (items.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="11" class="empty-state">暂无数据</td>';
            tbody.appendChild(tr);
        } else {
            const esc = this._tvoEscapeHtml.bind(this);
            const fmtNum = this._tvoFmtNum.bind(this);
            items.forEach((row) => {
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
                    '<td>' + esc(up) + '</td>';
                tbody.appendChild(tr);
            });
        }
        const pager = document.getElementById('dailyTvoObservePager');
        if (pager) {
            pager.textContent = '共 ' + (data.total || 0) + ' 条，本页 ' + items.length + ' 条';
        }
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
        // 绑定所有刷新按钮
        document.querySelectorAll('.refresh-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const strategy = btn.dataset.strategy;
                this.loadScreeningResults(strategy);
            });
        });

        // 绑定所有导出按钮
        document.querySelectorAll('.export-btn').forEach(btn => {
            if (btn.id === 'exportExcelBtn-gms') return; // GMS Excel 单独绑定
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

        // 绑定 GMS 策略范围切换事件
        document.querySelectorAll('input[name="gmsScope"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.syncGmsWatchlistMarketWrap();
                this.loadScreeningResults('gms');
            });
        });
        document.querySelectorAll('input[name="gmsWatchlistMarket"]').forEach(radio => {
            radio.addEventListener('change', () => {
                const scopeEl = document.querySelector('input[name="gmsScope"]:checked');
                if (scopeEl && scopeEl.value === 'gms_watchlist') {
                    this.loadScreeningResults('gms');
                }
            });
        });
        this.syncGmsWatchlistMarketWrap();

        // GMS 策略参数：保存按钮
        const gmsParamsSaveBtn = document.getElementById('gmsParamsSaveBtn');
        if (gmsParamsSaveBtn) {
            gmsParamsSaveBtn.addEventListener('click', () => this.saveGmsParams());
        }

        // GMS 得分明细：点击「得分明细」展开/收起（事件委托）
        const gmsContainer = document.getElementById('resultsContainer-gms');
        if (gmsContainer) {
            gmsContainer.addEventListener('click', (e) => {
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
     * @param {{ page?: number, includePagination?: boolean }} options
     */
    getGmsQuerySearchParams(options = {}) {
        const includePagination = options.includePagination !== false;
        const page = options.page != null ? options.page : this.gmsPage;
        const scopeElement = document.querySelector('input[name="gmsScope"]:checked');
        const scope = scopeElement ? scopeElement.value : 'all';
        const gmsParams = this.getGmsParams();
        const q = new URLSearchParams();
        q.set('scope', scope);
        if (scope === 'gms_watchlist') {
            const mEl = document.querySelector('input[name="gmsWatchlistMarket"]:checked');
            q.set('gms_watchlist_market', mEl ? mEl.value : 'all');
        }
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
        if (includePagination) {
            q.set('use_pagination', 'true');
            q.set('page', String(page));
            q.set('page_size', String(this.GMS_PAGE_SIZE));
        } else {
            q.set('use_pagination', 'false');
        }
        return q;
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
            this.renderResults([hit], result.search_date, 'gms', null, { enabled: false });
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
        if (meta.trace_complete !== true) {
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
        label.textContent = totalPages > 0
            ? `第 ${page} / ${totalPages} 页（每页 ${paging.page_size || this.GMS_PAGE_SIZE} 条，共 ${total} 条）`
            : `共 ${total} 条`;
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
                gmsQueryString = this.getGmsQuerySearchParams({
                    page: this.gmsPage,
                    includePagination: true,
                }).toString();
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
                const emptyMsg = (result.data.length === 0 && result.message) ? result.message : null;
                const gmsPaging = strategy === 'gms' ? result.paging : null;
                this.renderResults(result.data, result.search_date, strategy, emptyMsg, gmsPaging);
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
                // 显示导出按钮
                if (exportBtn && result.data.length > 0) {
                    exportBtn.style.display = 'inline-block';
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

    // 加载 GMS 策略参数到表单（localStorage）
    loadGmsParams() {
        const statusEl = document.getElementById('gmsParamsSaveStatus');
        try {
            const saved = localStorage.getItem('gmsParams');
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
            const data = saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
            const set = (id, value) => {
                const el = document.getElementById(id);
                if (el) el.value = value != null ? value : '';
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

    // 保存 GMS 策略参数（localStorage）
    saveGmsParams() {
        const statusEl = document.getElementById('gmsParamsSaveStatus');
        const body = this.getGmsParams();
        try {
            localStorage.setItem('gmsParams', JSON.stringify(body));
            if (statusEl) statusEl.textContent = '已保存';
            if (window.CommonUtils) CommonUtils.showToast('GMS 参数已保存', 'success');
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
                colSpan = 16;
            } else if (strategy === 'volume-shrink-breakout') {
                colSpan = 16;
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
                resultsCount.textContent = `本页 ${data.length} 条，合计 ${gmsPaging.total} 条（每页 ${gmsPaging.page_size || this.GMS_PAGE_SIZE} 条）`;
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
                    ...(stock.score_detail || stock.indicators?.score_detail || {})
                };
                const fmtPct = (v) => (v != null && typeof v === 'number') ? (v * 100).toFixed(1) + '%' : '--';
                const gmsParam = (id, def) => {
                    const el = document.getElementById(id);
                    if (!el) return def;
                    const v = parseFloat(el.value);
                    return isNaN(v) ? def : v;
                };
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
                let gmsDominantHint = '';
                const _acc = sd.score_accumulation;
                const _mom = sd.score_momentum;
                const _an = (_acc != null && !isNaN(_acc)) ? Number(_acc) : NaN;
                const _mn = (_mom != null && !isNaN(_mom)) ? Number(_mom) : NaN;
                if (!isNaN(_an) || !isNaN(_mn)) {
                    if (!isNaN(_an) && !isNaN(_mn)) {
                        if (_an > _mom) gmsDominantHint = '当前主导：均值收敛态（蓄势）。';
                        else if (_mn > _an) gmsDominantHint = '当前主导：动量溢出态。';
                        else gmsDominantHint = '两模块小计相同。';
                    } else if (!isNaN(_an)) gmsDominantHint = '当前主导：均值收敛态（蓄势）。';
                    else gmsDominantHint = '当前主导：动量溢出态。';
                }
                const scoreDetailHtml = `
                    <div class="gms-score-detail-inner">
                        <div class="gms-score-detail-section">
                            <strong>【均值收敛态】得分明细</strong>
                            <table class="gms-weight-table">
                                <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                                <tbody>
                                    <tr><td>时间耗散 F/Z</td><td>${(sd.score_acc_fz != null ? sd.score_acc_fz.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_fz_judge || '—'}</td><td>权重${wAccFz}: ≥${fzTiers[0]}→满分; [${fzTiers[1]},${fzTiers[0]})→2/3</td></tr>
                                    <tr><td>引力粘合 |Δ/d|</td><td>${(sd.score_acc_balance != null ? sd.score_acc_balance.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_balance_judge || '—'}</td><td>权重${wAccBal}: ≤${(balTiers[0] * 100).toFixed(1)}%→满分; ≤${(balTiers[1] * 100).toFixed(1)}%→1/2</td></tr>
                                    <tr><td>成交量缩 m₂₀/m</td><td>${(sd.score_acc_volume != null ? sd.score_acc_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_volume_judge || '—'}</td><td>权重${wAccVol}: ≤${volShrink[0]}→满分; (${volShrink[0]},${volShrink[1]}]→1/2</td></tr>
                                    <tr><td>均值收敛态小计</td><td><strong>${sd.score_accumulation != null ? sd.score_accumulation.toFixed(1) : '--'}</strong></td><td colspan="2"><strong>判定: ${sd.accumulation_grade || '—'}</strong> (≥${accS} S; ≥${accA} A)</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <div class="gms-score-detail-section">
                            <strong>【动量溢出态】得分明细</strong>
                            <table class="gms-weight-table">
                                <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                                <tbody>
                                    <tr><td>盈亏反转 Δ/d₁</td><td>${(sd.score_mom_ratio_d1 != null ? sd.score_mom_ratio_d1.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_ratio_d1_judge || '—'}</td><td>权重${wMomD1}: (0,${(ratioD1Tiers[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2</td></tr>
                                    <tr><td>推力支撑 d₂₀-d</td><td>${(sd.score_mom_deviation != null ? sd.score_mom_deviation.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_deviation_judge || '—'}</td><td>权重${wMomDev}: 站稳3日→满分; 仅当日→1/2; &lt;0→-10</td></tr>
                                    <tr><td>攻击强度 m₂₀/m</td><td>${(sd.score_mom_volume != null ? sd.score_mom_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_volume_judge || '—'}</td><td>权重${wMomVol}: ≥${volAttack[0]}→满分; [${volAttack[1]},${volAttack[0]})→2/3</td></tr>
                                    <tr><td>动量溢出态小计</td><td><strong>${sd.score_momentum != null ? sd.score_momentum.toFixed(1) : '--'}</strong></td><td colspan="2"><strong>判定: ${sd.momentum_grade || '—'}</strong> (≥${momFull}全速; ≥${momBatch}分批)</td></tr>
                                </tbody>
                            </table>
                        </div>
                        <div class="gms-score-detail-section">
                            <strong>综合</strong> 总分=${sd.score_total != null ? sd.score_total.toFixed(1) : '--'}；信号强度=总分/100
                            <p class="gms-total-hint-text" style="font-size:12px;color:#666;margin:6px 0 0 0;line-height:1.45;">
                                总分 = max(均值收敛态小计, 动量溢出态小计)，非两模块分数相加。
                                ${gmsDominantHint ? '<br>' + gmsDominantHint : ''}
                            </p>
                        </div>
                        <div class="gms-score-detail-section gms-indicators-section">
                            <strong>计算指标细项</strong>
                            <table class="gms-weight-table gms-indicators-table">
                                <tbody>
                                    <tr><td>d₁ (首日收盘价)</td><td>${gmsFmt(sd.d1, 'price')}</td><td>周期起点价格${sd.d1_date ? '，交易日期 ' + sd.d1_date : ''}</td></tr>
                                    <tr><td>d₂₀ (末日收盘价)</td><td>${gmsFmt(sd.d20, 'price')}</td><td>周期末位/当日价格${sd.d20_date ? '，交易日期 ' + sd.d20_date : ''}</td></tr>
                                    <tr><td>d (20日均价)</td><td>${gmsFmt(sd.d, 'price')}</td><td>周期均价</td></tr>
                                    <tr><td>Δ (d₂₀ - d₁)</td><td>${gmsFmt(sd.delta, 'num')}</td><td>宏观位移</td></tr>
                                    <tr><td>Δ/d</td><td>${(sd.delta != null && sd.d != null && sd.d !== 0 ? gmsFmt(sd.delta / sd.d, 'pct') : '--')}</td><td>宏观位移相对均价 (Δ/d)</td></tr>
                                    <tr><td>Δ/d₂₀（宏观位移/收盘价）</td><td>${gmsFmt(sd.ratio_d20, 'pct')}</td><td>左侧买点粘合用 |Δ/d₂₀|；≠ 下方均线乖离 Δ₂₀/d</td></tr>
                                    <tr><td>Δ/d₁（突变率）</td><td>${gmsFmt(sd.ratio_d1, 'pct')}</td><td>现价相对周期起点位移</td></tr>
                                    <tr><td>Δ₂₀/d（均线乖离）</td><td>${gmsFmt(sd.ratio_d, 'pct')}</td><td>(d₂₀−d)/d；不是左侧判定用的 Δ/d₂₀</td></tr>
                                    <tr><td>Z (上涨天数)</td><td>${gmsFmt(sd.rising_days, 'int')}</td><td>多头天数</td></tr>
                                    <tr><td>F (下跌天数)</td><td>${gmsFmt(sd.falling_days, 'int')}</td><td>空头天数</td></tr>
                                    <tr><td>m (20日平均成交量)</td><td>${gmsFmt(sd.avg_volume_20d, 'vol')}</td><td>平均量</td></tr>
                                    <tr><td>m₂₀ (当日成交量)</td><td>${gmsFmt(sd.current_volume, 'vol')}</td><td>当日成交量</td></tr>
                                    <tr><td>量比 (m₂₀/m)</td><td>${gmsFmt(sd.volume_ratio, 'ratio')}</td><td>放量/地量判断</td></tr>
                                    <tr><td>F/Z (数方比)</td><td>${gmsFmt(sd.fz_ratio, 'ratio')}</td><td>蓄势判断</td></tr>
                                    <tr><td>d₂₀ - d (价格vs均线)</td><td>${gmsFmt(sd.instant_deviation, 'num')}</td><td>价格相对均线偏离</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
                const buyType = stock.buy_type || '—';
                const buyTypeClass = stock.left_buy_signal ? 'gms-left' : (stock.right_buy_signal ? 'gms-right' : '');
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
                const gmsScopeElement = document.querySelector('input[name="gmsScope"]:checked');
                const gmsScope = gmsScopeElement ? gmsScopeElement.value : 'all';
                const canShowWatchlistAction = gmsScope !== 'watchlist';
                const gmsDetailHref = `stock.html?code=${encodeURIComponent(gmsCode)}&name=${encodeURIComponent(stock.name || '')}`;
                html += `
                    <tr data-gms-row="${index}">
                        <td class="gms-col-code"><a class="stock-code gms-stock-code-link" href="${gmsDetailHref}" target="_blank" rel="noopener noreferrer" title="打开股票详情">${gmsCode}</a></td>
                        <td class="gms-col-name"><span class="stock-name" title="${gmsTitleAttr}">${gmsName}</span></td>
                        <td style="display:none;"><span class="gms-score-total">${stock.score_total != null ? stock.score_total.toFixed(1) : '--'}</span></td>
                        <td class="gms-col-narrow"><span class="${strengthClass}">${(signalStrength * 100).toFixed(1)}%</span></td>
                        <td class="gms-col-narrow"><span class="${buyTypeClass}">${buyType}</span></td>
                        <td class="gms-col-price">${stock.current_price != null ? stock.current_price.toFixed(2) : '--'}</td>
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
                                <a href="stock_gms_trace.html?code=${stock.symbol || stock.code}&name=${encodeURIComponent(stock.name || '')}" class="action-link" target="_blank">历史</a>
                                ${canShowWatchlistAction ? `<button type="button" class="action-link gms-watchlist-add" data-code="${gmsCode}" data-name="${gmsTitleAttr}" title="加入自选股">+自选</button>` : ''}
                                <button type="button" class="action-link gms-score-detail-toggle" data-row="${index}" title="展开/收起得分明细">得分明细</button>
                            </div>
                        </td>
                    </tr>
                    <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
                        <td colspan="16" class="gms-score-detail-cell">${scoreDetailHtml}</td>
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
            const q = this.getGmsQuerySearchParams({ includePagination: false });
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
                '股票代码', '股票名称', '信号强度', '买点类型', '当前价格',
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
                    (sig * 100).toFixed(1) + '%',
                    stock.buy_type || '',
                    stock.current_price != null ? stock.current_price.toFixed(2) : '',
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
        const n = (v) => (v != null && !isNaN(v)) ? v.toFixed(1) : '--';
        const lines = [];
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
        lines.push('说明  总分=max(均值收敛态小计,动量溢出态小计)，非两模块相加');
        lines.push('');
        lines.push('计算指标细项');
        lines.push('d₁ (首日收盘价)\t' + gmsFmt(sd.d1, 'price') + '\t周期起点价格' + (sd.d1_date ? '，交易日期 ' + sd.d1_date : ''));
        lines.push('d₂₀ (末日收盘价)\t' + gmsFmt(sd.d20, 'price') + '\t周期末位/当日价格' + (sd.d20_date ? '，交易日期 ' + sd.d20_date : ''));
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
            const q = this.getGmsQuerySearchParams({ includePagination: false });
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
            '股票代码', '股票名称', '信号强度', '买点类型', '当前价格',
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
            if (sig === 0 && sd.score_total != null && sd.score_total > 0) sig = sd.score_total / 100;
            aoa.push([
                '\u2060' + (stock.symbol || stock.code),
                stock.name || '',
                (sig * 100).toFixed(1) + '%',
                stock.buy_type || '',
                stock.current_price != null ? stock.current_price.toFixed(2) : '',
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
            merges.push({ s: { r: detailRowIdx, c: 0 }, e: { r: detailRowIdx, c: 14 } });
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

