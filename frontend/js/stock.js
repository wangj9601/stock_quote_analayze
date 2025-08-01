// 可选：格式化为"+2.34亿"或"-1.11亿"
const formatInflow = (val) => {
    if (val === null || val === undefined || val === '' || isNaN(val)) return '--';
    let num = Number(val);
    return (num / 1e8).toFixed(2);
};

function parseProfitToYi(val) {
    if (typeof val !== 'string') return 0;
    if (val.endsWith('亿')) {
        return parseFloat(val.replace('亿', ''));
    } else if (val.endsWith('万')) {
        return parseFloat(val.replace('万', '')) / 10000;
    } else {
        return parseFloat(val) || 0;
    }
};

function parsePercent(val) {
    if (typeof val !== 'string') return 0;
    if (val.endsWith('%')) {
        return parseFloat(val.replace('%', ''));
    }
    return parseFloat(val) || 0;
}

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
    pre_close: null,
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
    analysisDataLoaded: false, // 添加标志跟踪智能分析数据是否已加载
    //API_BASE_URL: 'http://192.168.31.237:5000',

    // 初始化
    async init() {
        // 先加载header组件
        await this.loadHeader();
        
        this.bindEvents();
        this.initCharts();
        this.loadStockData();
        this.startDataUpdate();
    },

    // 加载header组件
    async loadHeader() {
        try {
            console.log('[loadHeader] 开始加载header组件');
            
            // 检查是否已经加载了header.js
            if (typeof loadHeader === 'function') {
                await loadHeader('stock');
                console.log('[loadHeader] header组件加载完成');
            } else {
                console.warn('[loadHeader] loadHeader函数未找到，尝试动态加载');
                
                // 动态加载header.js
                const script = document.createElement('script');
                script.src = 'components/header.js';
                script.onload = async () => {
                    if (typeof loadHeader === 'function') {
                        await loadHeader('stock');
                        console.log('[loadHeader] header组件动态加载完成');
                    }
                };
                document.head.appendChild(script);
            }
        } catch (error) {
            console.error('[loadHeader] header组件加载失败:', error);
        }
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
        // 延迟绑定，确保header组件已加载
        setTimeout(() => {
            const searchBtn = document.querySelector('.search-btn');
            const searchModal = document.getElementById('searchModal');
            const closeSearch = document.querySelector('.close-search');
            const searchInput = document.querySelector('.search-input');

            if (searchBtn) {
                searchBtn.addEventListener('click', () => {
                    searchModal.style.display = 'flex';
                    searchInput.focus();
                });
            }

            if (closeSearch) {
                closeSearch.addEventListener('click', () => {
                    searchModal.style.display = 'none';
                    searchInput.value = '';
                });
            }

            if (searchModal) {
                searchModal.addEventListener('click', (e) => {
                    if (e.target === searchModal) {
                        searchModal.style.display = 'none';
                        searchInput.value = '';
                    }
                });
            }
        }, 500); // 延迟500ms确保header组件加载完成
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
        console.log('[initCharts] 开始初始化图表');
        this.initKlineChart();
        this.initMinuteChart();
        this.initProfitChart();
        this.initFlowChart();
        console.log('[initCharts] 图表初始化完成');
    },

    // 初始化K线图
    initKlineChart() {
        console.log('[initKlineChart] 开始初始化K线图表');
        const chartDom = document.getElementById('klineChart');
        if (!chartDom) {
            console.error('[initKlineChart] 未找到klineChart元素');
            return;
        }
        console.log('[initKlineChart] 找到klineChart元素，开始初始化ECharts');
        this.klineChart = echarts.init(chartDom);
        const option = {
            backgroundColor: 'transparent',
            grid: [
                { left: '10%', right: '8%', height: '65%' },
                { left: '10%', right: '8%', top: '75%', height: '15%' }
            ],
            xAxis: [
                { type: 'category', data: [], boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false } },
                { type: 'category', gridIndex: 1, data: [], boundaryGap: false, axisLine: { onZero: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false } }
            ],
            yAxis: [
                { scale: true, splitArea: { show: true } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } }
            ],
            dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }],
            series: [
                { 
                    name: 'K线', 
                    type: 'candlestick', 
                    data: [], 
                    itemStyle: { 
                        color: '#dc2626', 
                        color0: '#16a34a', 
                        borderColor: '#dc2626', 
                        borderColor0: '#16a34a',
                        borderWidth: 1
                    },
                    emphasis: {
                        itemStyle: {
                            borderWidth: 2
                        }
                    }
                },
                { name: 'MA5', type: 'line', data: [], smooth: true, lineStyle: { width: 1, color: '#fbbf24' }, showSymbol: false },
                { name: 'MA10', type: 'line', data: [], smooth: true, lineStyle: { width: 1, color: '#3b82f6' }, showSymbol: false },
                { 
                    name: '成交量', 
                    type: 'bar', 
                    xAxisIndex: 1, 
                    yAxisIndex: 1, 
                    data: [], 
                    itemStyle: { 
                        color: function(params) { 
                            return params.dataIndex % 2 === 0 ? '#dc2626' : '#16a34a'; 
                        } 
                    } 
                }
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
                top: '15%',
                bottom: '18%'
            },
            xAxis: {
                type: 'category',
                data: []
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
                data: [],
                itemStyle: {
                    color: '#2563eb'
                }
            }, {
                name: 'ROE',
                type: 'line',
                yAxisIndex: 1,
                data: [],
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
                this.pre_close = d.pre_close;
                this.high = d.high;
                this.low = d.low;
                this.average_price = d.average_price;
                this.volume = d.volume;
                this.turnover = d.turnover;
                this.turnover_rate = d.turnover_rate;
                this.pe_dynamic = d.pe_dynamic;
                
                this.updateStockInfo();
                this.updateStockDetails();
                
                // 同步更新关键价位的当前价格
                this.updateKeyLevelsCurrentPrice();
                
                // 加载图表数据，完成后自动加载智能分析数据
                await this.loadChartDataWithCallback();
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
            '昨收': this.pre_close,
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
        console.log('[loadChartData] 开始加载图表数据');
        console.log('[loadChartData] 当前图表类型:', this.currentChartType);
        console.log('[loadChartData] K线图表状态:', !!this.klineChart);
        console.log('[loadChartData] 分时图表状态:', !!this.minuteChart);
        
        if (this.currentChartType === 'kline' && this.klineChart) {
            console.log('[loadChartData] 加载K线数据');
            this.loadKlineData();
        } else if (this.currentChartType === 'minute' && this.minuteChart) {
            console.log('[loadChartData] 加载分时数据');
            this.loadMinuteData();
        } else {
            console.error('[loadChartData] 图表未初始化或类型不匹配');
        }
    },

    // 加载标签数据
    loadTabData(tabId) {
        switch (tabId) {
            case 'analysis':
                // 如果智能分析数据已经加载过，不再重复加载
                if (!this.analysisDataLoaded) {
                    this.loadAnalysisData();
                } else {
                    console.log('[loadTabData] 智能分析数据已加载，跳过重复加载');
                }
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
    async loadAnalysisData() {
        try {
            console.log('[智能分析] 开始加载分析数据...');
            
            // 显示加载状态
            this.showAnalysisLoading();
            
            // 调用智能分析API
            const response = await fetch(`${API_BASE_URL}/api/analysis/stock/${this.stockCode}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.message || '获取分析数据失败');
            }
            
            console.log('[智能分析] 数据获取成功:', result.data);
            
            const data = result.data;
            
            // 更新价格预测
            this.updatePricePrediction(data.price_prediction);
            
            // 更新交易建议
            this.updateTradingRecommendation(data.trading_recommendation);
            
            // 更新技术指标
            this.updateTechnicalIndicators(data.technical_indicators);
            
            // 更新关键价位
            this.updateKeyLevels(data.key_levels);
            
            // 隐藏加载状态
            this.hideAnalysisLoading();
            
            // 设置数据已加载标志
            this.analysisDataLoaded = true;
            
        } catch (error) {
            console.error('[智能分析] 加载分析数据失败:', error);
            // 如果API调用失败，使用模拟数据
            this.loadMockAnalysisData();
            this.hideAnalysisLoading();
            
            // 显示错误提示
            this.showAnalysisError(error.message);
            
            // 即使失败也设置标志，避免重复尝试
            this.analysisDataLoaded = true;
        }
    },

    // 显示分析加载状态
    showAnalysisLoading() {
        const analysisPanel = document.getElementById('analysis');
        if (analysisPanel) {
            const loadingDiv = document.createElement('div');
            loadingDiv.id = 'analysis-loading';
            loadingDiv.className = 'analysis-loading';
            loadingDiv.innerHTML = `
                <div class="loading-spinner"></div>
                <div class="loading-text">正在分析数据...</div>
            `;
            analysisPanel.appendChild(loadingDiv);
        }
    },

    // 隐藏分析加载状态
    hideAnalysisLoading() {
        const loadingDiv = document.getElementById('analysis-loading');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    },

    // 显示分析错误
    showAnalysisError(message) {
        const analysisPanel = document.getElementById('analysis');
        if (analysisPanel) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'analysis-error';
            errorDiv.innerHTML = `
                <div class="error-icon">⚠️</div>
                <div class="error-text">分析数据加载失败: ${message}</div>
                <button onclick="this.parentElement.remove()" class="error-close">×</button>
            `;
            analysisPanel.appendChild(errorDiv);
        }
    },

    // 更新价格预测
    updatePricePrediction(prediction) {
        console.log('[价格预测] 更新数据:', prediction);
        
        const targetPriceElement = document.querySelector('.target-price');
        const changeElement = document.querySelector('.prediction-change');
        const rangeElement = document.querySelector('.prediction-range span');
        const confidenceElement = document.querySelector('.confidence span:first-child');
        const periodElement = document.querySelector('.confidence span:last-child');
        
        if (targetPriceElement && prediction.target_price !== undefined) {
            targetPriceElement.textContent = prediction.target_price.toFixed(2);
        }
        
        if (changeElement && prediction.change_percent !== undefined) {
            const change = prediction.change_percent;
            changeElement.textContent = `${change > 0 ? '+' : ''}${change.toFixed(2)}%`;
            changeElement.className = `prediction-change ${change > 0 ? 'positive' : 'negative'}`;
        }
        
        if (rangeElement && prediction.prediction_range) {
            const range = prediction.prediction_range;
            rangeElement.textContent = `预测区间：${range.min} - ${range.max}`;
        }
        
        if (confidenceElement && prediction.confidence !== undefined) {
            confidenceElement.textContent = `置信度：${prediction.confidence}%`;
        }
        
        if (periodElement) {
            periodElement.textContent = `预测周期：30天`;
        }
    },

    // 更新交易建议
    updateTradingRecommendation(recommendation) {
        console.log('[交易建议] 更新数据:', recommendation);
        
        const actionBadge = document.querySelector('.action-badge');
        const reasonsContainer = document.querySelector('.recommendation-reasons');
        const riskBadge = document.querySelector('.risk-badge');
        
        if (actionBadge && recommendation.action) {
            actionBadge.textContent = this.getActionText(recommendation.action);
            actionBadge.className = `action-badge ${recommendation.action}`;
        }
        
        if (reasonsContainer && recommendation.reasons) {
            reasonsContainer.innerHTML = '';
            recommendation.reasons.forEach(reason => {
                const reasonItem = document.createElement('div');
                reasonItem.className = 'reason-item positive';
                reasonItem.innerHTML = `<span class="checkmark">✓</span> ${reason}`;
                reasonsContainer.appendChild(reasonItem);
            });
            
            // 添加风险提示
            if (recommendation.risk_level === 'high') {
                const warningItem = document.createElement('div');
                warningItem.className = 'reason-item warning';
                warningItem.innerHTML = `<span class="warning-icon">⚠</span> 注意大盘风险`;
                reasonsContainer.appendChild(warningItem);
            }
        }
        
        if (riskBadge && recommendation.risk_level) {
            riskBadge.textContent = this.getRiskText(recommendation.risk_level);
            riskBadge.className = `risk-badge ${recommendation.risk_level}`;
        }
    },

    // 更新技术指标
    updateTechnicalIndicators(indicators) {
        console.log('[技术指标] 更新数据:', indicators);
        
        if (!indicators) {
            console.warn('[技术指标] 指标数据为空');
            return;
        }
        
        // 更新RSI
        if (indicators.rsi) {
            this.updateIndicator('RSI(14)', indicators.rsi.value, indicators.rsi.signal);
        }
        
        // 更新MACD
        if (indicators.macd) {
            this.updateIndicator('MACD', indicators.macd.value, indicators.macd.signal);
        }
        
        // 更新KDJ
        if (indicators.kdj) {
            this.updateIndicator('KDJ', indicators.kdj.value, indicators.kdj.signal);
        }
        
        // 更新布林带
        if (indicators.bollinger_bands) {
            const bbSignal = indicators.bollinger_bands.signal;
            this.updateIndicator('布林带', '上轨', bbSignal);
        }
    },

    // 更新单个指标
    updateIndicator(name, value, signal) {
        const indicatorRows = document.querySelectorAll('.indicator-row');
        indicatorRows.forEach(row => {
            const nameElement = row.querySelector('.indicator-name');
            if (nameElement && nameElement.textContent.includes(name)) {
                const valueElement = row.querySelector('.indicator-value');
                const signalElement = row.querySelector('.indicator-signal');
                
                if (valueElement) {
                    valueElement.textContent = value;
                }
                
                if (signalElement) {
                    signalElement.textContent = signal;
                    signalElement.className = `indicator-signal ${this.getSignalClass(signal)}`;
                }
            }
        });
    },

    // 更新关键价位
    updateKeyLevels(levels) {
        console.log('[关键价位] 更新数据:', levels);
        
        if (!levels) {
            console.warn('[关键价位] 价位数据为空');
            return;
        }
        
        // 更新阻力位
        if (levels.resistance_levels && levels.resistance_levels.length > 0) {
            const resistanceElements = document.querySelectorAll('.level-item:not(.current) .level-value.resistance');
            levels.resistance_levels.forEach((level, index) => {
                if (resistanceElements[index]) {
                    resistanceElements[index].textContent = level.toFixed(2);
                }
            });
        }
        
        // 更新支撑位
        if (levels.support_levels && levels.support_levels.length > 0) {
            const supportElements = document.querySelectorAll('.level-item:not(.current) .level-value.support');
            levels.support_levels.forEach((level, index) => {
                if (supportElements[index]) {
                    supportElements[index].textContent = level.toFixed(2);
                }
            });
        }
        
        // 更新当前价格 - 使用最新的实时价格而不是智能分析API返回的价格
        this.updateKeyLevelsCurrentPrice();
    },

    // 更新关键价位的当前价格
    updateKeyLevelsCurrentPrice() {
        const currentPriceElement = document.querySelector('.level-item.current .level-value');
        if (currentPriceElement && this.currentPrice !== null) {
            currentPriceElement.textContent = Number(this.currentPrice).toFixed(2);
        }
    },

    // 获取操作文本
    getActionText(action) {
        const actionMap = {
            'buy': '建议买入',
            'sell': '建议卖出',
            'hold': '建议持有'
        };
        return actionMap[action] || '建议持有';
    },

    // 获取风险等级文本
    getRiskText(riskLevel) {
        const riskMap = {
            'low': '低',
            'medium': '中等',
            'high': '高'
        };
        return riskMap[riskLevel] || '中等';
    },

    // 获取信号样式类
    getSignalClass(signal) {
        if (signal.includes('看多') || signal.includes('超卖')) {
            return 'bullish';
        } else if (signal.includes('看空') || signal.includes('超买')) {
            return 'bearish';
        } else {
            return 'neutral';
        }
    },

    // 加载模拟分析数据（备用）
    loadMockAnalysisData() {
        console.log('[loadMockAnalysisData] 加载模拟分析数据');
        
        // 更新价格预测
        const targetPrice = (this.currentPrice * (1 + (Math.random() * 0.2 - 0.1))).toFixed(2);
        const change = ((targetPrice - this.currentPrice) / this.currentPrice * 100).toFixed(2);
        
        document.querySelector('.target-price').textContent = targetPrice;
        const changeElement = document.querySelector('.prediction-change');
        changeElement.textContent = `${change > 0 ? '+' : ''}${change}%`;
        changeElement.className = `prediction-change ${change > 0 ? 'positive' : 'negative'}`;
        
        // 更新关键价位 - 确保支撑位严格小于当前价格，阻力位严格大于当前价格
        const currentPrice = this.currentPrice || 6.80;
        
        // 生成合理的支撑位（严格小于当前价格）
        const supportLevels = [
            (currentPrice * 0.95).toFixed(2),  // 支撑位1：当前价格的95%
            (currentPrice * 0.90).toFixed(2),  // 支撑位2：当前价格的90%
            (currentPrice * 0.85).toFixed(2)   // 支撑位3：当前价格的85%
        ];
        
        // 生成合理的阻力位（严格大于当前价格）
        const resistanceLevels = [
            (currentPrice * 1.05).toFixed(2),  // 阻力位1：当前价格的105%
            (currentPrice * 1.10).toFixed(2),  // 阻力位2：当前价格的110%
            (currentPrice * 1.15).toFixed(2)   // 阻力位3：当前价格的115%
        ];
        
        // 更新阻力位显示
        const resistanceElements = document.querySelectorAll('.level-item:not(.current) .level-value.resistance');
        resistanceLevels.forEach((level, index) => {
            if (resistanceElements[index]) {
                resistanceElements[index].textContent = level;
            }
        });
        
        // 更新支撑位显示
        const supportElements = document.querySelectorAll('.level-item:not(.current) .level-value.support');
        supportLevels.forEach((level, index) => {
            if (supportElements[index]) {
                supportElements[index].textContent = level;
            }
        });
        
        // 更新当前价格
        this.updateKeyLevelsCurrentPrice();
        
        // 设置数据已加载标志
        this.analysisDataLoaded = true;
    },

    // 加载新闻数据
    async loadNewsData() {
        try {
            console.log('[loadNewsData] 开始加载新闻数据:', this.stockCode);
            const url = `${API_BASE_URL}/api/stock/news_combined?symbol=${this.stockCode}&news_limit=50&announcement_limit=20&research_limit=10`;
            const resp = await fetch(url);
            const data = await resp.json();
            
            if (data.success && data.data) {
                console.log('[loadNewsData] 获取到新闻数据:', data.data.length, '条');
                this.renderNewsData(data.data);
            } else {
                console.error('[loadNewsData] 获取新闻数据失败:', data.message);
                CommonUtils.showToast('获取新闻数据失败: ' + (data.message || '未知错误'), 'error');
            }
        } catch (error) {
            console.error('[loadNewsData] 请求异常:', error);
            CommonUtils.showToast('新闻数据请求异常', 'error');
        }
    },

    // 渲染新闻数据
    renderNewsData(newsData) {
        const newsContainer = document.querySelector('.news-items');
        if (!newsContainer) return;
        
        // 清空现有内容
        newsContainer.innerHTML = '';
        
        // 如果没有数据，显示空状态
        if (!newsData || newsData.length === 0) {
            newsContainer.innerHTML = '<div class="no-data">暂无新闻数据</div>';
            return;
        }
        
        // 渲染新闻项目
        newsData.forEach(item => {
            const newsCard = document.createElement('div');
            newsCard.className = 'news-card';
            
            // 确定新闻类型显示文本和样式
            let typeText = '新闻';
            let typeClass = 'news';
            if (item.type === 'announcement') {
                typeText = '公告';
                typeClass = 'announcement';
            } else if (item.type === 'research') {
                typeText = '研报';
                typeClass = 'research';
            }
            
            // 格式化发布时间
            const publishTime = item.publish_time ? item.publish_time.split(' ')[0] : '未知时间';
            
            // 构建新闻卡片HTML
            newsCard.innerHTML = `
                <div class="news-meta">
                    <span class="news-date">${publishTime}</span>
                    <span class="news-type ${typeClass}">${typeText}</span>
                    ${item.source ? `<span class="news-source">${item.source}</span>` : ''}
                    ${item.rating ? `<span class="research-rating">${item.rating}</span>` : ''}
                </div>
                <h4 class="news-title">${item.title || '无标题'}</h4>
                <p class="news-summary">${item.summary || item.content || '无摘要'}</p>
                ${item.target_price ? `<div class="target-price">目标价: ${item.target_price}</div>` : ''}
                ${item.url ? `<a href="${item.url}" target="_blank" class="news-link">查看详情</a>` : ''}
            `;
            
            newsContainer.appendChild(newsCard);
        });
        
        console.log('[loadNewsData] 新闻数据渲染完成，共', newsData.length, '条');
    },

    // 加载研报数据
    async loadResearchData() {
        try {
            console.log('[loadResearchData] 开始加载研报数据:', this.stockCode);
            const url = `${API_BASE_URL}/api/stock/research_reports?symbol=${this.stockCode}&limit=20`;
            const resp = await fetch(url);
            const data = await resp.json();
            
            if (data.success && data.data) {
                console.log('[loadResearchData] 获取到研报数据:', data.data.length, '条');
                this.renderResearchData(data.data);
            } else {
                console.error('[loadResearchData] 获取研报数据失败:', data.message);
                CommonUtils.showToast('获取研报数据失败: ' + (data.message || '未知错误'), 'error');
            }
        } catch (error) {
            console.error('[loadResearchData] 请求异常:', error);
            CommonUtils.showToast('研报数据请求异常', 'error');
        }
    },

    // 渲染研报数据gu'pgup
    renderResearchData(researchData) {
        const researchContainer = document.querySelector('.research-list');
        if (!researchContainer) return;
        
        // 清空现有内容
        researchContainer.innerHTML = '';
        
        // 如果没有数据，显示空状态
        if (!researchData || researchData.length === 0) {
            researchContainer.innerHTML = '<div class="no-data">暂无研报数据</div>';
            return;
        }
        
        // 渲染研报项目
        researchData.forEach(item => {
            const researchItem = document.createElement('div');
            researchItem.className = 'research-item';
            
            // 确定评级样式
            let ratingClass = 'hold';
            const rating = item.rating || item.keywords || '';
            if (rating.includes('买入') || rating.includes('推荐')) {
                ratingClass = 'buy';
            } else if (rating.includes('卖出') || rating.includes('减持')) {
                ratingClass = 'sell';
            }
            
            // 格式化发布时间
            const publishTime = item.publish_time ? item.publish_time.split(' ')[0] : '未知时间';
            
            // 计算目标价涨幅（如果有当前价格）
            let targetUpside = '';
            if (item.target_price && this.currentPrice) {
                try {
                    const target = parseFloat(item.target_price);
                    const current = parseFloat(this.currentPrice);
                    const upside = ((target - current) / current * 100).toFixed(1);
                    targetUpside = `<span class="target-upside ${upside > 0 ? 'positive' : 'negative'}">${upside}%</span>`;
                } catch (e) {
                    // 忽略计算错误
                }
            }
            
            // 构建研报项目HTML
            researchItem.innerHTML = `
                <div class="research-header">
                    <h4>${item.title && item.title !== '研报标题' ? item.title : '暂无研报标题'}</h4>
                    <div class="research-meta">
                        <span class="research-firm">${item.source && item.source !== '研究机构' ? item.source : '暂无机构信息'}</span>
                        <span class="research-date">${publishTime}</span>
                        <span class="research-rating ${ratingClass}">${rating && rating !== '未评级' ? rating : '暂无评级'}</span>
                    </div>
                </div>
                ${item.target_price && item.target_price !== '' ? `
                    <div class="research-target">
                        <span>目标价：${item.target_price}元</span>
                        ${targetUpside}
                    </div>
                ` : ''}
                <p class="research-summary">${item.summary && item.summary !== '研报摘要暂无' ? item.summary : (item.content || '暂无研报摘要')}</p>
                ${item.url && item.url !== '' ? `<a href="#" class="research-link" onclick="StockPage.downloadPDF('${item.url}', '${item.title}')">下载报告</a>` : ''}
            `;
            
            researchContainer.appendChild(researchItem);
        });
        
        console.log('[loadResearchData] 研报数据渲染完成，共', researchData.length, '条');
    },

    // 下载PDF报告
    downloadPDF(url, title) {
        try {
            console.log('[downloadPDF] 开始下载PDF:', url, title);
            
            // 方案1：尝试直接在新窗口打开（最可靠的方式）
            if (this.shouldUseDirectOpen(url)) {
                this.openPDFInNewWindow(url, title);
                return;
            }
            
            // 方案2：如果是同域，尝试直接下载
            if (!this.isCrossOriginURL(url)) {
                this.directDownload(url, title);
                return;
            }
            
            // 方案3：跨域情况，尝试多种下载策略
            this.downloadPDFWithProxy(url, title);
            
        } catch (error) {
            console.error('[downloadPDF] 下载失败:', error);
            // 最终回退：直接打开链接
            this.openPDFInNewWindow(url, title);
        }
    },

    // 判断是否应该使用后端重定向页面
    shouldUseDirectOpen(url) {
        // 对于所有PDF链接，都优先使用后端重定向页面来绕过防盗链
        return true;
    },

    // 在新窗口打开PDF
    openPDFInNewWindow(url, title) {
        console.log('[openPDFInNewWindow] 在新窗口打开PDF:', url);
        
        // 方案1：使用后端重定向页面（最强力的去referrer方法）
        try {
            const redirectUrl = `${API_BASE_URL}/api/stock/pdf_redirect?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title || 'PDF文档')}`;
            const newWindow = window.open(redirectUrl, '_blank', 'width=1000,height=800,scrollbars=yes,resizable=yes');
            
            if (newWindow) {
                CommonUtils.showToast(`正在新窗口打开: ${title}`, 'success');
                return;
            }
        } catch (error) {
            console.warn('[openPDFInNewWindow] 后端重定向失败，尝试方案2:', error);
        }
        
        // 方案2：使用about:blank中间页面去除referrer
        try {
            const newWindow = window.open('about:blank', '_blank', 'width=1000,height=800,scrollbars=yes,resizable=yes');
            if (newWindow) {
                // 在新窗口中写入重定向代码，去除referrer
                newWindow.document.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>正在加载PDF...</title>
                        <meta charset="UTF-8">
                        <style>
                            body { 
                                font-family: Arial, sans-serif; 
                                text-align: center; 
                                padding: 50px;
                                background: #f5f5f5;
                            }
                            .loading {
                                font-size: 18px;
                                color: #666;
                                margin-bottom: 20px;
                            }
                            .spinner {
                                border: 4px solid #f3f3f3;
                                border-top: 4px solid #3498db;
                                border-radius: 50%;
                                width: 40px;
                                height: 40px;
                                animation: spin 1s linear infinite;
                                margin: 20px auto;
                            }
                            @keyframes spin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                        </style>
                    </head>
                    <body>
                        <div class="loading">正在加载PDF文件...</div>
                        <div class="spinner"></div>
                        <p>如果页面没有自动跳转，请点击下面的链接：</p>
                        <a href="${url}" target="_blank" rel="noreferrer noopener">点击这里打开PDF</a>
                        <script>
                            // 延迟跳转，去除referrer
                            setTimeout(function() {
                                window.location.replace('${url}');
                            }, 1000);
                        </script>
                    </body>
                    </html>
                `);
                newWindow.document.close();
                
                CommonUtils.showToast(`正在新窗口打开: ${title}`, 'success');
                return;
            }
                    } catch (error) {
            console.warn('[openPDFInNewWindow] 方案2失败，尝试方案3:', error);
        }
        
        // 方案3：使用data URI去除referrer
        try {
            const redirectHtml = `
                <!DOCTYPE html>
                <html>
                <head>
                    <title>PDF跳转页面</title>
                    <meta charset="UTF-8">
                    <style>
                        body { 
                            font-family: Arial, sans-serif; 
                            text-align: center; 
                            padding: 50px;
                            background: #f5f5f5;
                        }
                        .info {
                            font-size: 16px;
                            color: #333;
                            margin-bottom: 20px;
                        }
                        .link {
                            display: inline-block;
                            padding: 10px 20px;
                            background: #007cba;
                            color: white;
                            text-decoration: none;
                            border-radius: 5px;
                            margin: 10px;
                        }
                        .link:hover {
                            background: #005a8b;
                        }
                    </style>
                </head>
                <body>
                    <div class="info">
                        <h3>PDF文件访问</h3>
                        <p>请点击下面的链接访问PDF文件：</p>
                        <p><strong>${title}</strong></p>
                    </div>
                    <a href="${url}" class="link" target="_blank" rel="noreferrer noopener">打开PDF文件</a>
                    <br><br>
                    <div style="font-size: 12px; color: #666;">
                        <p>如果遇到访问限制，请复制以下链接到新的浏览器窗口：</p>
                        <input type="text" value="${url}" style="width: 80%; padding: 5px; border: 1px solid #ccc;" readonly onclick="this.select();">
                    </div>
                </body>
                </html>
            `;
            
            const dataUri = 'data:text/html;charset=utf-8,' + encodeURIComponent(redirectHtml);
            const newWindow = window.open(dataUri, '_blank', 'width=1000,height=800,scrollbars=yes,resizable=yes');
            
            if (newWindow) {
                CommonUtils.showToast(`正在新窗口打开: ${title}`, 'success');
                return;
            }
        } catch (error) {
            console.warn('[openPDFInNewWindow] 方案3失败，尝试方案4:', error);
        }
        
        // 方案4：创建临时链接元素（传统方式）
        try {
            const link = document.createElement('a');
            link.href = url;
            link.target = '_blank';
            link.rel = 'noreferrer noopener';  // 关键：去除referrer
            link.style.display = 'none';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            CommonUtils.showToast(`正在新窗口打开: ${title}`, 'success');
            return;
        } catch (error) {
            console.warn('[openPDFInNewWindow] 方案4失败，使用最后备选方案:', error);
        }
        
        // 方案5：最后备选 - 复制链接到剪贴板
        CommonUtils.showToast('无法直接打开PDF，正在复制链接到剪贴板', 'warning');
        this.copyToClipboard(url, title);
        
        // 显示操作提示
        setTimeout(() => {
            CommonUtils.showToast('请在新的浏览器窗口中粘贴链接访问PDF', 'info');
        }, 1000);
    },

    // 直接下载（同域情况）
    directDownload(url, title) {
        console.log('[directDownload] 直接下载PDF:', url);
        
        const link = document.createElement('a');
        link.style.display = 'none';
        link.href = url;
        link.download = `${title || '研报'}.pdf`;
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        CommonUtils.showToast(`开始下载: ${title}`, 'success');
    },

    // 复制链接到剪贴板
    copyToClipboard(url, title) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(() => {
                CommonUtils.showToast(`链接已复制到剪贴板，请手动打开: ${title}`, 'info');
            }).catch(() => {
                this.fallbackCopyToClipboard(url, title);
            });
        } else {
            this.fallbackCopyToClipboard(url, title);
        }
    },

    // 回退的复制方法
    fallbackCopyToClipboard(url, title) {
        const textArea = document.createElement('textarea');
        textArea.value = url;
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            CommonUtils.showToast(`链接已复制: ${title}`, 'info');
        } catch (err) {
            CommonUtils.showToast(`无法复制链接，请手动访问: ${url}`, 'warning');
        }
        
        document.body.removeChild(textArea);
    },

    // 检查是否是跨域URL
    isCrossOriginURL(url) {
        try {
            const urlObj = new URL(url);
            return urlObj.origin !== window.location.origin;
        } catch (error) {
            return true; // 如果URL解析失败，当作跨域处理
        }
    },

    // 通过代理下载PDF（改进版）
    async downloadPDFWithProxy(url, title) {
        try {
            console.log('[downloadPDFWithProxy] 尝试通过后端代理下载PDF:', url);
            
            // 显示下载提示
            CommonUtils.showToast('正在尝试下载...', 'info');
            
            // 方案1：使用后端代理下载
            try {
                const proxyUrl = `${API_BASE_URL}/api/stock/download_pdf?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(title || '研报')}.pdf`;
                console.log('[downloadPDFWithProxy] 尝试后端代理下载:', proxyUrl);
                
                const link = document.createElement('a');
                link.style.display = 'none';
                link.href = proxyUrl;
                link.download = `${title || '研报'}.pdf`;
                
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                CommonUtils.showToast(`正在通过服务器下载: ${title}`, 'success');
                return; // 成功后直接返回
                
            } catch (proxyError) {
                console.warn('[downloadPDFWithProxy] 后端代理下载失败，尝试直接下载:', proxyError);
                // 继续执行下面的直接下载逻辑
            }
            
            // 方案2：直接fetch下载（作为后备方案）
            console.log('[downloadPDFWithProxy] 尝试直接fetch下载PDF:', url);
            
            // 设置更宽松的请求头
            const response = await fetch(url, {
                method: 'GET',
                mode: 'cors',
                cache: 'no-cache',
                redirect: 'follow',
                referrerPolicy: 'no-referrer', // 不发送referrer
                headers: {
                    'Accept': 'application/pdf,application/octet-stream,*/*',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 检查响应类型
            const contentType = response.headers.get('content-type');
            if (contentType && !contentType.includes('pdf') && !contentType.includes('octet-stream')) {
                console.warn('[downloadPDFWithProxy] 响应不是PDF类型:', contentType);
                // 如果不是PDF，可能是HTML错误页面，直接打开
                throw new Error('响应不是PDF文件');
            }
            
            // 获取文件内容
            const blob = await response.blob();
            
            // 检查blob大小
            if (blob.size < 1024) {
                console.warn('[downloadPDFWithProxy] 文件太小，可能不是有效PDF:', blob.size);
                throw new Error('文件大小异常');
            }
            
            // 创建下载链接
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.style.display = 'none';
            link.href = downloadUrl;
            link.download = `${title || '研报'}.pdf`;
            
            // 执行下载
            document.body.appendChild(link);
            link.click();
            
            // 清理
            document.body.removeChild(link);
            
            // 延迟清理blob URL
            setTimeout(() => {
                window.URL.revokeObjectURL(downloadUrl);
            }, 1000);
            
            CommonUtils.showToast(`下载完成: ${title}`, 'success');
            
        } catch (error) {
            console.error('[downloadPDFWithProxy] 所有下载方案都失败:', error);
            
            // 最终回退策略：直接在新窗口打开
            CommonUtils.showToast('下载失败，已在新窗口打开PDF', 'warning');
            this.openPDFInNewWindow(url, title);
        }
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

    // 过滤新闻
    filterNews(filter) {
        const newsCards = document.querySelectorAll('.news-card');
        
        newsCards.forEach(card => {
            const typeElement = card.querySelector('.news-type');
            if (!typeElement) return;
            
            const type = typeElement.textContent.toLowerCase();
            const typeClass = typeElement.className;
            
            if (filter === 'all' || 
                (filter === 'announcement' && (type.includes('公告') || typeClass.includes('announcement'))) ||
                (filter === 'news' && (type.includes('新闻') || typeClass.includes('news'))) ||
                (filter === 'research' && (type.includes('研报') || typeClass.includes('research')))) {
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
                this.pre_close = d.pre_close; 
                this.high = d.high;
                this.low = d.low;
                this.average_price = d.average_price;
                this.volume = d.volume;
                this.turnover = d.turnover;
                this.turnover_rate = d.turnover_rate;
                this.pe_dynamic = d.pe_dynamic;
                
                this.updateStockInfo();
                this.updateStockDetails();
                
                // 同步更新关键价位的当前价格
                this.updateKeyLevelsCurrentPrice();
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
        console.log('[loadKlineData] 开始加载K线数据');
        console.log('[loadKlineData] 股票代码:', this.stockCode);
        console.log('[loadKlineData] 当前周期:', this.currentPeriod);
        
        if (!this.klineChart) {
            console.error('[loadKlineData] K线图表未初始化');
            return;
        }
        
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
            
            console.log('[loadKlineData] 请求URL:', url);
            const resp = await fetch(url);
            const data = await resp.json();
            console.log('[loadKlineData] API响应:', data);
            if (data.success) {
                const list = data.data;
                
                // 检查数据是否为空
                if (!list || list.length === 0) {
                    CommonUtils.showToast('暂无K线数据', 'info');
                    return;
                }
                
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
                // 更新option - 根据数据量调整显示效果
                const option = this.klineChart.getOption();
                option.xAxis[0].data = dates;
                option.xAxis[1].data = dates;
                option.series[0].data = kline;
                option.series[1].data = ma5;
                option.series[2].data = ma10;
                option.series[3].data = volume;
                
                // 当数据量较少时，优化显示效果
                const dataCount = kline.length;
                if (dataCount <= 50) {
                    // 数据少时，显示全部数据，不进行缩放
                    option.dataZoom[0].start = 0;
                    option.dataZoom[0].end = 100;
                    
                    // 调整K线柱子宽度，让它们更显眼
                    option.series[0].barWidth = Math.max(3, Math.min(15, 300 / dataCount));
                    // 同时调整成交量柱子宽度
                    option.series[3].barWidth = Math.max(3, Math.min(15, 300 / dataCount));
                    
                    // 优化X轴显示
                    option.xAxis[0].boundaryGap = true; // 让K线不贴边显示
                    option.xAxis[1].boundaryGap = true;
                } else if (dataCount <= 200) {
                    // 中等数据量时，调整显示范围
                    option.dataZoom[0].start = Math.max(0, 100 - (100 * 100 / dataCount));
                    option.dataZoom[0].end = 100;
                    
                    // 适中的柱子宽度
                    option.series[0].barWidth = Math.max(2, Math.min(8, 200 / dataCount));
                    option.series[3].barWidth = Math.max(2, Math.min(8, 200 / dataCount));
                    
                    option.xAxis[0].boundaryGap = true;
                    option.xAxis[1].boundaryGap = true;
                } else {
                    // 数据量充足时，保持原有的显示方式
                    option.dataZoom[0].start = 50;
                    option.dataZoom[0].end = 100;
                    
                    // 恢复默认设置
                    delete option.series[0].barWidth;
                    delete option.series[3].barWidth;
                    option.xAxis[0].boundaryGap = false;
                    option.xAxis[1].boundaryGap = false;
                }
                
                this.klineChart.setOption(option);
            } else {
                CommonUtils.showToast('K线数据获取失败: ' + data.message, 'error');
            }
        } catch (e) {
            CommonUtils.showToast('K线数据请求异常', 'error');
        }
    },

    // 加载财务数据,更新财务指标列表,更新财务指标图表
    async loadFinanceData() {
        console.log('[loadFinanceData] 加载财务数据');  
        try{
            const resp = await fetch(`${API_BASE_URL}/api/stock/latest_financial?code=${this.stockCode}`);
            const data = await resp.json();
            if (data.success && data.data) {
                const d = data.data;
                document.getElementById('pe').innerText = d.pe ?? '--';
                document.getElementById('pb').innerText = d.pb ?? '--';
                document.getElementById('roe').innerText = d.roe ? d.roe.toFixed(2) : '--';
                document.getElementById('roa').innerText = d.roa ? d.roa.toFixed(2) : '--';
                document.getElementById('revenue').innerText = d.revenue ? formatInflow(d.revenue) + '亿' : '--';
                document.getElementById('profit').innerText = d.profit ? formatInflow(d.profit) + '亿' : '--';
                document.getElementById('eps').innerText = d.eps ? d.eps.toFixed(2) : '--';
                document.getElementById('bps').innerText = d.bps ? d.bps.toFixed(2) : '--';
            } else {
                CommonUtils.showToast('财务数据获取失败: ' + data.message, 'error');    
            }
        } catch (e) {
            CommonUtils.showToast('财务数据请求异常', 'error');
        }
        //加载财务指标盈利能力图表数据列表
        this.loadFinancialIndicatorList();

    },

    // 加载财务指标盈利能力图表数据列表
    async loadFinancialIndicatorList() {
        try {
            const res = await fetch(`${API_BASE_URL}/api/stock/financial_indicator_list?symbol=${this.stockCode}&indicator=2`);
            const json = await res.json();
            if (json.success && json.data) {
                const data = json.data;
                const names = data.map(item => item['报告期']);
                const profitValues = data.map(item => parseProfitToYi(item['净利润']));
                const roeValues = data.map(item => parsePercent(item['净资产收益率']));
                this.updateProfitBarChart(names, profitValues, roeValues);
            }
        } catch (e) {
            console.error(e);
            CommonUtils.showToast('财务指标盈利能力图表数据列表请求异常', 'error');
        }
    },
    
    // 示例：更新ECharts
    updateProfitBarChart(names, profitValues, roeValues) {
        if (!this.profitChart) return;
        const option = {
            xAxis: { data: names },
            series: [
                { name: '净利润', type: 'bar', data: profitValues },
                { name: 'ROE', type: 'line', yAxisIndex: 1, data: roeValues }
            ]
        };
        this.profitChart.setOption(option);
        this.profitChart.resize();
    },

    // 加载图表数据并等待完成后触发智能分析
    async loadChartDataWithCallback() {
        console.log('[loadChartDataWithCallback] 开始加载图表数据并等待完成');
        
        try {
            // 根据当前图表类型加载数据
            if (this.currentChartType === 'kline' && this.klineChart) {
                console.log('[loadChartDataWithCallback] 等待K线数据加载完成');
                await this.loadKlineData();
            } else if (this.currentChartType === 'minute' && this.minuteChart) {
                console.log('[loadChartDataWithCallback] 等待分时数据加载完成');
                await this.loadMinuteData();
            } else {
                console.warn('[loadChartDataWithCallback] 图表未初始化，直接加载智能分析');
            }
            
            // 图表数据加载完成后，自动加载智能分析数据
            console.log('[loadChartDataWithCallback] 图表数据加载完成，开始加载智能分析数据');
            await this.loadAnalysisData();
            
        } catch (error) {
            console.error('[loadChartDataWithCallback] 图表数据加载失败:', error);
            // 即使图表加载失败，也尝试加载智能分析数据
            await this.loadAnalysisData();
        }
    }

};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    StockPage.init();
}); 