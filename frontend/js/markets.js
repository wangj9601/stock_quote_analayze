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

    // 全局API前缀
    API_BASE_URL: Config ? Config.getApiBaseUrl() : 'http://192.168.31.237:5000',

    // 初始化
    async init() {
        this.bindEvents();
        this.loadMarketIndices(); // 加载真实指数数据
        this.loadIndexCharts();
        this.loadRankingData();
        this.startDataUpdate();
        
        // 初始化自选股管理器
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

        // 点击股票行跳转
        document.addEventListener('click', (e) => {
            if (e.target.closest('.hot-stock-item')) {
                const stockCode = e.target.closest('.hot-stock-item').querySelector('.stock-code').textContent;
                this.goToStock(stockCode);
            }
        });
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
        this.loadRankingData(1);
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
                this.loadSectorData();
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
        indicesData.forEach(function(index) {
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

    // 加载板块数据
    async loadSectorData() {
        try {
            console.log('加载行业板块数据...');
            const response = await fetch(`${this.API_BASE_URL}/api/market/industry_board`);
            const result = await response.json();
            
            if (result.success && result.data) {
                this.updateIndustryBoardDisplay(result.data);
                console.log('行业板块数据加载成功');
            } else {
                throw new Error('API返回错误');
            }
        } catch (error) {
            console.error('行业板块数据加载失败:', error);
            // 使用模拟数据作为后备
            this.updateSectorData();
            console.log('使用模拟行业板块数据');
        }
    },

    // 更新行业板块显示（使用真实数据）
    async updateIndustryBoardDisplay(industryData) {
        // 获取前4个行业板块数据
        const topSectors = industryData.slice(0, 4);
        
        // 清空现有的行业板块内容
        const sectorsGrid = document.querySelector('.sectors-grid');
        if (!sectorsGrid) return;
        
        sectorsGrid.innerHTML = '';
        
        // 为每个行业板块创建卡片（异步）
        for (const sector of topSectors) {
            const sectorCard = await this.createIndustryBoardCard(sector);
            sectorsGrid.appendChild(sectorCard);
        }
        
        // 如果没有数据，显示默认卡片
        if (topSectors.length === 0) {
            this.createDefaultSectorCards();
        }
    },

    // 创建行业板块卡片
    async createIndustryBoardCard(sector) {
        const card = document.createElement('div');
        card.className = 'sector-card';
        
        const changePercent = parseFloat(sector.change_percent || 0);
        const isPositive = changePercent >= 0;
        
        // 模拟上涨、下跌、平盘数量（实际数据中可能没有这些字段）
        const upCount = Math.floor(Math.random() * 50) + 20;
        const downCount = Math.floor(Math.random() * 30) + 5;
        const flatCount = Math.floor(Math.random() * 5) + 1;
        
        // 处理龙头股信息
        const leadingStockName = sector.leading_stock_name || '--';
        const leadingStockChange = parseFloat(sector.leading_stock_change_percent || 0);
        const leadingStockCode = sector.leading_stock_code || '';
        
        // 如果有龙头股代码，可以添加点击跳转功能
        const leadingStockDisplay = leadingStockCode ? 
            `<span class="stock-name clickable" onclick="goToStock('${leadingStockCode}')" title="点击查看股票详情">${leadingStockName}</span>` :
            `<span class="stock-name">${leadingStockName}</span>`;
        
        // 获取板块内涨幅领先的股票
        let topStocks = [];
        if (sector.board_code) {
            try {
                // 传递板块代码和名称，支持智能匹配
                const params = new URLSearchParams({
                    board_code: sector.board_code,
                    board_name: sector.board_name || ''
                });
                const response = await fetch(`${this.API_BASE_URL}/api/market/industry_board/${sector.board_code}/top_stocks?${params}`);
                const result = await response.json();
                if (result.success && result.data.top_stocks) {
                    topStocks = result.data.top_stocks;
                }
            } catch (error) {
                console.error(`获取板块 ${sector.board_name} 龙头股失败:`, error);
            }
        }
        
        // 构建龙头股显示
        let leadersHTML = '';
        if (topStocks.length > 0) {
            // 显示前两只龙头股
            topStocks.slice(0, 2).forEach((stock, index) => {
                const stockDisplay = stock.code ? 
                    `<span class="stock-name clickable" onclick="goToStock('${stock.code}')" title="点击查看股票详情">${stock.name}</span>` :
                    `<span class="stock-name">${stock.name}</span>`;
                
                leadersHTML += `
                    <div class="leader-stock">
                        ${stockDisplay}
                        <span class="stock-change ${this.getChangeClass(stock.change_percent)}">${this.formatPercent(stock.change_percent)}</span>
                    </div>
                `;
            });
            
            // 如果只有一只股票，添加占位符
            if (topStocks.length === 1) {
                leadersHTML += `
                    <div class="leader-stock">
                        <span class="stock-name">--</span>
                        <span class="stock-change">--</span>
                    </div>
                `;
            }
        } else {
            // 使用默认的龙头股信息
            leadersHTML = `
                <div class="leader-stock">
                    ${leadingStockDisplay}
                    <span class="stock-change ${this.getChangeClass(leadingStockChange)}">${this.formatPercent(leadingStockChange)}</span>
                </div>
                <div class="leader-stock">
                    <span class="stock-name">--</span>
                    <span class="stock-change">--</span>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="sector-header">
                <h3>${sector.board_name || '未知板块'}</h3>
                <span class="sector-change ${isPositive ? 'positive' : 'negative'}">${this.formatPercent(changePercent)}</span>
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
                    <span class="label">平盘</span>
                    <span class="value">${flatCount}</span>
                </div>
            </div>
            <div class="sector-leaders">
                ${leadersHTML}
            </div>
            <button class="sector-detail-btn" onclick="goToSectorDetail('${sector.board_name || '未知板块'}')">查看详情</button>
        `;
        
        return card;
    },

    // 创建默认行业板块卡片（当没有数据时）
    createDefaultSectorCards() {
        const sectorsGrid = document.querySelector('.sectors-grid');
        if (!sectorsGrid) return;
        
        const defaultSectors = [
            { name: '新能源汽车', change: 3.45, up: 45, down: 12, flat: 3, leader1: '比亚迪', leader1Change: 5.67, leader2: '宁德时代', leader2Change: 4.32 },
            { name: '人工智能', change: 2.87, up: 38, down: 15, flat: 2, leader1: '科大讯飞', leader1Change: 6.89, leader2: '百度', leader2Change: 4.56 },
            { name: '生物医药', change: -1.23, up: 18, down: 35, flat: 4, leader1: '药明康德', leader1Change: 2.34, leader2: '恒瑞医药', leader2Change: -1.45 },
            { name: '半导体', change: 4.12, up: 52, down: 8, flat: 3, leader1: '中芯国际', leader1Change: 7.89, leader2: '韦尔股份', leader2Change: 6.23 }
        ];
        
        defaultSectors.forEach(sector => {
            const card = document.createElement('div');
            card.className = 'sector-card';
            
            card.innerHTML = `
                <div class="sector-header">
                    <h3>${sector.name}</h3>
                    <span class="sector-change ${sector.change >= 0 ? 'positive' : 'negative'}">${this.formatPercent(sector.change)}</span>
                </div>
                <div class="sector-stats">
                    <div class="stat-item">
                        <span class="label">上涨</span>
                        <span class="value positive">${sector.up}</span>
                    </div>
                    <div class="stat-item">
                        <span class="label">下跌</span>
                        <span class="value negative">${sector.down}</span>
                    </div>
                    <div class="stat-item">
                        <span class="label">平盘</span>
                        <span class="value">${sector.flat}</span>
                    </div>
                </div>
                <div class="sector-leaders">
                    <div class="leader-stock">
                        <span class="stock-name">${sector.leader1}</span>
                        <span class="stock-change ${sector.leader1Change >= 0 ? 'positive' : 'negative'}">${this.formatPercent(sector.leader1Change)}</span>
                    </div>
                    <div class="leader-stock">
                        <span class="stock-name">${sector.leader2}</span>
                        <span class="stock-change ${sector.leader2Change >= 0 ? 'positive' : 'negative'}">${this.formatPercent(sector.leader2Change)}</span>
                    </div>
                </div>
                <button class="sector-detail-btn" onclick="goToSectorDetail('${sector.name}')">查看详情</button>
            `;
            
            sectorsGrid.appendChild(card);
        });
    },

    // 更新板块数据（模拟数据，作为后备）
    updateSectorData() {
        const sectorCards = document.querySelectorAll('.sector-card');
        sectorCards.forEach(card => {
            // 模拟数据变化
            const changeEl = card.querySelector('.sector-change');
            const currentChange = parseFloat(changeEl.textContent.replace('%', ''));
            const newChange = currentChange + (Math.random() - 0.5) * 0.5;
            
            changeEl.textContent = this.formatPercent(newChange);
            changeEl.className = `sector-change ${this.getChangeClass(newChange)}`;

            // 更新统计数据
            const statValues = card.querySelectorAll('.stat-item .value');
            statValues.forEach(valueEl => {
                if (!valueEl.classList.contains('positive') && !valueEl.classList.contains('negative')) {
                    const current = parseInt(valueEl.textContent);
                    const newValue = Math.max(0, current + Math.floor((Math.random() - 0.5) * 3));
                    valueEl.textContent = newValue;
                }
            });
        });
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

    // 格式化成交量（以万为单位，保留两位小数）
    formatVolume(volume) {
        if (volume === null || typeof volume === 'undefined' || isNaN(volume)) return '--';
        // 转换为万为单位
        const volumeInWan = volume / 10000;
        return `${volumeInWan.toFixed(2)}万`;
    },

    // 格式化成交额（以亿为单位，保留两位小数）
    formatTurnover(turnover) {
        if (turnover === null || typeof turnover === 'undefined' || isNaN(turnover)) return '--';
        // 转换为亿为单位
        const turnoverInYi = turnover / 100000000;
        return `${turnoverInYi.toFixed(2)}亿`;
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
        // 定期更新数据
        setInterval(() => {
            if (this.currentTab === 'rankings') {
                //this.updateRankingPrices();
                this.loadRankingData(this.currentPage);
            } else if (this.currentTab === 'sectors') {
                this.loadSectorData(); // 重新加载真实数据
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
                    this.loadRankingData(page);
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

function goToSectorDetail(sectorName) {
    CommonUtils.showToast(`查看${sectorName}板块详情`, 'info');
    // 实际项目中这里会跳转到板块详情页
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
                }).catch(() => {});
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
    
    // 获取股票名称
    const stockRow = event.target.closest('tr');
    const stockName = stockRow ? stockRow.querySelector('.stock-name').textContent : code;
    
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
document.addEventListener('DOMContentLoaded', function() {
    MarketsPage.init();
    // 查询输入框和按钮只绑定一次
    setTimeout(function() {
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
            searchInput.onkeydown = function(e) {
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

