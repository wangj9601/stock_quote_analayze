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
    isInWatchlist: false, // 跟踪股票是否已在自选股中
    //API_BASE_URL: 'http://192.168.31.237:5000',

    // 初始化
    async init() {
        // 先加载header组件
        await this.loadHeader();
        
        this.bindEvents();
        this.initCharts();
        this.loadStockData();
        this.checkWatchlistStatus(); // 检查自选股状态
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

    // 检查自选股状态
    async checkWatchlistStatus() {
        try {
            // 检查用户是否已登录
            const userInfo = CommonUtils.auth.getUserInfo();
            if (!userInfo || !userInfo.id) {
                console.log('用户未登录，跳过自选股状态检查');
                return;
            }

            // 调用后端API获取用户自选股列表
            const res = await authFetch(`${API_BASE_URL}/api/watchlist`);
            const result = await res.json();
            
            if (result.success && result.data) {
                // 检查当前股票是否在自选股列表中
                this.isInWatchlist = result.data.some(item => item.code === this.stockCode);
                console.log(`股票 ${this.stockCode} 自选股状态:`, this.isInWatchlist);
            } else {
                this.isInWatchlist = false;
            }
        } catch (error) {
            console.error('检查自选股状态失败:', error);
            this.isInWatchlist = false;
        }
        
        // 更新按钮显示
        this.updateWatchlistButton();
    },

    // 更新自选股按钮状态
    updateWatchlistButton() {
        const toggleBtn = document.querySelector('.watchlist-toggle');
        if (!toggleBtn) return;
        
        if (this.isInWatchlist) {
            toggleBtn.classList.add('active');
            toggleBtn.textContent = '⭐ 已自选';
        } else {
            toggleBtn.classList.remove('active');
            toggleBtn.textContent = '⭐ 自选';
        }
    },

    // 切换自选股状态
    async toggleWatchlist() {
        // 检查用户登录状态
        const userInfo = CommonUtils.auth.getUserInfo();
        if (!userInfo || !userInfo.id) {
            CommonUtils.showToast('请先登录后再操作自选股', 'warning');
            // 跳转到登录页面
            window.location.href = 'login.html';
            return;
        }

        if (this.isInWatchlist) {
            // 从自选股中删除
            await this.removeFromWatchlist();
        } else {
            // 添加到自选股
            await this.addToWatchlist();
        }
    },

    // 添加到自选股
    async addToWatchlist() {
        try {
            // 检查登录状态并处理失效
            if (!CommonUtils.checkLoginAndHandleExpiry()) {
                return;
            }
            
            const userInfo = CommonUtils.auth.getUserInfo();
            
            const res = await authFetch(`${API_BASE_URL}/api/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userInfo.id,
                    stock_code: this.stockCode,
                    stock_name: this.stockName,
                    group_name: 'default'
                })
            });
            
            const result = await res.json();
            if (result.success) {
                this.isInWatchlist = true;
                this.updateWatchlistButton();
                CommonUtils.showToast(`已添加 ${this.stockName} 到自选股`, 'success');
            } else {
                CommonUtils.showToast(result.message || '添加失败', 'error');
            }
        } catch (error) {
            console.error('添加到自选股失败:', error);
            CommonUtils.showToast('网络错误，添加失败', 'error');
        }
    },

    // 从自选股删除
    async removeFromWatchlist() {
        try {
            const userInfo = CommonUtils.auth.getUserInfo();
            const res = await authFetch(`${API_BASE_URL}/api/watchlist/delete_by_code`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userInfo.id,
                    stock_code: this.stockCode
                })
            });
            
            const result = await res.json();
            if (result.success) {
                this.isInWatchlist = false;
                this.updateWatchlistButton();
                CommonUtils.showToast(`已从自选股中移除 ${this.stockName}`, 'info');
            } else {
                CommonUtils.showToast(result.message || '删除失败', 'error');
            }
        } catch (error) {
            console.error('从自选股删除失败:', error);
            CommonUtils.showToast('网络错误，删除失败', 'error');
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
            '1d': '日线',
            '1w': '周线',
            '1M': '月线',
            '1Q': '季线',
            '6M': '半年线',
            '1Y': '年线'
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
                { left: '8%', right: '6%', top: '5%', height: '55%' },  // K线图区域
                { left: '8%', right: '6%', top: '63%', height: '12%' },  // 成交量区域
                { left: '8%', right: '6%', top: '78%', height: '18%' }  // MACD区域
            ],
            xAxis: [
                { 
                    type: 'category', 
                    data: [], 
                    boundaryGap: [0.1, 0.1], 
                    axisLine: { onZero: false }, 
                    splitLine: { show: false },
                    axisLabel: {
                        interval: 'auto',
                        rotate: 0
                    }
                },
                { 
                    type: 'category', 
                    gridIndex: 1, 
                    data: [], 
                    boundaryGap: [0.1, 0.1], 
                    axisLine: { onZero: false }, 
                    axisTick: { show: false }, 
                    splitLine: { show: false }, 
                    axisLabel: { show: false } 
                },
                { 
                    type: 'category', 
                    gridIndex: 2, 
                    data: [], 
                    boundaryGap: [0.1, 0.1], 
                    axisLine: { onZero: false }, 
                    axisTick: { show: false }, 
                    splitLine: { show: false }, 
                    axisLabel: { show: false } 
                }
            ],
            yAxis: [
                { scale: true, splitArea: { show: true } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
                { 
                    scale: true, 
                    gridIndex: 2, 
                    splitNumber: 2, 
                    axisLabel: { 
                        show: true, 
                        color: '#999',
                        formatter: function(value) {
                            if (Math.abs(value) < 0.01) {
                                return '0';
                            }
                            return value.toFixed(2);
                        }
                    }, 
                    axisLine: { show: false }, 
                    axisTick: { show: false }, 
                    splitLine: { 
                        show: true, 
                        lineStyle: { 
                            type: 'dashed', 
                            color: '#666',
                            width: 1
                        }
                    }
                }
            ],
            dataZoom: [
                { 
                    type: 'inside', 
                    xAxisIndex: [0, 1, 2], 
                    start: 30, 
                    end: 100,
                    zoomOnMouseWheel: true,
                    moveOnMouseMove: true,
                    moveOnMouseWheel: true
                },
                {
                    type: 'slider',
                    xAxisIndex: [0, 1, 2],
                    bottom: '2%',
                    height: '15px',
                    start: 30,
                    end: 100,
                    handleStyle: {
                        color: '#1890ff'
                    },
                    textStyle: {
                        color: '#333'
                    }
                }
            ],
            series: [
                { 
                    name: 'K线', 
                    type: 'candlestick', 
                    data: [], 
                    barWidth: '80%',
                    barMaxWidth: '90%',
                    itemStyle: { 
                        color: '#dc2626', 
                        color0: '#16a34a', 
                        borderColor: '#dc2626', 
                        borderColor0: '#16a34a',
                        borderWidth: 1.5
                    },
                    emphasis: {
                        itemStyle: {
                            borderWidth: 3,
                            shadowBlur: 15,
                            shadowColor: 'rgba(0, 0, 0, 0.4)'
                        }
                    }
                },
                { name: 'MA5', type: 'line', data: [], smooth: true, lineStyle: { width: 2, color: '#fbbf24' }, showSymbol: false },
                { name: 'MA10', type: 'line', data: [], smooth: true, lineStyle: { width: 2, color: '#3b82f6' }, showSymbol: false },
                { 
                    name: '成交量', 
                    type: 'bar', 
                    xAxisIndex: 1, 
                    yAxisIndex: 1, 
                    data: [], 
                    barWidth: '80%',
                    barMaxWidth: '90%',
                    itemStyle: { 
                        color: function(params) { 
                            return params.dataIndex % 2 === 0 ? '#dc2626' : '#16a34a'; 
                        },
                        borderRadius: [3, 3, 0, 0],
                        borderWidth: 0.5,
                        borderColor: function(params) {
                            return params.dataIndex % 2 === 0 ? '#b91c1c' : '#15803d';
                        }
                    },
                    emphasis: {
                        itemStyle: {
                            shadowBlur: 12,
                            shadowColor: 'rgba(0, 0, 0, 0.4)',
                            borderWidth: 1
                        } 
                    } 
                },
                { 
                    name: 'DIF', 
                    type: 'line', 
                    xAxisIndex: 2, 
                    yAxisIndex: 2, 
                    data: [], 
                    smooth: true, 
                    lineStyle: { width: 2, color: '#ffffff' }, 
                    showSymbol: false,
                    z: 2
                },
                { 
                    name: 'DEA', 
                    type: 'line', 
                    xAxisIndex: 2, 
                    yAxisIndex: 2, 
                    data: [], 
                    smooth: true, 
                    lineStyle: { width: 2, color: '#fbbf24' }, 
                    showSymbol: false,
                    z: 2
                },
                { 
                    name: 'MACD', 
                    type: 'bar', 
                    xAxisIndex: 2, 
                    yAxisIndex: 2, 
                    data: [], 
                    barWidth: '60%',
                    z: 1,
                    itemStyle: {
                        color: function(params) {
                            // 正值显示红色，负值显示青色/浅蓝色
                            return params.value >= 0 ? '#dc2626' : '#06b6d4';
                        }
                    }
                }
            ],
            tooltip: { 
                trigger: 'axis', 
                axisPointer: { type: 'cross' }, 
                backgroundColor: 'rgba(245, 245, 245, 0.9)', 
                borderWidth: 1, 
                borderColor: '#ccc', 
                textStyle: { color: '#000' },
                formatter: function(params) {
                    let result = params[0].name + '<br/>';
                    let macdInfo = '';
                    params.forEach(function(item) {
                        if (item.seriesName === 'K线') {
                            result += item.marker + ' ' + item.seriesName + ': ';
                            result += '开盘:' + item.data[1] + ' 收盘:' + item.data[2] + '<br/>';
                            result += '最低:' + item.data[3] + ' 最高:' + item.data[4] + '<br/>';
                        } else if (item.seriesName === 'DIF') {
                            macdInfo += item.marker + ' DIF: ' + (item.data !== null && item.data !== undefined ? item.data.toFixed(2) : '-') + ' ';
                        } else if (item.seriesName === 'DEA') {
                            macdInfo += item.marker + ' DEA: ' + (item.data !== null && item.data !== undefined ? item.data.toFixed(2) : '-') + ' ';
                        } else if (item.seriesName === 'MACD') {
                            macdInfo += item.marker + ' MACD: ' + (item.data !== null && item.data !== undefined ? item.data.toFixed(2) : '-');
                        } else {
                            result += item.marker + ' ' + item.seriesName + ': ' + (item.data !== null && item.data !== undefined ? item.data : '-') + '<br/>';
                        }
                    });
                    if (macdInfo) {
                        result += '<br/>MACD(12,26,9)<br/>' + macdInfo;
                    }
                    return result;
                }
            },
            legend: {
                data: ['K线', 'MA5', 'MA10', '成交量', 'DIF', 'DEA', 'MACD'],
                top: '1%',
                textStyle: {
                    color: '#999'
                }
            }
        };
        this.klineChart.setOption(option);
        
        // 初始化时默认显示成交量，隐藏MACD
        const initOption = this.klineChart.getOption();
        this.showVolumeChart(initOption);
        this.hideMACDChart(initOption);
        this.klineChart.setOption(initOption);
    },

    // 初始化分时图
    initMinuteChart() {
        const chartDom = document.getElementById('minuteChart');
        if (!chartDom) return;

        this.minuteChart = echarts.init(chartDom);
        
        const option = {
            backgroundColor: 'transparent',
            grid: {
                left: '8%',
                right: '6%',
                top: '5%',
                bottom: '12%'
            },
            xAxis: {
                type: 'category',
                data: [], // 初始为空
                boundaryGap: [0.05, 0.05],
                axisLabel: {
                    interval: 'auto',
                    rotate: 0
                }
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
                    width: 3
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

  

    // 加载股票数据
    async loadStockData() {
        try {
            const url = `${API_BASE_URL}/api/stock/hk/realtime_quote_by_code?code=${this.stockCode}`;
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
        
        // 更新当前价格，并根据与昨收价格比较设置颜色
        const currentPriceElement = document.querySelector('.current-price');
        currentPriceElement.textContent = this.currentPrice ? Number(this.currentPrice).toFixed(2) : '-';
        // 根据当前价格和昨收价格比较设置颜色类
        if (this.currentPrice !== null && this.currentPrice !== undefined && !isNaN(this.currentPrice) &&
            this.pre_close !== null && this.pre_close !== undefined && !isNaN(this.pre_close)) {
            const current = parseFloat(this.currentPrice);
            const pre = parseFloat(this.pre_close);
            if (current > pre) {
                currentPriceElement.className = 'current-price positive';  // 比昨收高，红色
            } else if (current < pre) {
                currentPriceElement.className = 'current-price negative';  // 比昨收低，绿色
            } else {
                currentPriceElement.className = 'current-price';  // 相等，默认颜色
            }
        } else {
            currentPriceElement.className = 'current-price';  // 数据无效，默认颜色
        }
        
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
            const response = await authFetch(`${API_BASE_URL}/api/analysis/stock/${this.stockCode}`);
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
        
        console.log('[关键价位] 当前价格:', this.currentPrice);
        console.log('[关键价位] 阻力位数据:', levels.resistance_levels);
        console.log('[关键价位] 支撑位数据:', levels.support_levels);
        
        // 更新阻力位
        if (levels.resistance_levels && levels.resistance_levels.length > 0) {
            const resistanceElements = document.querySelectorAll('.level-item:not(.current) .level-value.resistance');
            console.log('[关键价位] 找到阻力位元素数量:', resistanceElements.length);
            levels.resistance_levels.forEach((level, index) => {
                if (resistanceElements[index]) {
                    // 验证阻力位数据：阻力位必须严格大于当前价格
                    if (level <= this.currentPrice) {
                        console.warn(`[关键价位] 阻力位${index+1}数据无效: ${level.toFixed(2)} <= 当前价格 ${this.currentPrice.toFixed(2)}`);
                        return; // 跳过无效数据
                    }
                    console.log(`[关键价位] 更新阻力位${index+1}: ${level.toFixed(2)}`);
                    resistanceElements[index].textContent = level.toFixed(2);
                }
            });
        }
        
        // 更新支撑位
        if (levels.support_levels && levels.support_levels.length > 0) {
            const supportElements = document.querySelectorAll('.level-item:not(.current) .level-value.support');
            console.log('[关键价位] 找到支撑位元素数量:', supportElements.length);
            levels.support_levels.forEach((level, index) => {
                if (supportElements[index]) {
                    // 验证支撑位数据：支撑位必须严格小于当前价格
                    if (level >= this.currentPrice) {
                        console.warn(`[关键价位] 支撑位${index+1}数据无效: ${level.toFixed(2)} >= 当前价格 ${this.currentPrice.toFixed(2)}`);
                        return; // 跳过无效数据
                    }
                    console.log(`[关键价位] 更新支撑位${index+1}: ${level.toFixed(2)}`);
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
        
        // 注意：不在这里更新关键价位，因为关键价位应该使用后端计算的真实数据
        // 关键价位会在 loadAnalysisData() 中通过后端API获取
        
        // 设置数据已加载标志
        this.analysisDataLoaded = true;
    },

    // 加载新闻数据
    async loadNewsData() {
        try {
            console.log('[loadNewsData] 开始加载新闻数据:', this.stockCode);
            const url = `${API_BASE_URL}/api/stock/news/news_combined?symbol=${this.stockCode}&news_limit=50&announcement_limit=20&research_limit=10`;
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
                ${item.url ? `<a href="#" onclick="StockPage.viewPDFDetail('${item.url}', '${item.title || 'PDF文档'}'); return false;" class="news-link">查看详情</a>` : ''}
            `;
            
            newsContainer.appendChild(newsCard);
        });
        
        console.log('[loadNewsData] 新闻数据渲染完成，共', newsData.length, '条');
    },

    // 加载研报数据
    async loadResearchData() {
        try {
            console.log('[loadResearchData] 开始加载研报数据:', this.stockCode);
            const url = `${API_BASE_URL}/api/stock/news/research_reports?symbol=${this.stockCode}&limit=20`;
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

    // 查看PDF详情（使用重定向API）
    viewPDFDetail(url, title) {
        try {
            console.log('[viewPDFDetail] 查看PDF详情:', url, title);
            
            // 使用后端重定向页面来绕过防盗链
            const redirectUrl = `${API_BASE_URL}/api/stock/news/pdf_redirect?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title || 'PDF文档')}`;
            const newWindow = window.open(redirectUrl, '_blank', 'width=1000,height=800,scrollbars=yes,resizable=yes');
            
            if (newWindow) {
                CommonUtils.showToast(`正在打开: ${title}`, 'success');
                return;
            } else {
                // 如果弹窗被阻止，尝试直接访问
                console.warn('[viewPDFDetail] 弹窗被阻止，尝试直接访问');
                window.open(url, '_blank');
            }
            
        } catch (error) {
            console.error('[viewPDFDetail] 查看PDF详情失败:', error);
            CommonUtils.showToast('打开PDF失败，请稍后重试', 'error');
        }
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
            const redirectUrl = `${API_BASE_URL}/api/stock/news/pdf_redirect?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title || 'PDF文档')}`;
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
                const proxyUrl = `${API_BASE_URL}/api/stock/news/download_pdf?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(title || '研报')}.pdf`;
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
        console.log(`[技术指标] 切换到${indicator}指标`);
        
        if (!this.klineChart) {
            console.error('[技术指标] K线图表未初始化');
            return;
        }
        
        const option = this.klineChart.getOption();
        
        // 清除现有的技术指标线
        this.clearTechnicalIndicators(option);
        
        switch(indicator) {
            case 'ma':
                this.addMAIndicators(option);
                break;
            case 'ema':
                this.addEMAIndicators(option);
                break;
            case 'boll':
                this.addBollingerBands(option);
                break;
            default:
                console.warn(`[技术指标] 未知指标类型: ${indicator}`);
        }
        
        this.klineChart.setOption(option);
        CommonUtils.showToast(`已切换到${this.getIndicatorName(indicator)}`, 'success');
    },

    // 更新副图指标
    updateSubIndicator(indicator) {
        console.log(`[副图指标] 切换到${indicator}指标`);
        
        if (!this.klineChart) {
            console.error('[副图指标] K线图表未初始化');
            return;
        }
        
        const option = this.klineChart.getOption();
        
        // 根据选择的指标显示/隐藏对应的图表区域和系列
        switch(indicator) {
            case 'vol':
                // 显示成交量，隐藏MACD
                this.showVolumeChart(option);
                this.hideMACDChart(option);
                break;
            case 'macd':
                // 显示MACD，隐藏成交量
                this.hideVolumeChart(option);
                this.showMACDChart(option);
                break;
            case 'kdj':
            case 'rsi':
                // 暂时显示成交量（KDJ和RSI还未实现）
                this.showVolumeChart(option);
                this.hideMACDChart(option);
                CommonUtils.showToast(`${indicator.toUpperCase()}指标功能开发中`, 'info');
                return;
            default:
                console.warn(`[副图指标] 未知指标类型: ${indicator}`);
                return;
        }
        
        this.klineChart.setOption(option);
        CommonUtils.showToast(`已切换到${this.getSubIndicatorName(indicator)}`, 'success');
    },
    
    showVolumeChart(option) {
        // 显示成交量区域（grid[1]），隐藏MACD区域（grid[2]）
        if (option.grid && option.grid[1]) {
            option.grid[1].height = '12%';
            option.grid[1].top = '63%';
        }
        if (option.grid && option.grid[2]) {
            option.grid[2].height = '0%';
            option.grid[2].top = '100%';
        }
        
        // 调整K线图区域高度
        if (option.grid && option.grid[0]) {
            option.grid[0].height = '55%';
        }
        
        // 显示成交量系列，隐藏MACD系列
        if (option.series) {
            if (option.series[3]) {
                option.series[3].show = true;
                option.series[3].xAxisIndex = 1;
                option.series[3].yAxisIndex = 1;
            }
            if (option.series[4]) option.series[4].show = false; // DIF
            if (option.series[5]) option.series[5].show = false; // DEA
            if (option.series[6]) option.series[6].show = false; // MACD
        }
        
        // 更新dataZoom的xAxisIndex
        if (option.dataZoom) {
            option.dataZoom.forEach(zoom => {
                if (zoom.xAxisIndex) {
                    zoom.xAxisIndex = [0, 1];
                }
            });
        }
    },
    
    hideVolumeChart(option) {
        // 隐藏成交量区域（grid[1]）
        if (option.grid && option.grid[1]) {
            option.grid[1].height = '0%';
            option.grid[1].top = '100%';
        }
        
        // 隐藏成交量系列
        if (option.series && option.series[3]) {
            option.series[3].show = false;
        }
    },
    
    showMACDChart(option) {
        // 显示MACD区域（grid[2]），隐藏成交量区域（grid[1]）
        if (option.grid && option.grid[1]) {
            option.grid[1].height = '0%';
            option.grid[1].top = '100%';
        }
        if (option.grid && option.grid[2]) {
            option.grid[2].height = '18%';
            option.grid[2].top = '78%';
        }
        
        // 调整K线图区域高度
        if (option.grid && option.grid[0]) {
            option.grid[0].height = '60%';
        }
        
        // 显示MACD系列，隐藏成交量系列
        if (option.series) {
            if (option.series[3]) {
                option.series[3].show = false; // 隐藏成交量
            }
            if (option.series[4]) {
                option.series[4].show = true; // DIF
                option.series[4].xAxisIndex = 2;
                option.series[4].yAxisIndex = 2;
            }
            if (option.series[5]) {
                option.series[5].show = true; // DEA
                option.series[5].xAxisIndex = 2;
                option.series[5].yAxisIndex = 2;
            }
            if (option.series[6]) {
                option.series[6].show = true; // MACD
                option.series[6].xAxisIndex = 2;
                option.series[6].yAxisIndex = 2;
            }
        }
        
        // 更新dataZoom的xAxisIndex
        if (option.dataZoom) {
            option.dataZoom.forEach(zoom => {
                if (zoom.xAxisIndex) {
                    zoom.xAxisIndex = [0, 2];
                }
            });
        }
    },
    
    hideMACDChart(option) {
        // 隐藏MACD区域（grid[2]）
        if (option.grid && option.grid[2]) {
            option.grid[2].height = '0%';
            option.grid[2].top = '100%';
        }
        
        // 隐藏MACD系列
        if (option.series) {
            if (option.series[4]) option.series[4].show = false; // DIF
            if (option.series[5]) option.series[5].show = false; // DEA
            if (option.series[6]) option.series[6].show = false; // MACD
        }
    },
    
    getSubIndicatorName(indicator) {
        const names = {
            'vol': '成交量',
            'macd': 'MACD',
            'kdj': 'KDJ',
            'rsi': 'RSI'
        };
        return names[indicator] || indicator;
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
            const resp = await fetch(`${API_BASE_URL}/api/stock/hk/realtime_quote_by_code?code=${this.stockCode}`);
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
            const url = `${API_BASE_URL}/api/stock/hk/minute_data_by_code?code=${this.stockCode}`;
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
                url = `${API_BASE_URL}/api/stock/hk/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=`;
            } else if (this.currentPeriod === '1M') {
                period = 'monthly';
                url = `${API_BASE_URL}/api/stock/hk/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=`;
            } else if (this.currentPeriod === '1Q') {
                period = 'quarterly';
                url = `${API_BASE_URL}/api/stock/hk/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=`;
            } else if (this.currentPeriod === '6M') {
                period = 'semiannual';
                url = `${API_BASE_URL}/api/stock/hk/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=`;
            } else if (this.currentPeriod === '1Y') {
                period = 'annual';
                url = `${API_BASE_URL}/api/stock/hk/kline_hist?code=${this.stockCode}&period=${period}&start_date=${startDate}&end_date=${endDate}&adjust=`;
            } else {
                // 默认日线
                url = `${API_BASE_URL}/api/stock/hk/kline_hist?code=${this.stockCode}&period=daily&start_date=${startDate}&end_date=${endDate}&adjust=`;
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
                // K线数据 - 根据ECharts candlestick格式要求
                // ECharts candlestick格式: [open, close, low, high]
                const kline = list.map((item, index) => {
                    // 确保数据顺序正确
                    const open = parseFloat(item.open) || 0;
                    const close = parseFloat(item.close) || 0;
                    const low = parseFloat(item.low) || 0;
                    const high = parseFloat(item.high) || 0;
                    
                    // 调试：显示前3条数据
                    if (index < 3) {
                        console.log(`[K线数据映射] 第${index + 1}条:`, {
                            date: item.date,
                            original: { open: item.open, close: item.close, high: item.high, low: item.low },
                            parsed: { open, close, high, low },
                            mapped: [open, close, low, high]
                        });
                    }
                    
                    // 返回正确的ECharts candlestick格式
                    return [open, close, low, high];
                });
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
                // MACD数据
                const dif = list.map(item => item.dif !== null && item.dif !== undefined ? parseFloat(item.dif) : null);
                const dea = list.map(item => item.dea !== null && item.dea !== undefined ? parseFloat(item.dea) : null);
                const macd = list.map(item => item.macd !== null && item.macd !== undefined ? parseFloat(item.macd) : null);
                
                option.xAxis[0].data = dates;
                option.xAxis[1].data = dates;
                option.xAxis[2].data = dates;
                option.series[0].data = kline;
                option.series[1].data = ma5;
                option.series[2].data = ma10;
                option.series[3].data = volume;
                option.series[4].data = dif;
                option.series[5].data = dea;
                option.series[6].data = macd;
                
                // 根据当前选择的副图指标设置显示状态
                const subIndicatorSelect = document.querySelector('.sub-indicator-select');
                const currentSubIndicator = subIndicatorSelect ? subIndicatorSelect.value : 'vol';
                if (currentSubIndicator === 'macd') {
                    this.showMACDChart(option);
                    this.hideVolumeChart(option);
                } else {
                    this.showVolumeChart(option);
                    this.hideMACDChart(option);
                }
                
                // 当数据量较少时，优化显示效果
                const dataCount = kline.length;
                if (dataCount <= 30) {
                    // 数据很少时，显示全部数据，K线更宽更显眼
                    option.dataZoom[0].start = 0;
                    option.dataZoom[0].end = 100;
                    
                    // 调整K线柱子宽度，让它们更显眼
                    option.series[0].barWidth = Math.max(8, Math.min(20, 400 / dataCount));
                    // 同时调整成交量柱子宽度
                    option.series[3].barWidth = Math.max(8, Math.min(20, 400 / dataCount));
                    
                    // 优化X轴显示
                    option.xAxis[0].boundaryGap = true; // 让K线不贴边显示
                    option.xAxis[1].boundaryGap = true;
                } else if (dataCount <= 80) {
                    // 数据少时，显示全部数据，不进行缩放
                    option.dataZoom[0].start = 0;
                    option.dataZoom[0].end = 100;
                    
                    // 调整K线柱子宽度，让它们更显眼
                    option.series[0].barWidth = Math.max(6, Math.min(15, 350 / dataCount));
                    // 同时调整成交量柱子宽度
                    option.series[3].barWidth = Math.max(6, Math.min(15, 350 / dataCount));
                    
                    // 优化X轴显示
                    option.xAxis[0].boundaryGap = true; // 让K线不贴边显示
                    option.xAxis[1].boundaryGap = true;
                } else if (dataCount <= 200) {
                    // 中等数据量时，调整显示范围
                    option.dataZoom[0].start = Math.max(0, 100 - (100 * 100 / dataCount));
                    option.dataZoom[0].end = 100;
                    
                    // 适中的柱子宽度
                    option.series[0].barWidth = Math.max(4, Math.min(12, 250 / dataCount));
                    option.series[3].barWidth = Math.max(4, Math.min(12, 250 / dataCount));
                    
                    option.xAxis[0].boundaryGap = true;
                    option.xAxis[1].boundaryGap = true;
                } else {
                    // 数据量充足时，保持原有的显示方式，但使用更宽的默认宽度
                    option.dataZoom[0].start = 50;
                    option.dataZoom[0].end = 100;
                    
                    // 使用更宽的默认设置
                    option.series[0].barWidth = '85%';
                    option.series[3].barWidth = '85%';
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
    },
    
    // 测试关键价位更新（用于调试）
    testKeyLevelsUpdate() {
        console.log('[测试] 开始测试关键价位更新...');
        
        // 模拟后端返回的关键价位数据
        const mockLevels = {
            resistance_levels: [23.50, 24.80, 26.20],
            support_levels: [20.50, 19.20, 18.00],
            current_price: 22.19
        };
        
        console.log('[测试] 模拟数据:', mockLevels);
        
        // 调用更新函数
        this.updateKeyLevels(mockLevels);
        
        console.log('[测试] 关键价位更新完成');
    },
    
    // 清除技术指标线
    clearTechnicalIndicators(option) {
        // 移除所有技术指标相关的series
        option.series = option.series.filter(series => {
            return !series.name.includes('MA') && 
                   !series.name.includes('EMA') && 
                   !series.name.includes('布林带') &&
                   !series.name.includes('BB');
        });
    },
    
    // 添加MA均线
    addMAIndicators(option) {
        const klineData = option.series[0].data;
        if (!klineData || klineData.length === 0) {
            console.warn('[MA均线] 没有K线数据');
            return;
        }
        
        // 计算收盘价
        const closes = klineData.map(item => item[1]); // 收盘价
        
        // 计算MA5, MA10, MA20
        const ma5 = this.calculateMA(closes, 5);
        const ma10 = this.calculateMA(closes, 10);
        const ma20 = this.calculateMA(closes, 20);
        
        // 添加MA线
        option.series.push({
            name: 'MA5',
            type: 'line',
            data: ma5,
            smooth: true,
            lineStyle: { width: 1, color: '#fbbf24' },
            showSymbol: false
        });
        
        option.series.push({
            name: 'MA10',
            type: 'line',
            data: ma10,
            smooth: true,
            lineStyle: { width: 1, color: '#3b82f6' },
            showSymbol: false
        });
        
        option.series.push({
            name: 'MA20',
            type: 'line',
            data: ma20,
            smooth: true,
            lineStyle: { width: 1, color: '#8b5cf6' },
            showSymbol: false
        });
    },
    
    // 添加EMA均线
    addEMAIndicators(option) {
        const klineData = option.series[0].data;
        if (!klineData || klineData.length === 0) {
            console.warn('[EMA均线] 没有K线数据');
            return;
        }
        
        // 计算收盘价
        const closes = klineData.map(item => item[1]); // 收盘价
        
        // 计算EMA12, EMA26
        const ema12 = this.calculateEMA(closes, 12);
        const ema26 = this.calculateEMA(closes, 26);
        
        // 添加EMA线
        option.series.push({
            name: 'EMA12',
            type: 'line',
            data: ema12,
            smooth: true,
            lineStyle: { width: 1, color: '#f59e0b' },
            showSymbol: false
        });
        
        option.series.push({
            name: 'EMA26',
            type: 'line',
            data: ema26,
            smooth: true,
            lineStyle: { width: 1, color: '#6366f1' },
            showSymbol: false
        });
    },
    
    // 添加布林带
    addBollingerBands(option) {
        const klineData = option.series[0].data;
        if (!klineData || klineData.length === 0) {
            console.warn('[布林带] 没有K线数据');
            return;
        }
        
        // 计算收盘价
        const closes = klineData.map(item => item[1]); // 收盘价
        
        // 计算布林带（使用标准参数：20日移动平均，2倍标准差）
        const bb = this.calculateBollingerBands(closes, 20, 2);
        
        // 添加布林带中线（MA20）
        option.series.push({
            name: '布林带中线',
            type: 'line',
            data: bb.middle,
            smooth: true,
            lineStyle: { 
                width: 1.5, 
                color: '#8b5cf6',
                type: 'solid',
                opacity: 0.8
            },
            showSymbol: false,
            z: 10
        });
        
        // 添加布林带上轨
        option.series.push({
            name: '布林带上轨',
            type: 'line',
            data: bb.upper,
            smooth: true,
            lineStyle: { 
                width: 1, 
                color: '#64748b',
                type: 'solid',
                opacity: 0.7
            },
            showSymbol: false,
            z: 5
        });
        
        // 添加布林带下轨
        option.series.push({
            name: '布林带下轨',
            type: 'line',
            data: bb.lower,
            smooth: true,
            lineStyle: { 
                width: 1, 
                color: '#64748b',
                type: 'solid',
                opacity: 0.7
            },
            showSymbol: false,
            z: 5
        });
        
        // 添加布林带填充区域
        option.series.push({
            name: '布林带区域',
            type: 'line',
            data: bb.upper,
            lineStyle: { opacity: 0 },
            showSymbol: false,
            stack: 'bollinger',
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(100, 116, 139, 0.05)' },
                        { offset: 0.5, color: 'rgba(139, 92, 246, 0.03)' },
                        { offset: 1, color: 'rgba(100, 116, 139, 0.05)' }
                    ]
                }
            },
            z: 1
        });
        
        option.series.push({
            name: '布林带区域填充',
            type: 'line',
            data: bb.lower,
            lineStyle: { opacity: 0 },
            showSymbol: false,
            stack: 'bollinger',
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(100, 116, 139, 0.05)' },
                        { offset: 0.5, color: 'rgba(139, 92, 246, 0.03)' },
                        { offset: 1, color: 'rgba(100, 116, 139, 0.05)' }
                    ]
                }
            },
            z: 1
        });
    },
    
    // 计算移动平均线
    calculateMA(data, period) {
        const result = [];
        for (let i = 0; i < data.length; i++) {
            if (i < period - 1) {
                result.push(null);
            } else {
                const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
                result.push(sum / period);
            }
        }
        return result;
    },
    
    // 计算指数移动平均线
    calculateEMA(data, period) {
        const result = [];
        const multiplier = 2 / (period + 1);
        
        // 第一个值使用SMA
        if (data.length >= period) {
            const sum = data.slice(0, period).reduce((a, b) => a + b, 0);
            result.push(sum / period);
        }
        
        // 计算EMA
        for (let i = period; i < data.length; i++) {
            const ema = (data[i] - result[result.length - 1]) * multiplier + result[result.length - 1];
            result.push(ema);
        }
        
        // 前面补null
        const paddedResult = new Array(data.length).fill(null);
        for (let i = period - 1; i < data.length; i++) {
            paddedResult[i] = result[i - period + 1];
        }
        
        return paddedResult;
    },
    
    // 计算布林带
    calculateBollingerBands(data, period, multiplier) {
        const result = {
            upper: [],
            middle: [],
            lower: []
        };
        
        for (let i = 0; i < data.length; i++) {
            if (i < period - 1) {
                result.upper.push(null);
                result.middle.push(null);
                result.lower.push(null);
            } else {
                const slice = data.slice(i - period + 1, i + 1);
                const mean = slice.reduce((a, b) => a + b, 0) / period;
                
                // 使用样本标准差（n-1）而不是总体标准差（n），更符合金融标准
                const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (period - 1);
                const stdDev = Math.sqrt(variance);
                
                result.middle.push(parseFloat(mean.toFixed(4)));
                result.upper.push(parseFloat((mean + multiplier * stdDev).toFixed(4)));
                result.lower.push(parseFloat((mean - multiplier * stdDev).toFixed(4)));
            }
        }
        
        return result;
    },
    
    // 获取指标名称
    getIndicatorName(indicator) {
        const names = {
            'ma': 'MA均线',
            'ema': 'EMA均线',
            'boll': '布林带'
        };
        return names[indicator] || indicator;
    },
    
    // 测试布林带功能（用于调试）
    testBollingerBands() {
        console.log('[测试] 开始测试布林带功能...');
        
        if (!this.klineChart) {
            console.error('[测试] K线图表未初始化');
            return;
        }
        
        // 模拟K线数据
        const mockKlineData = [
            [100, 102, 98, 101],   // [开,收,低,高]
            [101, 103, 99, 104],
            [103, 105, 101, 106],
            [105, 107, 103, 108],
            [107, 109, 105, 110],
            [109, 111, 107, 112],
            [111, 113, 109, 114],
            [113, 115, 111, 116],
            [115, 117, 113, 118],
            [117, 119, 115, 120],
            [119, 121, 117, 122],
            [121, 123, 119, 124],
            [123, 125, 121, 126],
            [125, 127, 123, 128],
            [127, 129, 125, 130],
            [129, 131, 127, 132],
            [131, 133, 129, 134],
            [133, 135, 131, 136],
            [135, 137, 133, 138],
            [137, 139, 135, 140],
            [139, 141, 137, 142],
            [141, 143, 139, 144],
            [143, 145, 141, 146],
            [145, 147, 143, 148],
            [147, 149, 145, 150]
        ];
        
        // 设置模拟数据
        const option = this.klineChart.getOption();
        option.series[0].data = mockKlineData;
        option.xAxis[0].data = mockKlineData.map((_, index) => `Day${index + 1}`);
        
        // 添加布林带
        this.addBollingerBands(option);
        
        // 更新图表
        this.klineChart.setOption(option);
        
        console.log('[测试] 布林带功能测试完成');
        CommonUtils.showToast('布林带功能测试完成', 'success');
    },
    
    // 测试研报下载功能（用于调试）
    testResearchDownload() {
        console.log('[测试] 开始测试研报下载功能...');
        
        // 测试PDF重定向API
        const testUrl = 'https://pdf.dfcfw.com/pdf/H3_AP202308301596848153_1.pdf';
        const testTitle = '2023年中报研报';
        
        console.log('[测试] 测试URL:', testUrl);
        console.log('[测试] 测试标题:', testTitle);
        
        // 调用下载方法
        this.downloadPDF(testUrl, testTitle);
        
        console.log('[测试] 研报下载功能测试完成');
        CommonUtils.showToast('研报下载功能测试完成', 'success');
    },
    
    // 测试研报查看详情功能（用于调试）
    testResearchViewDetail() {
        console.log('[测试] 开始测试研报查看详情功能...');
        
        // 测试PDF查看详情API
        const testUrl = 'https://pdf.dfcfw.com/pdf/H3_AP202504251662360192_1.pdf';
        const testTitle = '2024年年报点评:超硬刀具量价齐升,新业务稳步拓展';
        
        console.log('[测试] 测试URL:', testUrl);
        console.log('[测试] 测试标题:', testTitle);
        
        // 调用查看详情方法
        this.viewPDFDetail(testUrl, testTitle);
        
        console.log('[测试] 研报查看详情功能测试完成');
        CommonUtils.showToast('研报查看详情功能测试完成', 'success');
    },
    
    // 测试K线图显示优化（用于调试）
    testKlineDisplayOptimization() {
        console.log('[测试] 开始测试K线图显示优化...');
        
        if (!this.klineChart) {
            console.warn('[测试] K线图未初始化');
            CommonUtils.showToast('K线图未初始化', 'warning');
            return;
        }
        
        // 获取当前配置
        const currentOption = this.klineChart.getOption();
        console.log('[测试] 当前K线图配置:', currentOption);
        
        // 检查关键配置项
        const klineSeries = currentOption.series.find(s => s.name === 'K线');
        const volumeSeries = currentOption.series.find(s => s.name === '成交量');
        
        console.log('[测试] K线配置:', {
            barWidth: klineSeries.barWidth,
            barMaxWidth: klineSeries.barMaxWidth,
            boundaryGap: currentOption.xAxis[0].boundaryGap
        });
        
        console.log('[测试] 成交量配置:', {
            barWidth: volumeSeries.barWidth,
            barMaxWidth: volumeSeries.barMaxWidth
        });
        
        console.log('[测试] 网格配置:', {
            grid: currentOption.grid,
            dataZoom: currentOption.dataZoom
        });
        
        console.log('[测试] K线图显示优化测试完成');
        CommonUtils.showToast('K线图显示优化测试完成', 'success');
    },
    
    // 测试K线图数据正确性（用于调试最高最低价格显示）
    testKlineDataCorrectness() {
        console.log('[测试] 开始测试K线图数据正确性...');
        
        if (!this.klineChart) {
            console.warn('[测试] K线图未初始化');
            CommonUtils.showToast('K线图未初始化', 'warning');
            return;
        }
        
        // 获取当前配置
        const currentOption = this.klineChart.getOption();
        const klineData = currentOption.series[0].data;
        
        if (!klineData || klineData.length === 0) {
            console.warn('[测试] 没有K线数据');
            CommonUtils.showToast('没有K线数据', 'warning');
            return;
        }
        
        console.log('[测试] K线数据格式验证:');
        console.log('[测试] ECharts candlestick格式: [开盘, 收盘, 最低, 最高]');
        
        // 检查前几条数据
        const sampleData = klineData.slice(0, 3);
        sampleData.forEach((item, index) => {
            if (Array.isArray(item) && item.length >= 4) {
                const [open, close, low, high] = item;
                console.log(`[测试] 数据${index + 1}: [${open}, ${close}, ${low}, ${high}]`);
                
                // 验证数据逻辑性
                if (high < low) {
                    console.error(`[测试] ❌ 数据${index + 1}错误: 最高价(${high}) < 最低价(${low})`);
                } else {
                    console.log(`[测试] ✅ 数据${index + 1}正确: 最高价(${high}) >= 最低价(${low})`);
                }
                
                if (high < open || high < close) {
                    console.warn(`[测试] ⚠️ 数据${index + 1}异常: 最高价(${high}) < 开盘价(${open}) 或 收盘价(${close})`);
                }
                
                if (low > open || low > close) {
                    console.warn(`[测试] ⚠️ 数据${index + 1}异常: 最低价(${low}) > 开盘价(${open}) 或 收盘价(${close})`);
                }
            } else {
                console.error(`[测试] ❌ 数据${index + 1}格式错误:`, item);
            }
        });
        
        console.log('[测试] K线图数据正确性测试完成');
        CommonUtils.showToast('K线图数据正确性测试完成', 'success');
    }

};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    StockPage.init();
}); 