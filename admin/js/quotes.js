// 全局配置
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000/api/admin',
    TOKEN_KEY: 'admin_token'
};

// 工具函数
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // 2秒后自动消失
    setTimeout(() => {
        toast.remove();
    }, 2000);
}

async function apiRequest(url, options = {}) {
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);
    const defaultOptions = {
        method: 'GET',
        mode: 'cors',  // 明确指定CORS模式
        credentials: 'include',  // 包含凭证
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
    };

    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        // 处理401未授权错误
        if (response.status === 401) {
            localStorage.removeItem(CONFIG.TOKEN_KEY);
            // 管理端应该重定向到管理端首页，而不是前端登录页
            window.location.href = '/admin/';
            throw new Error('登录已过期，请重新登录');
        }
        
        // 处理其他HTTP错误
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API请求错误:', error);
        throw error;
    }
}

// 行情数据管理模块
const QuotesManager = {
    // 全局配置
    config: {
        pageSize: 20,
        currentPage: 1,
        currentTab: 'realtime',
        searchKeyword: '',
        dateRange: 'today',
        startDate: '',
        endDate: ''
    },

    // 初始化
    init() {
        this.bindEvents();
        this.loadData();
        this.startAutoRefresh();
    },

    // 绑定事件
    bindEvents() {
        // 标签切换
        document.querySelectorAll('.quotes-tabs .tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchTab(btn.dataset.tab);
            });
        });

        // 搜索框回车
        document.getElementById('stockSearch').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.searchStocks();
            }
        });

        // 日期范围选择
        document.getElementById('dateRange').addEventListener('change', (e) => {
            this.filterByDate(e.target.value);
        });
    },

    // 切换标签
    switchTab(tab) {
        if (this.config.currentTab === tab) return;
        
        this.config.currentTab = tab;
        this.config.currentPage = 1;
        
        // 更新UI
        document.querySelectorAll('.quotes-tabs .tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });

        // 使用动画切换内容
        const contents = document.querySelectorAll('.quotes-content');
        contents.forEach(content => {
            if (content.id === `${tab}Quotes`) {
                content.style.display = 'block';
                // 触发重排以启动动画
                content.offsetHeight;
                content.classList.add('active');
            } else {
                content.classList.remove('active');
                // 等待动画完成后隐藏
                setTimeout(() => {
                    if (!content.classList.contains('active')) {
                        content.style.display = 'none';
                    }
                }, 300);
            }
        });

        // 加载数据
        this.loadData();
        
        // 更新自动刷新
        this.updateAutoRefresh();
    },

    // 加载数据
    async loadData() {
        const { currentTab, currentPage, pageSize, searchKeyword, dateRange, startDate, endDate } = this.config;
        
        // 显示加载状态
        const contentDiv = document.getElementById(`${currentTab}Quotes`);
        const tbody = document.getElementById(`${currentTab}QuotesBody`);
        if (contentDiv && tbody) {
            contentDiv.classList.add('quotes-loading');
            tbody.innerHTML = '';
        }
        
        try {
            const url = new URL(`${CONFIG.API_BASE_URL}/quotes/${currentTab}`);
            url.searchParams.append('page', currentPage);
            url.searchParams.append('page_size', pageSize);
            if (searchKeyword) url.searchParams.append('keyword', searchKeyword);
            if (dateRange !== 'custom') {
                url.searchParams.append('date_range', dateRange);
            } else {
                url.searchParams.append('start_date', startDate);
                url.searchParams.append('end_date', endDate);
            }

            const result = await apiRequest(url.toString());

            // 移除加载状态
            if (contentDiv) {
                contentDiv.classList.remove('quotes-loading');
            }

            if (result.success) {
                this.renderData(result.data);
                this.renderPagination(result.total);
            } else {
                throw new Error(result.message || '获取数据失败');
            }
        } catch (error) {
            console.error('加载数据出错:', error);
            showToast(error.message || '加载数据失败', 'error');
            if (contentDiv) {
                contentDiv.classList.remove('quotes-loading');
            }
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="12" class="text-center">网络错误，请重试</td></tr>';
            }
        }
    },

    // 渲染数据
    renderData(data) {
        const tbody = document.getElementById(`${this.config.currentTab}QuotesBody`);
        if (!tbody) return;

        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="12" class="text-center">暂无数据</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(item => {
            if (this.config.currentTab === 'realtime') {
                return this.renderRealtimeRow(item);
            } else {
                return this.renderHistoricalRow(item);
            }
        }).join('');
    },

    // 渲染实时行情行
    renderRealtimeRow(item) {
        const changeClass = item.change_percent > 0 ? 'price-up' : item.change_percent < 0 ? 'price-down' : '';
        return `
            <tr>
                <td>${item.code}</td>
                <td>${item.name}</td>
                <td class="${changeClass}">${formatPrice(item.current_price)}</td>
                <td class="${changeClass}">${formatPercent(item.change_percent)}</td>
                <td class="${changeClass}">${formatChange(item.change_amount)}</td>
                <td>${formatVolume(item.volume)}</td>
                <td>${formatAmount(item.amount)}</td>
                <td>${formatPrice(item.high)}</td>
                <td>${formatPrice(item.low)}</td>
                <td>${formatPrice(item.open)}</td>
                <td>${formatPrice(item.pre_close)}</td>
                <td>${formatDateTime(item.update_time)}</td>
            </tr>
        `;
    },

    // 渲染历史行情行
    renderHistoricalRow(item) {
        const changeClass = item.change_percent > 0 ? 'price-up' : item.change_percent < 0 ? 'price-down' : '';
        return `
            <tr>
                <td>${item.code}</td>
                <td>${item.name}</td>
                <td>${formatDate(item.date)}</td>
                <td>${formatPrice(item.open)}</td>
                <td>${formatPrice(item.high)}</td>
                <td>${formatPrice(item.low)}</td>
                <td>${formatPrice(item.close)}</td>
                <td class="${changeClass}">${formatPercent(item.change_percent)}</td>
                <td>${formatVolume(item.volume)}</td>
                <td>${formatAmount(item.amount)}</td>
            </tr>
        `;
    },

    // 渲染分页
    renderPagination(total) {
        const totalPages = Math.ceil(total / this.config.pageSize);
        const pagination = document.getElementById(`${this.config.currentTab}Pagination`);
        if (!pagination) return;

        let html = '';
        
        // 上一页
        html += `
            <button onclick="QuotesManager.changePage(${this.config.currentPage - 1})"
                    ${this.config.currentPage === 1 ? 'disabled' : ''}>
                上一页
            </button>
        `;

        // 页码按钮
        for (let i = 1; i <= totalPages; i++) {
            if (
                i === 1 || 
                i === totalPages || 
                (i >= this.config.currentPage - 2 && i <= this.config.currentPage + 2)
            ) {
                html += `
                    <button onclick="QuotesManager.changePage(${i})"
                            class="${i === this.config.currentPage ? 'active' : ''}">
                        ${i}
                    </button>
                `;
            } else if (
                i === this.config.currentPage - 3 || 
                i === this.config.currentPage + 3
            ) {
                html += '<span>...</span>';
            }
        }

        // 下一页
        html += `
            <button onclick="QuotesManager.changePage(${this.config.currentPage + 1})"
                    ${this.config.currentPage === totalPages ? 'disabled' : ''}>
                下一页
            </button>
        `;

        pagination.innerHTML = html;
    },

    // 切换页码
    changePage(page) {
        this.config.currentPage = page;
        this.loadData();
    },

    // 搜索股票
    searchStocks() {
        const keyword = document.getElementById('stockSearch').value.trim();
        if (this.config.searchKeyword === keyword) return;
        
        this.config.searchKeyword = keyword;
        this.config.currentPage = 1;
        this.loadData();
    },

    // 按日期筛选
    filterByDate(range) {
        if (this.config.dateRange === range) return;
        
        this.config.dateRange = range;
        const customDateRange = document.getElementById('customDateRange');
        
        if (range === 'custom') {
            customDateRange.style.display = 'flex';
            // 设置默认日期范围（最近30天）
            const end = new Date();
            const start = new Date();
            start.setDate(start.getDate() - 30);
            
            document.getElementById('startDate').value = start.toISOString().split('T')[0];
            document.getElementById('endDate').value = end.toISOString().split('T')[0];
            
            this.config.startDate = start.toISOString().split('T')[0];
            this.config.endDate = end.toISOString().split('T')[0];
        } else {
            customDateRange.style.display = 'none';
            this.config.currentPage = 1;
            this.loadData();
        }
    },

    // 应用自定义日期范围
    applyCustomDateRange() {
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        
        if (!startDate || !endDate) {
            showToast('请选择完整的日期范围', 'warning');
            return;
        }
        
        if (new Date(startDate) > new Date(endDate)) {
            showToast('开始日期不能大于结束日期', 'warning');
            return;
        }

        if (this.config.startDate === startDate && this.config.endDate === endDate) {
            return;
        }

        this.config.startDate = startDate;
        this.config.endDate = endDate;
        this.config.currentPage = 1;
        this.loadData();
    },

    // 导出数据
    async exportQuotesData() {
        const { currentTab, searchKeyword, dateRange, startDate, endDate } = this.config;
        
        try {
            // 显示导出中状态
            const exportBtn = document.querySelector('.header-actions .btn-primary');
            const originalText = exportBtn.textContent;
            exportBtn.disabled = true;
            exportBtn.textContent = '导出中...';
            
            const url = new URL(`${CONFIG.API_BASE_URL}/quotes/${currentTab}/export`);
            if (searchKeyword) url.searchParams.append('keyword', searchKeyword);
            if (dateRange !== 'custom') {
                url.searchParams.append('date_range', dateRange);
            } else {
                url.searchParams.append('start_date', startDate);
                url.searchParams.append('end_date', endDate);
            }

            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem(CONFIG.TOKEN_KEY)}`
                }
            });
            if (!response.ok) throw new Error('导出失败');

            const blob = await response.blob();
            const filename = `${currentTab}_quotes_${formatDate(new Date())}.xlsx`;
            
            // 创建下载链接
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showToast('数据导出成功', 'success');
        } catch (error) {
            console.error('导出数据出错:', error);
            showToast('导出失败，请稍后重试', 'error');
        } finally {
            // 恢复按钮状态
            const exportBtn = document.querySelector('.header-actions .btn-primary');
            exportBtn.disabled = false;
            exportBtn.textContent = '导出数据';
        }
    },

    // 自动刷新（仅实时行情）
    startAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
        }
        
        this._refreshTimer = setInterval(() => {
            if (this.config.currentTab === 'realtime') {
                this.loadData();
            }
        }, 30000); // 每30秒刷新一次
    },

    // 更新自动刷新状态
    updateAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
        }
        
        if (this.config.currentTab === 'realtime') {
            this.startAutoRefresh();
        }
    }
};

// 工具函数
function formatPrice(price) {
    return price ? price.toFixed(2) : '--';
}

function formatPercent(percent) {
    if (percent === null || percent === undefined) return '--';
    return (percent > 0 ? '+' : '') + percent.toFixed(2) + '%';
}

function formatChange(change) {
    if (change === null || change === undefined) return '--';
    return (change > 0 ? '+' : '') + change.toFixed(2);
}

function formatVolume(volume) {
    if (!volume) return '--';
    if (volume >= 100000000) {
        return (volume / 100000000).toFixed(2) + '亿';
    } else if (volume >= 10000) {
        return (volume / 10000).toFixed(2) + '万';
    }
    return volume.toString();
}

function formatAmount(amount) {
    if (!amount) return '--';
    if (amount >= 100000000) {
        return (amount / 100000000).toFixed(2) + '亿';
    } else if (amount >= 10000) {
        return (amount / 10000).toFixed(2) + '万';
    }
    return amount.toString();
}

function formatDate(date) {
    if (!date) return '--';
    return new Date(date).toLocaleDateString('zh-CN');
}

function formatDateTime(datetime) {
    if (!datetime) return '--';
    return new Date(datetime).toLocaleString('zh-CN');
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    QuotesManager.init();
}); 