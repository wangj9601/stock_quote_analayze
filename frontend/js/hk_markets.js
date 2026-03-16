// 港股行情页面功能模块
const HKMarketsPage = {
    
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
        this.loadHKIndices(); // 加载港股指数模拟数据
        this.loadHKRankingData();
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
        // 内容标签切换（港股标签页内的）
        document.querySelectorAll('#hk-market-tab .content-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
                this.updateActiveTab(tab);
            });
        });

        // 排行榜类型切换
        document.querySelectorAll('#hk-market-tab .ranking-type-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchRankingType(btn.dataset.type);
                this.updateActiveRankingType(btn);
            });
        });

        // 市场过滤器（港股标签页下的搜索）
        const hkFilterSelect = document.querySelector('#hk-market-tab .filter-select');
        if (hkFilterSelect) {
            hkFilterSelect.addEventListener('change', (e) => {
                // 港股暂时不需要市场过滤，可以用于其他用途
                this.loadHKRankingData(1);
            });
        }

        // 搜索按钮
        const hkSearchBtn = document.getElementById('hkMarketSearchBtn');
        if (hkSearchBtn) {
            hkSearchBtn.addEventListener('click', () => {
                const keyword = document.getElementById('hkMarketSearchInput').value.trim();
                this.searchHKStocks(keyword);
            });
        }

        // 点击股票行跳转
        document.addEventListener('click', (e) => {
            if (e.target.closest('#hk-market-tab .hot-stock-item')) {
                const stockCode = e.target.closest('.hot-stock-item').querySelector('.stock-code').textContent;
                this.goToStock(stockCode);
            }
        });
    },

    // 切换标签
    switchTab(tabId) {
        this.currentTab = tabId;
        
        // 隐藏所有面板
        document.querySelectorAll('#hk-market-tab .tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        
        // 显示目标面板
        const targetPanel = document.querySelector(`#hk-market-tab .tab-panel[data-tab="${tabId}"]`);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }

        // 根据标签加载相应数据
        this.loadTabData(tabId);
    },

    // 更新活动标签样式
    updateActiveTab(activeTab) {
        document.querySelectorAll('#hk-market-tab .content-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        activeTab.classList.add('active');
    },

    // 切换排行榜类型
    switchRankingType(type) {
        this.currentRankingType = type;
        this.currentPage = 1;
        this.loadHKRankingData(1);
    },

    // 更新活动排行榜类型按钮样式
    updateActiveRankingType(activeBtn) {
        document.querySelectorAll('#hk-market-tab .ranking-type-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        activeBtn.classList.add('active');
    },

    // 加载标签数据
    loadTabData(tabId) {
        switch(tabId) {
            case 'rankings':
                this.loadHKRankingData();
                break;
            case 'sectors':
                // 港股行业板块暂时使用模拟数据
                break;
            case 'hot':
                // 港股热门关注暂时使用模拟数据
                break;
            case 'stats':
                // 港股市场统计暂时使用模拟数据
                break;
        }
    },

    // 加载港股指数模拟数据
    async loadHKIndices() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/api/stock/hk_indices`);
            const result = await response.json();
            
            if (result.success && result.data) {
                this.updateHKIndicesDisplay(result.data);
            } else {
                // 如果API失败，使用本地模拟数据
                this.updateHKIndicesDisplay(this.getMockHKIndices());
            }
        } catch (error) {
            console.error('加载港股指数失败:', error);
            // 使用本地模拟数据
            this.updateHKIndicesDisplay(this.getMockHKIndices());
        }
    },

    // 获取模拟港股指数数据
    getMockHKIndices() {
        return [
            {
                code: 'HSI',
                name: '恒生指数',
                value: 18500 + Math.random() * 500 - 250,
                change: Math.random() * 200 - 100,
                change_percent: Math.random() * 1.5 - 0.75
            },
            {
                code: 'HSTECH',
                name: '恒生科技指数',
                value: 4500 + Math.random() * 200 - 100,
                change: Math.random() * 80 - 40,
                change_percent: Math.random() * 2.0 - 1.0
            },
            {
                code: 'HSCEI',
                name: '恒生中国企业指数',
                value: 6500 + Math.random() * 300 - 150,
                change: Math.random() * 150 - 75,
                change_percent: Math.random() * 2.5 - 1.25
            },
            {
                code: 'HSCI',
                name: '恒生综合指数',
                value: 2800 + Math.random() * 100 - 50,
                change: Math.random() * 50 - 25,
                change_percent: Math.random() * 2.0 - 1.0
            }
        ];
    },

    // 更新港股指数显示
    updateHKIndicesDisplay(indicesData) {
        indicesData.forEach((index, idx) => {
            const indexCard = document.querySelector(`#hk-market-tab .hk-index-card[data-index-code="${index.code}"]`);
            if (!indexCard) return;

            const valueEl = indexCard.querySelector('.index-value');
            const changeValueEl = indexCard.querySelector('.change-value');
            const changePercentEl = indexCard.querySelector('.change-percent');

            if (valueEl) {
                valueEl.textContent = index.value.toFixed(2);
            }
            if (changeValueEl) {
                changeValueEl.textContent = index.change >= 0 ? `+${index.change.toFixed(2)}` : index.change.toFixed(2);
                changeValueEl.className = `change-value ${index.change >= 0 ? 'positive' : 'negative'}`;
            }
            if (changePercentEl) {
                changePercentEl.textContent = index.change_percent >= 0 ? `+${index.change_percent.toFixed(2)}%` : `${index.change_percent.toFixed(2)}%`;
                changePercentEl.className = `change-percent ${index.change_percent >= 0 ? 'positive' : 'negative'}`;
            }
        });
    },

    // 加载港股排行榜数据
    async loadHKRankingData(page = 1) {
        const typeMap = {
            rise: 'rise',
            fall: 'fall',
            volume: 'volume',
            turnover: 'turnover_rate'
        };
        const rankingType = typeMap[this.currentRankingType] || 'rise';
        this.currentPage = page;
        const pageSize = this.pageSize;
        
        // 获取搜索关键词
        const searchInput = document.getElementById('hkMarketSearchInput');
        const keyword = searchInput ? searchInput.value.trim() : '';
        
        try {
            let url = `${this.API_BASE_URL}/api/stock/hk_quote_board_list?ranking_type=${rankingType}&page=${page}&page_size=${pageSize}`;
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
                    english_name: item.english_name || '',
                    price: item.current,
                    change: item.change,
                    percent: item.change_percent,
                    volume: item.volume,
                    turnover: item.turnover,
                    rate: item.rate
                }));
                this.renderHKRankingTable(data);
                this.renderHKPagination();
            } else {
                this.renderHKRankingTable([]);
                this.renderHKPagination();
                CommonUtils.showToast(result.message || '获取港股数据失败', 'error');
            }
        } catch (e) {
            console.error('加载港股数据失败:', e);
            this.renderHKRankingTable([]);
            this.renderHKPagination();
            CommonUtils.showToast('网络错误，获取港股数据失败', 'error');
        }
    },

    // 搜索港股股票
    searchHKStocks(keyword) {
        if (keyword) {
            this.loadHKRankingData(1);
        } else {
            // 清空搜索，重新加载
            this.loadHKRankingData(1);
        }
    },

    // 渲染港股排行榜表格
    renderHKRankingTable(data) {
        const tbody = document.getElementById('hkRankingsTableBody');
        if (!tbody) return;

        tbody.innerHTML = data.map(stock => `
            <tr data-code="${stock.code}" onclick="goToStock('${stock.code}', '${stock.name}')" style="cursor: pointer;">
                <td>
                    <span class="rank-number ${stock.rank <= 3 ? 'rank-' + stock.rank : ''}">${stock.rank}</span>
                </td>
                <td>
                    <div class="stock-info">
                        <div class="stock-name">${stock.name}${stock.english_name ? '<br><small style="color:#666;">' + stock.english_name + '</small>' : ''}</div>
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
                        <button class="btn btn-sm btn-primary" onclick="HKMarketsPage.handleQuickTrade(event, '${stock.code}', '${stock.name}', 'buy')">买入</button>
                        <button class="btn btn-sm btn-danger" onclick="HKMarketsPage.handleQuickTrade(event, '${stock.code}', '${stock.name}', 'sell')" style="margin-left:5px;">卖出</button>
                        <button class="btn btn-sm btn-secondary" data-stock-code="${stock.code}" data-stock-name="${stock.name}" onclick="addToWatchlist('${stock.code}', event); event.stopPropagation();" style="margin-left:5px;">+自选</button>
                        <button class="btn btn-sm btn-secondary" onclick="goToStockHistory('${stock.code}', '${stock.name}'); event.stopPropagation();" style="margin-left:5px;">历史</button>
                    </div>
                </td>
            </tr>
        `).join('');
        
        // 渲染完成后，更新所有自选股按钮的状态
        this.updateAllWatchlistButtons();
    },

    // 快速交易处理
    async handleQuickTrade(event, code, name, side) {
        event.stopPropagation();
        try {
            const response = await fetch(`${this.API_BASE_URL}/api/simtrade/order`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    code: code,
                    name: name,
                    side: side,
                    quantity: 100,
                    price: null
                })
            });
            const result = await response.json();
            if (result.success) {
                CommonUtils.showToast(`${side === 'buy' ? '买入' : '卖出'} ${name}(${code}) 成功`, 'success');
            } else {
                CommonUtils.showToast(result.message || '交易失败', 'error');
            }
        } catch (e) {
            CommonUtils.showToast('网络异常，模拟交易下单失败', 'error');
        }
    },

    // 渲染港股分页
    renderHKPagination() {
        const container = document.querySelector('#hk-market-tab .rankings-content');
        if (!container) return;
        
        let pagination = document.getElementById('hkRankingsPagination');
        if (!pagination) {
            pagination = document.createElement('div');
            pagination.id = 'hkRankingsPagination';
            pagination.className = 'pagination';
            container.insertBefore(pagination, container.querySelector('table'));
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
            if (i === 1 || i === totalPages) continue;
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
                    this.loadHKRankingData(page);
                }
            };
        });
    },

    // 更新所有自选股按钮的状态
    updateAllWatchlistButtons() {
        const buttons = document.querySelectorAll('#hkRankingsTableBody button[data-stock-code]');
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

    // 开始数据更新
    startDataUpdate() {
        // 定期更新数据
        setInterval(() => {
            if (this.currentTab === 'rankings') {
                this.loadHKRankingData(this.currentPage);
            }
        }, 60000); // 每60秒更新一次

        // 更新指数数据
        setInterval(() => {
            this.loadHKIndices();
        }, 30000); // 每30秒更新指数数据
    },

    // 格式化价格
    formatPrice(price) {
        if (price === null || typeof price === 'undefined' || isNaN(price)) return '--';
        return price.toFixed(2);
    },

    // 格式化涨跌额
    formatChange(change) {
        if (change === null || typeof change === 'undefined' || isNaN(change)) return '--';
        return change >= 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
    },

    // 格式化涨跌幅（加上%符号，保留两位小数）
    formatPercent(percent) {
        if (percent === null || typeof percent === 'undefined' || isNaN(percent)) return '--';
        return percent >= 0 ? `+${percent.toFixed(2)}%` : `${percent.toFixed(2)}%`;
    },

    // 格式化成交量（库存为手；按手显示：万手/亿手）
    formatVolume(volume) {
        if (volume === null || typeof volume === 'undefined' || isNaN(volume)) return '--';
        const v = Number(volume);
        if (v >= 100000000) return `${(v / 100000000).toFixed(2)}亿手`;
        if (v >= 10000) return `${(v / 10000).toFixed(2)}万手`;
        return `${v.toFixed(0)}手`;
    },

    // 格式化成交额
    formatTurnover(turnover) {
        if (turnover === null || typeof turnover === 'undefined' || isNaN(turnover)) return '--';
        if (turnover >= 100000000) {
            return `${(turnover / 100000000).toFixed(2)}亿`;
        } else if (turnover >= 10000) {
            return `${(turnover / 10000).toFixed(2)}万`;
        }
        return turnover.toLocaleString();
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
            console.log(`跳转到港股详情: ${stockCode}`);
            // 这里可以根据实际需求跳转到股票详情页面
            alert(`港股代码: ${stockCode}`);
        }
    }
};

