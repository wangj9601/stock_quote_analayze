// 行情页面功能模块
const MarketsPage = {

    // 模拟数据
    /*
    rankingData: {
        rise: [
            { rank: 1, code: '002594', name: '比亚迪', price: 245.67, change: 24.56, percent: 11.11, volume: '8.9亿', turnover: '1245.6亿', rate: '12.5%' },
            { rank: 2, code: '300750', name: '宁德时代', price: 187.50, change: 18.75, percent: 11.11, volume: '6.8亿', turnover: '956.7亿', rate: '8.9%' },
            { rank: 3, code: '000858', name: '五粮液', price: 156.78, change: 14.78, percent: 10.41, volume: '2.1亿', turnover: '456.8亿', rate: '6.7%' },
            { rank: 4, code: '600519', name: '贵州茅台', price: 1865.00, change: 165.00, percent: 9.71, volume: '0.8亿', turnover: '789.3亿', rate: '4.2%' },
            { rank: 5, code: '002415', name: '海康威视', price: 32.45, change: 2.95, percent: 10.01, volume: '4.2亿', turnover: '234.5亿', rate: '9.8%' }
        ],
        fall: [
            { rank: 1, code: '600036', name: '招商银行', price: 45.67, change: -4.33, percent: -8.67, volume: '3.5亿', turnover: '567.8亿', rate: '5.4%' },
            { rank: 2, code: '000001', name: '平安银行', price: 12.34, change: -1.16, percent: -8.58, volume: '1.2亿', turnover: '234.5亿', rate: '7.8%' },
            { rank: 3, code: '600000', name: '浦发银行', price: 8.76, change: -0.74, percent: -7.78, volume: '2.8亿', turnover: '345.6亿', rate: '8.9%' },
            { rank: 4, code: '601166', name: '兴业银行', price: 18.45, change: -1.55, percent: -7.75, volume: '1.9亿', turnover: '456.7亿', rate: '6.7%' },
            { rank: 5, code: '600887', name: '伊利股份', price: 32.10, change: -2.40, percent: -6.96, volume: '1.5亿', turnover: '234.8亿', rate: '4.5%' }
        ]
    },
    */

    currentTab: 'rankings',
    currentRankingType: 'rise',
    lhbBoardType: 'all',
    auctionPage: 1,
    auctionPageSize: 20,
    auctionTotal: 0,

    currentPage: 1,
    pageSize: 20,
    total: 0,
    initialized: false, // 是否已经初始化过

    // 行业板块：默认按板块斜率（走强优先）
    sectorView: 'list',
    sectorData: [],
    sectorSortKey: 'sector_slope',
    sectorSortAsc: false,

    // 概念板块（与行业板块同布局）
    conceptView: 'list',
    conceptData: [],
    conceptSortKey: 'sector_slope',
    conceptSortAsc: false,

    // 全局API前缀
    API_BASE_URL: Config ? Config.getApiBaseUrl() : '',

    // 初始化
    async init() {
        // 独立板块详情页只复用 showSectorDetail，不跑行情中心全量初始化
        if (document.body && document.body.classList.contains('board-detail-page')) {
            return;
        }
        if (!this.initialized) {
            this.bindEvents();
            this.startDataUpdate();
            this.initialized = true;
        }
        
        this.loadMarketIndices(); // 加载真实指数数据
        this.loadIndexCharts();
        this.loadRankingData();

        // 确保自选股管理器已初始化 (管理器内部已有单例保护)
        await watchlistManager.init();

        // 确保搜索弹窗隐藏
        const searchModal = document.getElementById('searchModal');
        if (searchModal) {
            searchModal.classList.remove('show');
        }

        await this.applySectorDetailDeepLink();
    },

    /**
     * 深链：旧版 markets.html?board_code=… 统一跳到独立板块详情页。
     */
    async applySectorDetailDeepLink() {
        let q;
        try {
            q = new URLSearchParams(window.location.search || '');
        } catch (e) {
            return;
        }
        const code = String(q.get('board_code') || '').trim();
        if (!code) return;
        // 已在独立详情页则不再跳转（board_detail 也会加载 markets.js）
        const path = String(window.location.pathname || '');
        if (/board_detail\.html$/i.test(path)) return;
        const kind =
            String(q.get('board_kind') || '').trim().toLowerCase() === 'concept'
                ? 'concept'
                : 'industry';
        const name = String(q.get('board_name') || '').trim();
        const source = String(q.get('board_code_source') || 'tonghuashun').trim() || 'tonghuashun';
        const next = new URLSearchParams({
            board_kind: kind,
            board_code: code,
            board_code_source: source,
        });
        if (name) next.set('board_name', name);
        window.location.replace(`board_detail.html?${next.toString()}`);
    },

    // 绑定事件
    bindEvents() {
        // 内容标签切换
        document.querySelectorAll('.content-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
                this.updateActiveTab(tab);
            });
        });

        // 排行榜类型切换
        document.querySelectorAll('.ranking-type-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchRankingType(btn.dataset.type);
                this.updateActiveRankingType(btn);
            });
        });

        // 市场过滤器
        document.querySelector('.filter-select').addEventListener('change', (e) => {
            this.filterMarket(e.target.value);
        });

        // 成交量异动榜：查询、导出
        const queryBtn = document.getElementById('volumeAberrationQueryBtn');
        if (queryBtn) queryBtn.addEventListener('click', () => this.loadVolumeAberrationData(1));
        const marketSel = document.getElementById('volumeAberrationMarket');
        const orderSel = document.getElementById('volumeAberrationOrder');
        if (marketSel) marketSel.addEventListener('change', () => this.loadVolumeAberrationData(1));
        if (orderSel) orderSel.addEventListener('change', () => this.loadVolumeAberrationData(1));
        const exportCsv = document.getElementById('volumeAberrationExportCsv');
        const exportExcel = document.getElementById('volumeAberrationExportExcel');
        if (exportCsv) exportCsv.addEventListener('click', () => this.exportVolumeAberrationCsv());
        if (exportExcel) exportExcel.addEventListener('click', () => this.exportVolumeAberrationExcel());

        // 点击股票行跳转
        document.addEventListener('click', (e) => {
            if (e.target.closest('.hot-stock-item')) {
                const stockCode = e.target.closest('.hot-stock-item').querySelector('.stock-code').textContent;
                this.goToStock(stockCode);
            }
        });

        // 行业/概念板块视图切换
        document.querySelectorAll('[data-sector-view]').forEach(btn => {
            btn.addEventListener('click', () => {
                const kind = btn.dataset.boardKind || 'industry';
                this.switchSectorView(btn.dataset.sectorView, kind);
            });
        });

        // 行业/概念列表：中线/短线斜率表头排序
        document.querySelectorAll('.sectors-table th.th-sortable[data-sort-key]').forEach(th => {
            th.addEventListener('click', () => {
                const kind = th.dataset.boardKind || 'industry';
                const key = th.dataset.sortKey || 'sector_slope';
                this.setSectorSort(kind, key);
            });
        });

        const refreshSlopeBtn = document.getElementById('refreshSectorSlopeBtn');
        if (refreshSlopeBtn) {
            refreshSlopeBtn.addEventListener('click', () => this.refreshSectorSlopes('industry'));
        }
        const refreshConceptSlopeBtn = document.getElementById('refreshConceptSlopeBtn');
        if (refreshConceptSlopeBtn) {
            refreshConceptSlopeBtn.addEventListener('click', () => this.refreshSectorSlopes('concept'));
        }

        document.querySelectorAll('[data-lhb-type]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.lhbBoardType = btn.dataset.lhbType || 'all';
                document.querySelectorAll('[data-lhb-type]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.loadDragonTiger();
            });
        });
        const lhbQueryBtn = document.getElementById('lhbQueryBtn');
        if (lhbQueryBtn) {
            lhbQueryBtn.addEventListener('click', () => this.loadDragonTiger());
        }

        const auctionQueryBtn = document.getElementById('auctionQueryBtn');
        if (auctionQueryBtn) {
            auctionQueryBtn.addEventListener('click', () => {
                this.auctionPage = 1;
                this.loadAuction();
            });
        }
        const auctionCollectBtn = document.getElementById('auctionCollectBtn');
        if (auctionCollectBtn) {
            auctionCollectBtn.addEventListener('click', () => this.collectAuction());
        }

        const closeSectorDetailBtn = document.getElementById('closeSectorDetailBtn');
        if (closeSectorDetailBtn) {
            closeSectorDetailBtn.addEventListener('click', () => this.hideSectorDetailModal());
        }
        const sectorDetailModal = document.getElementById('sectorDetailModal');
        if (sectorDetailModal) {
        this._sectorDetailCtx = null;
            sectorDetailModal.addEventListener('click', (e) => {
                if (e.target === sectorDetailModal) this.hideSectorDetailModal();
            });
        }
    },

    // 切换标签
    switchTab(tabId) {
        this.currentTab = tabId;

        // 隐藏所有面板
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });

        // 显示目标面板
        const targetPanel = document.getElementById(tabId);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }

        // 根据标签加载相应数据
        this.loadTabData(tabId);
    },

    // 更新活动标签
    updateActiveTab(activeTab) {
        document.querySelectorAll('.content-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        activeTab.classList.add('active');
    },

    // 切换排行榜类型
    switchRankingType(type) {
        this.currentRankingType = type;
        this.currentPage = 1;
        const toolbar = document.getElementById('volumeAberrationToolbar');
        const thead = document.getElementById('rankingsTableHead');
        if (type === 'volume_aberration') {
            if (toolbar) toolbar.style.display = 'flex';
            const hintWrap = document.getElementById('volumeAberrationHintWrap');
            if (hintWrap) hintWrap.style.display = 'block';
            if (thead) {
                this._defaultRankingThead = this._defaultRankingThead || thead.innerHTML;
                thead.innerHTML = '<tr><th>排名</th><th>股票代码</th><th>股票名称</th><th>日期</th><th>当日成交量(手)</th><th>成交额</th><th>MAVOL5(手)</th><th>MAVOL10(手)</th><th>MAVOL20(手)</th><th>量比(5)</th><th>量比(20)</th><th>涨跌幅(%)</th><th>收盘价</th><th>换手率(%)</th><th>操作</th></tr>';
            }
            this.loadVolumeAberrationData(1);
        } else {
            if (toolbar) toolbar.style.display = 'none';
            const hintWrap = document.getElementById('volumeAberrationHintWrap');
            if (hintWrap) hintWrap.style.display = 'none';
            if (thead && this._defaultRankingThead) thead.innerHTML = this._defaultRankingThead;
            this.loadRankingData(1);
        }
    },

    // 更新活动排行榜类型
    updateActiveRankingType(activeBtn) {
        document.querySelectorAll('.ranking-type-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        activeBtn.classList.add('active');
    },

    // 加载标签数据
    loadTabData(tabId) {
        switch (tabId) {
            case 'rankings':
                this.loadRankingData();
                break;
            case 'sectors':
                this.loadSectorData('industry');
                break;
            case 'concepts':
                this.loadSectorData('concept');
                break;
            case 'hot':
                this.loadHotData();
                break;
            case 'stats':
                this.loadStatsData();
                break;
            case 'dragon-tiger':
                this.loadDragonTiger();
                break;
            case 'auction':
                this.loadAuction();
                break;
        }
    },

    // 加载市场指数数据
    async loadMarketIndices() {
        try {
            console.log('加载指数数据...');
            const response = await fetch(`${this.API_BASE_URL}/api/market/indices`);
            const result = await response.json();

            if (result.success && result.data) {
                this.updateIndexDisplay(result.data);
                console.log('指数数据加载成功');
            } else {
                throw new Error('API返回错误');
            }
        } catch (error) {
            console.error('指数数据加载失败:', error);
            // 使用模拟数据作为后备
            const fallbackData = [
                { code: '000001', name: '上证指数', current: 3234.56, change: 12.34, change_percent: 0.38, volume: 12456789 },
                { code: '399001', name: '深证成指', current: 11456.78, change: -23.45, change_percent: -0.20, volume: 8567123 },
                { code: '399006', name: '创业板指', current: 2345.67, change: 5.67, change_percent: 0.24, volume: 5678901 },
                { code: '000300', name: '沪深300', current: 4567.89, change: -8.90, change_percent: -0.19, volume: 9876543 }
            ];
            this.updateIndexDisplay(fallbackData);
            console.log('使用模拟指数数据');
        }
    },

    // 更新指数显示
    updateIndexDisplay(indicesData) {
        indicesData.forEach(function (index) {
            const card = document.querySelector('[data-index-code="' + index.code + '"]');
            if (card) {
                const valueEl = card.querySelector('.index-value');
                const changeEl = card.querySelector('.index-change');
                const changeValueEl = card.querySelector('.change-value');
                const changePercentEl = card.querySelector('.change-percent');

                if (valueEl) {
                    valueEl.textContent = (typeof index.current === 'number' && !isNaN(index.current)) ? index.current.toFixed(2) : '--';
                }

                if (changeEl && changeValueEl && changePercentEl) {
                    const change = (typeof index.change === 'number' && !isNaN(index.change)) ? index.change : 0;
                    const change_percent = (typeof index.change_percent === 'number' && !isNaN(index.change_percent)) ? index.change_percent : 0;

                    const changeStr = change >= 0 ? '+' + change.toFixed(2) : change.toFixed(2);
                    const percentStr = change_percent >= 0 ? '+' + change_percent.toFixed(2) + '%' : change_percent.toFixed(2) + '%';

                    changeValueEl.textContent = changeStr;
                    changePercentEl.textContent = percentStr;

                    // 设置颜色类
                    changeEl.className = 'index-change ' + (change > 0 ? 'positive' : change < 0 ? 'negative' : '');
                }
            }
        });
        this.loadIndexCharts();
    },

    // 加载指数图表
    loadIndexCharts() {
        const chartIds = ['sh000001Chart', 'sz399001Chart', 'sz399006Chart', 'csi000300Chart'];

        chartIds.forEach(chartId => {
            this.drawMiniChart(chartId);
        });
    },

    // 绘制迷你图表
    drawMiniChart(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 生成随机数据点
        const points = 30;
        const data = [];
        let trend = Math.random() > 0.5 ? 1 : -1;

        for (let i = 0; i < points; i++) {
            if (Math.random() > 0.8) trend *= -1; // 偶尔改变趋势
            const value = 0.3 + 0.4 * Math.random() + trend * 0.1 * (i / points);
            data.push(Math.max(0.1, Math.min(0.9, value)));
        }

        // 绘制线条（优先跟指数涨跌语义色；无语义时按曲线首末方向）
        const card = canvas.closest('.index-card');
        const changeEl = card && card.querySelector('.index-change');
        let color = data[data.length - 1] > data[0] ? '#c23b3b' : '#2f9e6b';
        if (changeEl && changeEl.classList.contains('positive')) {
            color = '#c23b3b';
        } else if (changeEl && changeEl.classList.contains('negative')) {
            color = '#2f9e6b';
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();

        data.forEach((value, index) => {
            const x = (width / (points - 1)) * index;
            const y = height - (value * height);

            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        ctx.stroke();

        // 填充渐变
        ctx.globalAlpha = 0.1;
        ctx.fillStyle = color;
        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        ctx.fill();
        ctx.globalAlpha = 1;
    },

    async handleQuickTrade(event, code, name, side) {
        if (event) {
            event.stopPropagation();
        }

        const actionLabel = side === 'sell' ? '卖出' : '买入';

        const quantityInput = prompt(`请输入${actionLabel}股数`, '100');
        if (!quantityInput) {
            return;
        }

        const quantity = parseInt(quantityInput, 10);
        if (!quantity || quantity <= 0) {
            CommonUtils.showToast('请输入正确的股数', 'error');
            return;
        }

        const priceInput = prompt('请输入成交价格，留空则使用最新价', '');
        let price = null;
        if (priceInput && priceInput.trim() !== '') {
            const parsed = parseFloat(priceInput.trim());
            if (Number.isNaN(parsed) || parsed <= 0) {
                CommonUtils.showToast('请输入正确的价格', 'error');
                return;
            }
            price = parsed;
        }

        try {
            const payload = {
                stock_code: code,
                stock_name: name,
                side,
                quantity,
            };
            if (price !== null) {
                payload.price = price;
            }

            const response = await authFetch(`${API_BASE_URL}/api/simtrade/orders`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            const result = await response.json();

            if (response.ok) {
                CommonUtils.showToast(`${actionLabel}指令已提交`, 'success');
            } else {
                CommonUtils.showToast(result.detail || result.message || '模拟交易下单失败', 'error');
            }
        } catch (error) {
            console.error('模拟交易下单失败:', error);
            CommonUtils.showToast('网络异常，模拟交易下单失败', 'error');
        }
    },

    // 加载排行榜数据
    async loadRankingData(page = 1, keyword = null) {
        if (this.currentRankingType === 'volume_aberration') {
            return this.loadVolumeAberrationData(page, keyword);
        }
        const typeMap = {
            rise: 'rise',
            fall: 'fall',
            volume: 'volume',
            turnover: 'turnover_rate'
        };
        const rankingType = typeMap[this.currentRankingType] || 'rise';
        let market = document.querySelector('.filter-select')?.value || 'all';
        if (market === 'cy') market = 'cy';
        this.currentPage = page;
        const pageSize = this.pageSize;

        // 获取搜索关键词（如果未传入）
        if (!keyword) {
            const searchInput = document.getElementById('marketSearchInput');
            keyword = searchInput ? searchInput.value.trim() : null;
        }

        try {
            let url = `${API_BASE_URL}/api/stock/quote_board_list?ranking_type=${rankingType}&market=${market}&page=${page}&page_size=${pageSize}`;
            if (keyword) {
                url += `&keyword=${encodeURIComponent(keyword)}`;
            }

            const resp = await fetch(url);
            const result = await resp.json();
            if (result.success) {
                this.total = result.total || 0;
                const data = (result.data || []).map((item, idx) => ({
                    rank: (page - 1) * pageSize + idx + 1,
                    code: item.code,
                    name: item.name,
                    price: item.current,
                    change: item.change,
                    percent: item.change_percent,
                    volume: item.volume,
                    turnover: item.turnover,
                    rate: item.rate
                }));
                this.renderRankingTable(data, keyword);
                this.renderPagination();
            } else {
                this.renderRankingTable([]);
                this.renderPagination();
                CommonUtils.showToast(result.message || '获取数据失败', 'error');
            }
        } catch (e) {
            this.renderRankingTable([]);
            this.renderPagination();
            CommonUtils.showToast('网络错误，获取数据失败', 'error');
        }
    },

    // 渲染排行榜表格
    renderRankingTable(data, searchKeyword = null) {
        const tbody = document.getElementById('rankingsTableBody');
        if (!tbody) return;

        tbody.innerHTML = data.map(stock => `
            <tr data-code="${stock.code}" onclick="goToStock('${stock.code}', '${stock.name}')" style="cursor: pointer;">
                <td>
                    <span class="rank-number ${stock.rank <= 3 ? 'rank-' + stock.rank : ''}">${stock.rank}</span>
                </td>
                <td>
                    <div class="stock-info">
                        <div class="stock-name">${stock.name}</div>
                        <div class="stock-code">${stock.code}</div>
                    </div>
                </td>
                <td class="price-column">${this.formatPrice(stock.price)}</td>
                <td class="price-column ${this.getChangeClass(stock.percent)}">
                    ${this.formatPercent(stock.percent)}
                </td>
                <td class="price-column ${this.getChangeClass(stock.change)}">
                    ${this.formatChange(stock.change)}
                </td>
                <td class="price-column">${this.formatVolume(stock.volume)}</td>
                <td class="price-column">${this.formatTurnover(stock.turnover)}</td>
                <td class="price-column">${this.formatTurnoverRate(stock.rate)}</td>
                <td>
                    <div class="ranking-actions">
                        <button class="btn btn-sm btn-primary" onclick="MarketsPage.handleQuickTrade(event, '${stock.code}', '${stock.name}', 'buy')">买入</button>
                        <button class="btn btn-sm btn-danger" onclick="MarketsPage.handleQuickTrade(event, '${stock.code}', '${stock.name}', 'sell')" style="margin-left:5px;">卖出</button>
                        <button class="btn btn-sm btn-secondary" data-stock-code="${stock.code}" data-stock-name="${stock.name}" onclick="addToWatchlist('${stock.code}', event); event.stopPropagation();" style="margin-left:5px;">+自选</button>
                        <button class="btn btn-sm btn-secondary" onclick="goToStockHistory('${stock.code}', '${stock.name}'); event.stopPropagation();" style="margin-left:5px;">历史</button>
                    </div>
                </td>
            </tr>
        `).join('');

        // 渲染完成后，更新所有自选股按钮的状态
        this.updateAllWatchlistButtons();

        // 如果有搜索关键词，定位到第一条匹配的记录
        if (searchKeyword && data.length > 0) {
            this.highlightAndScrollToStock(data[0].code);
        }
    },

    // 加载成交量异动榜数据
    normalizeVolumeAberrationStockCode(input) {
        if (input == null) return '';
        const v = String(input).trim();
        // 仅处理纯数字股票代码：补齐到6位（例如输入“1”->“000001”）
        if (/^\d+$/.test(v) && v.length < 6) return v.padStart(6, '0');
        return v;
    },

    async loadVolumeAberrationData(page = 1, keyword = null) {
        this.currentPage = page;
        // 获取搜索关键词（如果未传入）
        if (!keyword) {
            const searchInput = document.getElementById('marketSearchInput');
            keyword = searchInput ? searchInput.value.trim() : null;
        }
        const market = (document.getElementById('volumeAberrationMarket')?.value || 'cn').toLowerCase();
        const dateInput = document.getElementById('volumeAberrationDate');
        const date = dateInput?.value?.trim() || '';
        const order = document.getElementById('volumeAberrationOrder')?.value || 'desc';
        const pageSize = this.pageSize;
        try {
            let url = `${this.API_BASE_URL}/api/stock/volume_aberration_list?market=${market}&order=${order}&page=${page}&page_size=${pageSize}`;
            if (date) url += `&date=${encodeURIComponent(date)}`;
            if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
            const resp = await fetch(url);
            const result = await resp.json();
            if (result.success) {
                this.total = result.total || 0;
                this._volumeAberrationDate = result.date || '';
                this._volumeAberrationRows = result.data || [];
                this.renderVolumeAberrationTable(this._volumeAberrationRows);
                // 支持定位
                if (keyword && this._volumeAberrationRows.length > 0) {
                    // 如果结果中直接包含该股票（精确匹配或包含匹配），则定位到第一条
                    this.highlightAndScrollToStock(String(this._volumeAberrationRows[0].code));
                } else if (keyword && this._volumeAberrationRows.length === 0) {
                    CommonUtils.showToast('未找到匹配该关键词的异动记录', 'info');
                }
                this.renderPagination();
            } else {
                this.total = 0;
                this._volumeAberrationRows = [];
                this.renderVolumeAberrationTable([]);
                this.renderPagination();
                CommonUtils.showToast(result.message || '获取成交量异动榜失败', 'error');
            }
        } catch (e) {
            this.total = 0;
            this._volumeAberrationRows = [];
            this.renderVolumeAberrationTable([]);
            this.renderPagination();
            CommonUtils.showToast('网络错误，获取数据失败', 'error');
        }
    },

    // 渲染成交量异动榜表格
    renderVolumeAberrationTable(data) {
        const tbody = document.getElementById('rankingsTableBody');
        if (!tbody) return;
        const fmtNum = (v) => (v != null && v !== '' && !Number.isNaN(Number(v))) ? Number(v) : null;
        const fmtStr = (v) => v != null ? String(v) : '--';
        // 量比(5)、量比(20)：保留两位小数
        const fmtRatio = (v) => (v != null && v !== '') ? Number(v).toFixed(2) : '--';
        // 涨跌幅：保留两位小数（带 +/- 与 %）
        const fmtPct = (v) => {
            const n = fmtNum(v);
            return n != null ? (n >= 0 ? '+' + n.toFixed(2) : n.toFixed(2)) + '%' : '--';
        };
        tbody.innerHTML = (data || []).map(row => {
            const code = fmtStr(row.code);
            const name = fmtStr(row.name);
            return `<tr data-code="${code}" onclick="goToStock('${code.replace(/'/g, "\\'")}', '${(name || '').replace(/'/g, "\\'")}')" style="cursor: pointer;">
                <td><span class="rank-number ${row.rank <= 3 ? 'rank-' + row.rank : ''}">${row.rank != null ? row.rank : '--'}</span></td>
                <td>${code}</td>
                <td><div class="stock-name">${name}</div></td>
                <td>${fmtStr(row.date)}</td>
                <td class="price-column">${row.volume != null ? this.formatVolume(row.volume) : '--'}</td>
                <td class="price-column">${row.amount != null ? this.formatTurnover(row.amount) : '--'}</td>
                <td class="price-column">${fmtStr(row.mavol5 != null ? this.formatVolume(row.mavol5) : '--')}</td>
                <td class="price-column">${fmtStr(row.mavol10 != null ? this.formatVolume(row.mavol10) : '--')}</td>
                <td class="price-column">${fmtStr(row.mavol20 != null ? this.formatVolume(row.mavol20) : '--')}</td>
                <td>${fmtRatio(row.ratio_5)}</td>
                <td>${fmtRatio(row.ratio_20)}</td>
                <td class="price-column ${this.getChangeClass(row.change_percent)}">${fmtPct(row.change_percent)}</td>
                <td class="price-column">${row.close != null ? this.formatPrice(row.close) : '--'}</td>
                <td class="price-column">${row.turnover_rate != null ? this.formatTurnoverRate(row.turnover_rate) : '--'}</td>
                <td>
                    <div class="ranking-actions">
                        <button class="btn btn-sm btn-secondary" data-stock-code="${code}" data-stock-name="${name}" onclick="addToWatchlist('${code.replace(/'/g, "\\'")}', event); event.stopPropagation();">+自选</button>
                        <button class="btn btn-sm btn-secondary" onclick="goToStockHistory('${code.replace(/'/g, "\\'")}', '${(name || '').replace(/'/g, "\\'")}'); event.stopPropagation();">历史</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        this.updateAllWatchlistButtons();
    },

    getVolumeAberrationExportScope() {
        const sel = document.getElementById('volumeAberrationExportScope');
        return sel?.value === 'all' ? 'all' : 'page';
    },

    getVolumeAberrationQueryParams() {
        const market = (document.getElementById('volumeAberrationMarket')?.value || 'cn').toLowerCase();
        const dateInput = document.getElementById('volumeAberrationDate');
        const date = dateInput?.value?.trim() || '';
        const order = document.getElementById('volumeAberrationOrder')?.value || 'desc';
        return { market, date, order };
    },

    async fetchAllVolumeAberrationRows(pageSize = 500) {
        const { market, date, order } = this.getVolumeAberrationQueryParams();
        // 优先用已有 total；没有的话先拉第一页拿 total
        let page = 1;
        let all = [];
        // pageSize 要和后端允许的范围一致（接口 page_size 最大500）
        const firstUrl = `${this.API_BASE_URL}/api/stock/volume_aberration_list?market=${market}&order=${order}&page=1&page_size=${pageSize}` + (date ? `&date=${encodeURIComponent(date)}` : '');
        const firstResp = await fetch(firstUrl);
        const firstResult = await firstResp.json();
        if (!firstResult.success) return [];
        const total = firstResult.total || 0;
        all = firstResult.data || [];
        const totalPages = Math.max(1, Math.ceil(total / pageSize));
        for (page = 2; page <= totalPages; page++) {
            const url = `${this.API_BASE_URL}/api/stock/volume_aberration_list?market=${market}&order=${order}&page=${page}&page_size=${pageSize}` + (date ? `&date=${encodeURIComponent(date)}` : '');
            const resp = await fetch(url);
            const result = await resp.json();
            if (!result.success) break;
            all = all.concat(result.data || []);
        }
        return all;
    },

    // 导出成交量异动榜 CSV（支持当前页/全部，不含操作列）
    async exportVolumeAberrationCsv() {
        let rows = this._volumeAberrationRows || [];
        if (this.getVolumeAberrationExportScope() === 'all') {
            CommonUtils.showToast('正在拉取全部数据用于导出...', 'info');
            rows = await this.fetchAllVolumeAberrationRows(500);
        }
        if (rows.length === 0) {
            CommonUtils.showToast('没有可导出的数据', 'warning');
            return;
        }
        const headers = ['排名', '股票代码', '股票名称', '日期', '当日成交量(手)', '成交额', 'MAVOL5(手)', 'MAVOL10(手)', 'MAVOL20(手)', '量比(5)', '量比(20)', '涨跌幅(%)', '收盘价', '换手率(%)'];
        const toStr = (v) => (v != null && v !== '') ? String(v) : '';
        const fmt2 = (v) => (v != null && v !== '' && !Number.isNaN(Number(v))) ? Number(v).toFixed(2) : '';
        const escapeCsv = (s) => {
            const t = String(s);
            if (/[",\n\r]/.test(t)) return '"' + t.replace(/"/g, '""') + '"';
            return t;
        };
        const lines = [headers.map(escapeCsv).join(',')];
        rows.forEach(row => {
            const r = [
                row.rank != null ? row.rank : '',
                '\u2060' + toStr(row.code),
                toStr(row.name),
                toStr(row.date),
                row.volume != null ? (row.volume / 10000).toFixed(2) : '',
                row.amount != null ? row.amount : '',
                row.mavol5 != null ? (row.mavol5 / 10000).toFixed(2) : '',
                row.mavol10 != null ? (row.mavol10 / 10000).toFixed(2) : '',
                row.mavol20 != null ? (row.mavol20 / 10000).toFixed(2) : '',
                fmt2(row.ratio_5),
                fmt2(row.ratio_20),
                fmt2(row.change_percent),
                row.close != null ? row.close : '',
                row.turnover_rate != null ? row.turnover_rate : ''
            ];
            lines.push(r.map(escapeCsv).join(','));
        });
        const BOM = '\uFEFF';
        const blob = new Blob([BOM + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `成交量异动榜_${this._volumeAberrationDate || new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
        CommonUtils.showToast('CSV 导出成功', 'success');
    },

    // 导出成交量异动榜 Excel（支持当前页/全部，不含操作列）
    async exportVolumeAberrationExcel() {
        let rows = this._volumeAberrationRows || [];
        if (this.getVolumeAberrationExportScope() === 'all') {
            CommonUtils.showToast('正在拉取全部数据用于导出...', 'info');
            rows = await this.fetchAllVolumeAberrationRows(500);
        }
        if (rows.length === 0) {
            CommonUtils.showToast('没有可导出的数据', 'warning');
            return;
        }
        try {
            if (typeof window.ensureSheetJsLoaded === 'function') {
                await window.ensureSheetJsLoaded();
            }
        } catch (e) {
            const msg = (e && e.message) ? e.message : String(e);
            CommonUtils.showToast(`Excel 组件加载失败: ${msg}`, 'warning');
            return;
        }
        if (typeof XLSX === 'undefined') {
            CommonUtils.showToast('请刷新页面后重试（Excel 导出依赖未加载）', 'warning');
            return;
        }
        const headers = ['排名', '股票代码', '股票名称', '日期', '当日成交量(手)', '成交额', 'MAVOL5(手)', 'MAVOL10(手)', 'MAVOL20(手)', '量比(5)', '量比(20)', '涨跌幅(%)', '收盘价', '换手率(%)'];
        const aoa = [headers];
        const toStr = (v) => (v != null && v !== '') ? String(v) : '';
        const fmt2 = (v) => (v != null && v !== '' && !Number.isNaN(Number(v))) ? Number(v).toFixed(2) : '';
        rows.forEach(row => {
            aoa.push([
                row.rank != null ? row.rank : '',
                '\u2060' + toStr(row.code),
                toStr(row.name),
                toStr(row.date),
                row.volume != null ? (row.volume / 10000).toFixed(2) : '',
                row.amount != null ? row.amount : '',
                row.mavol5 != null ? (row.mavol5 / 10000).toFixed(2) : '',
                row.mavol10 != null ? (row.mavol10 / 10000).toFixed(2) : '',
                row.mavol20 != null ? (row.mavol20 / 10000).toFixed(2) : '',
                fmt2(row.ratio_5),
                fmt2(row.ratio_20),
                fmt2(row.change_percent),
                row.close != null ? row.close : '',
                row.turnover_rate != null ? row.turnover_rate : ''
            ]);
        });
        const ws = XLSX.utils.aoa_to_sheet(aoa);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, '成交量异动榜');
        const filename = `成交量异动榜_${this._volumeAberrationDate || new Date().toISOString().split('T')[0]}.xlsx`;
        XLSX.writeFile(wb, filename, { cellStyles: true });
        CommonUtils.showToast('Excel 导出成功', 'success');
    },

    // 高亮并滚动到指定股票
    highlightAndScrollToStock(stockCode) {
        const row = document.querySelector(`#rankingsTableBody tr[data-code="${stockCode}"]`);
        if (row) {
            // 移除之前的高亮
            document.querySelectorAll('#rankingsTableBody tr.highlight').forEach(r => {
                r.classList.remove('highlight');
            });

            // 添加高亮
            row.classList.add('highlight');

            // 滚动到该行
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // 3秒后移除高亮
            setTimeout(() => {
                row.classList.remove('highlight');
            }, 3000);
        }
    },

    _boardKindUi(kind) {
        const isConcept = kind === 'concept';
        return {
            kind: isConcept ? 'concept' : 'industry',
            label: isConcept ? '概念板块' : '行业板块',
            dataKey: isConcept ? 'conceptData' : 'sectorData',
            viewKey: isConcept ? 'conceptView' : 'sectorView',
            countId: isConcept ? 'conceptCount' : 'sectorCount',
            gridId: isConcept ? 'conceptsGrid' : 'sectorsGrid',
            listId: isConcept ? 'conceptsList' : 'sectorsList',
            tbodyId: isConcept ? 'conceptsTableBody' : 'sectorsTableBody',
            listApi: isConcept
                ? '/api/market/concept_board/list'
                : '/api/market/industry_board/list',
            detailApiPrefix: isConcept
                ? '/api/market/concept_board/'
                : '/api/market/industry_board/',
            refreshApi: isConcept
                ? '/api/market/concept_board/refresh_sector_slopes'
                : '/api/market/industry_board/refresh_sector_slopes',
            refreshBtnId: isConcept ? 'refreshConceptSlopeBtn' : 'refreshSectorSlopeBtn',
        };
    },

    // 加载板块数据（同花顺全量列表 + 斜率）；kind=industry|concept
    async loadSectorData(kind = 'industry') {
        const ui = this._boardKindUi(kind);
        const tbody = document.getElementById(ui.tbodyId);
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888;">加载中...</td></tr>';
        }
        try {
            const response = await fetch(
                `${this.API_BASE_URL}${ui.listApi}?board_code_source=tonghuashun`
            );
            const result = await response.json();

            if (result.success && Array.isArray(result.data)) {
                this[ui.dataKey] = result.data;
                this.renderSectorViews(ui.kind);
                // 库空时列表全为 --：自动后台算一次（同花顺），避免概念板从未挂载刷新时长期无斜率
                this._maybeAutoRefreshSectorSlopes(ui.kind);
            } else {
                throw new Error(result.message || 'API返回错误');
            }
        } catch (error) {
            console.error(`${ui.label}数据加载失败:`, error);
            this[ui.dataKey] = [];
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:#c00;">${ui.label}加载失败</td></tr>`;
            }
            const grid = document.getElementById(ui.gridId);
            if (grid) {
                grid.innerHTML = `<div class="empty-tip" style="text-align:center;padding:2em;color:#c00;">${ui.label}加载失败</div>`;
            }
            CommonUtils.showToast(`${ui.label}加载失败`, 'error');
        }
    },

    _countSectorSlopes(rows) {
        if (!Array.isArray(rows)) return 0;
        return rows.filter((x) => x && x.sector_slope != null && !isNaN(Number(x.sector_slope))).length;
    },

    /** 是否已具备完整多窗口斜率（120/60/20/10/5）中的任一板。 */
    _hasFullWindowSlopes(rows) {
        if (!Array.isArray(rows) || !rows.length) return false;
        const keys = [
            'sector_slope_120',
            'sector_slope',
            'sector_slope_20',
            'sector_slope_short',
            'sector_slope_5',
        ];
        return rows.some((x) => {
            if (!x) return false;
            return keys.every((k) => x[k] != null && !isNaN(Number(x[k])));
        });
    },

    /**
     * 列表无完整多窗口斜率且有板数据时，自动触发一次后台刷新（每 kind 每会话最多一次）。
     */
    _maybeAutoRefreshSectorSlopes(kind = 'industry') {
        const ui = this._boardKindUi(kind);
        const rows = this[ui.dataKey] || [];
        if (!rows.length) return;
        // 已有任一板具备全窗口则不自动刷；仅中线有值但缺 120/20/5 时仍会刷一次
        if (this._hasFullWindowSlopes(rows)) return;
        const flagKey = `_autoSlopeRefreshTried_${ui.kind}`;
        if (this[flagKey]) return;
        this[flagKey] = true;
        const hasMid = this._countSectorSlopes(rows) > 0;
        CommonUtils.showToast(
            hasMid
                ? `${ui.label}正在补算 120/20/5 日斜率…`
                : `${ui.label}斜率尚未入库，正在后台计算…`,
            'info'
        );
        this.refreshSectorSlopes(ui.kind);
    },

    /**
     * 刷新同花顺行业/概念板斜率。
     * @param {string} kind industry|concept
     * @param {{ boardCode?: string, boardCodes?: string[], triggerBtn?: HTMLElement }} [opts]
     *   传入 boardCode/boardCodes 时仅重算指定板块（同步等待）；否则全量后台刷新并轮询。
     */
    async refreshSectorSlopes(kind = 'industry', opts = {}) {
        const ui = this._boardKindUi(kind);
        const codes = [];
        if (opts && opts.boardCode) {
            const c = String(opts.boardCode).trim();
            if (c) codes.push(c);
        }
        if (opts && Array.isArray(opts.boardCodes)) {
            opts.boardCodes.forEach((c) => {
                const s = String(c || '').trim();
                if (s && !codes.includes(s)) codes.push(s);
            });
        }
        const singleOrFew = codes.length > 0;
        const toolbarBtn = document.getElementById(ui.refreshBtnId);
        const triggerBtn = (opts && opts.triggerBtn) || (!singleOrFew ? toolbarBtn : null);
        const restoreLabel = singleOrFew ? '重算斜率' : '刷新斜率';

        if (triggerBtn && triggerBtn.disabled) return;
        if (triggerBtn) {
            triggerBtn.disabled = true;
            triggerBtn.textContent = '计算中…';
        }
        try {
            const qs = new URLSearchParams({
                board_code_source: 'tonghuashun',
                board_kind: ui.kind,
                sync: singleOrFew ? 'true' : 'false',
            });
            if (singleOrFew) {
                qs.set('board_codes', codes.join(','));
            }
            const response = await fetch(
                `${this.API_BASE_URL}${ui.refreshApi}?${qs.toString()}`,
                { method: 'POST' }
            );
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.message || (singleOrFew ? '单板斜率重算失败' : '启动斜率刷新失败'));
            }

            if (singleOrFew) {
                const written = Number(result.written != null ? result.written : 0);
                const total = Number(result.total != null ? result.total : codes.length);
                await this.loadSectorData(ui.kind);
                // 若详情弹窗正打开同一板块，刷新详情
                const detail = this._sectorDetailCtx;
                if (
                    detail
                    && detail.kind === ui.kind
                    && codes.includes(String(detail.boardCode || ''))
                ) {
                    this.showSectorDetail(
                        detail.boardName || '',
                        detail.boardCode || '',
                        detail.boardSource || 'tonghuashun',
                        detail.kind
                    );
                }
                if (written > 0) {
                    CommonUtils.showToast(
                        codes.length === 1
                            ? `已重算斜率：${codes[0]}`
                            : `已重算斜率：${written}/${total} 个板块`,
                        'success'
                    );
                } else {
                    CommonUtils.showToast(
                        result.message || '未写入有效斜率（成分不足或数据不足）',
                        'warning'
                    );
                }
                return;
            }

            CommonUtils.showToast(
                result.message || '已启动后台斜率计算，完成后列表将自动更新',
                'success'
            );
            const before = this._countSectorSlopes(this[ui.dataKey]);
            let attempts = 0;
            const maxAttempts = 24; // ~8 分钟（每 20s）
            const timerKey = ui.kind === 'concept'
                ? '_conceptSlopePollTimer'
                : '_sectorSlopePollTimer';
            const poll = async () => {
                attempts += 1;
                try {
                    await this.loadSectorData(ui.kind);
                } catch (_e) { /* loadSectorData 已 toast */ }
                const after = this._countSectorSlopes(this[ui.dataKey]);
                if (after > before || (before === 0 && after > 0)) {
                    if (triggerBtn) {
                        triggerBtn.disabled = false;
                        triggerBtn.textContent = restoreLabel;
                    }
                    CommonUtils.showToast(`斜率已更新：${after} 个板块`, 'success');
                    return;
                }
                if (attempts >= maxAttempts) {
                    if (triggerBtn) {
                        triggerBtn.disabled = false;
                        triggerBtn.textContent = restoreLabel;
                    }
                    CommonUtils.showToast('斜率仍在计算或未写入，请稍后手动刷新列表', 'info');
                    return;
                }
                this[timerKey] = setTimeout(poll, 20000);
            };
            if (this[timerKey]) {
                clearTimeout(this[timerKey]);
            }
            this[timerKey] = setTimeout(poll, 15000);
        } catch (error) {
            console.error('刷新板块斜率失败:', error);
            CommonUtils.showToast(error.message || '刷新板块斜率失败', 'error');
            if (triggerBtn) {
                triggerBtn.disabled = false;
                triggerBtn.textContent = restoreLabel;
            }
        } finally {
            if (singleOrFew && triggerBtn) {
                triggerBtn.disabled = false;
                triggerBtn.textContent = restoreLabel;
            }
        }
    },

    switchSectorView(view, kind = 'industry') {
        const ui = this._boardKindUi(kind);
        this[ui.viewKey] = view === 'grid' ? 'grid' : 'list';
        document.querySelectorAll(`[data-sector-view][data-board-kind="${ui.kind}"]`).forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sectorView === this[ui.viewKey]);
        });
        const grid = document.getElementById(ui.gridId);
        const list = document.getElementById(ui.listId);
        if (grid) grid.style.display = this[ui.viewKey] === 'grid' ? 'grid' : 'none';
        if (list) list.style.display = this[ui.viewKey] === 'list' ? 'block' : 'none';
        this.renderSectorViews(ui.kind);
    },

    renderSectorViews(kind = 'industry') {
        const ui = this._boardKindUi(kind);
        const rows = this[ui.dataKey] || [];
        const countEl = document.getElementById(ui.countId);
        if (countEl) countEl.textContent = String(rows.length || 0);
        this._syncSectorSortHeaders(kind);
        if (this[ui.viewKey] === 'list') {
            this.renderSectorListView(rows, ui.kind);
        } else {
            this.renderSectorGridView(rows, ui.kind);
        }
    },

    _boardEnvSortRank(d, mode = 'mid') {
        const envMap = {
            short: {
                env: (d && d.board_env_short)
                    || (d && d.board_strong_short ? 'strong' : (d && d.board_weak_short ? 'weak' : '')),
            },
            '120': {
                env: (d && d.board_env_120)
                    || (d && d.board_strong_120 ? 'strong' : (d && d.board_weak_120 ? 'weak' : '')),
            },
            '20': {
                env: (d && d.board_env_20)
                    || (d && d.board_strong_20 ? 'strong' : (d && d.board_weak_20 ? 'weak' : '')),
            },
            '5': {
                env: (d && d.board_env_5)
                    || (d && d.board_strong_5 ? 'strong' : (d && d.board_weak_5 ? 'weak' : '')),
            },
            mid: {
                env: (d && d.board_env)
                    || (d && d.board_strong ? 'strong' : (d && d.board_weak ? 'weak' : '')),
            },
        };
        const env = (envMap[mode] || envMap.mid).env;
        if (env === 'strong') return 0;
        if (env === 'neutral') return 1;
        if (env === 'weak') return 2;
        return 3; // unknown / 无斜率
    },

    _slopeSortMeta(sortKey) {
        const key = String(sortKey || 'sector_slope');
        const meta = {
            sector_slope: { key: 'sector_slope', mode: 'mid' },
            sector_slope_short: { key: 'sector_slope_short', mode: 'short' },
            sector_slope_120: { key: 'sector_slope_120', mode: '120' },
            sector_slope_20: { key: 'sector_slope_20', mode: '20' },
            sector_slope_5: { key: 'sector_slope_5', mode: '5' },
        };
        return meta[key] || meta.sector_slope;
    },

    setSectorSort(kind, sortKey) {
        const isConcept = kind === 'concept';
        const keyProp = isConcept ? 'conceptSortKey' : 'sectorSortKey';
        const ascProp = isConcept ? 'conceptSortAsc' : 'sectorSortAsc';
        const key = this._slopeSortMeta(sortKey).key;
        if (this[keyProp] === key) {
            this[ascProp] = !this[ascProp];
        } else {
            this[keyProp] = key;
            this[ascProp] = false; // 新列默认降序（斜率高优先）
        }
        this._syncSectorSortHeaders(kind);
        this.renderSectorViews(kind);
    },

    _syncSectorSortHeaders(kind = 'industry') {
        const isConcept = kind === 'concept';
        const activeKey = isConcept
            ? (this.conceptSortKey || 'sector_slope')
            : (this.sectorSortKey || 'sector_slope');
        const asc = isConcept ? !!this.conceptSortAsc : !!this.sectorSortAsc;
        document.querySelectorAll(
            `.sectors-table th.th-sortable[data-board-kind="${isConcept ? 'concept' : 'industry'}"]`
        ).forEach(th => {
            const key = th.dataset.sortKey || '';
            const ind = th.querySelector('.sort-indicator');
            const active = key === activeKey;
            th.classList.toggle('is-sorted', active);
            if (ind) ind.textContent = active ? (asc ? '↑' : '↓') : '';
        });
    },

    _sortedSectors(sectors, kind = 'industry') {
        const list = Array.isArray(sectors) ? sectors.slice() : [];
        const key = kind === 'concept'
            ? (this.conceptSortKey || 'sector_slope')
            : (this.sectorSortKey || 'sector_slope');
        const asc = kind === 'concept' ? !!this.conceptSortAsc : !!this.sectorSortAsc;
        const slopeKeys = new Set([
            'sector_slope',
            'sector_slope_short',
            'sector_slope_120',
            'sector_slope_20',
            'sector_slope_5',
        ]);
        list.sort((a, b) => {
            // 各窗口斜率：先按对应环境档，再按斜率数值
            if (slopeKeys.has(key)) {
                const mode = this._slopeSortMeta(key).mode;
                const ra = this._boardEnvSortRank(a, mode);
                const rb = this._boardEnvSortRank(b, mode);
                if (ra !== rb) return ra - rb;
                const na = a[key] == null || a[key] === '' ? null : Number(a[key]);
                const nb = b[key] == null || b[key] === '' ? null : Number(b[key]);
                if (na == null && nb == null) {
                    return String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh');
                }
                if (na == null) return 1;
                if (nb == null) return -1;
                const cmp = asc ? na - nb : nb - na;
                if (cmp !== 0) return cmp;
                return String(a.board_name || '').localeCompare(String(b.board_name || ''), 'zh');
            }
            let va = a[key];
            let vb = b[key];
            if (key === 'board_name' || key === 'board_code') {
                va = String(va || '');
                vb = String(vb || '');
                return asc ? va.localeCompare(vb, 'zh') : vb.localeCompare(va, 'zh');
            }
            const na = va == null || va === '' ? null : Number(va);
            const nb = vb == null || vb === '' ? null : Number(vb);
            if (na == null && nb == null) return 0;
            if (na == null) return 1;
            if (nb == null) return -1;
            return asc ? na - nb : nb - na;
        });
        return list;
    },

    formatAmount(val) {
        if (val == null || val === '' || isNaN(Number(val))) return '--';
        const n = Number(val);
        const abs = Math.abs(n);
        if (abs >= 1e8) return (n / 1e8).toFixed(2) + '亿';
        if (abs >= 1e4) return (n / 1e4).toFixed(2) + '万';
        return n.toFixed(2);
    },

    /** 行业板指数点位（东财「最新价」）；与个股最新价区分，保留两位小数 */
    formatBoardIndex(val) {
        if (val == null || val === '' || isNaN(Number(val))) return '--';
        return Number(val).toFixed(2);
    },

    /**
     * 行业板块成交量 → 固定「万」单位数值（两位小数，单位见标签）。
     * 同花顺/库内 realtime 口径多为「万手」；若量级像「手」(≥1e5) 则 /10000。
     */
    formatBoardVolumeWan(val) {
        if (val == null || val === '' || isNaN(Number(val))) return '--';
        const n = Number(val);
        const wan = Math.abs(n) >= 1e5 ? n / 1e4 : n;
        return wan.toFixed(2);
    },

    /**
     * 行业板块成交额 → 固定「亿」单位数值（两位小数，单位见标签）。
     * 同花顺/库内 realtime 口径多为「亿元」；若量级像「元」(≥1e6) 则 /1e8。
     */
    formatBoardAmountYi(val) {
        if (val == null || val === '' || isNaN(Number(val))) return '--';
        const n = Number(val);
        const yi = Math.abs(n) >= 1e6 ? n / 1e8 : n;
        return yi.toFixed(2);
    },

    formatSlope(val) {
        // ln(I_t) 日斜率量级较小，展示四位小数
        if (val == null || val === '' || isNaN(Number(val))) return '--';
        return Number(val).toFixed(4);
    },

    formatR2(val) {
        if (val == null || val === '' || isNaN(Number(val))) return '--';
        return Number(val).toFixed(3);
    },

    formatSlopeSource(src) {
        const s = String(src || '').trim();
        if (s === 'ths_index') return '同花顺指数';
        if (s === 'equal_weight_return') return '等权收益';
        return s || '--';
    },

    boardEnvChipHtml(d, mode = 'mid') {
        let env = '';
        let label = '';
        let tipRaw = '';
        if (mode === 'trend') {
            env = (d && d.board_trend_env) || '';
            label = (d && d.board_trend_label) || '--';
            tipRaw = (d && d.board_trend_summary) || label;
        } else if (mode === 'short') {
            env = (d && d.board_env_short) || (d && d.board_strong_short ? 'strong' : (d && d.board_weak_short ? 'weak' : ''));
            label = (d && d.board_env_short_label)
                || (env === 'strong' ? '走强' : env === 'weak' ? '走弱' : env === 'neutral' ? '正常' : '--');
            tipRaw = (d && (d.board_weak_short_summary || d.board_env_short_label)) || '短线环境';
        } else if (mode === '120' || mode === '20' || mode === '5') {
            env = (d && d[`board_env_${mode}`])
                || (d && d[`board_strong_${mode}`] ? 'strong' : (d && d[`board_weak_${mode}`] ? 'weak' : ''));
            label = (d && d[`board_env_${mode}_label`])
                || (env === 'strong' ? '走强' : env === 'weak' ? '走弱' : env === 'neutral' ? '正常' : '--');
            tipRaw = (d && d[`board_env_${mode}_label`]) || `${mode}日环境`;
        } else {
            env = (d && d.board_env) || (d && d.board_strong ? 'strong' : (d && d.board_weak ? 'weak' : ''));
            label = (d && d.board_env_label)
                || (env === 'strong' ? '走强' : env === 'weak' ? '走弱' : env === 'neutral' ? '正常' : '--');
            tipRaw = (d && (d.board_weak_summary || d.board_weak_reason)) || '';
        }
        const tip = this.escapeHtml(tipRaw);
        let cls = 'sector-weak-chip unknown';
        if (env === 'strong') cls = 'sector-weak-chip strong';
        else if (env === 'weak') cls = 'sector-weak-chip weak';
        else if (env === 'neutral') cls = 'sector-weak-chip ok';
        else if (env === 'mixed') cls = 'sector-weak-chip mixed';
        return `<span class="${cls}" title="${tip}">${this.escapeHtml(label)}</span>`;
    },

    boardTrendSummaryHtml(d) {
        const summary = (d && d.board_trend_summary)
            || (d && d.board_weak_summary)
            || '暂无判断说明';
        const chip = d && d.board_trend_label
            ? this.boardEnvChipHtml(d, 'trend')
            : this.boardEnvChipHtml(d);
        return `
            <div class="sector-trend-summary-head">
                <span class="sector-trend-summary-title">综合走势</span>
                ${chip}
            </div>
            <div class="sector-trend-summary-body">${this.escapeHtml(summary)}</div>
        `;
    },

    escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    renderSectorListView(sectors, kind = 'industry') {
        const ui = this._boardKindUi(kind);
        const tbody = document.getElementById(ui.tbodyId);
        if (!tbody) return;
        const rows = this._sortedSectors(sectors, ui.kind);
        if (!rows.length) {
            tbody.innerHTML = `<tr><td colspan="11" class="ops-empty-cell">暂无同花顺${ui.label}数据</td></tr>`;
            return;
        }
        tbody.innerHTML = rows.map(sector => {
            const code = this.escapeHtml(sector.board_code || '');
            const name = this.escapeHtml(sector.board_name || '--');
            const srcRaw = this.escapeHtml(sector.board_code_source || 'tonghuashun');
            const cp = sector.change_percent;
            const memberCount = sector.member_count != null ? sector.member_count : (sector.stock_count != null ? sector.stock_count : '--');
            return `
                <tr data-board-code="${code}" data-board-source="${srcRaw}" data-board-name="${name}">
                    <td>
                        <div class="stock-info-cell">
                            <span class="stock-name">${name}</span>
                            <span class="stock-code">${code || '--'}</span>
                        </div>
                    </td>
                    <td>${this.formatBoardIndex(sector.latest_price)}</td>
                    <td class="${this.getChangeClass(cp)}">${cp == null ? '--' : this.formatPercent(cp)}</td>
                    <td>${this.formatBoardAmountYi(sector.amount)}</td>
                    <td>${memberCount}</td>
                    <td class="${this.getChangeClass(sector.sector_slope_120)}">${this.formatSlope(sector.sector_slope_120)}</td>
                    <td class="${this.getChangeClass(sector.sector_slope)}">${this.formatSlope(sector.sector_slope)}</td>
                    <td class="${this.getChangeClass(sector.sector_slope_20)}">${this.formatSlope(sector.sector_slope_20)}</td>
                    <td class="${this.getChangeClass(sector.sector_slope_short)}">${this.formatSlope(sector.sector_slope_short)}</td>
                    <td class="${this.getChangeClass(sector.sector_slope_5)}">${this.formatSlope(sector.sector_slope_5)}</td>
                    <td class="sector-row-actions">
                        <div class="sector-row-actions-inner">
                            <button type="button" class="btn btn-secondary sector-row-detail-btn">详情</button>
                            <button type="button" class="btn btn-secondary sector-row-slope-btn" title="仅重算该板块斜率">重算斜率</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        tbody.querySelectorAll('tr[data-board-code]').forEach(tr => {
            const openDetail = (e) => {
                if (e.target.closest('button') && !e.target.closest('.sector-row-detail-btn')) return;
                goToSectorDetail(
                    tr.dataset.boardName || '',
                    tr.dataset.boardCode || '',
                    tr.dataset.boardSource || 'tonghuashun',
                    ui.kind
                );
            };
            tr.addEventListener('click', openDetail);
            const slopeBtn = tr.querySelector('.sector-row-slope-btn');
            if (slopeBtn) {
                slopeBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.refreshSectorSlopes(ui.kind, {
                        boardCode: tr.dataset.boardCode || '',
                        triggerBtn: slopeBtn,
                    });
                });
            }
        });
    },

    renderSectorGridView(sectors, kind = 'industry') {
        const ui = this._boardKindUi(kind);
        const grid = document.getElementById(ui.gridId);
        if (!grid) return;
        const rows = this._sortedSectors(sectors, ui.kind);
        if (!rows.length) {
            grid.innerHTML = `<div class="empty-tip ops-empty-tip">暂无同花顺${ui.label}数据</div>`;
            return;
        }
        grid.innerHTML = rows.map(sector => {
            const code = this.escapeHtml(sector.board_code || '');
            const name = this.escapeHtml(sector.board_name || '未知板块');
            const srcRaw = this.escapeHtml(sector.board_code_source || 'tonghuashun');
            const sourceLabel = this.escapeHtml(sector.board_code_source_label || '同花顺');
            const cp = parseFloat(sector.change_percent);
            const hasCp = sector.change_percent != null && !isNaN(cp);
            const upCount = sector.up_count != null ? Number(sector.up_count) : '--';
            const downCount = sector.down_count != null ? Number(sector.down_count) : '--';
            const memberCount = sector.member_count != null ? sector.member_count : (sector.stock_count != null ? sector.stock_count : '--');
            const leadingName = this.escapeHtml(sector.leading_stock_name || '--');
            const leadingCp = sector.leading_stock_change_percent;
            return `
                <div class="sector-card" data-board-code="${code}" data-board-source="${srcRaw}" data-board-name="${name}">
                    <div class="sector-header">
                        <h3>${name}<span class="board-source-chip" title="代码来源">${sourceLabel}</span></h3>
                        <span class="sector-change ${hasCp ? this.getChangeClass(cp) : ''}">${hasCp ? this.formatPercent(cp) : '--'}</span>
                    </div>
                    <div class="sector-stats">
                        <div class="stat-item">
                            <span class="label">上涨</span>
                            <span class="value positive">${upCount}</span>
                        </div>
                        <div class="stat-item">
                            <span class="label">下跌</span>
                            <span class="value negative">${downCount}</span>
                        </div>
                        <div class="stat-item">
                            <span class="label">成分</span>
                            <span class="value">${memberCount}</span>
                        </div>
                    </div>
                    <div class="sector-leaders">
                        <div class="leader-stock">
                            <span class="stock-name">领涨 ${leadingName}</span>
                            <span class="stock-change ${this.getChangeClass(leadingCp)}">${leadingCp == null ? '--' : this.formatPercent(leadingCp)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">120日斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope_120)}">${this.formatSlope(sector.sector_slope_120)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">60日斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope)}">${this.formatSlope(sector.sector_slope)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">20日斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope_20)}">${this.formatSlope(sector.sector_slope_20)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">10日斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope_short)}">${this.formatSlope(sector.sector_slope_short)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">5日斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope_5)}">${this.formatSlope(sector.sector_slope_5)}</span>
                        </div>
                    </div>
                    <div class="sector-card-actions">
                        <button type="button" class="sector-detail-btn">查看详情</button>
                        <button type="button" class="sector-slope-btn" title="仅重算该板块斜率">重算斜率</button>
                    </div>
                </div>
            `;
        }).join('');

        grid.querySelectorAll('.sector-card').forEach(card => {
            const open = () => goToSectorDetail(
                card.dataset.boardName || '',
                card.dataset.boardCode || '',
                card.dataset.boardSource || 'tonghuashun',
                ui.kind
            );
            card.querySelector('.sector-detail-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                open();
            });
            card.querySelector('.sector-slope-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                const btn = e.currentTarget;
                this.refreshSectorSlopes(ui.kind, {
                    boardCode: card.dataset.boardCode || '',
                    triggerBtn: btn,
                });
            });
            card.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                open();
            });
        });
    },

    hideSectorDetailModal() {
        this._sectorDetailCtx = null;
        const modal = document.getElementById('sectorDetailModal');
        if (modal) modal.classList.remove('show');
    },

    /** 详情 API：优先 leaders/mids 全量列表（有几只渲染几只），兼容旧 leader/mid 单对象与 roles 嵌套。 */
    _normalizeSectorRoleList(d, listKey, singularKey) {
        if (Array.isArray(d[listKey])) return d[listKey];
        const nested = d.roles && Array.isArray(d.roles[listKey]) ? d.roles[listKey] : null;
        if (nested) return nested;
        const one = d[singularKey];
        if (one && (one.code || one.name)) return [one];
        const nestedOne = d.roles && d.roles[singularKey];
        if (nestedOne && (nestedOne.code || nestedOne.name)) return [nestedOne];
        return [];
    },

    /** 对齐分析频道板块分析短线角色 pill；优先 StockTradeLink 打开交易分析 Tab */
    _stockDetailHref(code, name) {
        const c = String(code || '').trim();
        if (!c) return '';
        if (window.StockTradeLink && typeof StockTradeLink.buildHref === 'function') {
            return StockTradeLink.buildHref(c, name, { tab: 'analysis' });
        }
        const q = new URLSearchParams({ code: c });
        const nm = String(name || '').trim();
        if (nm) q.set('name', nm);
        q.set('tab', 'analysis');
        return `stock.html?${q.toString()}`;
    },

    _formatSectorRolePct(v) {
        if (v == null || !Number.isFinite(Number(v))) return '';
        const n = Number(v);
        const sign = n > 0 ? '+' : '';
        return `${sign}${n.toFixed(2)}%`;
    },

    _renderSectorRolePill(kind, s) {
        const code = s.code || s.stock_code || '';
        const name = s.name || s.stock_name || '';
        const label = kind === 'leader' ? '龙头' : '中军';
        const cls =
            kind === 'leader' ? 'ba-role-pill ba-role-pill--leader' : 'ba-role-pill ba-role-pill--mid';
        const pct = this._formatSectorRolePct(s.change_percent);
        const pctHtml = pct ? ` (${this.escapeHtml(pct)})` : '';
        const title = this.escapeHtml(s.role_reason || label);
        let show;
        if (code && name) show = `${this.escapeHtml(code)} ${this.escapeHtml(name)}`;
        else show = this.escapeHtml(name || code || '--');
        if (!code) {
            return `<span class="${cls}" title="${title}">${label} ${show}${pctHtml}</span>`;
        }
        const href = this._stockDetailHref(code, name);
        return `<a class="${cls}" href="${this.escapeHtml(href)}" target="_blank" rel="noopener noreferrer" title="${title}">${label} ${show}${pctHtml}</a>`;
    },

    /** 故意不 slice：分类结果有几只就展示几只；视觉对齐 BoardRolesPanel.renderShortlineRoles */
    _renderSectorRolesSection(leaders, mids) {
        const pills = [
            ...leaders.map((s) => this._renderSectorRolePill('leader', s)),
            ...mids.map((s) => this._renderSectorRolePill('mid', s)),
        ];
        const body = pills.length
            ? pills.join('')
            : '<span class="ba-muted">暂无</span>';
        return `<div class="ba-short-roles">
            <span class="ba-short-roles-label">短线角色：</span>
            ${body}
        </div>`;
    },

    async showSectorDetail(boardName, boardCode, boardSource, boardKind = 'industry') {
        const ui = this._boardKindUi(boardKind);
        const modal = document.getElementById('sectorDetailModal');
        const title = document.getElementById('sectorDetailTitle');
        const sub = document.getElementById('sectorDetailSub');
        const body = document.getElementById('sectorDetailBody');
        if (!modal || !body) return;

        modal.classList.add('show');
        this._sectorDetailCtx = {
            kind: ui.kind,
            boardCode: boardCode || '',
            boardName: boardName || '',
            boardSource: boardSource || 'tonghuashun',
        };
        this._sectorSlopeTrendActiveWins = null;
        this._sectorSlopeTrendData = null;
        if (title) title.textContent = boardName || boardCode || '板块详情';
        if (sub) {
            sub.textContent = `${ui.label} · ${boardCode || '--'} · ${boardSource || 'tonghuashun'}`;
        }
        body.innerHTML = '<div class="sector-detail-loading">加载中...</div>';

        try {
            const params = new URLSearchParams({
                board_code_source: boardSource || 'tonghuashun',
                include_roles: 'true',
            });
            if (boardName) params.set('board_name', boardName);
            const response = await fetch(
                `${this.API_BASE_URL}${ui.detailApiPrefix}${encodeURIComponent(boardCode)}/detail?${params}`
            );
            const result = await response.json();
            if (!result.success || !result.data) {
                throw new Error(result.message || '详情加载失败');
            }
            this.renderSectorDetail(result.data);
        } catch (err) {
            console.error(err);
            body.innerHTML = `<div class="sector-detail-error">${this.escapeHtml(err.message || '详情加载失败')}</div>`;
        }
    },

    renderSectorDetail(d) {
        const title = document.getElementById('sectorDetailTitle');
        const sub = document.getElementById('sectorDetailSub');
        const body = document.getElementById('sectorDetailBody');
        if (!body) return;

        if (title) title.textContent = d.board_name || d.board_code || '板块详情';
        if (sub) {
            const kindLabel = d.board_kind === 'concept' ? '概念板块' : '行业板块';
            sub.innerHTML = `${kindLabel} · ${this.escapeHtml(d.board_code || '--')} · ${this.escapeHtml(d.board_code_source_label || d.board_code_source || '')}${d.mapped_em_board_code ? ` · 映射东财 ${this.escapeHtml(d.mapped_em_board_code)}` : ''}${d.mapped_ths_board_code ? ` · 映射同花顺 ${this.escapeHtml(d.mapped_ths_board_code)}` : ''}${d.quote_board_code && d.quote_board_code !== d.board_code ? ` · 行情码 ${this.escapeHtml(d.quote_board_code)}` : ''}${d.board_trend_label ? this.boardEnvChipHtml(d, 'trend') : this.boardEnvChipHtml(d)}`;
        }

        const item = (label, value, cls) => `
            <div class="sector-detail-item">
                <span class="label">${label}</span>
                <span class="value ${cls || ''}">${value}</span>
            </div>
        `;
        const cp = d.change_percent;
        const leaders = this._normalizeSectorRoleList(d, 'leaders', 'leader');
        const mids = this._normalizeSectorRoleList(d, 'mids', 'mid');
        const rolesHtml = this._renderSectorRolesSection(leaders, mids);

        body.innerHTML = `
            <div class="sector-detail-grid">
                ${item('指数', this.formatBoardIndex(d.latest_price))}
                ${item('涨跌幅', cp == null ? '--' : this.formatPercent(cp), this.getChangeClass(cp))}
                ${item('涨跌额', d.change_amount != null ? Number(d.change_amount).toFixed(2) : '--', this.getChangeClass(d.change_amount))}
                ${item('成交额(亿)', this.formatBoardAmountYi(d.amount))}
                ${item('成交量(万)', this.formatBoardVolumeWan(d.volume))}
                ${item('换手率', d.turnover_rate != null ? Number(d.turnover_rate).toFixed(2) + '%' : '--')}
                ${item('上涨/下跌', `${d.up_count != null ? d.up_count : '--'} / ${d.down_count != null ? d.down_count : '--'}`)}
                ${item('成分股数量', d.member_count != null ? d.member_count : (d.stock_count != null ? d.stock_count : '--'))}
            </div>
            <div class="sector-detail-section">
                <h3>板块斜率与强弱</h3>
                
                <div class="sector-detail-actions">
                    <button type="button" class="btn btn-secondary sector-detail-slope-btn" title="仅重算当前板块斜率">重算斜率</button>
                    <button type="button" class="btn btn-primary sector-detail-rpe-btn" title="进入比价效应策略选股（预选当前板块）">比价选股</button>
                </div>
                <div class="sector-detail-grid">
                    ${item('120日斜率(ln)', this.formatSlope(d.sector_slope_120), this.getChangeClass(d.sector_slope_120))}
                    ${item('120日环境', this.boardEnvChipHtml(d, '120'))}
                    ${item('60日斜率(ln)', this.formatSlope(d.sector_slope), this.getChangeClass(d.sector_slope))}
                    ${item('中线环境', this.boardEnvChipHtml(d))}
                    ${item('20日斜率(ln)', this.formatSlope(d.sector_slope_20), this.getChangeClass(d.sector_slope_20))}
                    ${item('20日环境', this.boardEnvChipHtml(d, '20'))}
                    ${item('10日斜率(ln)', this.formatSlope(d.sector_slope_short), this.getChangeClass(d.sector_slope_short))}
                    ${item('短线环境', this.boardEnvChipHtml(d, 'short'))}
                    ${item('5日斜率(ln)', this.formatSlope(d.sector_slope_5), this.getChangeClass(d.sector_slope_5))}
                    ${item('5日环境', this.boardEnvChipHtml(d, '5'))}
                    ${item('斜率来源', this.formatSlopeSource(d.slope_source))}
                    ${item('60日 R²', this.formatR2(d.slope_r2))}
                    ${item('60日asof', d.slope_asof_date || '--')}
                    ${item('10日asof', d.slope_short_asof_date || '--')}
                    ${item('member_count_used', d.member_count_used != null ? d.member_count_used : '--')}
                </div>
                <div class="sector-detail-summary">${this.boardTrendSummaryHtml(d)}</div>
                <div class="sector-slope-trend-wrap">
                    <div class="sector-slope-trend-head">
                        <span class="sector-slope-trend-title">斜率趋势</span>
                        <span class="sector-slope-trend-hint">5 / 10 / 20 / 60 / 120 日 · 近60个交易日</span>
                    </div>
                    <div id="sectorSlopeTrendHost" class="sector-slope-trend-host">
                        <div class="sector-detail-loading">斜率趋势加载中…</div>
                    </div>
                </div>
            </div>
            <div class="sector-detail-section sector-fund-flow-section">
                <h3>资金流向</h3>
                <div id="sectorFundFlowHost" class="sector-fund-flow-host">
                    <div class="sector-detail-loading">资金流向加载中…</div>
                </div>
            </div>
            <div class="sector-detail-section">
                <h3>龙头 / 中军</h3>
                ${rolesHtml}
            </div>
            <div class="sector-detail-section sector-limit-up-section">
                <h3>本轮涨停分析</h3>
                <div id="sectorLimitUpHost" class="sector-limit-up-host">
                    <div class="sector-detail-loading">涨停分析加载中…</div>
                </div>
            </div>
            <div class="sector-detail-section">
                <h3>更新时间</h3>
                <div class="sector-detail-meta">${this.escapeHtml(d.update_time || '--')}</div>
            </div>
        `;

        const kind = (d.board_kind === 'concept') ? 'concept' : 'industry';
        const code = d.board_code || (this._sectorDetailCtx && this._sectorDetailCtx.boardCode) || '';
        const slopeBtn = body.querySelector('.sector-detail-slope-btn');
        if (slopeBtn) {
            slopeBtn.addEventListener('click', () => {
                this.refreshSectorSlopes(kind, {
                    boardCode: code,
                    triggerBtn: slopeBtn,
                });
            });
        }
        const rpeBtn = body.querySelector('.sector-detail-rpe-btn');
        if (rpeBtn) {
            rpeBtn.addEventListener('click', () => {
                this.goToRpeScreeningFromSector(d);
            });
        }

        const src = String(d.board_code_source || (this._sectorDetailCtx && this._sectorDetailCtx.boardSource) || 'tonghuashun').trim();
        this.loadSectorSlopeTrend(kind, code);
        this.loadSectorFundFlow(kind, code, src);
        this.loadSectorLimitUpStocks(kind, code, src, d.board_name || '', {
            waveStartMode: (this._sectorLimitUpPrefs && this._sectorLimitUpPrefs.waveStartMode) || 'board_start',
            startMinCount: (this._sectorLimitUpPrefs && this._sectorLimitUpPrefs.startMinCount) || 2,
        });
    },

    async loadSectorSlopeTrend(kind, boardCode, days = 60) {
        const host = document.getElementById('sectorSlopeTrendHost');
        if (!host) return;
        const code = String(boardCode || '').trim();
        if (!code) {
            host.innerHTML = '<div class="sector-detail-meta">缺少板块代码</div>';
            return;
        }
        const token = `${kind}|${code}|slopeTrend|${days}|${Date.now()}`;
        this._sectorSlopeTrendToken = token;
        host.innerHTML = '<div class="sector-detail-loading">斜率趋势加载中…</div>';
        try {
            const ui = this._boardKindUi(kind);
            const params = new URLSearchParams({
                days: String(days || 60),
                windows: '5,10,20,60,120',
            });
            const url = `${this.API_BASE_URL}${ui.detailApiPrefix}${encodeURIComponent(code)}/sector_slope_series?${params}`;
            const resp = await fetch(url);
            const result = await resp.json().catch(() => ({}));
            if (this._sectorSlopeTrendToken !== token) return;
            if (!resp.ok || !result.success) {
                host.innerHTML = `<div class="sector-detail-meta">${this.escapeHtml((result && result.message) || '暂无斜率趋势数据')}</div>`;
                return;
            }
            this.renderSectorSlopeTrend(host, result.data || {});
        } catch (err) {
            if (this._sectorSlopeTrendToken !== token) return;
            console.error(err);
            host.innerHTML = `<div class="sector-detail-error">${this.escapeHtml(err.message || '斜率趋势加载失败')}</div>`;
        }
    },

    _slopeTrendWindowMeta() {
        return [
            { w: 5, label: '5日', color: '#f59e0b' },
            { w: 10, label: '10日', color: '#8b5cf6' },
            { w: 20, label: '20日', color: '#06b6d4' },
            { w: 60, label: '60日', color: '#2563eb' },
            { w: 120, label: '120日', color: '#dc2626' },
        ];
    },

    renderSectorSlopeTrend(host, data) {
        if (!host) return;
        const seriesMap = (data && data.series) || {};
        const meta = this._slopeTrendWindowMeta();
        const hasAny = meta.some((m) => Array.isArray(seriesMap[String(m.w)]) && seriesMap[String(m.w)].length > 0);
        if (!hasAny) {
            host.innerHTML = '<div class="sector-detail-meta">暂无斜率历史（需日度入库；可点「重算斜率」）</div>';
            return;
        }

        const active = new Set(
            (this._sectorSlopeTrendActiveWins && this._sectorSlopeTrendActiveWins.size)
                ? [...this._sectorSlopeTrendActiveWins]
                : meta.map((m) => m.w)
        );
        this._sectorSlopeTrendActiveWins = active;
        this._sectorSlopeTrendData = data;

        const legend = meta.map((m) => {
            const n = (seriesMap[String(m.w)] || []).length;
            const on = active.has(m.w);
            return `<button type="button" class="sector-slope-legend-btn${on ? ' is-on' : ''}" data-win="${m.w}" style="--leg:${m.color}" ${n ? '' : 'disabled'}>
                <span class="sector-slope-legend-swatch"></span>${m.label}<span class="sector-slope-legend-n">${n || 0}</span>
            </button>`;
        }).join('');

        const latestBits = meta.map((m) => {
            const pts = seriesMap[String(m.w)] || [];
            const last = pts.length ? pts[pts.length - 1] : null;
            const v = last && last.sector_slope != null ? Number(last.sector_slope) : null;
            return `<div class="sector-slope-latest-item">
                <span class="sector-slope-latest-lab" style="color:${m.color}">${m.label}</span>
                <span class="sector-slope-latest-val ${this.getChangeClass(v)}">${this.formatSlope(v)}</span>
            </div>`;
        }).join('');

        host.innerHTML = `
            <div class="sector-slope-legend">${legend}</div>
            <div class="sector-slope-latest">${latestBits}</div>
            <div class="sector-slope-chart-box">
                <canvas id="sectorSlopeTrendCanvas" width="640" height="220" aria-label="板块斜率趋势图"></canvas>
            </div>
            <div class="sector-slope-chart-foot" id="sectorSlopeTrendFoot"></div>
        `;

        host.querySelectorAll('.sector-slope-legend-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const w = Number(btn.getAttribute('data-win'));
                if (!Number.isFinite(w)) return;
                if (active.has(w)) {
                    if (active.size <= 1) return;
                    active.delete(w);
                } else {
                    active.add(w);
                }
                this.renderSectorSlopeTrend(host, this._sectorSlopeTrendData || data);
            });
        });

        this.drawSectorSlopeTrendChart(
            document.getElementById('sectorSlopeTrendCanvas'),
            data,
            active,
            document.getElementById('sectorSlopeTrendFoot')
        );
    },

    drawSectorSlopeTrendChart(canvas, data, activeWins, footEl) {
        if (!canvas) return;
        const seriesMap = (data && data.series) || {};
        const meta = this._slopeTrendWindowMeta().filter((m) => activeWins.has(m.w));
        const box = canvas.parentElement;
        const cssW = Math.max(280, (box && box.clientWidth) || 640);
        const cssH = 220;
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = Math.floor(cssW * dpr);
        canvas.height = Math.floor(cssH * dpr);
        canvas.style.width = `${cssW}px`;
        canvas.style.height = `${cssH}px`;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);

        const pad = { t: 14, r: 12, b: 28, l: 52 };
        const plotW = cssW - pad.l - pad.r;
        const plotH = cssH - pad.t - pad.b;

        const dateSet = new Set();
        meta.forEach((m) => {
            (seriesMap[String(m.w)] || []).forEach((p) => {
                if (p && p.date) dateSet.add(String(p.date).slice(0, 10));
            });
        });
        const dates = [...dateSet].sort();
        if (!dates.length) {
            ctx.fillStyle = '#94a3b8';
            ctx.font = '13px sans-serif';
            ctx.fillText('无有效点', pad.l, pad.t + 20);
            if (footEl) footEl.textContent = '';
            return;
        }
        const dateIndex = new Map(dates.map((d, i) => [d, i]));

        let ymin = 0;
        let ymax = 0;
        let hasVal = false;
        meta.forEach((m) => {
            (seriesMap[String(m.w)] || []).forEach((p) => {
                const v = p && p.sector_slope != null ? Number(p.sector_slope) : NaN;
                if (!Number.isFinite(v)) return;
                if (!hasVal) {
                    ymin = ymax = v;
                    hasVal = true;
                } else {
                    ymin = Math.min(ymin, v);
                    ymax = Math.max(ymax, v);
                }
            });
        });
        if (!hasVal) {
            ctx.fillStyle = '#94a3b8';
            ctx.font = '13px sans-serif';
            ctx.fillText('无有效斜率', pad.l, pad.t + 20);
            return;
        }
        if (ymin === ymax) {
            ymin -= 0.001;
            ymax += 0.001;
        }
        const padY = (ymax - ymin) * 0.12;
        ymin -= padY;
        ymax += padY;
        if (ymin > 0) ymin = 0;
        if (ymax < 0) ymax = 0;

        const xAt = (i) => pad.l + (dates.length === 1 ? plotW / 2 : (plotW * i) / (dates.length - 1));
        const yAt = (v) => pad.t + plotH * (1 - (v - ymin) / (ymax - ymin));

        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        for (let g = 0; g <= 4; g++) {
            const y = pad.t + (plotH * g) / 4;
            ctx.beginPath();
            ctx.moveTo(pad.l, y);
            ctx.lineTo(pad.l + plotW, y);
            ctx.stroke();
            const val = ymax - ((ymax - ymin) * g) / 4;
            ctx.fillStyle = '#94a3b8';
            ctx.font = '10px ui-monospace, Consolas, monospace';
            ctx.textAlign = 'right';
            ctx.fillText(val.toFixed(4), pad.l - 6, y + 3);
        }
        if (ymin < 0 && ymax > 0) {
            const y0 = yAt(0);
            ctx.strokeStyle = '#94a3b8';
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(pad.l, y0);
            ctx.lineTo(pad.l + plotW, y0);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        meta.forEach((m) => {
            const pts = (seriesMap[String(m.w)] || [])
                .map((p) => {
                    const d = String(p.date || '').slice(0, 10);
                    const v = p.sector_slope != null ? Number(p.sector_slope) : NaN;
                    const i = dateIndex.get(d);
                    if (i == null || !Number.isFinite(v)) return null;
                    return { i, v, d };
                })
                .filter(Boolean);
            if (pts.length < 1) return;
            ctx.strokeStyle = m.color;
            ctx.lineWidth = m.w === 60 ? 2.4 : 1.7;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.beginPath();
            pts.forEach((p, idx) => {
                const x = xAt(p.i);
                const y = yAt(p.v);
                if (idx === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
            const last = pts[pts.length - 1];
            ctx.fillStyle = m.color;
            ctx.beginPath();
            ctx.arc(xAt(last.i), yAt(last.v), 3.2, 0, Math.PI * 2);
            ctx.fill();
        });

        ctx.fillStyle = '#64748b';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        const tickIdx = dates.length === 1
            ? [0]
            : [0, Math.floor((dates.length - 1) / 2), dates.length - 1];
        [...new Set(tickIdx)].forEach((i) => {
            const label = String(dates[i] || '').slice(5);
            ctx.fillText(label, xAt(i), cssH - 8);
        });

        if (footEl) {
            footEl.textContent = `样本 ${dates[0]} ~ ${dates[dates.length - 1]}（${dates.length} 日）· 虚线为零轴 · 点击图例可显隐窗口`;
        }
    },

    async loadSectorLimitUpStocks(kind, boardCode, boardSource, boardName, prefs) {
        const host = document.getElementById('sectorLimitUpHost');
        if (!host) return;
        const code = String(boardCode || '').trim();
        if (!code) {
            host.innerHTML = '<div class="sector-detail-meta">缺少板块代码</div>';
            return;
        }
        const options = prefs || {};
        const waveStartMode = String(options.waveStartMode || 'board_start').trim() || 'board_start';
        const startMinCount = Math.max(1, Math.min(50, Number(options.startMinCount) || 2));
        this._sectorLimitUpPrefs = {
            kind,
            boardCode: code,
            boardSource: boardSource || 'tonghuashun',
            boardName: boardName || '',
            waveStartMode,
            startMinCount,
        };
        const token = `${kind}|${code}|limitup|${waveStartMode}|${startMinCount}|${Date.now()}`;
        this._sectorLimitUpToken = token;
        host.innerHTML = '<div class="sector-detail-loading">涨停分析加载中…</div>';
        try {
            const ui = this._boardKindUi(kind);
            const params = new URLSearchParams({
                board_code_source: boardSource || 'tonghuashun',
                days: '60',
                wave_start_mode: waveStartMode,
                start_min_count: String(startMinCount),
            });
            if (boardName) params.set('board_name', boardName);
            const url = `${this.API_BASE_URL}${ui.detailApiPrefix}${encodeURIComponent(code)}/limit_up_stocks?${params}`;
            const resp = await fetch(url);
            const result = await resp.json().catch(() => ({}));
            if (this._sectorLimitUpToken !== token) return;
            if (!resp.ok || !result.success) {
                host.innerHTML = `<div class="sector-detail-meta">${this.escapeHtml((result && result.message) || '暂无涨停分析数据')}</div>`;
                return;
            }
            this.renderSectorLimitUpStocks(host, result.data || {});
        } catch (err) {
            if (this._sectorLimitUpToken !== token) return;
            console.error(err);
            host.innerHTML = `<div class="sector-detail-error">${this.escapeHtml(err.message || '涨停分析加载失败')}</div>`;
        }
    },

    renderSectorLimitUpStocks(host, data) {
        if (!host) return;
        const stocks = Array.isArray(data.stocks) ? data.stocks : [];
        const days = data.days != null ? data.days : 60;
        const scanStart = data.scan_start_date || data.start_date || '';
        const waveStart = data.wave_start_date || '';
        const waveReason = data.wave_start_reason || '';
        const waveDayN = data.wave_start_day_limit_up_count;
        const peakN = data.peak_limit_up_count;
        const peakDate = data.peak_limit_up_date || '';
        const mode = data.wave_start_mode || 'board_start';
        const minCnt = data.wave_start_min_count != null ? data.wave_start_min_count : 2;
        const total = data.total != null ? data.total : stocks.length;
        const cons = data.constituent_count != null ? data.constituent_count : '--';
        const leaderCode = data.leader_code || '';
        const leaderName = data.leader_name || '';

        const modeOpts = [
            { v: 'board_start', t: '板块启动日' },
            { v: 'leader_first', t: '龙头首板日' },
            { v: 'scan_window', t: '全扫描窗' },
        ].map((o) => `<option value="${o.v}"${o.v === mode ? ' selected' : ''}>${o.t}</option>`).join('');

        const controls = `<div class="sector-limit-up-controls">
            <label>起涨点
                <select class="sector-limit-up-mode">${modeOpts}</select>
            </label>
            <label class="sector-limit-up-min-wrap" title="当日涨停家数达到该阈值视为板块启动">
                启动阈值≥
                <input type="number" class="sector-limit-up-min" min="1" max="50" value="${this.escapeHtml(String(minCnt))}">
            </label>
            <button type="button" class="btn btn-secondary btn-sm sector-limit-up-reload">重算</button>
        </div>`;

        const waveHtml = `<div class="sector-limit-up-wave">
            <div><strong>本轮起涨点</strong>：${waveStart ? this.escapeHtml(waveStart) : '—'}${waveReason ? ` · ${this.escapeHtml(waveReason)}` : ''}</div>
            <div class="sector-limit-up-wave-meta">
                扫描窗近 ${this.escapeHtml(String(days))} 日${scanStart ? `（自 ${this.escapeHtml(scanStart)}）` : ''} ·
                成分 ${this.escapeHtml(String(cons))} 只 ·
                自起涨曾涨停 ${this.escapeHtml(String(total))} 只
                ${waveDayN != null ? ` · 起涨日涨停 ${this.escapeHtml(String(waveDayN))} 家` : ''}
                ${peakN != null ? ` · 峰值 ${this.escapeHtml(String(peakN))} 家${peakDate ? `（${this.escapeHtml(peakDate)}）` : ''}` : ''}
                ${leaderCode ? ` · 参考龙头 ${this.escapeHtml(leaderCode)}${leaderName ? ' ' + this.escapeHtml(leaderName) : ''}` : ''}
            </div>
            <div class="sector-limit-up-hint">涨停口径：主板≥9.8%，创业/科创≥19.8%；连板按相邻涨停间隔≤3自然日近似</div>
        </div>`;

        if (!stocks.length) {
            host.innerHTML = `${controls}${waveHtml}<div class="sector-detail-meta">自起涨点起暂无涨停成分股</div>`;
            this._bindSectorLimitUpControls(host);
            return;
        }

        const rows = stocks.map((s) => {
            const code = String(s.code || '').trim();
            const name = String(s.name || '').trim();
            const href = this._stockDetailHref(code, name);
            const nameCell = href
                ? `<a class="sector-limit-up-link" href="${this.escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${this.escapeHtml(code)} ${this.escapeHtml(name || '')}</a>`
                : this.escapeHtml(`${code} ${name}`);
            const cnt = s.limit_up_count != null ? s.limit_up_count : '--';
            const consec = s.max_consecutive != null ? s.max_consecutive : '--';
            const last = s.last_limit_up_date || '--';
            const first = s.first_limit_up_date || '--';
            return `<tr>
                <td class="sector-limit-up-check">
                    <input type="checkbox" class="sector-limit-up-cb" data-code="${this.escapeHtml(code)}" data-name="${this.escapeHtml(name)}" value="${this.escapeHtml(code)}">
                </td>
                <td>${nameCell}</td>
                <td class="num">${this.escapeHtml(String(cnt))}</td>
                <td class="num">${this.escapeHtml(String(consec))}</td>
                <td>${this.escapeHtml(String(last))}</td>
                <td>${this.escapeHtml(String(first))}</td>
            </tr>`;
        }).join('');

        host.innerHTML = `
            ${controls}
            ${waveHtml}
            <div class="sector-limit-up-actions">
                <button type="button" class="btn btn-secondary btn-sm sector-limit-up-select-all" title="全选本列表">全选</button>
                <button type="button" class="btn btn-secondary btn-sm sector-limit-up-clear" title="取消勾选">清空</button>
                <button type="button" class="btn btn-primary btn-sm sector-limit-up-batch" title="将勾选股票批量打开交易分析">批量分析</button>
            </div>
            <div class="sector-limit-up-table-wrap">
                <table class="sector-limit-up-table">
                    <thead>
                        <tr>
                            <th class="sector-limit-up-check"></th>
                            <th>股票</th>
                            <th class="num">自起涨板数</th>
                            <th class="num">最高连板</th>
                            <th>最近涨停</th>
                            <th>起涨后首次</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;

        this._bindSectorLimitUpControls(host);
        const selectAllBtn = host.querySelector('.sector-limit-up-select-all');
        const clearBtn = host.querySelector('.sector-limit-up-clear');
        const batchBtn = host.querySelector('.sector-limit-up-batch');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                host.querySelectorAll('.sector-limit-up-cb').forEach((el) => { el.checked = true; });
            });
        }
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                host.querySelectorAll('.sector-limit-up-cb').forEach((el) => { el.checked = false; });
            });
        }
        if (batchBtn) {
            batchBtn.addEventListener('click', () => {
                this.openSectorLimitUpBatchAnalysis(host);
            });
        }
    },

    _bindSectorLimitUpControls(host) {
        if (!host) return;
        const reload = () => {
            const prefs = this._sectorLimitUpPrefs || {};
            const modeEl = host.querySelector('.sector-limit-up-mode');
            const minEl = host.querySelector('.sector-limit-up-min');
            const waveStartMode = modeEl ? modeEl.value : (prefs.waveStartMode || 'board_start');
            const startMinCount = minEl ? Number(minEl.value) || 2 : (prefs.startMinCount || 2);
            this.loadSectorLimitUpStocks(
                prefs.kind || 'industry',
                prefs.boardCode || '',
                prefs.boardSource || 'tonghuashun',
                prefs.boardName || '',
                { waveStartMode, startMinCount }
            );
        };
        const btn = host.querySelector('.sector-limit-up-reload');
        if (btn) btn.addEventListener('click', reload);
        const modeEl = host.querySelector('.sector-limit-up-mode');
        if (modeEl) modeEl.addEventListener('change', reload);
    },

    openSectorLimitUpBatchAnalysis(host) {
        const stocks = [];
        const root = host || document.getElementById('sectorLimitUpHost');
        if (!root) return;
        root.querySelectorAll('.sector-limit-up-cb:checked').forEach((el) => {
            const code = String(el.getAttribute('data-code') || el.value || '').trim();
            if (!code) return;
            stocks.push({
                code,
                name: String(el.getAttribute('data-name') || '').trim(),
            });
        });
        if (!stocks.length) {
            if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                CommonUtils.showToast('请先勾选至少一只股票', 'warning');
            }
            return;
        }
        if (window.StockTradeLink && typeof StockTradeLink.openBatchAnalysis === 'function') {
            StockTradeLink.openBatchAnalysis(stocks, { toastPrefix: '已打开交易分析' });
            return;
        }
        const codesQs = stocks.map((s) => encodeURIComponent(s.code)).join(',');
        window.open(`analysis.html?tab=stock-ai&batch=selected&popup=1&codes=${codesQs}`, '_blank');
    },

    formatFundFlowYi(yuan) {
        if (yuan == null || yuan === '' || Number.isNaN(Number(yuan))) return '--';
        const yi = Number(yuan) / 1e8;
        const abs = Math.abs(yi);
        const txt = abs >= 100 ? yi.toFixed(1) : yi.toFixed(2);
        return `${yi > 0 ? '+' : ''}${txt}亿`;
    },

    async loadSectorFundFlow(kind, boardCode, boardSource) {
        const host = document.getElementById('sectorFundFlowHost');
        if (!host) return;
        const code = String(boardCode || '').trim();
        if (!code) {
            host.innerHTML = '<div class="sector-detail-meta">缺少板块代码</div>';
            return;
        }
        const token = `${kind}|${code}|${Date.now()}`;
        this._sectorFundFlowToken = token;
        host.innerHTML = '<div class="sector-detail-loading">资金流向加载中…</div>';
        try {
            const base = (typeof API_BASE_URL !== 'undefined' && API_BASE_URL) ? API_BASE_URL : '';
            const src = encodeURIComponent(boardSource || 'tonghuashun');
            const url = `${base}/api/board_fund_flow/daily?board_kind=${encodeURIComponent(kind)}&board_code=${encodeURIComponent(code)}&board_code_source=${src}&days=20`;
            const resp = await fetch(url);
            const result = await resp.json().catch(() => ({}));
            if (this._sectorFundFlowToken !== token) return;
            if (!resp.ok || !result.success) {
                host.innerHTML = `<div class="sector-detail-meta">${this.escapeHtml((result && result.message) || '暂无板块资金流数据（需日采入库）')}</div>`;
                return;
            }
            this.renderSectorFundFlow(host, result.data || {});
        } catch (err) {
            if (this._sectorFundFlowToken !== token) return;
            console.error(err);
            host.innerHTML = `<div class="sector-detail-error">${this.escapeHtml(err.message || '资金流向加载失败')}</div>`;
        }
    },

    renderSectorFundFlow(host, data) {
        if (!host) return;
        const series = Array.isArray(data.series) ? data.series : [];
        const latest = data.latest || (series.length ? series[series.length - 1] : null);
        if (!latest && !series.length) {
            host.innerHTML = '<div class="sector-detail-meta">暂无板块资金流数据（需日采入库）</div>';
            return;
        }
        const item = (label, value, cls) => `
            <div class="sector-detail-item">
                <span class="label">${label}</span>
                <span class="value ${cls || ''}">${value}</span>
            </div>
        `;
        const net = latest ? latest.main_net_inflow : null;
        const inflow = latest ? latest.inflow_amount : null;
        const outflow = latest ? latest.outflow_amount : null;
        const asof = latest && latest.trade_date ? latest.trade_date : '--';
        const src = latest && latest.source ? latest.source : (data.series_source || '');

        let tiersHtml = '';
        if (latest && (
            latest.super_large_net_inflow != null
            || latest.large_net_inflow != null
            || latest.mid_net_inflow != null
            || latest.small_net_inflow != null
        )) {
            tiersHtml = `
                <details class="sector-fund-flow-tiers">
                    <summary>分档净流入</summary>
                    <div class="sector-detail-grid">
                        ${item('超大单', this.formatFundFlowYi(latest.super_large_net_inflow), this.getChangeClass(latest.super_large_net_inflow))}
                        ${item('大单', this.formatFundFlowYi(latest.large_net_inflow), this.getChangeClass(latest.large_net_inflow))}
                        ${item('中单', this.formatFundFlowYi(latest.mid_net_inflow), this.getChangeClass(latest.mid_net_inflow))}
                        ${item('小单', this.formatFundFlowYi(latest.small_net_inflow), this.getChangeClass(latest.small_net_inflow))}
                    </div>
                </details>
            `;
        }

        const maxAbs = series.reduce((m, r) => {
            const v = Math.abs(Number(r.main_net_inflow) || 0);
            return v > m ? v : m;
        }, 0) || 1;
        const bars = series.map((r) => {
            const v = Number(r.main_net_inflow) || 0;
            const pct = Math.min(100, (Math.abs(v) / maxAbs) * 100);
            const cls = v >= 0 ? 'up' : 'down';
            const day = String(r.trade_date || '').slice(5);
            return `<div class="sector-ff-bar-col" title="${this.escapeHtml(String(r.trade_date || ''))}: ${this.formatFundFlowYi(v)}">
                <div class="sector-ff-bar-track"><div class="sector-ff-bar ${cls}" style="height:${pct}%"></div></div>
                <div class="sector-ff-bar-label">${this.escapeHtml(day)}</div>
            </div>`;
        }).join('');

        host.innerHTML = `
            <div class="sector-detail-grid">
                ${item('净流入', this.formatFundFlowYi(net), this.getChangeClass(net))}
                ${item('流入', this.formatFundFlowYi(inflow), 'positive')}
                ${item('流出', this.formatFundFlowYi(outflow), 'negative')}
                ${item('数据日', this.escapeHtml(asof))}
                ${item('来源', this.escapeHtml(src || '--'))}
            </div>
            ${tiersHtml}
            <div class="sector-ff-chart" aria-label="近20日净流入">
                ${bars || '<div class="sector-detail-meta">暂无序列</div>'}
            </div>
        `;
    },

    /**
     * 从板块详情进入比价效应选股页，并预选当前行业/概念板。
     * 落地 URL：screening.html?board_kind=&board_code=&board_code_source=&board_name=#rpe
     */
    goToRpeScreeningFromSector(d) {
        const ctx = this._sectorDetailCtx || {};
        const kind = (d && d.board_kind === 'concept') || ctx.kind === 'concept'
            ? 'concept'
            : 'industry';
        const code = String((d && d.board_code) || ctx.boardCode || '').trim();
        if (!code) {
            if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                CommonUtils.showToast('缺少板块代码，无法进入比价选股', 'warning');
            }
            return;
        }
        const name = String((d && d.board_name) || ctx.boardName || '').trim();
        const params = new URLSearchParams({
            board_kind: kind,
            board_code: code,
        });
        const sourceKey = String((d && d.board_code_source) || ctx.boardSource || 'tonghuashun').trim();
        if (sourceKey) params.set('board_code_source', sourceKey);
        if (name) params.set('board_name', name);
        const url = `screening.html?${params.toString()}#rpe`;
        const win = window.open(url, '_blank');
        if (win) {
            try { win.opener = null; } catch (_) { /* ignore */ }
        } else if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
            CommonUtils.showToast('无法打开新标签页，请检查浏览器弹窗拦截', 'warning');
        }
    },

    // 加载热门数据
    loadHotData() {
        this.updateCapitalFlow();
        this.updateMarketSentiment();
    },

    // 更新资金流向
    updateCapitalFlow() {
        const flowItems = document.querySelectorAll('.flow-item .flow-value');
        flowItems.forEach(item => {
            const currentValue = parseFloat(item.textContent.replace(/[+\-亿]/g, ''));
            const change = (Math.random() - 0.5) * 20;
            const newValue = currentValue + change;

            item.textContent = newValue >= 0 ? `+${newValue.toFixed(2)}亿` : `${newValue.toFixed(2)}亿`;
            item.className = `flow-value ${this.getChangeClass(newValue)}`;
        });
    },

    // 更新市场情绪
    updateMarketSentiment() {
        const sentiment = 50 + (Math.random() - 0.5) * 40; // 30-70%之间
        const meterFill = document.querySelector('.meter-fill');
        const meterValue = document.querySelector('.meter-value');

        if (meterFill && meterValue) {
            meterFill.style.width = `${sentiment}%`;
            meterValue.textContent = `${Math.round(sentiment)}%`;
            meterFill.className = `meter-fill ${sentiment > 50 ? 'positive' : 'negative'}`;
        }

        // 更新股票统计
        const sentimentValues = document.querySelectorAll('.sentiment-item .value');
        const total = 4526; // 总股票数
        const upCount = Math.round(total * sentiment / 100);
        const downCount = Math.round(total * (100 - sentiment) / 100);
        const flatCount = total - upCount - downCount;

        if (sentimentValues.length >= 3) {
            sentimentValues[0].textContent = upCount.toLocaleString();
            sentimentValues[1].textContent = downCount.toLocaleString();
            sentimentValues[2].textContent = flatCount.toLocaleString();
        }
    },

    // 加载统计数据
    loadStatsData() {
        this.drawDistributionChart();
        this.updateHeatIndicators();
    },

    // 绘制分布图
    drawDistributionChart() {
        const canvas = document.getElementById('distributionChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 绘制饼图
        const data = [
            { label: '上涨', value: 2847, color: '#dc2626' },
            { label: '下跌', value: 1523, color: '#16a34a' },
            { label: '平盘', value: 156, color: '#6b7280' }
        ];

        const total = data.reduce((sum, item) => sum + item.value, 0);
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 2 - 20;

        let currentAngle = -Math.PI / 2;

        data.forEach(item => {
            const sliceAngle = (item.value / total) * 2 * Math.PI;

            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
            ctx.closePath();
            ctx.fillStyle = item.color;
            ctx.fill();

            // 绘制标签
            const labelAngle = currentAngle + sliceAngle / 2;
            const labelX = centerX + Math.cos(labelAngle) * (radius * 0.7);
            const labelY = centerY + Math.sin(labelAngle) * (radius * 0.7);

            ctx.fillStyle = 'white';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(item.label, labelX, labelY);

            currentAngle += sliceAngle;
        });
    },

    // 更新热度指标
    updateHeatIndicators() {
        const indicators = document.querySelectorAll('.heat-value');
        indicators.forEach(indicator => {
            const current = parseInt(indicator.textContent);
            const change = Math.floor((Math.random() - 0.5) * 20);
            const newValue = Math.max(0, current + change);
            indicator.textContent = newValue;
        });
    },

    // 过滤市场
    filterMarket(market) {
        // 根据选择的市场过滤排行榜数据
        console.log('过滤市场:', market);
        CommonUtils.showToast(`已切换到${market === 'all' ? '全部市场' : market}`, 'info');
        this.currentPage = 1;
        this.loadRankingData(1);
    },

    // 跳转到股票详情
    goToStock(code) {
        window.location.href = `stock.html?code=${code}`;
    },

    // 格式化价格
    formatPrice(price) {
        if (price === null || typeof price === 'undefined' || isNaN(price)) return '--';
        return price.toFixed(2);
    },

    // 格式化涨跌额
    formatChange(change) {
        if (change === null || typeof change === 'undefined' || isNaN(change)) return '--';
        const sign = change > 0 ? '+' : '';
        return `${sign}${change.toFixed(2)}`;
    },

    // 格式化百分比
    formatPercent(percent) {
        if (percent === null || typeof percent === 'undefined' || isNaN(percent)) return '--';
        return `${percent.toFixed(2)}%`;
    },

    // 格式化成交量（库存为手；按手显示：万手/亿手）
    formatVolume(volume) {
        if (volume === null || typeof volume === 'undefined' || isNaN(volume)) return '--';
        const v = Number(volume);
        if (v >= 100000000) return `${(v / 100000000).toFixed(2)}亿`;
        if (v >= 10000) return `${(v / 10000).toFixed(2)}万`;
        return `${v.toFixed(0)}`;
    },

    // 格式化成交额（保留两位小数，显示万或亿）
    formatTurnover(turnover) {
        if (turnover === null || typeof turnover === 'undefined' || isNaN(turnover)) return '--';
        const t = Number(turnover);
        const absT = Math.abs(t);
        if (absT >= 100000000) return `${(t / 100000000).toFixed(2)}亿`;
        return `${(t / 10000).toFixed(2)}万`;
    },

    // 格式化换手率（加上%符号，保留两位小数）
    formatTurnoverRate(rate) {
        if (rate === null || typeof rate === 'undefined' || isNaN(rate)) return '--';
        return `${rate.toFixed(2)}%`;
    },

    // 获取涨跌颜色
    getChangeClass(value) {
        if (value === null || typeof value === 'undefined' || isNaN(value)) return '';
        if (value > 0) return 'positive';
        if (value < 0) return 'negative';
        return '';
    },

    // 跳转到股票详情页面
    goToStock(stockCode) {
        if (stockCode && stockCode !== '--') {
            console.log(`跳转到股票详情: ${stockCode}`);
            // 这里可以根据实际需求跳转到股票详情页面
            // 例如：window.location.href = `/stock.html?code=${stockCode}`;
            // 或者打开新窗口：window.open(`/stock.html?code=${stockCode}`, '_blank');

            // 临时实现：显示股票代码
            alert(`股票代码: ${stockCode}`);
        }
    },

    // 开始数据更新
    startDataUpdate() {
        // 定期更新数据已按需求关闭
        /*
        setInterval(() => {
            if (this.currentTab === 'rankings') {
                //this.updateRankingPrices();
                // 成交量异动榜不做定时刷新（避免前台持续请求接口）
                if (this.currentRankingType !== 'volume_aberration') {
                    this.loadRankingData(this.currentPage);
                }
            } else if (this.currentTab === 'sectors') {
                this.loadSectorData('industry');
            } else if (this.currentTab === 'concepts') {
                this.loadSectorData('concept');
            } else if (this.currentTab === 'hot') {
                this.updateCapitalFlow();
                this.updateMarketSentiment();
            }
        }, 60000); // 每60秒更新一次

        // 更新指数数据
        setInterval(() => {
            this.loadMarketIndices();
        }, 30000); // 每30秒更新指数数据

        // 更新指数图表
        setInterval(() => {
            this.loadIndexCharts();
        }, 30000); // 每30秒更新图表
        */
    },

    // 渲染分页
    renderPagination() {
        const container = document.querySelector('.rankings-content');
        let pagination = document.getElementById('rankingsPagination');
        if (!pagination) {
            pagination = document.createElement('div');
            pagination.id = 'rankingsPagination';
            pagination.className = 'pagination';
            container.appendChild(pagination);
        }
        const totalPages = Math.ceil(this.total / this.pageSize);
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }
        let html = '';

        // 上一页
        html += `<button class="page-btn prev-btn" ${this.currentPage === 1 ? 'disabled' : ''} data-page="${this.currentPage - 1}">上一页</button>`;

        // 首页
        if (this.currentPage > 3) {
            html += `<button class="page-btn" data-page="1">1</button>`;
            if (this.currentPage > 4) html += `<span class="page-ellipsis">...</span>`;
        }

        // 当前页前后各2页
        let start = Math.max(1, this.currentPage - 2);
        let end = Math.min(totalPages, this.currentPage + 2);
        for (let i = start; i <= end; i++) {
            if (i === 1 || i === totalPages) continue; // 首页和尾页已处理
            html += `<button class="page-btn${i === this.currentPage ? ' active' : ''}" data-page="${i}">${i}</button>`;
        }

        // 尾页
        if (this.currentPage < totalPages - 2) {
            if (this.currentPage < totalPages - 3) html += `<span class="page-ellipsis">...</span>`;
            html += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
        }

        // 下一页
        html += `<button class="page-btn next-btn" ${this.currentPage === totalPages ? 'disabled' : ''} data-page="${this.currentPage + 1}">下一页</button>`;

        pagination.innerHTML = html;
        pagination.querySelectorAll('.page-btn').forEach(btn => {
            btn.onclick = (e) => {
                const page = parseInt(btn.dataset.page);
                if (!isNaN(page) && page !== this.currentPage && page >= 1 && page <= totalPages) {
                    if (this.currentRankingType === 'volume_aberration') {
                        this.loadVolumeAberrationData(page);
                    } else {
                        this.loadRankingData(page);
                    }
                }
            };
        });
    },

    formatLhbYi(value) {
        if (value == null || !Number.isFinite(Number(value))) return '--';
        const yi = Number(value) / 1e8;
        const sign = yi > 0 ? '+' : '';
        return sign + yi.toFixed(2);
    },

    formatLhbPct(value) {
        if (value == null || !Number.isFinite(Number(value))) return '--';
        const n = Number(value);
        const sign = n > 0 ? '+' : '';
        return sign + n.toFixed(2) + '%';
    },

    lhbSignedClass(value) {
        if (value == null || !Number.isFinite(Number(value)) || Number(value) === 0) return '';
        return Number(value) > 0 ? 'positive' : 'negative';
    },

    async loadDragonTiger() {
        const tbody = document.getElementById('lhbTableBody');
        const meta = document.getElementById('lhbMeta');
        const hint = document.getElementById('lhbHint');
        const hotWrap = document.getElementById('lhbHotMoneyWrap');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:#888;">加载中...</td></tr>';
        if (hotWrap) hotWrap.style.display = 'none';
        if (hint) hint.style.display = 'none';
        const params = new URLSearchParams();
        params.set('board_type', this.lhbBoardType || 'all');
        const dateInput = document.getElementById('lhbDate');
        const day = dateInput && dateInput.value ? String(dateInput.value).trim() : '';
        if (day) params.set('date', day);
        try {
            const response = await fetch(`${this.API_BASE_URL}/api/market/dragon-tiger?${params.toString()}`);
            const result = await response.json();
            if (!result || !result.success || !result.data) {
                const msg = (result && result.message) || '龙虎榜加载失败';
                tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:#c62828;">${this.escapeHtml(msg)}</td></tr>`;
                if (meta) meta.textContent = '';
                return;
            }
            this.renderDragonTiger(result.data);
        } catch (error) {
            console.error('龙虎榜加载失败:', error);
            tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:#c62828;">龙虎榜请求异常</td></tr>';
            if (meta) meta.textContent = '';
        }
    },

    renderDragonTiger(data) {
        const tbody = document.getElementById('lhbTableBody');
        const meta = document.getElementById('lhbMeta');
        const hint = document.getElementById('lhbHint');
        const hotWrap = document.getElementById('lhbHotMoneyWrap');
        const hotBody = document.getElementById('lhbHotMoneyBody');
        if (!tbody) return;
        const dateInput = document.getElementById('lhbDate');
        if (dateInput && data.trade_date && !dateInput.value) {
            dateInput.value = data.trade_date;
        }
        const source = data.source_label || '';
        const count = data.stock_count != null ? data.stock_count : (data.items || []).length;
        if (meta) {
            meta.textContent = [data.trade_date || '', source ? `来源 ${source}` : '', `${count} 只`].filter(Boolean).join(' · ');
        }
        const note = data.fallback_reason || data.board_type_note || '';
        if (hint) {
            if (note) {
                hint.style.display = 'block';
                hint.textContent = note;
            } else {
                hint.style.display = 'none';
                hint.textContent = '';
            }
        }
        const items = Array.isArray(data.items) ? data.items : [];
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:#888;">暂无龙虎榜数据</td></tr>';
        } else {
            tbody.innerHTML = items.map(row => {
                const code = String(row.code || '');
                const name = String(row.name || '');
                const reason = row.reason || row.interpretation || '';
                const closeText = row.close == null || !Number.isFinite(Number(row.close)) ? '--' : Number(row.close).toFixed(2);
                return `<tr data-code="${this.escapeHtml(code)}" data-name="${this.escapeHtml(name)}" style="cursor:pointer;">
                    <td>${this.escapeHtml(code)}</td>
                    <td>${this.escapeHtml(name)}</td>
                    <td class="${this.lhbSignedClass(row.change_percent)}">${this.formatLhbPct(row.change_percent)}</td>
                    <td>${closeText}</td>
                    <td>${this.formatLhbYi(row.buy_value)}</td>
                    <td>${this.formatLhbYi(row.sell_value)}</td>
                    <td class="${this.lhbSignedClass(row.net_value)}">${this.formatLhbYi(row.net_value)}</td>
                    <td class="${this.lhbSignedClass(row.net_rate)}">${this.formatLhbPct(row.net_rate)}</td>
                    <td class="${this.lhbSignedClass(row.org_net_value)}">${this.formatLhbYi(row.org_net_value)}</td>
                    <td class="${this.lhbSignedClass(row.hot_money_net_value)}">${this.formatLhbYi(row.hot_money_net_value)}</td>
                    <td title="${this.escapeHtml(reason)}">${this.escapeHtml(reason || '--')}</td>
                </tr>`;
            }).join('');
            tbody.querySelectorAll('tr[data-code]').forEach(tr => {
                tr.addEventListener('click', () => {
                    const code = tr.dataset.code;
                    const name = tr.dataset.name || '';
                    if (code && typeof goToStock === 'function') goToStock(code, name);
                });
            });
        }
        const seats = Array.isArray(data.hot_money_items) ? data.hot_money_items : [];
        if (!hotWrap || !hotBody) return;
        if (!seats.length) {
            hotWrap.style.display = 'none';
            hotBody.innerHTML = '';
            return;
        }
        hotWrap.style.display = 'block';
        hotBody.innerHTML = seats.map(seat => {
            const stocks = Array.isArray(seat.stocks) ? seat.stocks : [];
            const stockText = stocks.map(s => {
                const label = `${s.name || ''}${s.code ? '(' + s.code + ')' : ''}`.trim();
                const net = this.formatLhbYi(s.net_value);
                return net === '--' ? label : `${label} ${net}`;
            }).filter(Boolean).join('、');
            return `<tr>
                <td>${this.escapeHtml(seat.name || '--')}</td>
                <td>${this.formatLhbYi(seat.buy_value)}</td>
                <td>${this.formatLhbYi(seat.sell_value)}</td>
                <td class="${this.lhbSignedClass(seat.net_value)}">${this.formatLhbYi(seat.net_value)}</td>
                <td>${this.escapeHtml(stockText || '--')}</td>
            </tr>`;
        }).join('');
    },

    formatAuctionPct(value) {
        if (value == null || !Number.isFinite(Number(value))) return '--';
        const n = Number(value);
        const sign = n > 0 ? '+' : '';
        return sign + n.toFixed(2) + '%';
    },

    formatAuctionNum(value, digits = 2) {
        if (value == null || !Number.isFinite(Number(value))) return '--';
        return Number(value).toFixed(digits);
    },

    /** 竞价量/未匹配：库存为手 → 万手/亿手 */
    formatAuctionVolume(value) {
        if (value == null || !Number.isFinite(Number(value))) return '--';
        const n = Number(value);
        const abs = Math.abs(n);
        if (abs >= 1e8) return (n / 1e8).toFixed(2) + '亿手';
        if (abs >= 1e4) return (n / 1e4).toFixed(2) + '万手';
        return n.toFixed(0) + '手';
    },

    formatAuctionAmount(value) {
        if (value == null || !Number.isFinite(Number(value))) return '--';
        const n = Number(value);
        if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿';
        if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万';
        return n.toFixed(0);
    },

    async loadAuction(page) {
        if (page) this.auctionPage = page;
        const tbody = document.getElementById('auctionTableBody');
        const meta = document.getElementById('auctionMeta');
        const hint = document.getElementById('auctionHint');
        const benchmarkWrap = document.getElementById('auctionBenchmarkCards');
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:#888;">加载中...</td></tr>';
        if (hint) hint.style.display = 'none';

        const params = new URLSearchParams();
        const dateInput = document.getElementById('auctionDate');
        const stageInput = document.getElementById('auctionStage');
        const keywordInput = document.getElementById('auctionKeyword');
        const day = dateInput && dateInput.value ? String(dateInput.value).trim() : '';
        const stage = stageInput && stageInput.value ? String(stageInput.value).trim() : 'final';
        const keyword = keywordInput && keywordInput.value ? String(keywordInput.value).trim() : '';
        if (day) params.set('date', day);
        params.set('stage', stage);
        if (keyword) params.set('keyword', keyword);
        params.set('page', String(this.auctionPage || 1));
        params.set('page_size', String(this.auctionPageSize || 20));

        try {
            const [listResp, benchResp] = await Promise.all([
                fetch(`${this.API_BASE_URL}/api/market/auction/list?${params.toString()}`),
                fetch(`${this.API_BASE_URL}/api/market/auction/benchmark?${day ? 'date=' + encodeURIComponent(day) : ''}`),
            ]);
            const listResult = await listResp.json();
            const benchResult = await benchResp.json();
            this.renderAuctionBenchmark(benchResult, benchmarkWrap, dateInput);
            if (!listResult || !listResult.success) {
                const msg = (listResult && listResult.message) || '集合竞价加载失败';
                tbody.innerHTML = `<tr><td colspan="12" style="text-align:center;color:#c62828;">${this.escapeHtml(msg)}</td></tr>`;
                if (meta) meta.textContent = '';
                return;
            }
            this.renderAuctionList(listResult, meta, hint, tbody);
        } catch (error) {
            console.error('集合竞价加载失败:', error);
            tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:#c62828;">集合竞价请求异常</td></tr>';
            if (meta) meta.textContent = '';
        }
    },

    renderAuctionBenchmark(result, wrap, dateInput) {
        if (!wrap) return;
        if (!result || !result.success || !Array.isArray(result.items) || !result.items.length) {
            wrap.innerHTML = '<div class="auction-empty">暂无短线风向标基准数据</div>';
            return;
        }
        if (dateInput && result.trade_date && !dateInput.value) {
            dateInput.value = result.trade_date;
        }
        wrap.innerHTML = result.items.map(item => {
            const tags = Array.isArray(item.tags) ? item.tags.join(' · ') : (item.tags || '');
            return `<div class="auction-benchmark-card" data-code="${this.escapeHtml(item.code || '')}" data-name="${this.escapeHtml(item.name || '')}">
                <div class="abc-head">
                    <span class="abc-name">${this.escapeHtml(item.name || '--')}</span>
                    <span class="abc-code">${this.escapeHtml(item.code || '')}</span>
                </div>
                <div class="abc-pct ${this.lhbSignedClass(item.auction_pct)}">${this.formatAuctionPct(item.auction_pct)}</div>
                <div class="abc-tags">${this.escapeHtml(tags || '--')}</div>
            </div>`;
        }).join('');
        wrap.querySelectorAll('.auction-benchmark-card[data-code]').forEach(card => {
            card.addEventListener('click', () => {
                const code = card.dataset.code;
                const name = card.dataset.name || '';
                if (code && typeof goToStock === 'function') goToStock(code, name);
            });
        });
    },

    renderAuctionList(result, meta, hint, tbody) {
        const dateInput = document.getElementById('auctionDate');
        if (dateInput && result.trade_date && !dateInput.value) {
            dateInput.value = result.trade_date;
        }
        this.auctionTotal = Number(result.total || 0);
        if (meta) {
            meta.textContent = [
                result.trade_date || '',
                result.auction_phase ? `阶段 ${result.auction_phase}` : '',
                `共 ${this.auctionTotal} 条`,
            ].filter(Boolean).join(' · ');
        }
        if (hint) {
            if (!this.auctionTotal) {
                hint.style.display = 'block';
                hint.textContent = '本地暂无数据，可点击「采集」从同花顺 Fuyao 拉取并落库。';
            } else {
                hint.style.display = 'none';
                hint.textContent = '';
            }
        }
        const items = Array.isArray(result.items) ? result.items : [];
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:#888;">暂无集合竞价数据</td></tr>';
            this.renderAuctionPagination();
            return;
        }
        tbody.innerHTML = items.map(row => {
            const code = String(row.code || '');
            const name = String(row.name || '');
            return `<tr data-code="${this.escapeHtml(code)}" data-name="${this.escapeHtml(name)}" style="cursor:pointer;">
                <td>${this.escapeHtml(code)}</td>
                <td>${this.escapeHtml(name)}</td>
                <td>${this.formatAuctionNum(row.auction_price)}</td>
                <td class="${this.lhbSignedClass(row.auction_pct)}">${this.formatAuctionPct(row.auction_pct)}</td>
                <td>${this.formatAuctionVolume(row.auction_volume)}</td>
                <td>${this.formatAuctionAmount(row.auction_amount)}</td>
                <td>${this.formatAuctionVolume(row.auction_unmatched)}</td>
                <td>${this.formatAuctionPct(row.auction_turnover_pct)}</td>
                <td>${this.formatAuctionPct(row.auction_yesterday_ratio_pct)}</td>
                <td>${this.formatAuctionNum(row.auction_volume_ratio)}</td>
                <td>${this.formatAuctionNum(row.pre_close_price)}</td>
                <td><button type="button" class="link-btn auction-view-btn">详情</button></td>
            </tr>`;
        }).join('');
        tbody.querySelectorAll('tr[data-code]').forEach(tr => {
            const go = () => {
                const code = tr.dataset.code;
                const name = tr.dataset.name || '';
                if (code) {
                    window.location.href = `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name || '')}&tab=auction`;
                }
            };
            tr.addEventListener('click', (e) => {
                if (e.target && e.target.classList.contains('auction-view-btn')) {
                    e.stopPropagation();
                }
                go();
            });
        });
        this.renderAuctionPagination();
    },

    renderAuctionPagination() {
        const pagination = document.getElementById('auctionPagination');
        if (!pagination) return;
        const totalPages = Math.max(Math.ceil((this.auctionTotal || 0) / (this.auctionPageSize || 20)), 1);
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }
        let html = '';
        html += `<button class="page-btn" ${this.auctionPage <= 1 ? 'disabled' : ''} data-page="${this.auctionPage - 1}">上一页</button>`;
        html += `<span class="page-info">${this.auctionPage} / ${totalPages}</span>`;
        html += `<button class="page-btn" ${this.auctionPage >= totalPages ? 'disabled' : ''} data-page="${this.auctionPage + 1}">下一页</button>`;
        pagination.innerHTML = html;
        pagination.querySelectorAll('.page-btn').forEach(btn => {
            btn.onclick = () => {
                const page = parseInt(btn.dataset.page, 10);
                if (!isNaN(page) && page >= 1 && page <= totalPages) {
                    this.loadAuction(page);
                }
            };
        });
    },

    async collectAuction() {
        const btn = document.getElementById('auctionCollectBtn');
        const hint = document.getElementById('auctionHint');
        const dateInput = document.getElementById('auctionDate');
        const stageInput = document.getElementById('auctionStage');
        const day = dateInput && dateInput.value ? String(dateInput.value).trim() : '';
        const stage = stageInput && stageInput.value ? String(stageInput.value).trim() : 'final';
        if (btn) {
            btn.disabled = true;
            btn.textContent = '采集中...';
        }
        if (hint) {
            hint.style.display = 'block';
            hint.textContent = '正在从同花顺 Fuyao 采集集合竞价，请稍候...';
        }
        try {
            const resp = await fetch(`${this.API_BASE_URL}/api/market/auction/collect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    stage,
                    trade_date: day || null,
                    refresh_benchmark: true,
                }),
            });
            const result = await resp.json();
            if (!result || !result.success || !result.task_id) {
                throw new Error((result && result.message) || '采集启动失败');
            }
            await this.pollAuctionCollect(result.task_id, hint);
            this.auctionPage = 1;
            await this.loadAuction();
        } catch (error) {
            console.error('集合竞价采集失败:', error);
            if (hint) {
                hint.style.display = 'block';
                hint.textContent = '采集失败：' + (error.message || error);
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '采集';
            }
        }
    },

    async pollAuctionCollect(taskId, hint) {
        const maxTry = 120;
        for (let i = 0; i < maxTry; i++) {
            await new Promise(r => setTimeout(r, 2000));
            const resp = await fetch(`${this.API_BASE_URL}/api/market/auction/collect/status/${encodeURIComponent(taskId)}`);
            const result = await resp.json();
            if (!result || !result.success) continue;
            const status = result.status;
            if (hint) {
                hint.textContent = `采集任务 ${taskId}：${status}`;
            }
            if (status === 'completed' || status === 'failed') {
                if (status === 'failed') {
                    throw new Error(result.message || '采集任务失败');
                }
                const saved = result.result && result.result.saved;
                if (hint) {
                    hint.textContent = `采集完成，落库 ${saved != null ? saved : 0} 条。`;
                }
                return;
            }
        }
        throw new Error('采集任务超时');
    },

    // 更新所有自选股按钮的状态
    updateAllWatchlistButtons() {
        const buttons = document.querySelectorAll('#rankingsTableBody button[data-stock-code]');
        buttons.forEach(button => {
            const stockCode = button.dataset.stockCode;
            const stockName = button.dataset.stockName;

            if (watchlistManager.isInWatchlist(stockCode)) {
                button.textContent = '已自选';
                button.className = 'btn btn-sm btn-secondary';
            } else {
                button.textContent = '+自选';
                button.className = 'btn btn-sm btn-primary';
            }
        });
    },

    // 更新排行榜价格
    /*
    updateRankingPrices() {
        const currentData = this.rankingData[this.currentRankingType];
        if (currentData) {
            currentData.forEach(stock => {
                const changeAmount = (Math.random() - 0.5) * 2;
                stock.price = Math.max(0.01, stock.price + changeAmount);
                stock.change = stock.change + changeAmount;
                stock.percent = (stock.change / (stock.price - stock.change)) * 100;
            });
            
            this.renderRankingTable(currentData);
        }
    }
    */
};

// 全局函数
function goToStock(code, name) {
    window.location.href = `stock.html?code=${code}&name=${encodeURIComponent(name)}`;
}

function goToSectorDetail(sectorName, boardCode, boardSource, boardKind) {
    if (!boardCode) {
        CommonUtils.showToast(`缺少板块代码，无法查看${sectorName || ''}详情`, 'warning');
        return;
    }
    MarketsPage.showSectorDetail(sectorName || '', boardCode, boardSource || 'tonghuashun', boardKind || 'industry');
}

function goToStockHistory(code, name) {
    window.location.href = `stock_history.html?code=${code}`;
}

// 自选股状态管理
const watchlistManager = {
    // 缓存用户的自选股列表
    userWatchlist: new Set(),

    // 初始化自选股管理器
    async init() {
        await this.loadUserWatchlist();
    },

    // 加载用户自选股列表
    async loadUserWatchlist() {
        try {
            // 检查用户是否已登录
            const userInfo = CommonUtils.auth.getUserInfo();
            if (!userInfo || !userInfo.id) {
                console.log('用户未登录，跳过自选股加载');
                return;
            }

            // 调用后端API获取用户自选股列表
            const res = await authFetch(`${API_BASE_URL}/api/watchlist`);
            const result = await res.json();

            if (result.success && result.data) {
                // 更新本地缓存
                this.userWatchlist.clear();
                result.data.forEach(item => {
                    this.userWatchlist.add(item.code);
                });
                console.log('自选股列表加载完成，共', this.userWatchlist.size, '只股票');
            }
        } catch (error) {
            console.error('加载自选股列表失败:', error);
        }
    },

    // 检查股票是否在自选股中
    isInWatchlist(stockCode) {
        return this.userWatchlist.has(stockCode);
    },

    // 添加到自选股
    async addToWatchlist(stockCode, stockName) {
        try {
            // 检查登录状态并处理失效
            if (!CommonUtils.checkLoginAndHandleExpiry()) {
                return false;
            }

            const userInfo = CommonUtils.auth.getUserInfo();

            const res = await authFetch(`${API_BASE_URL}/api/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userInfo.id,
                    stock_code: stockCode,
                    stock_name: stockName,
                    group_name: 'default'
                })
            });

            const result = await res.json();
            if (result.success) {
                this.userWatchlist.add(stockCode);
                CommonUtils.showToast(`已添加 ${stockName} 到自选股`, 'success');
                // 加入自选仅写库，不再调用第三方接口拉取历史行情/指标
                return true;
            } else {
                CommonUtils.showToast(result.message || '添加失败', 'error');
                return false;
            }
        } catch (error) {
            console.error('添加到自选股失败:', error);
            CommonUtils.showToast('网络错误，添加失败', 'error');
            return false;
        }
    },

    // 从自选股删除
    async removeFromWatchlist(stockCode, stockName) {
        try {
            const userInfo = CommonUtils.auth.getUserInfo();
            if (!userInfo || !userInfo.id) {
                CommonUtils.showToast('请先登录后再操作自选股', 'warning');
                return false;
            }

            const res = await authFetch(`${API_BASE_URL}/api/watchlist/delete_by_code`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userInfo.id,
                    stock_code: stockCode
                })
            });

            const result = await res.json();
            if (result.success) {
                this.userWatchlist.delete(stockCode);
                CommonUtils.showToast(`已从自选股中移除 ${stockName}`, 'info');
                return true;
            } else {
                CommonUtils.showToast(result.message || '删除失败', 'error');
                return false;
            }
        } catch (error) {
            console.error('从自选股删除失败:', error);
            CommonUtils.showToast('网络错误，删除失败', 'error');
            return false;
        }
    },

    // 切换自选股状态
    async toggleWatchlist(stockCode, stockName) {
        if (this.isInWatchlist(stockCode)) {
            return await this.removeFromWatchlist(stockCode, stockName);
        } else {
            return await this.addToWatchlist(stockCode, stockName);
        }
    },

    // 更新按钮状态
    updateButtonState(button, stockCode) {
        if (this.isInWatchlist(stockCode)) {
            button.textContent = '已自选';
            button.className = 'btn btn-sm btn-secondary';
            button.onclick = (event) => {
                event.stopPropagation();
                this.toggleWatchlist(stockCode, button.dataset.stockName);
            };
        } else {
            button.textContent = '+自选';
            button.className = 'btn btn-sm btn-primary';
            button.onclick = (event) => {
                event.stopPropagation();
                this.toggleWatchlist(stockCode, button.dataset.stockName);
            };
        }
    }
};

