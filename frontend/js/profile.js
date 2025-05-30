// 个人中心页面功能模块 - 专业股票交易风格
const ProfilePage = {
    // 用户信息
    userInfo: null,
    
    // 模拟持仓数据
    positions: [
        { code: '000001', name: '平安银行', shares: 1000, avgPrice: 15.20, currentPrice: 16.85, marketValue: 16850 },
        { code: '000002', name: '万科A', shares: 500, avgPrice: 22.30, currentPrice: 20.45, marketValue: 10225 },
        { code: '600519', name: '贵州茅台', shares: 10, avgPrice: 1850.00, currentPrice: 1920.50, marketValue: 19205 },
        { code: '600036', name: '招商银行', shares: 800, avgPrice: 42.50, currentPrice: 45.20, marketValue: 36160 }
    ],
    
    // 模拟交易记录
    transactions: [
        { date: '2025-01-15', type: 'buy', code: '000001', name: '平安银行', shares: 500, price: 15.20, amount: 7600 },
        { date: '2025-01-12', type: 'sell', code: '600036', name: '招商银行', shares: 200, price: 44.80, amount: 8960 },
        { date: '2025-01-10', type: 'buy', code: '600519', name: '贵州茅台', shares: 5, price: 1850.00, amount: 9250 },
        { date: '2025-01-08', type: 'buy', code: '000001', name: '平安银行', shares: 500, price: 15.20, amount: 7600 }
    ],

    // 初始化
    init() {
        this.loadUserInfo();
        this.calculatePortfolio();
        this.renderPositions();
        this.renderTransactions();
        this.renderAccountInfo();
        this.bindEvents();
        this.startDataUpdate();
        
        // 确保搜索弹窗隐藏
        const searchModal = document.getElementById('searchModal');
        if (searchModal) {
            searchModal.classList.remove('show');
        }
        
        // 绘制饼图
        this.drawPortfolioChart();
        this.drawPreferenceChart();
    },

    // 加载用户信息
    loadUserInfo() {
        this.userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        if (!this.userInfo.isLoggedIn) {
            window.location.href = 'login.html';
            return;
        }
    },

    // 计算投资组合数据
    calculatePortfolio() {
        let totalMarketValue = 0;
        let totalCost = 0;
        
        this.positions.forEach(position => {
            totalMarketValue += position.marketValue;
            totalCost += position.shares * position.avgPrice;
            
            // 计算单个股票盈亏
            position.profit = position.marketValue - (position.shares * position.avgPrice);
            position.profitPercent = ((position.currentPrice - position.avgPrice) / position.avgPrice * 100);
        });
        
        this.portfolioData = {
            totalMarketValue,
            totalCost,
            totalProfit: totalMarketValue - totalCost,
            totalProfitPercent: ((totalMarketValue - totalCost) / totalCost * 100),
            positionCount: this.positions.length
        };
    },

    // 渲染持仓列表
    renderPositions() {
        const container = document.getElementById('positionsList');
        if (!container) return;

        const html = this.positions.map(position => `
            <tr class="position-row" data-code="${position.code}">
                <td>
                    <div class="stock-info">
                        <div class="stock-name">${position.name}</div>
                        <div class="stock-code">${position.code}</div>
                    </div>
                </td>
                <td class="text-right">
                    <span class="shares">${position.shares.toLocaleString()}</span>
                </td>
                <td class="text-right">
                    <span class="price">¥${position.avgPrice.toFixed(2)}</span>
                </td>
                <td class="text-right">
                    <span class="price ${this.getPriceClass(position.profitPercent)}">¥${position.currentPrice.toFixed(2)}</span>
                </td>
                <td class="text-right">
                    <span class="market-value">¥${position.marketValue.toLocaleString()}</span>
                </td>
                <td class="text-right">
                    <div class="profit-info">
                        <div class="profit-amount ${this.getPriceClass(position.profitPercent)}">
                            ${position.profit >= 0 ? '+' : ''}¥${position.profit.toFixed(2)}
                        </div>
                        <div class="profit-percent ${this.getPriceClass(position.profitPercent)}">
                            ${position.profitPercent >= 0 ? '+' : ''}${position.profitPercent.toFixed(2)}%
                        </div>
                    </div>
                </td>
                <td class="text-center">
                    <div class="action-buttons">
                        <button class="btn btn-sm btn-primary" onclick="ProfilePage.showTradeModal('${position.code}', 'buy')">买入</button>
                        <button class="btn btn-sm btn-danger" onclick="ProfilePage.showTradeModal('${position.code}', 'sell')">卖出</button>
                    </div>
                </td>
            </tr>
        `).join('');
        
        container.innerHTML = html;
    },

    // 渲染交易记录
    renderTransactions() {
        const container = document.getElementById('transactionsList');
        if (!container) return;

        const html = this.transactions.map(transaction => `
            <tr class="transaction-row">
                <td>${transaction.date}</td>
                <td>
                    <span class="transaction-type ${transaction.type}">
                        ${transaction.type === 'buy' ? '买入' : '卖出'}
                    </span>
                </td>
                <td>
                    <div class="stock-info">
                        <div class="stock-name">${transaction.name}</div>
                        <div class="stock-code">${transaction.code}</div>
                    </div>
                </td>
                <td class="text-right">${transaction.shares.toLocaleString()}</td>
                <td class="text-right">¥${transaction.price.toFixed(2)}</td>
                <td class="text-right ${transaction.type === 'buy' ? 'price-fall' : 'price-rise'}">
                    ${transaction.type === 'buy' ? '-' : '+'}¥${transaction.amount.toLocaleString()}
                </td>
            </tr>
        `).join('');
        
        container.innerHTML = html;
    },

    // 渲染账户信息
    renderAccountInfo() {
        // 更新总资产
        const totalAssets = document.getElementById('totalAssets');
        if (totalAssets) {
            totalAssets.textContent = `¥${this.portfolioData.totalMarketValue.toLocaleString()}`;
        }

        // 更新总盈亏
        const totalProfit = document.getElementById('totalProfit');
        if (totalProfit) {
            totalProfit.textContent = `${this.portfolioData.totalProfit >= 0 ? '+' : ''}¥${this.portfolioData.totalProfit.toFixed(2)}`;
            totalProfit.className = `profit-amount ${this.getPriceClass(this.portfolioData.totalProfitPercent)}`;
        }

        // 更新盈亏比例
        const totalProfitPercent = document.getElementById('totalProfitPercent');
        if (totalProfitPercent) {
            totalProfitPercent.textContent = `${this.portfolioData.totalProfitPercent >= 0 ? '+' : ''}${this.portfolioData.totalProfitPercent.toFixed(2)}%`;
            totalProfitPercent.className = `profit-percent ${this.getPriceClass(this.portfolioData.totalProfitPercent)}`;
        }

        // 更新持仓数量
        const positionCount = document.getElementById('positionCount');
        if (positionCount) {
            positionCount.textContent = this.portfolioData.positionCount;
        }
    },

    // 获取价格颜色类
    getPriceClass(value) {
        if (value > 0) return 'price-rise';
        if (value < 0) return 'price-fall';
        return 'price-neutral';
    },

    // 显示交易弹窗
    showTradeModal(code, type) {
        const position = this.positions.find(p => p.code === code);
        if (!position) return;

        const modal = document.getElementById('tradeModal');
        const form = document.getElementById('tradeForm');
        const title = document.getElementById('tradeTitle');
        const submitBtn = document.getElementById('tradeSubmit');

        // 设置弹窗内容
        title.textContent = `${type === 'buy' ? '买入' : '卖出'} ${position.name} (${position.code})`;
        submitBtn.textContent = type === 'buy' ? '买入' : '卖出';
        submitBtn.className = `btn btn-primary ${type}`;
        
        // 设置当前价格
        document.getElementById('currentPrice').textContent = `当前价: ¥${position.currentPrice.toFixed(2)}`;
        
        // 重置表单
        form.reset();
        document.getElementById('tradeCode').value = code;
        document.getElementById('tradeType').value = type;
        
        // 显示弹窗
        modal.style.display = 'flex';
    },

    // 隐藏交易弹窗
    hideTradeModal() {
        document.getElementById('tradeModal').style.display = 'none';
    },

    // 处理交易提交
    handleTradeSubmit(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const code = formData.get('code');
        const type = formData.get('type');
        const shares = parseInt(formData.get('shares'));
        const price = parseFloat(formData.get('price'));
        
        if (!shares || !price) {
            this.showToast('请填写正确的股数和价格', 'error');
            return;
        }
        
        // 模拟交易执行
        this.showToast(`${type === 'buy' ? '买入' : '卖出'}订单已提交`, 'success');
        this.hideTradeModal();
        
        // 添加到交易记录
        const position = this.positions.find(p => p.code === code);
        this.transactions.unshift({
            date: new Date().toISOString().split('T')[0],
            type,
            code,
            name: position.name,
            shares,
            price,
            amount: shares * price
        });
        
        // 更新持仓
        if (type === 'buy') {
            const totalShares = position.shares + shares;
            const totalCost = (position.shares * position.avgPrice) + (shares * price);
            position.avgPrice = totalCost / totalShares;
            position.shares = totalShares;
        } else {
            position.shares = Math.max(0, position.shares - shares);
        }
        
        // 重新计算和渲染
        this.calculatePortfolio();
        this.renderPositions();
        this.renderTransactions();
        this.renderAccountInfo();
    },

    // 绑定事件
    bindEvents() {
        // 交易弹窗事件
        const modal = document.getElementById('tradeModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target.id === 'tradeModal') {
                    this.hideTradeModal();
                }
            });
        }

        const closeBtn = document.getElementById('closeTrade');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideTradeModal());
        }

        const tradeForm = document.getElementById('tradeForm');
        if (tradeForm) {
            tradeForm.addEventListener('submit', (e) => this.handleTradeSubmit(e));
        }

        // 标签切换
        const tabs = document.querySelectorAll('.profile-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTab(tab.dataset.tab);
            });
        });
    },

    // 切换标签
    switchTab(tabName) {
        // 更新标签状态
        document.querySelectorAll('.profile-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // 显示对应内容
        document.querySelectorAll('.tab-content').forEach(content => {
            content.style.display = content.id === `${tabName}Tab` ? 'block' : 'none';
        });
    },

    // 开始数据更新
    startDataUpdate() {
        // 模拟实时价格更新
        setInterval(() => {
            this.updatePrices();
        }, 5000);
    },

    // 更新价格数据
    updatePrices() {
        this.positions.forEach(position => {
            // 模拟价格波动 (-2% 到 +2%)
            const change = (Math.random() - 0.5) * 0.04;
            position.currentPrice = Math.max(0.01, position.currentPrice * (1 + change));
            position.marketValue = position.shares * position.currentPrice;
        });
        
        this.calculatePortfolio();
        this.renderPositions();
        this.renderAccountInfo();
    },

    // 显示提示信息
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (document.body.contains(toast)) {
                    document.body.removeChild(toast);
                }
            }, 300);
        }, 3000);
    },

    // 绘制持仓摘要饼图
    drawPortfolioChart() {
        const canvas = document.getElementById('portfolioChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 2 - 20;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 饼图数据
        const data = [
            { label: '科技股', value: 40, color: '#dc2626' },
            { label: '金融股', value: 25, color: '#16a34a' },
            { label: '消费股', value: 20, color: '#f59e0b' },
            { label: '其他', value: 15, color: '#6b7280' }
        ];

        let currentAngle = -Math.PI / 2; // 从顶部开始

        data.forEach(segment => {
            const sliceAngle = (segment.value / 100) * 2 * Math.PI;

            // 绘制扇形
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
            ctx.closePath();
            ctx.fillStyle = segment.color;
            ctx.fill();

            // 绘制边框
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            currentAngle += sliceAngle;
        });

        // 绘制中心圆
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius * 0.4, 0, 2 * Math.PI);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        ctx.stroke();

        // 绘制中心文字
        ctx.fillStyle = '#374151';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('持仓分布', centerX, centerY);
    },

    // 绘制投资偏好图表
    drawPreferenceChart() {
        const canvas = document.getElementById('preferenceChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 柱状图数据
        const data = [
            { label: '成长型', value: 45, color: '#dc2626' },
            { label: '价值型', value: 30, color: '#16a34a' },
            { label: '平衡型', value: 15, color: '#f59e0b' },
            { label: '保守型', value: 10, color: '#6b7280' }
        ];

        const maxValue = Math.max(...data.map(d => d.value));
        const barWidth = (width - 80) / data.length;
        const chartHeight = height - 60;

        data.forEach((item, index) => {
            const barHeight = (item.value / maxValue) * chartHeight;
            const x = 40 + index * barWidth + barWidth * 0.1;
            const y = height - 30 - barHeight;

            // 绘制柱子
            ctx.fillStyle = item.color;
            ctx.fillRect(x, y, barWidth * 0.8, barHeight);

            // 绘制标签
            ctx.fillStyle = '#374151';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(item.label, x + barWidth * 0.4, height - 10);

            // 绘制数值
            ctx.fillStyle = item.color;
            ctx.font = 'bold 12px Arial';
            ctx.fillText(`${item.value}%`, x + barWidth * 0.4, y - 5);
        });

        // 绘制Y轴
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(40, 20);
        ctx.lineTo(40, height - 30);
        ctx.stroke();

        // 绘制X轴
        ctx.beginPath();
        ctx.moveTo(40, height - 30);
        ctx.lineTo(width - 20, height - 30);
        ctx.stroke();
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    ProfilePage.init();
}); 