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
    API_BASE_URL: 'http://192.168.31.237:5000',

    // 初始化
    init() {
        this.bindEvents();
        this.loadIndexCharts();
        this.loadRankingData();
        this.startDataUpdate();
        
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

// 加载排行榜数据
async loadRankingData(page = 1) {
    const typeMap = {
        rise: 'rise',
        fall: 'fall',
        volume: 'volume',
        turnover: 'turnover_rate'
    };
    const rankingType = typeMap[this.currentRankingType] || 'rise';
    let market = document.querySelector('.filter-select').value;
    if (market === 'cy') market = 'cy';
    this.currentPage = page;
    const pageSize = this.pageSize;
    try {
        const url = `${API_BASE_URL}/api/stock/quote_board_list?ranking_type=${rankingType}&market=${market}&page=${page}&page_size=${pageSize}`;
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
            this.renderRankingTable(data);
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
    renderRankingTable(data) {
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
                <td class="price-column">${stock.volume}</td>
                <td class="price-column">${stock.turnover}</td>
                <td class="price-column">${stock.rate}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="addToWatchlist('${stock.code}', event)">+自选</button>
                </td>
            </tr>
        `).join('');
    },

    // 加载板块数据
    loadSectorData() {
        // 板块数据已在HTML中静态定义，这里可以添加动态更新逻辑
        setTimeout(() => {
            this.updateSectorData();
        }, 100);
    },

    // 更新板块数据
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

    // 获取涨跌颜色
    getChangeClass(value) {
        if (value === null || typeof value === 'undefined' || isNaN(value)) return 'text-gray-500';
        if (value > 0) return 'text-red-500';
        if (value < 0) return 'text-green-500';
        return '';
    },

    // 开始数据更新
    startDataUpdate() {
        // 定期更新数据
        setInterval(() => {
            if (this.currentTab === 'rankings') {
                //this.updateRankingPrices();
                this.loadRankingData(this.currentPage);
            } else if (this.currentTab === 'sectors') {
                this.updateSectorData();
            } else if (this.currentTab === 'hot') {
                this.updateCapitalFlow();
                this.updateMarketSentiment();
            }
        }, 60000); // 每60秒更新一次

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

function addToWatchlist(code, event) {
    if (event) {
        event.stopPropagation();
    }
    CommonUtils.showToast(`${code} 已添加到自选股`, 'success');
}



// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    MarketsPage.init();
}); 

