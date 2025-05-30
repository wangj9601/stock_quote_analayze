// 仪表板管理模块
const DashboardManager = {
    // 图表实例
    charts: {
        userActivity: null,
        dataCollection: null
    },

    // 初始化
    init() {
        this.loadStats();
        this.initCharts();
        this.loadActivities();
        this.startAutoRefresh();
    },

    // 加载统计数据
    async loadStats() {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/dashboard/stats`);
            const result = await response.json();

            if (result.success) {
                this.updateStats(result.data);
            } else {
                showToast(result.message || '加载统计数据失败', 'error');
            }
        } catch (error) {
            console.error('加载统计数据出错:', error);
            showToast('网络错误，请稍后重试', 'error');
        }
    },

    // 更新统计数据
    updateStats(data) {
        // 更新用户统计
        document.getElementById('userCount').textContent = formatNumber(data.userCount);
        this.updateChange('userChange', data.userChange);

        // 更新股票统计
        document.getElementById('stockCount').textContent = formatNumber(data.stockCount);
        this.updateChange('stockChange', data.stockChange);

        // 更新数据采集统计
        document.getElementById('dataSuccessRate').textContent = data.dataSuccessRate + '%';
        this.updateChange('dataChange', data.dataChange);

        // 更新响应时间统计
        document.getElementById('responseTime').textContent = data.responseTime + 's';
        this.updateChange('responseChange', data.responseChange);
    },

    // 更新变化指标
    updateChange(elementId, change) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const value = change.value;
        const isPositive = change.type === 'positive';
        
        element.textContent = (isPositive ? '+' : '') + value + (change.unit || '');
        element.className = 'stat-change ' + (isPositive ? 'positive' : 'negative');
    },

    // 初始化图表
    initCharts() {
        this.initUserActivityChart();
        this.initDataCollectionChart();
    },

    // 初始化用户活跃度图表
    initUserActivityChart() {
        const ctx = document.getElementById('userActivityChart').getContext('2d');
        this.charts.userActivity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '活跃用户数',
                    data: [],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        this.loadUserActivityData();
    },

    // 初始化数据采集状态图表
    initDataCollectionChart() {
        const ctx = document.getElementById('dataCollectionChart').getContext('2d');
        this.charts.dataCollection = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['成功', '失败', '进行中'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        '#48bb78',
                        '#f56565',
                        '#ed8936'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });

        this.loadDataCollectionData();
    },

    // 加载用户活跃度数据
    async loadUserActivityData() {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/dashboard/user-activity`);
            const result = await response.json();

            if (result.success) {
                this.updateUserActivityChart(result.data);
            }
        } catch (error) {
            console.error('加载用户活跃度数据出错:', error);
        }
    },

    // 更新用户活跃度图表
    updateUserActivityChart(data) {
        const chart = this.charts.userActivity;
        if (!chart) return;

        chart.data.labels = data.labels;
        chart.data.datasets[0].data = data.values;
        chart.update();
    },

    // 加载数据采集状态数据
    async loadDataCollectionData() {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/dashboard/data-collection`);
            const result = await response.json();

            if (result.success) {
                this.updateDataCollectionChart(result.data);
            }
        } catch (error) {
            console.error('加载数据采集状态数据出错:', error);
        }
    },

    // 更新数据采集状态图表
    updateDataCollectionChart(data) {
        const chart = this.charts.dataCollection;
        if (!chart) return;

        chart.data.datasets[0].data = [
            data.success,
            data.failed,
            data.inProgress
        ];
        chart.update();
    },

    // 加载最近活动
    async loadActivities() {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/dashboard/activities`);
            const result = await response.json();

            if (result.success) {
                this.renderActivities(result.data);
            }
        } catch (error) {
            console.error('加载最近活动出错:', error);
        }
    },

    // 渲染活动列表
    renderActivities(activities) {
        const container = document.getElementById('activityList');
        if (!container) return;

        container.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-icon">${activity.icon}</div>
                <div class="activity-content">
                    <p><strong>${activity.title}</strong> - ${activity.description}</p>
                    <span class="activity-time">${activity.time}</span>
                </div>
            </div>
        `).join('');
    },

    // 自动刷新
    startAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
        }
        
        this._refreshTimer = setInterval(() => {
            this.loadStats();
            this.loadUserActivityData();
            this.loadDataCollectionData();
            this.loadActivities();
        }, 60000); // 每分钟刷新一次
    }
};

// 工具函数
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    DashboardManager.init();
}); 