function addToWatchlist(code, event) {
    if (event) {
        event.stopPropagation();
    }

    // 获取股票名称 (通过 dataset 或 class 选择器)
    const stockName = event.target.dataset.stockName || 
                     (event.target.closest('tr')?.querySelector('.stock-name')?.textContent) || 
                     code;

    // 调用自选股管理器
    watchlistManager.toggleWatchlist(code, stockName).then(() => {
        // 更新按钮状态
        if (watchlistManager.isInWatchlist(code)) {
            event.target.textContent = '已自选';
            event.target.className = 'btn btn-sm btn-secondary';
        } else {
            event.target.textContent = '+自选';
            event.target.className = 'btn btn-sm btn-primary';
        }
    });
}



// 供独立页 / 内联 onclick 通过 window 访问（const 不会自动挂到 window）
window.MarketsPage = MarketsPage;

// DOM加载完成后初始化
// 查询到股票代码后定位到表格列表中相应记录
document.addEventListener('DOMContentLoaded', function () {
    if (document.body && document.body.classList.contains('board-detail-page')) {
        return;
    }
    MarketsPage.init();
    // 查询输入框和按钮只绑定一次
    setTimeout(function () {
        const searchInput = document.getElementById('marketSearchInput');
        const searchBtn = document.getElementById('marketSearchBtn');
        if (searchInput && searchBtn) {
            function doSearch() {
                const query = searchInput.value.trim();
                if (!query) {
                    CommonUtils.showToast('请输入股票代码或名称', 'warning');
                    return;
                }
                // 只在涨跌排行tab激活时生效
                const rankingsTab = document.getElementById('rankings');
                if (!rankingsTab || !rankingsTab.classList.contains('active')) {
                    CommonUtils.showToast('请先切换到"涨跌排行"标签页', 'warning');
                    return;
                }
                // 调用loadRankingData进行查询，查询结果会显示在表格中并定位到相应记录
                MarketsPage.loadRankingData(1, query);
            }
            searchBtn.onclick = doSearch;
            searchInput.onkeydown = function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    doSearch();
                }
            };
        }
    }, 300); // 延迟绑定，确保DOM渲染完成
});
// 高亮样式
const style = document.createElement('style');
style.innerHTML = `#rankingsTableBody tr.highlight { box-shadow: 0 0 0 3px #ff9800 !important; border-color: #ff9800 !important; }`;
document.head.appendChild(style);

