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

        // 绘制线条
        const color = data[data.length - 1] > data[0] ? '#dc2626' : '#16a34a';
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
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#c00;">${ui.label}加载失败</td></tr>`;
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

    /**
     * 列表无任何斜率且有板数据时，自动触发一次后台刷新（每 kind 每会话最多一次）。
     */
    _maybeAutoRefreshSectorSlopes(kind = 'industry') {
        const ui = this._boardKindUi(kind);
        const rows = this[ui.dataKey] || [];
        if (!rows.length) return;
        if (this._countSectorSlopes(rows) > 0) return;
        const flagKey = `_autoSlopeRefreshTried_${ui.kind}`;
        if (this[flagKey]) return;
        this[flagKey] = true;
        CommonUtils.showToast(`${ui.label}斜率尚未入库，正在后台计算…`, 'info');
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
        const isShort = mode === 'short';
        const env = isShort
            ? ((d && d.board_env_short)
                || (d && d.board_strong_short ? 'strong' : (d && d.board_weak_short ? 'weak' : '')))
            : ((d && d.board_env)
                || (d && d.board_strong ? 'strong' : (d && d.board_weak ? 'weak' : '')));
        if (env === 'strong') return 0;
        if (env === 'neutral') return 1;
        if (env === 'weak') return 2;
        return 3; // unknown / 无斜率
    },

    setSectorSort(kind, sortKey) {
        const isConcept = kind === 'concept';
        const keyProp = isConcept ? 'conceptSortKey' : 'sectorSortKey';
        const ascProp = isConcept ? 'conceptSortAsc' : 'sectorSortAsc';
        const key = (sortKey === 'sector_slope_short') ? 'sector_slope_short' : 'sector_slope';
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
        const slopeKeys = new Set(['sector_slope', 'sector_slope_short']);
        list.sort((a, b) => {
            // 中线/短线斜率：先按对应环境档，再按斜率数值
            if (slopeKeys.has(key)) {
                const mode = key === 'sector_slope_short' ? 'short' : 'mid';
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

    boardEnvChipHtml(d, mode = 'mid') {
        const isShort = mode === 'short';
        const env = isShort
            ? ((d && d.board_env_short) || (d && d.board_strong_short ? 'strong' : (d && d.board_weak_short ? 'weak' : '')))
            : ((d && d.board_env) || (d && d.board_strong ? 'strong' : (d && d.board_weak ? 'weak' : '')));
        const label = isShort
            ? ((d && d.board_env_short_label)
                || (env === 'strong' ? '走强' : env === 'weak' ? '走弱' : env === 'neutral' ? '正常' : '--'))
            : ((d && d.board_env_label)
                || (env === 'strong' ? '走强' : env === 'weak' ? '走弱' : env === 'neutral' ? '正常' : '--'));
        const tip = this.escapeHtml(
            isShort
                ? ((d && (d.board_weak_short_summary || d.board_env_short_label)) || '短线环境')
                : ((d && (d.board_weak_summary || d.board_weak_reason)) || '')
        );
        let cls = 'sector-weak-chip unknown';
        if (env === 'strong') cls = 'sector-weak-chip strong';
        else if (env === 'weak') cls = 'sector-weak-chip weak';
        else if (env === 'neutral') cls = 'sector-weak-chip ok';
        return `<span class="${cls}" title="${tip}">${this.escapeHtml(label)}</span>`;
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
            tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:#888;">暂无同花顺${ui.label}数据</td></tr>`;
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
                    <td class="${this.getChangeClass(sector.sector_slope)}">${this.formatSlope(sector.sector_slope)}</td>
                    <td>${this.boardEnvChipHtml(sector)}</td>
                    <td class="${this.getChangeClass(sector.sector_slope_short)}">${this.formatSlope(sector.sector_slope_short)}</td>
                    <td>${this.boardEnvChipHtml(sector, 'short')}</td>
                    <td class="sector-row-actions">
                        <button type="button" class="btn btn-secondary sector-row-detail-btn">详情</button>
                        <button type="button" class="btn btn-secondary sector-row-slope-btn" title="仅重算该板块斜率">重算斜率</button>
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
            grid.innerHTML = `<div class="empty-tip" style="text-align:center;padding:2em;color:#888;">暂无同花顺${ui.label}数据</div>`;
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
                            <span class="stock-name">中线斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope)}">${this.formatSlope(sector.sector_slope)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">中线环境</span>
                            <span class="stock-change">${this.boardEnvChipHtml(sector)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">短线斜率</span>
                            <span class="stock-change ${this.getChangeClass(sector.sector_slope_short)}">${this.formatSlope(sector.sector_slope_short)}</span>
                        </div>
                        <div class="leader-stock">
                            <span class="stock-name">短线环境</span>
                            <span class="stock-change">${this.boardEnvChipHtml(sector, 'short')}</span>
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

    /** 对齐分析频道板块分析短线角色 pill（ba-role-pill），保留 goToStock */
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
        return `<a class="${cls}" href="javascript:void(0)" onclick="goToStock('${this.escapeHtml(code)}','${this.escapeHtml(name)}')" title="${title}">${label} ${show}${pctHtml}</a>`;
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
            sub.innerHTML = `${kindLabel} · ${this.escapeHtml(d.board_code || '--')} · ${this.escapeHtml(d.board_code_source_label || d.board_code_source || '')}${d.mapped_em_board_code ? ` · 映射东财 ${this.escapeHtml(d.mapped_em_board_code)}` : ''}${d.mapped_ths_board_code ? ` · 映射同花顺 ${this.escapeHtml(d.mapped_ths_board_code)}` : ''}${d.quote_board_code && d.quote_board_code !== d.board_code ? ` · 行情码 ${this.escapeHtml(d.quote_board_code)}` : ''}${this.boardEnvChipHtml(d)}`;
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
                </div>
                <div class="sector-detail-grid">
                    ${item('中线斜率(ln)', this.formatSlope(d.sector_slope), this.getChangeClass(d.sector_slope))}
                    ${item('中线环境', this.boardEnvChipHtml(d))}
                    ${item('中线window', d.sector_slope_window != null ? d.sector_slope_window : 60)}
                    ${item('中线asof', d.slope_asof_date || '--')}
                    ${item('短线斜率(ln)', this.formatSlope(d.sector_slope_short), this.getChangeClass(d.sector_slope_short))}
                    ${item('短线环境', this.boardEnvChipHtml(d, 'short'))}
                    ${item('短线window', d.sector_slope_short_window != null ? d.sector_slope_short_window : 10)}
                    ${item('短线asof', d.slope_short_asof_date || '--')}
                    ${item('走强阈值(中)', d.slope_strong_threshold != null ? Number(d.slope_strong_threshold).toFixed(4) : '0.0010')}
                    ${item('走强阈值(短)', d.slope_short_strong_threshold != null ? Number(d.slope_short_strong_threshold).toFixed(4) : '0.0015')}
                    ${item('member_count_used', d.member_count_used != null ? d.member_count_used : '--')}
                </div>
                <div class="sector-detail-summary">${this.escapeHtml(d.board_weak_summary || '暂无判断说明')}（中线≈60日，短线≈10日；均为 ln 量权基准回归）</div>
            </div>
            <div class="sector-detail-section">
                <h3>龙头 / 中军</h3>
                ${rolesHtml}
            </div>
            <div class="sector-detail-section">
                <h3>更新时间</h3>
                <div class="sector-detail-meta">${this.escapeHtml(d.update_time || '--')}</div>
            </div>
        `;

        const slopeBtn = body.querySelector('.sector-detail-slope-btn');
        if (slopeBtn) {
            const kind = (d.board_kind === 'concept') ? 'concept' : 'industry';
            const code = d.board_code || (this._sectorDetailCtx && this._sectorDetailCtx.boardCode) || '';
            slopeBtn.addEventListener('click', () => {
                this.refreshSectorSlopes(kind, {
                    boardCode: code,
                    triggerBtn: slopeBtn,
                });
            });
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
                // 添加成功后触发历史行情采集与 MA/MACD/RSI/KDJ/BOLL/MAVOL/PVFRS 指标计算
                authFetch(`${API_BASE_URL}/api/watchlist/collect-and-calculate-indicators`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stock_code: stockCode })
                }).then(r => r.json()).then(data => {
                    if (data.success) {
                        CommonUtils.showToast('行情与指标已更新', 'success');
                    }
                }).catch(() => { });
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



// DOM加载完成后初始化
// 查询到股票代码后定位到表格列表中相应记录
document.addEventListener('DOMContentLoaded', function () {
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

