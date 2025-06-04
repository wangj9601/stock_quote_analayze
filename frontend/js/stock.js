// 股票详情页面功能模块
const getQueryParam = (name) => {
    const url = window.location.search;
    const params = new URLSearchParams(url);
    return params.get(name);
};

const StockPage = {
    stockCode: getQueryParam('code') || '',
    stockName: getQueryParam('name') || '',
    currentPrice: null,
    priceChange: null,
    priceChangePercent: null,
    open: null,
    yesterday_close: null,
    high: null,
    low: null,
    average_price: null,          
    volume: null,
    turnover: null,
    turnover_rate: null,
    pe_dynamic: null,
    klineChart: null,
    minuteChart: null,
    profitChart: null,
    flowChart: null,
    currentTab: 'analysis',
    currentChartType: 'kline',
    currentPeriod: '1d',
    //API_BASE_URL: 'http://192.168.31.237:5000',

    // 初始化
    init() {
        this.bindEvents();
        this.initCharts();
        this.loadStockData();
        this.startDataUpdate();
    },

    // 绑定事件
    bindEvents() {
        // 自选股切换
        document.querySelector('.watchlist-toggle').addEventListener('click', () => {
            this.toggleWatchlist();
        });

        // 图表类型切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchChartType(btn.dataset.type);
                this.updateActiveBtn(btn, '.tab-btn');
            });
        });

        // 时间周期切换
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchPeriod(btn.dataset.period);
                this.updateActiveBtn(btn, '.period-btn');
            });
        });

        // 内容标签切换
        document.querySelectorAll('.content-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchContentTab(tab.dataset.tab);
                this.updateActiveBtn(tab, '.content-tab');
            });
        });

        // 新闻过滤
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.filterNews(btn.dataset.filter);
                this.updateActiveBtn(btn, '.filter-btn');
            });
        });

        // 指标选择
        document.querySelector('.indicator-select').addEventListener('change', (e) => {
            this.updateMainIndicator(e.target.value);
        });

        document.querySelector('.sub-indicator-select').addEventListener('change', (e) => {
            this.updateSubIndicator(e.target.value);
        });

        // 搜索功能
        this.bindSearchEvents();
    },

    // 绑定搜索事件
    bindSearchEvents() {
        const searchBtn = document.querySelector('.search-btn');
        const searchModal = document.getElementById('searchModal');
        const closeSearch = document.querySelector('.close-search');
        const searchInput = document.querySelector('.search-input');

        searchBtn.addEventListener('click', () => {
            searchModal.style.display = 'flex';
            searchInput.focus();
        });

        closeSearch.addEventListener('click', () => {
            searchModal.style.display = 'none';
            searchInput.value = '';
        });

        searchModal.addEventListener('click', (e) => {
            if (e.target === searchModal) {
                searchModal.style.display = 'none';
                searchInput.value = '';
            }
        });
    },

    // 切换自选股状态
    toggleWatchlist() {
        const toggleBtn = document.querySelector('.watchlist-toggle');
        const isActive = toggleBtn.classList.contains('active');
        
        if (isActive) {
            toggleBtn.classList.remove('active');
            toggleBtn.textContent = '⭐ 自选';
            CommonUtils.showToast(`已从自选股中移除 ${this.stockName}`, 'info');
        } else {
            toggleBtn.classList.add('active');
            toggleBtn.textContent = '⭐ 已自选';
            CommonUtils.showToast(`已添加 ${this.stockName} 到自选股`, 'success');
        }
    },

    // 切换图表类型
    switchChartType(type) {
        this.currentChartType = type;

        // 控制K线相关标签栏和指标下拉框的显示/隐藏
        const periodTabs = document.querySelector('.chart-period-tabs');
        const indicators = document.querySelector('.chart-indicators');
        if (type === 'minute') {
            if (periodTabs) periodTabs.style.display = 'none';
            if (indicators) indicators.style.display = 'none';
        } else if (type === 'kline') {
            if (periodTabs) periodTabs.style.display = '';
            if (indicators) indicators.style.display = '';
        }
        
        // 隐藏所有图表
        document.querySelectorAll('.chart').forEach(chart => {
            chart.style.display = 'none';
        });
        
        // 显示目标图表
        const targetChart = document.getElementById(`${type}Chart`);
        if (targetChart) {
            targetChart.style.display = 'block';
            this.resizeChart(type);
        }

        // 切换类型后加载对应图表数据
        this.loadChartData();
    },

    // 切换时间周期
    switchPeriod(period) {
        this.currentPeriod = period;
        this.loadChartData();
        //CommonUtils.showToast(`切换到${this.getPeriodName(period)}`, 'info');
    },

    // 获取周期名称
    getPeriodName(period) {
        const periodNames = {
            '1m': '1分钟',
            '5m': '5分钟',
            '15m': '15分钟',
            '30m': '30分钟',
            '1h': '1小时',
            '1d': '日线',
            '1w': '周线',
            '1M': '月线'
        };
        return periodNames[period] || period;
    },

    // 切换内容标签
    switchContentTab(tabId) {
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
        // 切换到资金流向tab时，resize图表
        if (tabId === 'flow' && this.flowChart) {
            this.flowChart.resize();
        }
        // 根据标签加载相应数据
        this.loadTabData(tabId);
    },

    // 更新活动按钮
    updateActiveBtn(activeBtn, selector) {
        document.querySelectorAll(selector).forEach(btn => {
            btn.classList.remove('active');
        });
        activeBtn.classList.add('active');
    },

    // 初始化图表
    initCharts() {
        this.initKlineChart();
        this.initMinuteChart();
        this.initProfitChart();
        this.initFlowChart();
    },

    // 初始化K线图
    initKlineChart() {
        const chartDom = document.getElementById('klineChart');
        if (!chartDom) return;
        this.klineChart = echarts.init(chartDom);
        const option = {
            backgroundColor: 'transparent',
            grid: [
                { left: '10%', right: '8%', height: '65%' },
                { left: '10%', right: '8%', top: '75%', height: '15%' }
            ],
            xAxis: [
                { type: 'category', data: [], boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' },
                { type: 'category', gridIndex: 1, data: [], boundaryGap: false, axisLine: { onZero: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false }, min: 'dataMin', max: 'dataMax' }
            ],
            yAxis: [
                { scale: true, splitArea: { show: true } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } }
            ],
            dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }],
            series: [
                { name: 'K线', type: 'candlestick', data: [], itemStyle: { color: '#dc2626', color0: '#16a34a', borderColor: '#dc2626', borderColor0: '#16a34a' } },
                { name: 'MA5', type: 'line', data: [], smooth: true, lineStyle: { width: 1, color: '#fbbf24' }, showSymbol: false },
                { name: 'MA10', type: 'line', data: [], smooth: true, lineStyle: { width: 1, color: '#3b82f6' }, showSymbol: false },
                { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: [], itemStyle: { color: function(params) { return params.dataIndex % 2 === 0 ? '#dc2626' : '#16a34a'; } } }
            ],
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, backgroundColor: 'rgba(245, 245, 245, 0.8)', borderWidth: 1, borderColor: '#ccc', textStyle: { color: '#000' } }
        };
        this.klineChart.setOption(option);
    },

    // 初始化分时图
    initMinuteChart() {
        const chartDom = document.getElementById('minuteChart');
        if (!chartDom) return;

        this.minuteChart = echarts.init(chartDom);
        
        const option = {
            backgroundColor: 'transparent',
            grid: {
                left: '10%',
                right: '8%',
                top: '8%',
                bottom: '15%'
            },
            xAxis: {
                type: 'category',
                data: [], // 初始为空
                boundaryGap: false
            },
            yAxis: {
                type: 'value',
                scale: true,
                splitArea: { show: true }
            },
            series: [{
                name: '价格',
                type: 'line',
                data: [], // 初始为空
                smooth: true,
                lineStyle: {
                    color: '#2563eb',
                    width: 2
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [{
                            offset: 0, color: 'rgba(37, 99, 235, 0.3)'
                        }, {
                            offset: 1, color: 'rgba(37, 99, 235, 0.05)'
                        }]
                    }
                },
                showSymbol: false
            }],
            tooltip: {
                trigger: 'axis',
                formatter: function(params) {
                    const d = params[0];
                    const data = d.data;
                    return `
                        时间：${d.axisValue}<br/>
                        价格：<b>${data.value[1]}</b><br/>
                        成交量：${data.volume || '-'}<br/>
                        成交额：${data.amount || '-'}<br/>
                        买卖盘性质：${data.trade_type || '-'}
                    `;
                },
                backgroundColor: 'rgba(245, 245, 245, 0.8)',
                borderWidth: 1,
                borderColor: '#ccc',
                textStyle: {
                    color: '#000'
                }
            }
        };

        this.minuteChart.setOption(option);
    },

    // 初始化盈利能力图表
    initProfitChart() {
        const chartDom = document.getElementById('profitChart');
        if (!chartDom) return;

        this.profitChart = echarts.init(chartDom);
        
        const option = {
            backgroundColor: 'transparent',
            grid: {
                left: '10%',
                right: '8%',
                top: '8%',
                bottom: '15%'
            },
            xAxis: {
                type: 'category',
                data: ['2020', '2021', '2022', '2023', '2024']
            },
            yAxis: [{
                type: 'value',
                name: '净利润(亿)',
                position: 'left'
            }, {
                type: 'value',
                name: 'ROE(%)',
                position: 'right'
            }],
            series: [{
                name: '净利润',
                type: 'bar',
                data: [280, 320, 340, 345, 350],
                itemStyle: {
                    color: '#2563eb'
                }
            }, {
                name: 'ROE',
                type: 'line',
                yAxisIndex: 1,
                data: [11.2, 12.8, 12.1, 12.3, 12.8],
                lineStyle: {
                    color: '#dc2626',
                    width: 3
                },
                symbol: 'circle',
                symbolSize: 6
            }],
            tooltip: {
                trigger: 'axis'
            },
            legend: {
                data: ['净利润', 'ROE']
            }
        };

        this.profitChart.setOption(option);
    },

    // 初始化资金流向图表
    initFlowChart() {
        const chartDom = document.getElementById('flowChart');
        if (!chartDom) return;

        this.flowChart = echarts.init(chartDom);
        
        const option = {
            backgroundColor: 'transparent',
            grid: {
                left: '10%',
                right: '8%',
                top: '8%',
                bottom: '15%'
            },
            xAxis: [{
                type: 'category',
                data: []
            }],
            yAxis: [{
                type: 'value',
                name: '资金流入(亿)'
            }],
            series: [{
                name: '主力净流入',
                type: 'bar',
                data: [],
                itemStyle: {
                    color: function(params) {
                        return params.value > 0 ? '#dc2626' : '#16a34a';
                    }
                }
            }, {
                name: '大单净流入',
                type: 'bar',
                data: [],
                itemStyle: {
                    color: function(params) {
                        return params.value > 0 ? '#fbbf24' : '#6b7280';
                    }
                }
            }],
            tooltip: {
                trigger: 'axis'
            },
            legend: {
                data: ['主力净流入', '大单净流入']
            }
        };

        this.flowChart.setOption(option);
    },

    // 调整图表大小
    resizeChart(chartType) {
        setTimeout(() => {
            if (chartType === 'kline' && this.klineChart) {
                this.klineChart.resize();
            } else if (chartType === 'minute' && this.minuteChart) {
                this.minuteChart.resize();
            }
        }, 100);
    },

    // 生成模拟数据
    generateDateData() {
        const dates = [];
        const now = new Date();
        for (let i = 50; i >= 0; i--) {
            const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
            dates.push(date.toISOString().split('T')[0]);
        }
        return dates;
    },

    generateTimeData() {
        const times = [];
        const start = new Date();
        start.setHours(9, 30, 0, 0);
        
        for (let i = 0; i < 240; i++) {
            const time = new Date(start.getTime() + i * 60 * 1000);
            times.push(time.toTimeString().slice(0, 5));
        }
        return times;
    },

    // generateFlowDates() {
    //     const dates = [];
    //     const now = new Date();
    //     for (let i = 9; i >= 0; i--) {
    //         const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    //         dates.push(date.toISOString().split('T')[0].slice(5));
    //     }
    //     return dates;
    // },

    // generateFlowData(type) {
    //     const data = [];
    //     for (let i = 0; i < 10; i++) {
    //         const value = type === 'main' 
    //             ? (Math.random() - 0.3) * 5 
    //             : (Math.random() - 0.7) * 3;
    //         data.push(value.toFixed(2));
    //     }
    //     return data;
    // },

    // 加载股票数据
    async loadStockData() {
        try {
            const url = `${API_BASE_URL}/api/stock/realtime_quote_by_code?code=${this.stockCode}`;
            console.log('[loadStockData] 请求URL:', url);
            const resp = await fetch(url);
            const data = await resp.json();
            console.log('[loadStockData] 返回数据:', data);
            if (data.success) {
                const d = data.data;
                this.currentPrice = d.current_price;
                this.priceChange = d.change_amount;
                this.priceChangePercent = d.change_percent;
                this.stockName = d.name || this.stockName;
                this.open = d.open;
                this.yesterday_close = d.yesterday_close;
                this.high = d.high;
                this.low = d.low;
                this.average_price = d.average_price;
                this.volume = d.volume;
                this.turnover = d.turnover;
                this.turnover_rate = d.turnover_rate;
                this.pe_dynamic = d.pe_dynamic;
        this.updateStockInfo();
        this.updateStockDetails();
        this.loadChartData();
            } else {
                console.error('[loadStockData] API返回失败:', data.message);
                CommonUtils.showToast('实时行情获取失败: ' + data.message, 'error');
            }
        } catch (e) {
            console.error('[loadStockData] 请求异常:', e);
            CommonUtils.showToast('实时行情请求异常', 'error');
        }
    },

    // 更新股票信息
    updateStockInfo() {
        document.querySelector('.stock-name').textContent = this.stockName || '-';
        document.querySelector('.stock-code').textContent = this.stockCode || '-';
        document.querySelector('.current-price').textContent = this.currentPrice ? Number(this.currentPrice).toFixed(2) : '-';
        
        const changeElement = document.querySelector('.price-change');
        const change = this.priceChange ? Number(this.priceChange) : 0;
        const changePercent = this.priceChangePercent ? Number(this.priceChangePercent) : 0;
        const changeText = `${change > 0 ? '+' : ''}${change.toFixed(2)} (${change > 0 ? '+' : ''}${changePercent.toFixed(2)}%)`;
        changeElement.textContent = changeText;
        changeElement.className = `price-change ${change > 0 ? 'positive' : 'negative'}`;
        
        document.querySelector('.price-time').textContent = new Date().toLocaleTimeString();
    },

    // 更新股票详情
    updateStockDetails() {
        // 取API最新数据
        const d = {
            '今开': this.open,
            '昨收': this.yesterday_close,
            '最高': this.high,
            '最低': this.low,
            '均价': this.average_price,
            '成交量': this.volume,
            '成交额': this.turnover,
            '换手率': this.turnover_rate,
            '市盈率': this.pe_dynamic
        };
        document.querySelectorAll('.detail-item').forEach(item => {
            const label = item.querySelector('.label').textContent;
            const valueElement = item.querySelector('.value');
            let val = d[label];
            if (val === undefined || val === null || val === '') {
                valueElement.textContent = '-';
                valueElement.className = 'value';
            } else {
                // 格式化
                if (label === '成交量') {
                    // 假设后端volume为"手"，显示为"万手"
                    valueElement.textContent = (Number(val) / 10000).toFixed(2) + '万';
                } else if (label === '成交额') {
                    valueElement.textContent = (val / 100000000).toFixed(2) + '亿';
                } else if (label === '换手率') {
                    valueElement.textContent = (Number(val)).toFixed(2) + '%';
                } else {
                    valueElement.textContent = val;
                }
                // 颜色
                if (label === '最高') {
                    valueElement.className = 'value positive';
                } else if (label === '最低') {
                    valueElement.className = 'value negative';
                } else {
                    valueElement.className = 'value';
                }
            }
        });
    },

    // 加载图表数据
    loadChartData() {
        if (this.currentChartType === 'kline' && this.klineChart) {
            this.loadKlineData();
        } else if (this.currentChartType === 'minute' && this.minuteChart) {
            this.loadMinuteData();
        }
    },

    // 加载标签数据
    loadTabData(tabId) {
        switch (tabId) {
            case 'analysis':
                this.loadAnalysisData();
                break;
            case 'finance':
                this.loadFinanceData();
                break;
            case 'news':
                this.loadNewsData();
                break;
            case 'research':
                this.loadResearchData();
                break;
            case 'flow':
                this.loadFlowData();
                break;
        }
    },

    // 加载分析数据
    loadAnalysisData() {
        // 更新价格预测
        const targetPrice = (this.currentPrice * (1 + (Math.random() * 0.2 - 0.1))).toFixed(2);
        const change = ((targetPrice - this.currentPrice) / this.currentPrice * 100).toFixed(2);
        
        document.querySelector('.target-price').textContent = targetPrice;
        const changeElement = document.querySelector('.prediction-change');
        changeElement.textContent = `${change > 0 ? '+' : ''}${change}%`;
        changeElement.className = `prediction-change ${change > 0 ? 'positive' : 'negative'}`;
    },

    // 加载财务数据
    loadFinanceData() {
        if (this.profitChart) {
            this.profitChart.resize();
        }
    },

    // 加载新闻数据
    loadNewsData() {
        console.log('新闻数据已加载');
    },

    // 加载研报数据
    loadResearchData() {
        console.log('研报数据已加载');
    },

    // 加载资金流向数据，调用后端API
    async loadFlowData() {
        if (!this.flowChart) return;
        try {
            // 1. 先获取当日资金流向数据
            const todayUrl = `${API_BASE_URL}/api/stock_fund_flow/history?code=${this.stockCode}`;
            const todayResp = await fetch(todayUrl);
            const todayData = await todayResp.json();
            if (todayData.success && todayData.data) {
                // 依次赋值到页面
                const values = [
                    todayData.data["今日主力净流入-净额"],
                    todayData.data["今日超大单净流入-净额"],
                    todayData.data["今日大单净流入-净额"],
                    todayData.data["今日中单净流入-净额"],
                    todayData.data["今日小单净流入-净额"]
                ];
                document.querySelectorAll('.flow-summary .flow-value').forEach((el, idx) => {
                    const val = values[idx];
                    if (val == null) {
                        el.textContent = '-';
                        el.className = 'flow-value';
                    } else {
                        const num = Number(val) / 1e8;
                        el.textContent = (num > 0 ? '+' : '') + num.toFixed(2) + '亿';
                        el.className = 'flow-value ' + (num >= 0 ? 'positive' : 'negative');
                    }
                });
            } else {
                // 可选：清空或提示
            }

            // 2. 再获取多天资金流向数据，渲染图表            
            const url = `${API_BASE_URL}/api/stock_fund_flow/today?code=${this.stockCode}`;
            const resp = await fetch(url);
            const data = await resp.json();
            if (data.success && Array.isArray(data.data)) {
                // 回退：直接取原始数值（不除以1e8，不toFixed）
                const mainFlow = [];
                const largeFlow = [];
                data.data.forEach(item => {
                    mainFlow.push(Number(item.main_net_inflow || 0));
                    largeFlow.push(Number(item.large_net_inflow || 0));
                });
                // 更新ECharts配置
                const option = this.flowChart.getOption();
                option.xAxis[0].data = this.generateDateData();
                option.series[0].data = mainFlow;
                option.series[1].data = largeFlow;
                this.flowChart.setOption(option);
            } else {
                CommonUtils.showToast('资金流向获取失败: ' + (data.message || '无数据'), 'error');
            }

        } catch (e) {
            CommonUtils.showToast('资金流向请求异常', 'error');
        }
    },

    // 可选：格式化为“+2.34亿”或“-1.11亿”
    formatInflow(val) {
        if (val == null) return '-';
        const num = Number(val) / 1e8;
        const str = (num > 0 ? '+' : '') + num.toFixed(2) + '亿';
        return str;
    },

    // 过滤新闻
    filterNews(filter) {
        const newsCards = document.querySelectorAll('.news-card');
        
        newsCards.forEach(card => {
            const type = card.querySelector('.news-type').textContent.toLowerCase();
            
            if (filter === 'all' || 
                (filter === 'announcement' && type.includes('公告')) ||
                (filter === 'news' && type.includes('新闻'))) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    },

    // 更新主图指标
    updateMainIndicator(indicator) {
        CommonUtils.showToast(`切换到${indicator}指标`, 'info');
        // 实际项目中这里会更新图表指标
    },

    // 更新副图指标
    updateSubIndicator(indicator) {
        CommonUtils.showToast(`副图切换到${indicator}`, 'info');
        // 实际项目中这里会更新副图指标
    },

    // 开始数据更新
    startDataUpdate() {
        // 定期更新股价数据
        setInterval(() => {
            this.updateRealTimeData();
        }, 300000); // 每5分钟更新一次

        // 监听窗口大小变化
        window.addEventListener('resize', () => {
            setTimeout(() => {
                if (this.klineChart) this.klineChart.resize();
                if (this.minuteChart) this.minuteChart.resize();
                if (this.profitChart) this.profitChart.resize();
                if (this.flowChart) this.flowChart.resize();
            }, 100);
        });
    },

    // 更新实时数据
    async updateRealTimeData() {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/stock/realtime_quote_by_code?code=${this.stockCode}`);
            const data = await resp.json();
            if (data.success) {
                const d = data.data;
                this.currentPrice = d.current_price;
                this.priceChange = d.change_amount;
                this.priceChangePercent = d.change_percent;
                this.open = d.open;
                this.yesterday_close = d.yesterday_close;
                this.high = d.high;
                this.low = d.low;
                this.average_price = d.average_price;
                this.volume = d.volume;
                this.turnover = d.turnover;
                this.turnover_rate = d.turnover_rate;
                this.pe_dynamic = d.pe_dynamic;
        this.updateStockInfo();
                this.updateStockDetails();
            }
        } catch (e) {
            // 静默失败
        }
    },

    // 加载分时数据
    async loadMinuteData() {
        if (!this.minuteChart) return;
        try {
            const url = `${API_BASE_URL}/api/stock/minute_data_by_code?code=${this.stockCode}`;
            const resp = await fetch(url);
            const data = await resp.json();
            console.log('[loadMinuteData] 返回数据:', data);
            if (data.success) {
                const list = data.data;
                const times = list.map(item => item.time);
                // 组装对象数据，便于tooltip显示更多信息
                const seriesData = list.map(item => ({
                    value: [item.time, Number(item.price)],
                    volume: item.volume,
                    amount: item.amount,
                    trade_type: item.trade_type
                }));
                const option = this.minuteChart.getOption();
                option.xAxis[0].data = times;
                option.series[0].data = seriesData;
                this.minuteChart.setOption(option);
            } else {
                CommonUtils.showToast('分时数据获取失败: ' + data.message, 'error');
            }
        } catch (e) {
            CommonUtils.showToast('分时数据请求异常', 'error');
        }
    },

    // 修改loadKlineData，支持period参数
    async loadKlineData() {
        if (!this.klineChart) return;
        try {
            const today = new Date();
            let endDate = today.toISOString().split('T')[0];
            let startDate = (new Date(today.getFullYear() - 5, today.getMonth(), today.getDate())).toISOString().split('T')[0];
            let period = 'daily';
            let url = '';
            if (this.currentPeriod === '1w') {
                period = 'weekly';
                url = `${API_BASE_URL}/api/stock/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=qfq`;
            } else if (this.currentPeriod === '1M') {
                period = 'monthly';
                url = `${API_BASE_URL}/api/stock/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=qfq`;
            } else if (this.currentPeriod === '1h') {
                // 小时线，2年区间，精确到秒
                const end = today;
                const start = new Date(today.getFullYear() - 2, today.getMonth(), today.getDate(), today.getHours(), today.getMinutes(), today.getSeconds());
                const pad = n => n.toString().padStart(2, '0');
                const format = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
                const startStr = format(start);
                const endStr = format(end);
                url = `${API_BASE_URL}/api/stock/kline_min_hist?code=${this.stockCode}&period=60&start_datetime=${startStr}&end_datetime=${endStr}&adjust=qfq`;
            } else if (this.currentPeriod === '30m') {
                // 30分钟线，2年区间，精确到秒
                const end = today;
                const start = new Date(today.getFullYear() - 2, today.getMonth(), today.getDate(), today.getHours(), today.getMinutes(), today.getSeconds());
                const pad = n => n.toString().padStart(2, '0');
                const format = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
                const startStr = format(start);
                const endStr = format(end);
                url = `${API_BASE_URL}/api/stock/kline_min_hist?code=${this.stockCode}&period=30&start_datetime=${startStr}&end_datetime=${endStr}&adjust=qfq`;
            } else if (this.currentPeriod === '15m') {
                // 15分钟线，2年区间，精确到秒
                const end = today;
                const start = new Date(today.getFullYear() - 2, today.getMonth(), today.getDate(), today.getHours(), today.getMinutes(), today.getSeconds());
                const pad = n => n.toString().padStart(2, '0');
                const format = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
                const startStr = format(start);
                const endStr = format(end);
                url = `${API_BASE_URL}/api/stock/kline_min_hist?code=${this.stockCode}&period=15&start_datetime=${startStr}&end_datetime=${endStr}&adjust=qfq`;
            } else if (this.currentPeriod === '5m') {
                // 5分钟线，2年区间，精确到秒
                const end = today;
                const start = new Date(today.getFullYear() - 2, today.getMonth(), today.getDate(), today.getHours(), today.getMinutes(), today.getSeconds());
                const pad = n => n.toString().padStart(2, '0');
                const format = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
                const startStr = format(start);
                const endStr = format(end);
                url = `${API_BASE_URL}/api/stock/kline_min_hist?code=${this.stockCode}&period=5&start_datetime=${startStr}&end_datetime=${endStr}&adjust=qfq`;
            } else if (this.currentPeriod === '1m') {
                // 1分钟线，2年区间，精确到秒
                const end = today;
                const start = new Date(today.getFullYear() - 2, today.getMonth(), today.getDate(), today.getHours(), today.getMinutes(), today.getSeconds());
                const pad = n => n.toString().padStart(2, '0');
                const format = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
                const startStr = format(start);
                const endStr = format(end);
                url = `${API_BASE_URL}/api/stock/kline_min_hist?code=${this.stockCode}&period=1&start_datetime=${startStr}&end_datetime=${endStr}&adjust=qfq`;
            } else {
                // 默认日线
                url = `${API_BASE_URL}/api/stock/kline_hist?code=${this.stockCode}&period=daily&start_date=${startDate}&end_date=${endDate}&adjust=qfq`;
            }
            const resp = await fetch(url);
            const data = await resp.json();
            if (data.success) {
                const list = data.data;
                // x轴日期
                const dates = list.map(item => item.date ? item.date : '-');
                // K线数据 [开,收,低,高]
                const kline = list.map(item => [item.open, item.close, item.low, item.high]);
                // MA5/MA10
                function calcMA(arr, n) {
                    const result = [];
                    for (let i = 0; i < arr.length; i++) {
                        if (i < n - 1) { result.push('-'); continue; }
                        let sum = 0;
                        for (let j = 0; j < n; j++) sum += Number(arr[i - j][1]);
                        result.push((sum / n).toFixed(2));
                    }
                    return result;
                }
                const ma5 = calcMA(kline, 5);
                const ma10 = calcMA(kline, 10);
                // 成交量
                const volume = list.map(item => item.volume);
                // 更新option
                const option = this.klineChart.getOption();
                option.xAxis[0].data = dates;
                option.xAxis[1].data = dates;
                option.series[0].data = kline;
                option.series[1].data = ma5;
                option.series[2].data = ma10;
                option.series[3].data = volume;
                this.klineChart.setOption(option);
            } else {
                CommonUtils.showToast('K线数据获取失败: ' + data.message, 'error');
            }
        } catch (e) {
            CommonUtils.showToast('K线数据请求异常', 'error');
        }
    }
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    StockPage.init();
}); 